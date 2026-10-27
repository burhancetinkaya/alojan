#include "speech_bridge.hpp"
#include <algorithm>

namespace alojan {
using namespace std::chrono_literals;
namespace contract = ::voice::v1;

void SpeechBridge::monitor() noexcept {
    try {
        const auto &settings = gateway_settings_.interruption;
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
            unsigned pending = 0, samples = 0;
            InterruptionEvidence evidence;
            unsigned rejected_echo_frames = 0, vad_milli = 0;
            bool acknowledged = false;
            unsigned last_activity = 0;
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
                    ++rejected_echo_frames;
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
                    vad_milli = static_cast<unsigned>(probability * 1000);
                    if (probability >= 0.10f)
                        last_activity = samples;
                    if (evidence.observe(probability >= settings.vad_percent / 100.0f, samples / 16,
                                         settings))
                        acknowledged = false;
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
                bool fresh;
                {
                    std::lock_guard lock(mutex);
                    fresh = coverage > 0 && coverage >= evidence.last_voice_ms;
                    decision = interruption_policy(evidence.voiced_ms, evidence.sustained_ms,
                                                   samples / 16 - evidence.last_voice_ms, partial,
                                                   fresh, settings);
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
                    interrupt_voiced_ms.store(evidence.voiced_ms);
                    interrupt_sustained_ms.store(evidence.sustained_ms);
                    interrupt_quiet_ms.store(samples / 16 - evidence.last_voice_ms);
                    interrupt_vad_milli.store(vad_milli);
                    interrupt_echo_frames.store(rejected_echo_frames);
                    interrupt_asr_fresh.store(fresh);
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
            // Preserve speech that starts near the end of a recovery prompt, even before
            // it meets the interruption threshold. Echo-filtered pre-roll stays bounded.
            if (!input_event_.empty() && !interrupted_.load() && last_activity &&
                (samples - last_activity) / 16 < settings.max_quiet_ms && !stop_.load() &&
                state() != State::failed)
                replay_ = std::move(pre_roll);
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
