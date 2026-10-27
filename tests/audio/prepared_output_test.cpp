#include "speech_media.hpp"
#include <array>
#include <chrono>
#include <iostream>
#include <thread>

class Sink : public pj::AudioMediaPort {
  public:
    std::array<char, 320 * 50> pcm{};
    std::atomic<unsigned> frames{0};
    void onFrameReceived(pj::MediaFrame &frame) override {
        const auto index = frames.load();
        if (index < 50 && frame.type == PJMEDIA_FRAME_TYPE_AUDIO && frame.buf.size() == 320) {
            std::memcpy(pcm.data() + index * 320, frame.buf.data(), 320);
            frames.store(index + 1);
        }
    }
};

int main() {
    using namespace std::chrono_literals;
    pj::Endpoint endpoint;
    endpoint.libCreate();
    int result = 1;
    try {
        pj::EpConfig config;
        config.logConfig.level = config.logConfig.consoleLevel = 0;
        config.medConfig.clockRate = config.medConfig.sndClockRate = 8000;
        config.medConfig.noVad = true;
        endpoint.libInit(config);
        endpoint.libStart();
        endpoint.audDevManager().setNullDev();
        voice::v1::PreparedAudioRequest request;
        request.set_call_id("managed-native-port");
        request.set_release_id("00000000-0000-0000-0000-000000000001");
        request.set_manifest_digest(std::string(64, 'a'));
        voice::v1::PreparedAudioReply reply;
        reply.set_call_id(request.call_id());
        reply.set_release_id(request.release_id());
        reply.set_manifest_digest(request.manifest_digest());
        std::string tone;
        for (unsigned i = 0; i < 320; ++i) {
            tone += static_cast<char>(0xe8);
            tone += static_cast<char>(0x03); // 1000, little-endian PCM16
        }
        reply.set_greeting_pcm(std::string(640, '\0') + tone);
        reply.set_unavailable_pcm(tone);
        reply.set_greeting_pad_ms(40);
        auto audio = alojan::PreparedAudio::validate(request, reply);
        alojan::PreparedPlayback first(audio, true), second(audio, false), cancelled(audio, false);
        cancelled.cancel();
        PreparedOutput one, two, three;
        Sink sink1, sink2, sink3;
        pj::MediaFormatAudio format;
        format.init(PJMEDIA_FORMAT_PCM, 8000, 1, 20000, 16);
        sink1.createPort("prepared-sink-1", format);
        sink2.createPort("prepared-sink-2", format);
        sink3.createPort("prepared-sink-3", format);
        one.create(first);
        two.create(second);
        three.create(cancelled);
        one.startTransmit(sink1);
        two.startTransmit(sink2);
        three.startTransmit(sink3);
        const auto deadline = std::chrono::steady_clock::now() + 2s;
        while ((sink1.frames.load() < 20 || sink2.frames.load() < 20 || sink3.frames.load() < 20) &&
               std::chrono::steady_clock::now() < deadline)
            std::this_thread::sleep_for(5ms);
        one.stopTransmit(sink1);
        two.stopTransmit(sink2);
        three.stopTransmit(sink3);
        // Read only an already-published prefix; the callback may still publish later silence.
        const std::string a(sink1.pcm.data(), std::min(20U, sink1.frames.load()) * 320);
        const std::string b(sink2.pcm.data(), std::min(20U, sink2.frames.load()) * 320);
        const std::string c(sink3.pcm.data(), std::min(20U, sink3.frames.load()) * 320);
        result = first.sent_frames() == 4 && second.sent_frames() == 2 &&
                         cancelled.sent_frames() == 0 &&
                         a.find(reply.greeting_pcm()) != std::string::npos &&
                         b.find(tone) != std::string::npos && c.size() >= 6400 &&
                         c == std::string(c.size(), '\0')
                     ? 0
                     : 1;
        std::cout << "prepared_port_playback=" << (result == 0) << '\n';
    } catch (...) {
        std::cerr << "prepared port test failed\n";
    }
    endpoint.libDestroy();
    return result;
}
