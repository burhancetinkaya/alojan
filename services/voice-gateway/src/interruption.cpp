#include "interruption.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>

namespace alojan {
namespace {
float sample(const char *p) {
    return static_cast<std::int16_t>(static_cast<unsigned char>(p[0]) |
                                     (static_cast<unsigned char>(p[1]) << 8));
}
} // namespace
void EchoReference::append(std::span<const char, 320> pcm) {
    for (unsigned i = 0; i < 160; ++i)
        samples_[written_++ % samples_.size()] = sample(pcm.data() + 2 * i);
}
bool EchoReference::matches(std::span<const char, 640> pcm) const {
    std::array<float, 160> input{};
    double energy = 0;
    for (unsigned i = 0; i < input.size(); ++i) {
        input[i] = (sample(pcm.data() + 4 * i) + sample(pcm.data() + 4 * i + 2)) / 2;
        energy += input[i] * input[i];
    }
    if (energy < 160 * 100.0 * 100.0)
        return false;
    // Search up to 400 ms of delay in 1 ms steps, allowing polarity inversion.
    for (unsigned lag = 0; lag <= 3200 && written_ >= lag + 160; lag += 8) {
        double reference = 0, dot = 0;
        for (unsigned i = 0; i < 160; ++i) {
            const auto value = samples_[(written_ - lag - 160 + i) % samples_.size()];
            reference += value * value;
            dot += value * input[i];
        }
        if (reference > 160 * 100.0 * 100.0 && energy <= 2.25 * reference &&
            dot * dot > 0.82 * 0.82 * reference * energy)
            return true;
    }
    return false;
}
InterruptDecision interruption_policy(unsigned voiced_ms, unsigned quiet_ms, std::string_view text,
                                      bool fresh) {
    if (voiced_ms < 192 || quiet_ms > 800)
        return InterruptDecision::listen;
    std::string value(text);
    for (auto &c : value)
        if (c >= 'A' && c <= 'Z')
            c += 'a' - 'A';
    const auto end = value.find_last_not_of(" \t\r\n.,!?;:");
    value = end == std::string::npos ? "" : value.substr(0, end + 1);
    const auto start = value.find_first_not_of(" \t\r\n");
    if (start != std::string::npos)
        value.erase(0, start);
    const bool acknowledgment =
        value == "evet" || value == "hı hı" || value == "hıhı" || value == "tamam";
    if (fresh && acknowledgment && voiced_ms <= 640)
        return InterruptDecision::backchannel;
    // shortcut: bounded lexical backchannels; M4 must add question/semantic context.
    if ((fresh && !value.empty() && !acknowledgment) || (voiced_ms >= 640 && quiet_ms < 160))
        return InterruptDecision::interrupt;
    return InterruptDecision::listen;
}
} // namespace alojan
