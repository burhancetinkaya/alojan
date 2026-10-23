#include "turn_detector.hpp"
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>

// Test-only normalized float32 input and feature output, never a caller recording path.
int main(int argc, char **argv) {
    try {
        if (argc != 4)
            return 2;
        std::ifstream input(argv[2], std::ios::binary | std::ios::ate);
        const auto size = input.tellg();
        if (size <= 0 || size > 30 * 16000 * 4 || size % 4)
            return 2;
        std::vector<float> audio(static_cast<std::size_t>(size) / 4);
        input.seekg(0);
        if (!input.read(reinterpret_cast<char *>(audio.data()), size))
            return 2;
        auto models = std::make_shared<alojan::TurnModels>(argv[1]);
        const auto start = std::chrono::steady_clock::now();
        const float score = models->complete(audio);
        const auto ms =
            std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start)
                .count();
        const auto features = models->features(audio);
        std::ofstream output(argv[3], std::ios::binary);
        output.write(reinterpret_cast<const char *>(features.data()), features.size() * 4);
        if (!output)
            return 2;
        std::array<float, 576> frame{};
        std::array<float, 256> state{};
        float maximum = 0;
        std::vector<float> scores;
        for (std::size_t pos = 0; pos + 512 <= audio.size(); pos += 512) {
            std::copy_n(audio.begin() + pos, 512, frame.begin() + 64);
            const float value = models->vad(frame, state);
            maximum = std::max(maximum, value);
            scores.push_back(value);
            std::copy(frame.end() - 64, frame.end(), frame.begin());
        }
        std::ofstream vad_output(std::string(argv[3]) + ".vad", std::ios::binary);
        vad_output.write(reinterpret_cast<const char *>(scores.data()), scores.size() * 4);
        std::cout << "probability=" << score << " inference_ms=" << ms << " vad_max=" << maximum
                  << '\n';
    } catch (const std::exception &) {
        std::cerr << "turn model probe failed\n";
        return 1;
    }
}
