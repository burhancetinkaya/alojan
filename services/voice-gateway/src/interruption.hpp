#pragma once
#include <array>
#include <span>
#include <string_view>

namespace alojan {
// Bounded worker-only outbound reference; this is echo rejection, not an AEC.
class EchoReference {
    std::array<float, 8000> samples_{};
    unsigned written_ = 0;

  public:
    void append(std::span<const char, 320> pcm);
    bool matches(std::span<const char, 640> pcm) const;
};

enum class InterruptDecision { listen, backchannel, interrupt };
InterruptDecision interruption_policy(unsigned voiced_ms, unsigned quiet_ms, std::string_view text,
                                      bool fresh);
} // namespace alojan
