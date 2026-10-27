#include "prepared_audio.hpp"
#include <array>
#include <grpcpp/grpcpp.h>
#include <iostream>
#include <thread>

int main(int argc, char **argv) {
    using namespace std::chrono_literals;
    if (argc != 7)
        return 2;
    const std::string mode = argv[2];
    auto channel = alojan::prepared_audio_channel(std::stoul(argv[1]));
    voice::v1::PreparedAudioRequest request;
    request.set_call_id(argv[3]);
    request.set_release_id(argv[5]);
    request.set_manifest_digest(argv[6]);
    grpc::ClientContext context;
    std::atomic<bool> cancelled{false};
    std::thread canceller;
    if (mode == "cancel")
        canceller = std::thread([&] {
            std::this_thread::sleep_for(50ms);
            cancelled.store(true);
            context.TryCancel();
        });
    try {
        auto audio = alojan::fetch_prepared_audio(channel, request, argv[4],
                                                  std::chrono::system_clock::now() +
                                                      (mode == "deadline" ? 60ms : 1800ms),
                                                  context, cancelled);
        if (canceller.joinable())
            canceller.join();
        if (mode != "success")
            return 1;
        alojan::PreparedPlayback one(audio, true), two(audio, true), fallback(audio, false);
        std::array<char, 320> frame{}, other{};
        std::string output, unavailable;
        while (one.render(frame.data()))
            output.append(frame.data(), frame.size());
        if (output != audio->greeting() || one.sent_frames() != output.size() / 320 ||
            !two.render(other.data()) ||
            std::string(other.data(), other.size()) != output.substr(0, 320))
            return 1;
        while (fallback.render(frame.data()))
            unavailable.append(frame.data(), frame.size());
        if (unavailable != audio->unavailable())
            return 1;
        two.cancel();
        if (two.render(other.data()) || two.sent_frames() != 1 ||
            std::string(other.data(), other.size()) != std::string(320, '\0'))
            return 1;
        // Synthetic PCM checksums allow Python to verify exactly what native playback rendered.
        unsigned long long greeting_sum = 0, unavailable_sum = 0;
        for (unsigned char byte : output)
            greeting_sum += byte;
        for (unsigned char byte : unavailable)
            unavailable_sum += byte;
        std::cout << "played=" << output.size() << "," << unavailable.size()
                  << " sums=" << greeting_sum << "," << unavailable_sum << '\n';
        return 0;
    } catch (...) {
        if (canceller.joinable())
            canceller.join();
        std::cout << "prepared_audio_rejected\n";
        return mode == "success" ? 1 : 0;
    }
}
