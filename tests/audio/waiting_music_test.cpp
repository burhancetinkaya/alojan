#include "waiting_music.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

int main() {
    try {
        alojan::WaitingMusic music;
        std::array<char, 320> pcm{}, repeated{};
        long long energy = 0;
        int peak = 0, first = 0, last = 0;
        for (unsigned frame = 0; frame < 300; ++frame) {
            music.render(pcm.data(), frame);
            music.render(repeated.data(), frame + 300);
            if (pcm != repeated)
                throw std::runtime_error("loop is not deterministic");
            for (unsigned i = 0; i < 160; ++i) {
                const auto value =
                    static_cast<std::int16_t>(static_cast<unsigned char>(pcm[2 * i]) |
                                              (static_cast<unsigned char>(pcm[2 * i + 1]) << 8));
                if (frame == 0 && i == 0)
                    first = value;
                last = value;
                peak = std::max(peak, std::abs(static_cast<int>(value)));
                energy += static_cast<long long>(value) * value;
            }
        }
        const auto rms = std::sqrt(energy / 48000.0);
        if (peak > 1300 || rms < 250 || rms > 550 || std::abs(first) > 2 || std::abs(last) > 2)
            throw std::runtime_error("music level or smooth loop boundary invalid");
        std::cout << "waiting music peak=" << peak << " rms=" << rms << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
