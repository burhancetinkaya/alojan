#pragma once
#include <array>
#include <span>
#include <stdexcept>
#include <string_view>

namespace alojan {
struct InterruptionSettings {
    unsigned vad_percent = 50, min_voice_ms = 192, sustained_voice_ms = 640;
    unsigned max_quiet_ms = 800, sustained_quiet_ms = 160;
    void validate() const {
        if (vad_percent < 20 || vad_percent > 90 || min_voice_ms < 160 || min_voice_ms > 320 ||
            min_voice_ms % 32 || sustained_voice_ms < 320 || sustained_voice_ms > 1280 ||
            sustained_voice_ms % 32 || min_voice_ms >= sustained_voice_ms || max_quiet_ms < 400 ||
            max_quiet_ms > 1200 || max_quiet_ms % 20 || sustained_quiet_ms < 80 ||
            sustained_quiet_ms > 320 || sustained_quiet_ms % 20)
            throw std::invalid_argument("invalid interruption thresholds");
    }
};
// Worker-only evidence in 32 ms VAD blocks. ASR may span natural pauses, but
// separate bursts must not accumulate into the no-transcript sustained fallback.
struct InterruptionEvidence {
    unsigned voiced_ms = 0, sustained_ms = 0, last_voice_ms = 0;
    bool observe(bool voice, unsigned audio_ms, const InterruptionSettings &settings);
};
// Bounded worker-only outbound reference; this is echo rejection, not an AEC.
class EchoReference {
    std::array<float, 8000> samples_{};
    unsigned written_ = 0;

  public:
    void append(std::span<const char, 320> pcm);
    bool matches(std::span<const char, 640> pcm) const;
};

enum class InterruptDecision { listen, backchannel, interrupt };
InterruptDecision interruption_policy(unsigned voiced_ms, unsigned sustained_ms, unsigned quiet_ms,
                                      std::string_view text, bool fresh,
                                      const InterruptionSettings &settings = {});
} // namespace alojan
