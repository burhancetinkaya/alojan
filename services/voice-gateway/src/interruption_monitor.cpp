#include "speech_bridge.hpp"
#include <algorithm>

namespace alojan {
using namespace std::chrono_literals;
namespace contract = ::voice::v1;

void SpeechBridge::monitor() noexcept {
    try {
        auto stub = contract::Recognition::NewStub(asr_);
        auto stream = stub->StreamRecognize(asr_context_.get());
        std::atomic<bool> valid{true};
        std::atomic<unsigned> sent_frames{0};
        std::mutex mutex;
        std::string partial;
        unsigned coverage = 0;
        std::jthread reader([&] {
            try {
                contract::RecognitionEvent event;
                while (stream->Read(&event)) {
                    if (monitor_stop_.load() || stop_.load())
                        break;
                    std::lock_guard lock(mutex);
                    if (event.call_id() != call_ ||
                        event.generation_id() != generation_ + "-monitor" || event.is_final() ||
                        event.text().size() > 8192 || event.processed_audio_ms() < coverage ||
                        event.processed_audio_ms() > (sent_frames.load() + 1) * 20) {
                        valid.store(false);
                        asr_context_->TryCancel();
                        break;
                    }
                    partial = event.text();
                    coverage = event.processed_audio_ms();
                }
            } catch (...) {
                valid.store(false);
                asr_context_->TryCancel();
            }
        });
        try {
            EchoReference reference;
            std::array<float, 576> vad{};
            std::array<float, 256> vad_state{};
            unsigned pending = 0, samples = 0, voiced_ms = 0, last_voice = 0;
            bool acknowledged = false;
            std::deque<std::array<char, 640>> pre_roll;
            contract::AudioFrame frame;
            frame.set_call_id(call_);
            frame.set_generation_id(generation_ + "-monitor");
            frame.set_sample_rate_hz(16000);
            frame.set_channels(1);
            frame.set_format("pcm_s16le");
            while (!monitor_stop_.load() && !stop_.load() && state() != State::failed) {
                if (!valid.load() || overflow_.load() || sent_frames.load() >= 1500 ||
                    std::chrono::system_clock::now() >= deadline_) {
                    fail(overflow_.load() ? Error::input_overflow : Error::recognition);
                    break;
                }
                std::array<char, 320> output{};
                while (reference_.pop(output.data()))
                    reference.append(output);
                std::array<char, 640> pcm{};
                if (!input_.pop(pcm.data())) {
                    std::this_thread::sleep_for(1ms);
                    continue;
                }
                if (reference.matches(pcm)) {
                    pcm.fill(0);
                    echo_frames.fetch_add(1);
                }
                pre_roll.push_back(pcm);
                if (pre_roll.size() > 100)
                    pre_roll.pop_front();
                for (unsigned i = 0; i < 320; ++i) {
                    const auto lo = static_cast<unsigned char>(pcm[2 * i]);
                    const auto hi = static_cast<unsigned char>(pcm[2 * i + 1]);
                    vad[64 + pending++] = static_cast<std::int16_t>(lo | (hi << 8)) / 32768.0f;
                    ++samples;
                    if (pending != 512)
                        continue;
                    const auto probability = models_->vad(vad, vad_state);
                    if (probability >= 0.5f) {
                        if ((samples - last_voice) / 16 > 800) {
                            voiced_ms = 0;
                            acknowledged = false;
                        }
                        voiced_ms += 32;
                        last_voice = samples;
                    }
                    std::copy(vad.end() - 64, vad.end(), vad.begin());
                    pending = 0;
                }
                frame.set_sequence(sent_frames.load());
                frame.set_audio(pcm.data(), pcm.size());
                if (!stream->Write(frame)) {
                    if (!monitor_stop_.load() && !stop_.load())
                        fail(Error::recognition);
                    break;
                }
                sent_frames.fetch_add(1);
                InterruptDecision decision;
                {
                    std::lock_guard lock(mutex);
                    decision = interruption_policy(voiced_ms, (samples - last_voice) / 16, partial,
                                                   coverage > 0 && coverage >= last_voice / 16);
                    if (decision == InterruptDecision::backchannel && !acknowledged) {
                        backchannels.fetch_add(1);
                        acknowledged = true;
                    }
                }
                if (decision == InterruptDecision::interrupt) {
                    // Revoke locally before any network cancellation. No callback waits on RPCs.
                    output_epoch_.store(0);
                    interrupt_ms.store(std::chrono::duration_cast<std::chrono::milliseconds>(
                                           std::chrono::steady_clock::now().time_since_epoch())
                                           .count());
                    state_.store(State::recognizing);
                    interrupted_.store(true);
                    interrupted_turn.store(recognitions_started.load());
                    interruptions.fetch_add(1);
                    {
                        std::lock_guard lock(contexts_mutex_);
                        tts_context_->TryCancel();
                        agent_context_->TryCancel();
                    }
                    replay_ = std::move(pre_roll);
                    break;
                }
            }
        } catch (...) {
            fail(Error::turn_detection);
        }
        asr_context_->TryCancel();
        reader.join();
        stream->Finish();
    } catch (...) {
        fail(Error::internal);
    }
}
} // namespace alojan
