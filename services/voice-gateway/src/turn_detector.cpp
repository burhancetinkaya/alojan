#include "turn_detector.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace alojan {
namespace {
std::string normalized(std::string_view text) {
    std::string result(text);
    for (char &c : result)
        if (c >= 'A' && c <= 'Z')
            c += 'a' - 'A';
    for (const auto &[upper, lower] :
         {std::pair{"İ", "i"}, {"Ç", "ç"}, {"Ş", "ş"}, {"Ğ", "ğ"}, {"Ö", "ö"}, {"Ü", "ü"}}) {
        std::size_t pos = 0;
        while ((pos = result.find(upper, pos)) != std::string::npos) {
            result.replace(pos, std::strlen(upper), lower);
            pos += std::strlen(lower);
        }
    }
    const auto end = result.find_last_not_of(" \t\r\n.,!?;:");
    if (end == std::string::npos)
        return {};
    result.resize(end + 1);
    const auto start = result.find_first_not_of(" \t\r\n");
    return result.substr(start);
}
} // namespace

TurnDecision turn_policy(unsigned silence_ms, float probability, std::string_view text,
                         unsigned stable_ms, QuestionContext context, bool detector_failed,
                         const TurnSettings &settings) {
    if (detector_failed)
        return TurnDecision::detector_failed;
    if (silence_ms < settings.yes_no_ms)
        return TurnDecision::listen;
    // Default preserves the 200 ms endpoint pad beyond the 2 s incomplete-phrase wait.
    const bool expired = silence_ms >= settings.incomplete_ms;
    if (stable_ms < 200)
        return expired ? TurnDecision::incomplete_timeout : TurnDecision::listen;
    const auto value = normalized(text);
    const auto last = value.substr(value.find_last_of(" \t\r\n") + 1);
    // shortcut: lexical hesitation hints; richer semantics belongs to the M4 agent context.
    const bool incomplete = last == "ama" || last == "ve" || last == "çünkü" || last == "yani" ||
                            last == "şey" || last == "ee" || last == "bir" || last == "eğer" ||
                            value.ends_with("bir dakika") || value.ends_with("düşünüyorum");
    if (value.empty() || incomplete || !std::isfinite(probability) || probability < 0.5f ||
        probability > 1.0f)
        return expired ? TurnDecision::incomplete_timeout : TurnDecision::listen;
    const bool short_answer = value == "evet" || value == "hayır" || value == "tamam";
    const unsigned wait = context == QuestionContext::yes_no && short_answer ? settings.yes_no_ms
                          : probability >= 0.75f                             ? settings.open_ms
                                                 : settings.uncertain_ms;
    return silence_ms >= wait ? TurnDecision::complete : TurnDecision::listen;
}

TurnDetector::TurnDetector(std::shared_ptr<TurnModels> models, TurnSettings settings)
    : settings_(settings), models_(std::move(models)) {
    settings_.validate();
}

void TurnDetector::receive(std::span<const char, 640> pcm) {
    for (unsigned i = 0; i < 320; ++i) {
        const auto lo = static_cast<unsigned char>(pcm[2 * i]);
        const auto hi = static_cast<unsigned char>(pcm[2 * i + 1]);
        const float sample = static_cast<std::int16_t>(lo | (hi << 8)) / 32768.0f;
        history_[samples_++ % history_.size()] = sample;
        vad_input_[64 + pending_++] = sample;
        if (pending_ != 512)
            continue;
        const auto speech = models_->vad(vad_input_, vad_state_);
        // Low-confidence onset can precede confirmed speech by >200 ms after a long pause.
        // It only delays decisions; it cannot create a turn or authenticate transcript text.
        if (speech >= 0.10f) {
            last_activity_ = samples_;
            ++epoch_;
            score_ = -1;
        }
        if (speech >= settings_.vad_percent / 100.0f) {
            voiced_ += 512;
            last_voice_ = samples_;
        }
        std::copy(vad_input_.end() - 64, vad_input_.end(), vad_input_.begin());
        pending_ = 0;
    }
}

TurnDecision TurnDetector::decide(std::string_view text, unsigned stable_ms,
                                  QuestionContext context) {
    using namespace std::chrono_literals;
    if (job_.valid()) {
        if (job_.wait_for(0ms) == std::future_status::ready) {
            inference_ms_ =
                static_cast<unsigned>(std::chrono::duration_cast<std::chrono::milliseconds>(
                                          std::chrono::steady_clock::now() - job_started_)
                                          .count());
            try {
                const float result = job_.get();
                if (job_epoch_ == epoch_ && samples_ - job_sample_ <= 16000) {
                    score_ = result;
                    score_sample_ = job_sample_;
                }
            } catch (...) {
                failed_ = true;
            }
        } else if (std::chrono::steady_clock::now() - job_started_ > 1500ms)
            failed_ = true;
    }
    if (failed_)
        return TurnDecision::detector_failed;
    // At least 96 ms of speech; retain 8 s in memory, including leading silence/pre-roll.
    if (!has_speech() || silence_ms() < settings_.candidate_ms || samples_ - last_activity_ < 3200)
        return TurnDecision::listen;
    if (samples_ - score_sample_ > 16000)
        score_ = -1;
    const auto decision =
        turn_policy(silence_ms(), score_, text, stable_ms, context, false, settings_);
    if (decision != TurnDecision::listen)
        return decision;
    // Fresh positive evidence remains useful while waiting for transcript coverage.
    // Resumption invalidates it above; the existing one-second age bound still applies.
    const bool reuse = settings_.partial_hint && text.empty() && score_ >= 0.75f;
    if (!reuse && !job_.valid() && (job_epoch_ != epoch_ || samples_ - job_sample_ >= 5120)) {
        const auto count = std::min<std::size_t>(samples_, history_.size());
        std::vector<float> audio(count);
        for (std::size_t i = 0; i < count; ++i)
            audio[i] = history_[(samples_ - count + i) % history_.size()];
        ++jobs_started_;
        job_epoch_ = epoch_;
        job_sample_ = samples_;
        job_started_ = std::chrono::steady_clock::now();
        job_ = std::async(std::launch::async, [models = models_, audio = std::move(audio)] {
            return models->complete(audio);
        });
    }
    return TurnDecision::listen;
}
} // namespace alojan
