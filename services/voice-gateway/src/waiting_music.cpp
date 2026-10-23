#include "waiting_music.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <numbers>

namespace alojan {
WaitingMusic::WaitingMusic() {
    constexpr std::array notes{523.251, 659.255, 587.330, 391.995};
    constexpr auto tau = 2 * std::numbers::pi;
    for (unsigned i = 0; i < 48000; ++i) {
        const double t = i / 8000.0;
        const auto note = static_cast<unsigned>(t / 1.5);
        const double local = t - note * 1.5;
        const double envelope = std::pow(std::sin(std::numbers::pi * local / 1.5), 2);
        const double pad_envelope = std::pow(std::sin(std::numbers::pi * t / 6.0), 2);
        const double melody =
            std::sin(tau * notes[note] * local) + 0.12 * std::sin(tau * notes[note] * 2 * local);
        const double pad = std::sin(tau * 261.626 * t) + std::sin(tau * 329.628 * t);
        const auto sample = static_cast<std::int16_t>(
            std::lround(950 * envelope * melody + 110 * pad_envelope * pad));
        const auto bits = static_cast<std::uint16_t>(sample);
        frames_[i / 160][(i % 160) * 2] = static_cast<char>(bits & 255);
        frames_[i / 160][(i % 160) * 2 + 1] = static_cast<char>(bits >> 8);
    }
}

void WaitingMusic::render(char *pcm, std::uint64_t frame) const noexcept {
    std::memcpy(pcm, frames_[frame % frames_.size()].data(), 320);
}
} // namespace alojan
