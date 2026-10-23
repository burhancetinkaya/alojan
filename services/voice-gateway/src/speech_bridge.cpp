#include "speech_bridge.hpp"
#include <algorithm>
#include <google/protobuf/struct.pb.h>
#include <google/protobuf/util/json_util.h>
#include <mutex>

namespace alojan {
using namespace std::chrono_literals;
namespace contract = ::voice::v1;

std::int64_t SpeechBridge::now_ms() noexcept {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

static std::shared_ptr<grpc::Channel> channel(unsigned port) {
    grpc::ChannelArguments args;
    args.SetMaxReceiveMessageSize(16384);
    args.SetMaxSendMessageSize(16384);
    return grpc::CreateCustomChannel("127.0.0.1:" + std::to_string(port),
                                     grpc::InsecureChannelCredentials(), args);
}

SpeechBridge::SpeechBridge(std::string call, unsigned asr_port, unsigned tts_port,
                           unsigned capture_frames, std::string response, Deadline deadline,
                           std::shared_ptr<TurnModels> models, QuestionContext context,
                           bool barge_in, unsigned agent_port, std::string caller_number)
    : call_(std::move(call)), caller_number_(std::move(caller_number)),
      response_(std::move(response)), barge_in_(barge_in), capture_frames_(capture_frames),
      deadline_(deadline), models_(std::move(models)), question_context_(context),
      asr_(channel(asr_port)), tts_(channel(tts_port)),
      agent_(agent_port ? channel(agent_port) : nullptr) {
    if (barge_in_ && !models_)
        throw std::invalid_argument("barge-in requires native turn models");
    reset_contexts();
}

SpeechBridge::~SpeechBridge() {
    cancel();
    if (worker_.joinable())
        worker_.join();
}

void SpeechBridge::start() {
    if (state() != State::idle)
        return;
    reset_contexts();
    done_.store(false);
    state_.store(State::recognizing);
    try {
        worker_ = std::thread([this] { run(); });
    } catch (...) {
        done_.store(true);
        fail(Error::internal);
        throw;
    }
}

void SpeechBridge::cancel() noexcept {
    stop_.store(true);
    state_.store(State::cancelled);
    cancel_rpc();
}

void SpeechBridge::fail(Error reason) noexcept {
    error_.store(reason);
    if (!stop_.load())
        state_.store(State::failed);
    cancel_rpc();
}

void SpeechBridge::reset_contexts() {
    std::lock_guard lock(contexts_mutex_);
    asr_context_ = std::make_unique<grpc::ClientContext>();
    tts_context_ = std::make_unique<grpc::ClientContext>();
    agent_context_ = std::make_unique<grpc::ClientContext>();
    agent_context_->set_deadline(std::min(deadline_, std::chrono::system_clock::now() + 20s));
    asr_context_->set_deadline(
        std::min(deadline_, std::chrono::system_clock::now() +
                                std::chrono::milliseconds(capture_frames_ * 20) + 5s));
    tts_context_->set_deadline(deadline_);
    if (stop_.load()) {
        asr_context_->TryCancel();
        tts_context_->TryCancel();
        agent_context_->TryCancel();
    }
}
void SpeechBridge::cancel_rpc() noexcept {
    std::lock_guard lock(contexts_mutex_);
    asr_context_->TryCancel();
    tts_context_->TryCancel();
    agent_context_->TryCancel();
}
void SpeechBridge::receive(const char *pcm) noexcept {
    if (stop_.load() || !accepting_input_.load())
        return;
    const auto phase = state();
    if (phase != State::recognizing && !(barge_in_ && phase == State::synthesizing))
        return;
    if (!input_.push(pcm)) {
        overflow_.store(true);
        return;
    }
    captured.fetch_add(1);
}
bool SpeechBridge::render(char *pcm) noexcept {
    rendering_.fetch_add(1);
    bool sent = false;
    const auto epoch = output_epoch_.load();
    if (!stop_.load() && epoch && (state() == State::synthesizing || state() == State::complete)) {
        std::array<char, 328> frame{};
        for (unsigned i = 0; i < 32 && output_.pop(frame.data()); ++i) {
            std::uint64_t tag;
            std::memcpy(&tag, frame.data(), sizeof(tag));
            if (tag != epoch)
                continue;
            if (output_epoch_.load() != epoch || stop_.load() || state() == State::failed)
                break;
            std::memcpy(pcm, frame.data() + 8, 320);
            played.fetch_add(1);
            if (round_played_.fetch_add(1) == 0)
                first_playout_ms.store(now_ms());
            last_sent_ms.store(now_ms());
            if (!phrase_first_playout_ms_.load())
                phrase_first_playout_ms_.store(now_ms());
            sent = true;
            break;
        }
    }
    // Local music never occupies the speech queue or delays the first real PCM frame.
    const auto music_start = waiting_music_start_ms_.load();
    const auto music_elapsed = now_ms() - music_start;
    if (!sent && agent_ && music_start && music_elapsed >= 0 && !round_played_.load() &&
        !stop_.load() && epoch && output_epoch_.load() == epoch && state() == State::synthesizing) {
        if (music_generation_start_ != music_start) {
            music_generation_start_ = music_start;
            music_frame_ = 0;
        }
        waiting_music_.render(pcm, music_frame_++);
        waiting_music_frames.fetch_add(1);
        last_sent_ms.store(now_ms());
        sent = true;
    }
    if (barge_in_ && state() == State::synthesizing) {
        std::array<char, 320> silence{};
        if (!reference_.push(sent ? pcm : silence.data()))
            overflow_.store(true);
    }
    rendering_.fetch_sub(1);
    return sent;
}
bool SpeechBridge::playout_finished() const noexcept {
    return (!(barge_in_ || agent_) || done_.load()) && state() == State::complete &&
           output_.empty() && round_played_.load() == round_generated_.load();
}

bool SpeechBridge::recognize() {
    recognitions_started.fetch_add(1);
    final_text_.clear();
    written.store(0);
    half_close_ms.store(0);
    accepting_input_.store(true);
    state_.store(State::recognizing);
    std::unique_ptr<TurnDetector> detector;
    if (models_)
        detector = std::make_unique<TurnDetector>(models_);
    bool turn_ended = false;
    std::mutex partial_mutex;
    std::string partial_text;
    unsigned partial_coverage = 0;
    std::int64_t text_changed_ms = now_ms();
    auto stub = contract::Recognition::NewStub(asr_);
    auto stream = stub->StreamRecognize(asr_context_.get());
    std::atomic<bool> valid{true};
    bool final = false;
    std::jthread reader([&] {
        try {
            contract::RecognitionEvent event;
            while (stream->Read(&event)) {
                if (stop_.load())
                    break;
                if (final || event.call_id() != call_ || event.generation_id() != generation_ ||
                    event.text().size() > 8192 || (event.is_final() && half_close_ms.load() == 0) ||
                    (detector && event.is_final() &&
                     event.processed_audio_ms() != written.load() * 20)) {
                    valid.store(false);
                    asr_context_->TryCancel();
                    break;
                }
                if (event.is_final()) {
                    final = true;
                    final_text_ = event.text();
                    final_bytes.store(static_cast<unsigned>(event.text().size()));
                } else {
                    partials.fetch_add(1);
                    if (detector) {
                        std::lock_guard lock(partial_mutex);
                        if (event.processed_audio_ms() < partial_coverage ||
                            event.processed_audio_ms() > (written.load() + 1) * 20) {
                            valid.store(false);
                            asr_context_->TryCancel();
                            break;
                        }
                        if (partial_text != event.text())
                            text_changed_ms = now_ms();
                        partial_text = event.text();
                        partial_coverage = event.processed_audio_ms();
                    }
                }
            }
        } catch (...) {
            valid.store(false);
            asr_context_->TryCancel();
        }
    });
    try {
        contract::AudioFrame frame;
        frame.set_call_id(call_);
        frame.set_generation_id(generation_);
        frame.set_sample_rate_hz(16000);
        frame.set_channels(1);
        frame.set_format("pcm_s16le");
        std::array<char, 640> pcm;
        while (!stop_.load() && written.load() < capture_frames_) {
            if (overflow_.load()) {
                fail(Error::input_overflow);
                break;
            }
            if (!valid.load() || std::chrono::system_clock::now() >= asr_context_->deadline())
                break;
            if (!replay_.empty()) {
                pcm = replay_.front();
                replay_.pop_front();
            } else if (!input_.pop(pcm.data())) {
                std::this_thread::sleep_for(1ms);
                continue;
            }
            frame.set_sequence(written.load());
            frame.set_audio(pcm.data(), pcm.size());
            if (!stream->Write(frame))
                break;
            written.fetch_add(1);
            if (detector) {
                TurnDecision decision = TurnDecision::listen;
                try {
                    detector->receive(pcm);
                    std::string text;
                    unsigned stable = 0;
                    {
                        std::lock_guard lock(partial_mutex);
                        if (partial_coverage >= detector->last_voice_ms() && partial_coverage > 0) {
                            text = partial_text;
                            stable = static_cast<unsigned>(now_ms() - text_changed_ms);
                        }
                    }
                    decision = detector->decide(text, stable, question_context_);
                } catch (...) {
                    decision = TurnDecision::detector_failed;
                }
                if (decision == TurnDecision::detector_failed ||
                    decision == TurnDecision::incomplete_timeout) {
                    fail(decision == TurnDecision::detector_failed ? Error::turn_detection
                                                                   : Error::incomplete_turn);
                    break;
                }
                // Consume already captured speech before accepting a background decision.
                if (decision == TurnDecision::complete && input_.empty() && replay_.empty()) {
                    turn_silence_ms.store(detector->silence_ms());
                    turn_probability_milli.store(
                        static_cast<unsigned>(detector->probability() * 1000));
                    turn_inference_ms.store(detector->inference_ms());
                    accepting_input_.store(false);
                    turn_ended = true;
                    break;
                }
            }
        }
        if (detector && !turn_ended && state() != State::failed && !stop_.load())
            fail(Error::incomplete_turn);
        if (stop_.load() || overflow_.load() || (!turn_ended && written.load() != capture_frames_))
            asr_context_->TryCancel();
        accepting_input_.store(false);
        half_close_ms.store(now_ms());
        stream->WritesDone();
    } catch (...) {
        asr_context_->TryCancel();
        throw;
    }
    reader.join();
    const auto status = stream->Finish();
    asr_finished_ms_ = now_ms();
    if (stop_.load())
        return false;
    if (!status.ok() || !valid.load() || !final || !final_bytes.load() ||
        (!turn_ended && written.load() != capture_frames_) || overflow_.load() ||
        state() == State::failed) {
        if (state() != State::failed)
            fail(overflow_.load() ? Error::input_overflow : Error::recognition);
        return false;
    }
    return true;
}

bool SpeechBridge::synthesize_phrase(const std::string &text, const std::string &id,
                                     std::uint64_t epoch) {
    unsigned phrase_generated = 0;
    auto stub = contract::Synthesis::NewStub(tts_);
    contract::SynthesisRequest request;
    request.set_call_id(call_);
    request.set_generation_id(id);
    request.set_text(text);
    auto stream = stub->StreamSynthesize(tts_context_.get(), request);
    contract::AudioFrame frame;
    while (!stop_.load() && !interrupted_.load() && stream->Read(&frame)) {
        if (frame.call_id() != call_ || frame.generation_id() != id ||
            frame.sequence() != phrase_generated || frame.sample_rate_hz() != 8000 ||
            frame.channels() != 1 || frame.format() != "pcm_s16le" || frame.audio().size() != 320 ||
            frame.captured_at_unix_ms() < 0 || phrase_generated >= 1500) {
            fail(Error::invalid_output);
            break;
        }
        if (round_generated_.load() == 0)
            first_pcm_ms.store(now_ms());
        if (phrase_generated == 0)
            phrase_first_pcm_ms_ = now_ms();
        std::array<char, 328> tagged{};
        std::memcpy(tagged.data(), &epoch, 8);
        std::memcpy(tagged.data() + 8, frame.audio().data(), 320);
        const auto limit = std::chrono::steady_clock::now() + 250ms;
        bool queued = false;
        while (!stop_.load() && !interrupted_.load() && state() != State::failed) {
            if ((queued = output_.push(tagged.data())))
                break;
            if (std::chrono::steady_clock::now() >= limit) {
                fail(Error::playout_stall);
                break;
            }
            std::this_thread::sleep_for(1ms);
        }
        if (!queued)
            break;
        generated.fetch_add(1);
        round_generated_.fetch_add(1);
        ++phrase_generated;
    }
    const auto status = stream->Finish();
    if (!stop_.load() && !interrupted_.load() && state() != State::failed &&
        (!status.ok() || phrase_generated == 0))
        fail(Error::synthesis);
    if (barge_in_ || agent_) {
        while (!stop_.load() && !interrupted_.load() && state() != State::failed &&
               round_played_.load() != round_generated_.load()) {
            if (std::chrono::system_clock::now() >= deadline_) {
                fail(Error::playout_stall);
                break;
            }
            std::this_thread::sleep_for(1ms);
        }
    }

    return !stop_.load() && !interrupted_.load() && state() != State::failed;
}

void SpeechBridge::synthesize() {
    if (stop_.load())
        return;
    round_generated_.store(0);
    round_played_.store(0);
    interrupted_.store(false);
    monitor_stop_.store(false);
    const auto epoch = static_cast<std::uint64_t>(interruptions.load()) + 1;
    output_epoch_.store(epoch);
    waiting_music_start_ms_.store(agent_ ? now_ms() + 800 : 0);
    state_.store(State::synthesizing);
    responses_started.fetch_add(1);
    std::jthread monitor_thread;
    if (barge_in_) {
        // The preceding recognition stream has finished; a new monitor identity owns ASR.
        {
            std::lock_guard lock(contexts_mutex_);
            asr_context_ = std::make_unique<grpc::ClientContext>();
            asr_context_->set_deadline(deadline_);
            if (stop_.load())
                asr_context_->TryCancel();
        }
        accepting_input_.store(true);
        monitor_thread = std::jthread([this] { monitor(); });
    }
    std::jthread agent_reader;
    if (agent_) {
        agent_done_.store(false);
        finish_call_.store(false);
        agent_reader = std::jthread([this] { read_agent(); });
    }
    try {
        unsigned index = 0;
        do {
            std::string text = response_;
            bool waiting = false;
            std::int64_t ready_ms = now_ms();
            if (agent_) {
                text.clear();
                while (!stop_.load() && !interrupted_.load() && state() != State::failed) {
                    {
                        std::lock_guard lock(phrases_mutex_);
                        if (!phrases_.empty()) {
                            text = std::move(phrases_.front().text);
                            waiting = phrases_.front().waiting;
                            ready_ms = phrases_.front().ready_ms;
                            phrases_.pop_front();
                            break;
                        }
                    }
                    if (agent_done_.load())
                        break;
                    if (std::chrono::system_clock::now() >= deadline_) {
                        fail(Error::agent);
                        break;
                    }
                    std::this_thread::sleep_for(1ms);
                }
                if (text.empty())
                    break;
                std::lock_guard lock(contexts_mutex_);
                tts_context_ = std::make_unique<grpc::ClientContext>();
                tts_context_->set_deadline(deadline_);
                if (stop_.load() || interrupted_.load())
                    tts_context_->TryCancel();
            }
            const auto before = round_played_.load();
            const auto id = generation_ + (agent_ ? "-p" + std::to_string(index) : "");
            phrase_first_playout_ms_.store(0);
            phrase_first_pcm_ms_ = 0;
            const auto tts_started_ms = now_ms();
            const bool complete = synthesize_phrase(text, id, epoch);
            if (agent_) {
                while (rendering_.load())
                    std::this_thread::yield();
                const auto sent = (round_played_.load() - before) * 20;
                const auto audio_ms = phrase_first_playout_ms_.load();
                history_.push_back(
                    {id, complete ? text : "", sent, interrupted_.load(), waiting,
                     audio_ms ? audio_ms - half_close_ms.load() : -1,
                     asr_finished_ms_ - half_close_ms.load(), audio_ms ? audio_ms - ready_ms : -1,
                     phrase_first_pcm_ms_ ? phrase_first_pcm_ms_ - tts_started_ms : -1});
                report_playback(index, sent, complete);
                if (!complete)
                    invalidate(tts_, id);
            }
            ++index;
            if (!complete)
                break;
        } while (agent_);
    } catch (...) {
        fail(Error::internal);
    }
    if (agent_) {
        agent_context_->TryCancel();
        if (agent_reader.joinable())
            agent_reader.join();
    }
    if (barge_in_) {
        monitor_stop_.store(true);
        asr_context_->TryCancel();
        monitor_thread.join();
        invalidate(asr_, generation_ + "-monitor");
        // Invalidation precedes this barrier; a callback already handing off PCM may finish.
        while (rendering_.load())
            std::this_thread::yield();
        const bool complete = !interrupted_.load() && !stop_.load() && state() != State::failed &&
                              round_played_.load() == round_generated_.load();
        if (!agent_)
            history_.push_back({generation_, complete ? response_ : "", round_played_.load() * 20,
                                interrupted_.load()});
    }
    if (!stop_.load() && state() != State::failed && !interrupted_.load())
        state_.store(State::complete);
}

void SpeechBridge::invalidate(const std::shared_ptr<grpc::Channel> &target,
                              const std::string &generation) noexcept {
    try {
        auto stub = contract::GenerationControl::NewStub(target);
        grpc::ClientContext context;
        context.set_deadline(std::chrono::system_clock::now() + 150ms);
        contract::CancelRequest request;
        request.set_call_id(call_);
        request.set_generation_id(generation);
        contract::CancelReply reply;
        // Local invalidation and TryCancel remain effective if the service is unavailable.
        stub->CancelGeneration(&context, request, &reply);
    } catch (...) {
    }
}

void SpeechBridge::run() noexcept {
    try {
        const unsigned max_turns = agent_ ? 16 : 8;
        for (unsigned turn = 1; turn <= max_turns && !stop_.load(); ++turn) {
            if (!recognize())
                break;
            synthesize();
            if (state() == State::failed || stop_.load() ||
                (!interrupted_.load() && (!agent_ || finish_call_.load())))
                break;
            invalidate(tts_, generation_);
            if (turn == max_turns) {
                fail(Error::incomplete_turn);
                break;
            }
            if (agent_)
                invalidate(agent_, generation_);
            // Recognition owns the input again only after the monitor has joined.
            if (!interrupted_.load()) {
                std::array<char, 640> pending{};
                while (input_.pop(pending.data())) {
                }
            }
            {
                std::lock_guard lock(phrases_mutex_);
                phrases_.clear();
            }
            generation_ = "turn-" + std::to_string(turn + 1);
            reset_contexts();
        }
    } catch (...) {
        fail(Error::internal);
    }
    if (stop_.load() || state() == State::failed) {
        invalidate(asr_, generation_);
        invalidate(tts_, generation_);
    }
    end_reason_ = state() == State::complete ? "completed"
                  : error() != Error::none   ? "failed"
                                             : "disconnected";
    done_.store(true);
    // Post-call analysis starts only after gateway teardown has requested cancellation.
    if (agent_) {
        while (!stop_.load())
            std::this_thread::sleep_for(5ms);
        end_agent();
    }
}
} // namespace alojan
