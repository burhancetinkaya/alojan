#include "turn_detector.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <thread>

// Link-time test double: deterministic timing/faults, never model-readiness evidence.
namespace {
std::atomic<unsigned> runs{0};
std::atomic<bool> fail_score{false};
void require(bool condition, const char *message) {
    if (!condition)
        throw std::runtime_error(message);
}
} // namespace
namespace alojan {
struct TurnModels::Impl {};
TurnModels::TurnModels(const std::string &) {}
TurnModels::~TurnModels() = default;
float TurnModels::vad(std::span<const float, 576> audio, std::array<float, 256> &state) {
    require(state[0] == audio[0], "per-call VAD state/context mismatch");
    state[0] = audio[512];
    float peak = 0;
    for (auto x : audio.subspan(64))
        peak = std::max(peak, std::abs(x));
    return peak;
}
float TurnModels::complete(std::span<const float> audio) {
    require(audio.size() <= 128000, "unbounded model input");
    ++runs;
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    if (fail_score.load())
        throw std::runtime_error("synthetic detector failure");
    return .99f;
}
} // namespace alojan

int main() {
    using namespace alojan;
    using enum TurnDecision;
    try {
        auto models = std::make_shared<TurnModels>("test-only");
        TurnDetector first(models), other(models);
        std::array<char, 640> speech{}, silence{};
        for (unsigned i = 0; i < 320; ++i) {
            speech[i * 2] = 0;
            speech[i * 2 + 1] = 64;
        }
        auto feed = [&](TurnDetector &detector, bool voiced, unsigned frames) {
            for (unsigned i = 0; i < frames; ++i) {
                detector.receive(voiced ? speech : silence);
                detector.decide("Yarın arayın.", 300, QuestionContext::open);
            }
        };
        feed(first, true, 10);
        feed(other, false, 30);
        require(other.decide("Yarın arayın.", 300, QuestionContext::open) == listen,
                "silent call inherited speech");
        require(first.audio_ms() == 200 && other.audio_ms() == 600, "20-to-32 ms framing lost PCM");
        feed(first, false, 30);
        feed(first, true, 10);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        require(first.decide("Yarın arayın.", 300, QuestionContext::open) == listen &&
                    first.probability() < 0,
                "stale score accepted after resumed speech");
        feed(first, false, 30);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        require(first.decide("Yarın arayın.", 300, QuestionContext::open) == complete,
                "valid completion lost");
        require(first.decide("Yarın arayın ama", 300, QuestionContext::open) == listen,
                "incomplete phrase cut at short pause");
        std::array<char, 640> weak_onset{};
        for (unsigned i = 0; i < 320; ++i)
            weak_onset[2 * i + 1] = 32;
        first.receive(weak_onset);
        first.receive(weak_onset);
        require(first.decide("Yarın arayın.", 300, QuestionContext::open) == listen &&
                    first.probability() < 0,
                "low-confidence resumption reused an old completion score");
        feed(first, true, 10);
        feed(first, false, 30);
        fail_score.store(true);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        require(first.decide("Yarın arayın.", 300, QuestionContext::open) == detector_failed,
                "model failure allowed response");
        fail_score.store(false);
        TurnDetector long_turn(models);
        feed(long_turn, true, 600);
        feed(long_turn, false, 30);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        require(long_turn.decide("Yarın arayın.", 300, QuestionContext::open) == complete,
                "bounded history rollover failed");
        TurnDetector quiet(models);
        feed(quiet, false, 349);
        require(!quiet.reminder_due(), "early silence reminder");
        feed(quiet, false, 1);
        require(quiet.reminder_due(), "seven-second reminder missing");
        quiet.receive(weak_onset);
        quiet.receive(weak_onset);
        require(!quiet.reminder_due(), "reminder overlaps low-confidence onset");
        feed(quiet, true, 10);
        feed(quiet, false, 400);
        require(!quiet.reminder_due(), "incomplete spoken turn mistaken for idle caller");
        alojan::TurnSettings sensitive;
        sensitive.vad_percent = 20;
        TurnDetector configured(models, sensitive);
        for (unsigned i = 0; i < 10; ++i)
            configured.receive(weak_onset);
        require(configured.has_speech(), "configured VAD threshold ignored");
        sensitive.silence_reminder_ms = 3000;
        TurnDetector early_reminder(models, sensitive), default_reminder(models);
        sensitive.silence_reminder_ms = 15000;
        feed(early_reminder, false, 149);
        feed(default_reminder, false, 150);
        require(!early_reminder.reminder_due() && !default_reminder.reminder_due(),
                "reminder state leaked between calls");
        feed(early_reminder, false, 1);
        require(early_reminder.reminder_due() && !default_reminder.reminder_due(),
                "configured reminder lost its snapshot");
        require(runs.load() >= 3, "background inference never ran");
        std::cout << "turn detector: reframing, isolation, stale score, failure and bounded "
                     "history passed\n";
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
