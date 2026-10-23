#pragma once

#include <array>
#include <cstdint>
#include <future>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace alojan {
enum class QuestionContext { open, yes_no };
enum class TurnDecision { listen, complete, detector_failed, incomplete_timeout };

// Text is only a conservative timing hint, never an instruction or authorization.
TurnDecision turn_policy(unsigned silence_ms, float probability, std::string_view text,
                         unsigned stable_ms, QuestionContext context, bool detector_failed);

class TurnModels {
  public:
    explicit TurnModels(const std::string &directory);
    ~TurnModels();
    TurnModels(const TurnModels &) = delete;
    float vad(std::span<const float, 576> audio, std::array<float, 256> &state);
    float complete(std::span<const float> audio);
    static std::vector<float> features(std::span<const float> audio);

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

// Owned and called by the bridge worker only; callbacks only enqueue PCM.
class TurnDetector {
  public:
    explicit TurnDetector(std::shared_ptr<TurnModels> models);
    void receive(std::span<const char, 640> pcm);
    TurnDecision decide(std::string_view text, unsigned stable_ms, QuestionContext context);
    unsigned audio_ms() const { return samples_ / 16; }
    unsigned silence_ms() const { return (samples_ - last_voice_) / 16; }
    unsigned last_voice_ms() const { return last_voice_ / 16; }
    float probability() const { return score_; }
    unsigned inference_ms() const { return inference_ms_; }

  private:
    std::shared_ptr<TurnModels> models_;
    std::array<float, 128000> history_{};
    std::array<float, 576> vad_input_{};
    std::array<float, 256> vad_state_{};
    unsigned samples_ = 0, pending_ = 0, last_voice_ = 0, last_activity_ = 0, voiced_ = 0;
    unsigned epoch_ = 0, job_epoch_ = 0, job_sample_ = 0, score_sample_ = 0;
    unsigned inference_ms_ = 0;
    float score_ = -1;
    bool failed_ = false;
    std::future<float> job_;
    std::chrono::steady_clock::time_point job_started_;
};
} // namespace alojan
