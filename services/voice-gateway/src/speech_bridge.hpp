#pragma once

#include "interruption.hpp"
#include "turn_detector.hpp"
#include "voice/v1/voice.grpc.pb.h"
#include "waiting_music.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <cstring>
#include <deque>
#include <grpcpp/grpcpp.h>
#include <mutex>
#include <string>
#include <thread>

namespace alojan {

// One producer and one consumer; callbacks copy fixed PCM without allocating or waiting.
template <std::size_t Bytes, std::size_t Capacity> class PcmQueue {
    static_assert(std::atomic<std::uint64_t>::is_always_lock_free);
    std::array<std::array<char, Bytes>, Capacity> frames_{};
    std::atomic<std::uint64_t> read_{0}, write_{0};

  public:
    bool push(const char *data) noexcept {
        const auto write = write_.load(std::memory_order_relaxed);
        if (write - read_.load(std::memory_order_acquire) == Capacity)
            return false;
        std::memcpy(frames_[write % Capacity].data(), data, Bytes);
        write_.store(write + 1, std::memory_order_release);
        return true;
    }
    bool pop(char *data) noexcept {
        const auto read = read_.load(std::memory_order_relaxed);
        if (read == write_.load(std::memory_order_acquire))
            return false;
        std::memcpy(data, frames_[read % Capacity].data(), Bytes);
        read_.store(read + 1, std::memory_order_release);
        return true;
    }
    // Consumer-only diagnostic: frames of audio waiting, not wall-clock queue age.
    std::uint64_t queued_frames() const noexcept {
        const auto read = read_.load(std::memory_order_relaxed);
        return write_.load(std::memory_order_acquire) - read;
    }
    bool empty() const noexcept {
        return read_.load(std::memory_order_acquire) == write_.load(std::memory_order_acquire);
    }
};

class SpeechBridge {
  public:
    enum class State { idle, recognizing, synthesizing, complete, failed, cancelled };
    enum class Error {
        none,
        input_overflow,
        recognition,
        synthesis,
        invalid_output,
        playout_stall,
        internal,
        turn_detection,
        incomplete_turn,
        agent
    };
    using Deadline = std::chrono::system_clock::time_point;
    SpeechBridge(std::string call, unsigned asr_port, unsigned tts_port, unsigned capture_frames,
                 std::string response, Deadline deadline, std::shared_ptr<TurnModels> models = {},
                 QuestionContext context = QuestionContext::open, bool barge_in = false,
                 unsigned agent_port = 0, std::string caller_number = "",
                 TurnSettings turn_settings = {});
    ~SpeechBridge();
    SpeechBridge(const SpeechBridge &) = delete;
    SpeechBridge &operator=(const SpeechBridge &) = delete;
    void start();
    void cancel() noexcept;
    void receive(const char *pcm) noexcept;
    bool render(char *pcm) noexcept;
    bool playout_finished() const noexcept;
    bool finished() const noexcept { return done_.load(); }
    State state() const noexcept { return state_.load(); }
    Error error() const noexcept { return error_.load(); }
    struct SentSpeech {
        std::string generation, text;
        unsigned sent_audio_ms;
        bool interrupted;
        bool waiting = false;
        std::int64_t endpoint_to_audio_ms = -1, asr_finalize_ms = -1, phrase_ready_to_audio_ms = -1,
                     tts_first_chunk_ms = -1;
    };
    // Read only after finished(); partial utterances have no fabricated word alignment.
    const std::vector<SentSpeech> &sent_history() const { return history_; }
    std::atomic<unsigned> silence_reminders{0}, clarification_requests{0};
    std::atomic<unsigned> responses_started{0}, recognitions_started{0};
    std::atomic<unsigned> interruptions{0}, echo_frames{0}, backchannels{0};
    std::atomic<std::int64_t> interrupt_ms{0}, last_sent_ms{0};
    std::atomic<unsigned> interrupted_turn{0};
    std::atomic<unsigned> waiting_music_frames{0};
    std::atomic<unsigned> captured{0}, written{0}, partials{0}, final_bytes{0}, generated{0},
        played{0};
    std::atomic<std::int64_t> half_close_ms{0}, first_pcm_ms{0}, first_playout_ms{0};
    std::atomic<unsigned> turn_silence_ms{0}, turn_probability_milli{0}, turn_inference_ms{0};

  private:
    const std::string call_, caller_number_;
    std::string response_, final_text_, end_reason_ = "disconnected";
    std::string generation_ = "turn-1";
    const bool barge_in_;
    const unsigned capture_frames_;
    const Deadline deadline_;
    const std::shared_ptr<TurnModels> models_;
    const QuestionContext question_context_;
    const TurnSettings turn_settings_;
    std::string input_event_;
    bool reminder_sent_ = false;
    std::shared_ptr<grpc::Channel> asr_, tts_, agent_;
    std::unique_ptr<grpc::ClientContext> asr_context_, tts_context_, agent_context_;
    std::mutex contexts_mutex_;
    void reset_contexts();
    void cancel_rpc() noexcept;
    PcmQueue<640, 64> input_;
    // Epoch travels with PCM; the consumer alone discards invalidated queue entries.
    PcmQueue<328, 32> output_;
    PcmQueue<320, 64> reference_;
    std::atomic<std::uint64_t> output_epoch_{1};
    std::atomic<bool> interrupted_{false}, monitor_stop_{false};
    std::atomic<unsigned> rendering_{0};
    std::atomic<unsigned> round_generated_{0}, round_played_{0};
    const WaitingMusic waiting_music_;
    std::atomic<std::int64_t> waiting_music_start_ms_{0};
    // Only the render callback advances this cursor, independent of clock jitter.
    std::int64_t music_generation_start_ = 0;
    std::uint64_t music_frame_ = 0;
    std::deque<std::array<char, 640>> replay_;
    std::vector<SentSpeech> history_;
    void monitor() noexcept;
    std::atomic<State> state_{State::idle};
    std::atomic<Error> error_{Error::none};
    std::atomic<bool> stop_{false}, overflow_{false}, done_{true};
    std::atomic<bool> accepting_input_{true};
    std::thread worker_;
    void run() noexcept;
    bool recognize();
    void synthesize();
    void read_agent() noexcept;
    void report_playback(unsigned index, unsigned sent_ms, bool completed);
    void end_agent() noexcept;
    std::mutex phrases_mutex_;
    struct Phrase {
        std::string text;
        bool waiting;
        std::int64_t ready_ms;
    };
    std::deque<Phrase> phrases_;
    std::atomic<std::int64_t> phrase_first_playout_ms_{0};
    std::int64_t asr_finished_ms_ = 0, phrase_first_pcm_ms_ = 0;
    std::int64_t recognition_started_ms_ = 0, endpoint_silence_ms_ = -1;
    std::int64_t response_tts_ms_ = 0, response_pcm_ms_ = 0;
    std::atomic<std::int64_t> agent_request_ms_{0}, agent_phrase_ms_{0}, response_audio_ms_{0};
    std::atomic<bool> phrase_waiting_{false};
    bool turn_reported_ = true;
    void report_turn();
    static std::int64_t now_ms() noexcept;
    std::atomic<bool> agent_done_{false}, finish_call_{false};
    bool synthesize_phrase(const std::string &text, const std::string &id, std::uint64_t epoch);
    void invalidate(const std::shared_ptr<grpc::Channel> &channel,
                    const std::string &generation) noexcept;
    void fail(Error reason) noexcept;
};
} // namespace alojan
