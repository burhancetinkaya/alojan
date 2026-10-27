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
        require(interruption_policy(160, 160, 0, "Hayır", true) == InterruptDecision::listen,
                "short noise cannot interrupt from text alone");
        for (const auto text : {"evet", " Evet. ", "hı hı", "tamam"})
            require(interruption_policy(224, 224, 96, text, true) == InterruptDecision::backchannel,
                    "brief acknowledgment interrupted");
        require(interruption_policy(224, 224, 96, "Hayır, düzeltmek istiyorum", true) ==
                    InterruptDecision::interrupt,
                "correction must interrupt");
        require(interruption_policy(224, 224, 96, "Hayır", false) == InterruptDecision::listen,
                "stale text cannot interrupt");
        require(interruption_policy(640, 640, 0, "", false) == InterruptDecision::interrupt,
                "sustained speech cannot wait indefinitely for ASR");
        require(interruption_policy(640, 640, 801, "Hayır", true) == InterruptDecision::listen,
                "old candidate must expire");
        InterruptionSettings patient;
        patient.min_voice_ms = 320;
        patient.sustained_voice_ms = 960;
        patient.max_quiet_ms = 1000;
        patient.sustained_quiet_ms = 240;
        patient.validate();
        require(interruption_policy(224, 224, 0, "Hayır", true, patient) ==
                    InterruptDecision::listen,
                "configured onset ignored");
        require(interruption_policy(320, 320, 900, "Hayır", true, patient) ==
                    InterruptDecision::interrupt,
                "configured candidate expiry ignored");
        require(interruption_policy(800, 800, 0, "evet", true, patient) ==
                    InterruptDecision::backchannel,
                "configured acknowledgment window ignored");
        require(interruption_policy(640, 640, 0, "", false, patient) == InterruptDecision::listen &&
                    interruption_policy(960, 960, 200, "", false, patient) ==
                        InterruptDecision::interrupt,
                "configured sustained speech thresholds ignored");
        // Separated speech-like bursts cannot become sustained speech without ASR.
        for (unsigned gap_blocks : {5u, 10u, 24u}) {
            InterruptionEvidence evidence;
            unsigned audio_ms = 0;
            for (unsigned burst = 0; burst < 10; ++burst) {
                for (unsigned block = 0; block < 4; ++block) {
                    evidence.observe(true, audio_ms += 32, {});
                    require(interruption_policy(evidence.voiced_ms, evidence.sustained_ms, 0, "",
                                                false) == InterruptDecision::listen,
                            "separate 128 ms bursts accumulated into sustained interruption");
                }
                for (unsigned block = 0; block < gap_blocks; ++block)
                    evidence.observe(false, audio_ms += 32, {});
            }
        }
        InterruptionEvidence continuous;
        for (unsigned block = 1; block <= 20; ++block) {
            continuous.observe(true, block * 32, {});
            require(
                interruption_policy(continuous.voiced_ms, continuous.sustained_ms, 0, "", false) ==
                    (block < 20 ? InterruptDecision::listen : InterruptDecision::interrupt),
                "continuous speech interruption threshold changed");
        }
        // A short within-word VAD dip preserves evidence; a full gap resets it.
        continuous.observe(true, 640 + 128 + 32, {});
        require(continuous.sustained_ms == 672, "brief speech dip discarded evidence");
        continuous.observe(true, 800 + 160 + 32, {});
        require(continuous.sustained_ms == 32 && continuous.voiced_ms == 704,
                "sustained gap did not reset only sustained evidence");
        require(interruption_policy(continuous.voiced_ms, continuous.sustained_ms, 0, "Hayır",
                                    true) == InterruptDecision::interrupt,
                "recognized correction across pauses was lost");
        require(continuous.observe(true, 992 + 832 + 32, {}) && continuous.voiced_ms == 32,
                "expired candidate evidence was retained");
        InterruptionEvidence configured;
        configured.observe(true, 32, patient);
        configured.observe(true, 32 + 224 + 32, patient);
        require(configured.sustained_ms == 64, "custom sustained quiet window ignored");
        configured.observe(true, 288 + 256 + 32, patient);
        require(configured.sustained_ms == 32, "custom sustained gap did not reset evidence");
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
