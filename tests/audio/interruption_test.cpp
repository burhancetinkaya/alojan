#include "interruption.hpp"
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>

void require(bool ok, const char *why) {
    if (!ok)
        throw std::runtime_error(why);
}
int main() {
    using namespace alojan;
    try {
        require(interruption_policy(160, 0, "Hayır", true) == InterruptDecision::listen,
                "short noise cannot interrupt from text alone");
        for (const auto text : {"evet", " Evet. ", "hı hı", "tamam"})
            require(interruption_policy(224, 96, text, true) == InterruptDecision::backchannel,
                    "brief acknowledgment interrupted");
        require(interruption_policy(224, 96, "Hayır, düzeltmek istiyorum", true) ==
                    InterruptDecision::interrupt,
                "correction must interrupt");
        require(interruption_policy(224, 96, "Hayır", false) == InterruptDecision::listen,
                "stale text cannot interrupt");
        require(interruption_policy(640, 0, "", false) == InterruptDecision::interrupt,
                "sustained speech cannot wait indefinitely for ASR");
        require(interruption_policy(640, 801, "Hayır", true) == InterruptDecision::listen,
                "old candidate must expire");
        EchoReference reference;
        std::array<char, 320> sent{};
        std::array<char, 640> received{};
        std::array<std::int16_t, 3200> original{};
        std::uint32_t random = 12345;
        for (unsigned i = 0; i < original.size(); ++i) {
            random = random * 1664525u + 1013904223u;
            original[i] = static_cast<std::int16_t>((random >> 16) / 4);
        }
        for (unsigned f = 0; f < 20; ++f) {
            std::memcpy(sent.data(), original.data() + f * 160, 320);
            reference.append(sent);
        }
        for (unsigned i = 0; i < 160; ++i) {
            const std::int16_t value = -original[1600 + i] / 2;
            std::memcpy(received.data() + i * 4, &value, 2);
            std::memcpy(received.data() + i * 4 + 2, &value, 2);
        }
        require(reference.matches(received), "delayed attenuated inverted echo was not rejected");
        for (unsigned i = 0; i < 320; ++i) {
            const std::int16_t value = static_cast<std::int16_t>(12000 * std::sin(i * 0.17));
            std::memcpy(received.data() + 2 * i, &value, 2);
        }
        require(!reference.matches(received), "unrelated speech matched echo");
        // Comparable independent near-end speech must not be suppressed as pure echo.
        for (unsigned i = 0; i < 320; ++i) {
            const std::int16_t value =
                static_cast<std::int16_t>(12000 * std::sin(i * 0.17) + original[1600 + i / 2] / 2);
            std::memcpy(received.data() + 2 * i, &value, 2);
        }
        require(!reference.matches(received), "double-talk was suppressed as echo");
        received.fill(0);
        require(!reference.matches(received), "silence cannot count as echo evidence");
        std::cout << "interruption policy and delayed reference passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
