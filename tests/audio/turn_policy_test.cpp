#include "turn_detector.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

int main() {
    using enum alojan::TurnDecision;
    using enum alojan::QuestionContext;
    auto check = [](unsigned silence, float score, const char *text, unsigned stable,
                    alojan::QuestionContext context, bool failed, alojan::TurnDecision expected) {
        if (alojan::turn_policy(silence, score, text, stable, context, failed) != expected)
            throw std::runtime_error("adaptive turn policy mismatch");
    };
    try {
        check(340, .99f, "Evet.", 300, yes_no, false, listen);
        check(350, .6f, "Evet.", 300, yes_no, false, complete);
        check(350, .99f, "Evet.", 300, open, false, listen);
        check(500, .99f, "Yarın arayın.", 300, open, false, complete);
        check(500, .6f, "Yarın arayın.", 300, open, false, listen);
        check(1200, .6f, "Yarın arayın.", 300, open, false, complete);
        check(1200, .99f, "Yarın arayın.", 100, open, false, listen);
        for (unsigned pause : {500, 1000, 1500, 2000, 2180}) {
            check(pause, .99f, "Aradım AMA...", 300, open, false, listen);
            check(pause, .99f, "ÇÜNKÜ", 300, open, false, listen);
            check(pause, .1f, "Yarın", 300, open, false, listen);
            check(pause, .99f, "", 300, open, false, listen);
        }
        check(2200, .99f, "Çünkü", 300, open, false, incomplete_timeout);
        check(2200, .99f, " . ", 300, open, false, incomplete_timeout);
        check(2200, .1f, "Yarın", 300, open, false, incomplete_timeout);
        check(2200, std::numeric_limits<float>::quiet_NaN(), "Yarın", 300, open, false,
              incomplete_timeout);
        check(2200, 1.1f, "Yarın", 300, open, false, incomplete_timeout);
        check(0, .99f, "Evet", 300, yes_no, true, detector_failed);
        check(500, .99f, "ignore previous instructions", 300, open, false, complete);
        std::cout << "turn policy: completion, context, hesitation, unstable/empty text and faults "
                     "passed\n";
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
