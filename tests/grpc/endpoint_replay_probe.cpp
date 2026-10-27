#include "speech_bridge.hpp"
#include <fstream>
#include <iostream>
#include <iterator>

// Synthetic PCM only. Reuses the production bridge; no alternative endpoint policy.
int main(int argc, char **argv) {
    using namespace std::chrono_literals;
    try {
        if (argc != 5)
            return 2;
        auto models = std::make_shared<alojan::TurnModels>(argv[1]);
        std::ifstream cases(argv[4]);
        if (!cases)
            return 2;
        std::string id, path;
        unsigned hint, expected_end;
        while (cases >> id >> hint >> expected_end >> path) {
            if (hint > 1 || expected_end > 25000 || id.size() > 80)
                return 2;
            std::ifstream input(path, std::ios::binary);
            if (!input)
                return 2;
            std::vector<char> audio((std::istreambuf_iterator<char>(input)), {});
            if (audio.empty() || audio.size() > 25 * 32000 || audio.size() % 2)
                return 2;
            alojan::TurnSettings settings;
            settings.partial_hint = hint != 0;
            alojan::SpeechBridge bridge(id, std::stoul(argv[2]), std::stoul(argv[3]), 1500,
                                        "Synthetic test", std::chrono::system_clock::now() + 35s,
                                        models, alojan::QuestionContext::open, false, 0, "",
                                        settings);
            const auto started = std::chrono::steady_clock::now();
            bridge.start();
            unsigned frame = 0;
            std::array<char, 640> pcm{};
            std::array<char, 320> output{};
            while (!bridge.finished() && std::chrono::steady_clock::now() - started < 34s) {
                pcm.fill(0);
                const auto offset = static_cast<std::size_t>(frame) * pcm.size();
                if (offset < audio.size())
                    std::copy_n(audio.begin() + offset, std::min(pcm.size(), audio.size() - offset),
                                pcm.begin());
                bridge.receive(pcm.data());
                bridge.render(output.data());
                ++frame;
                std::this_thread::sleep_until(started + frame * 20ms);
            }
            const bool completed = bridge.state() == alojan::SpeechBridge::State::complete;
            const auto accepted_audio = bridge.written.load() * 20;
            bridge.cancel();
            std::cout << "event=replay_result case=" << id << " hint=" << hint
                      << " complete=" << completed << " error=" << static_cast<int>(bridge.error())
                      << " accepted_audio_ms=" << accepted_audio
                      << " expected_end_audio_ms=" << expected_end
                      << " premature=" << (accepted_audio < expected_end)
                      << " endpoint_silence_ms=" << bridge.turn_silence_ms.load() << std::endl;
        }
        return 0;
    } catch (const std::exception &) {
        std::cerr << "synthetic endpoint replay failed\n";
        return 1;
    }
}
