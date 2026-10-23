#include "speech_bridge.hpp"
#include <iostream>

int main(int argc, char **argv) {
    using namespace std::chrono_literals;
    if (argc != 3)
        return 2;
    const auto deadline = std::chrono::system_clock::now() + 3s;
    alojan::SpeechBridge bridge("probe-stalled-playout", std::stoul(argv[1]), std::stoul(argv[2]),
                                50, "Synthetic test", deadline);
    bridge.start();
    std::array<char, 640> pcm{};
    for (unsigned i = 0; i < 50; ++i)
        bridge.receive(pcm.data());
    // Deliberately never render: a stopped audio clock must not accumulate speech forever.
    while (!bridge.finished() && std::chrono::system_clock::now() < deadline)
        std::this_thread::sleep_for(1ms);
    const bool correct =
        bridge.finished() && bridge.error() == alojan::SpeechBridge::Error::playout_stall &&
        bridge.generated.load() == 32 && bridge.played.load() == 0 && !bridge.render(pcm.data());
    std::cout << "stalled_playout=" << correct << '\n';
    return correct ? 0 : 1;
}
