#include "call_setup.hpp"
#include "speech_bridge.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>

// Link-time detector double: test monitor/lease flow, never model readiness.
namespace alojan {
struct TurnModels::Impl {};
TurnModels::TurnModels(const std::string &) {}
TurnModels::~TurnModels() = default;
float TurnModels::vad(std::span<const float, 576> audio, std::array<float, 256> &) {
    float peak = 0;
    for (auto sample : audio.subspan(64))
        peak = std::max(peak, std::abs(sample));
    return peak;
}
float TurnModels::complete(std::span<const float>) { return .99f; }
} // namespace alojan

int main(int argc, char **argv) {
    using namespace std::chrono_literals;
    if (argc != 5 && argc != 6)
        return 2;
    const auto agent_port = std::stoul(argv[1]), asr_port = std::stoul(argv[2]);
    const auto tts_port = std::stoul(argv[3]);
    voice::v1::CallInitializationRequest request;
    request.set_call_id("managed-native-recognition");
    request.set_called_e164(argv[4]);
    request.set_called_source("request_uri");
    alojan::CallSetup setup(alojan::prepared_audio_channel(agent_port), request,
                            std::chrono::system_clock::now() + 1800ms,
                            alojan::speech_channel(asr_port), alojan::speech_channel(tts_port),
                            alojan::speech_channel(agent_port));
    while (setup.state() == alojan::CallSetup::State::pending)
        std::this_thread::sleep_for(1ms);
    if (!setup.recognition() || !setup.agent() || !setup.synthesis() || !setup.settings())
        return 3;
    // Reject foreign, malformed and incomplete bindings before any media RPC.
    for (unsigned service = 0; service < 3; ++service) {
        for (unsigned fault = 0; fault < 4; ++fault) {
            std::array<std::shared_ptr<const alojan::CallServiceBinding>, 3> bindings{
                setup.recognition(), setup.agent(), setup.synthesis()};
            auto invalid = std::make_shared<alojan::CallServiceBinding>(*bindings[service]);
            if (fault == 0)
                invalid->call_id = "managed-other";
            else if (fault == 1)
                invalid->lease = "invalid";
            else if (fault == 2)
                invalid->channel.reset();
            bindings[service] = fault == 3 ? nullptr : invalid;
            try {
                alojan::SpeechBridge rejected(
                    request.call_id(), asr_port, tts_port, 50, "Test",
                    std::chrono::system_clock::now() + 1s, {}, alojan::QuestionContext::open, false,
                    agent_port, "", {}, bindings[0], bindings[1], bindings[2], setup.settings());
                return 4;
            } catch (const std::invalid_argument &) {
            }
        }
    }
    try {
        alojan::SpeechBridge rejected(request.call_id(), asr_port, tts_port, 50, "Test",
                                      std::chrono::system_clock::now() + 1s, {},
                                      alojan::QuestionContext::open, false, agent_port, "", {},
                                      setup.recognition(), setup.agent(), setup.synthesis());
        return 5;
    } catch (const std::invalid_argument &) {
    }
    setup.answered();
    const auto deadline = std::chrono::system_clock::now() + 6s;
    bool success = false;
    const bool calibration = argc == 6 && std::string(argv[5]) == "calibration";
    const bool interrupt_calibration = argc == 6 && std::string(argv[5]) == "interrupt_calibration";
    const bool monitor =
        (argc == 6 && std::string(argv[5]) == "monitor") || calibration || interrupt_calibration;
    const bool cancel_stream = argc == 6 && std::string(argv[5]) == "cancel";
    const bool limited =
        argc == 6 && std::string(argv[5]) == "limit" && setup.settings()->max_call_turns == 1;
    const bool output_rejected = argc == 6 && std::string(argv[5]) == "output_rejected";
    const bool timed_out = argc == 6 && std::string(argv[5]) == "deadline";
    auto tts_binding = setup.synthesis();
    if (argc == 6 && std::string(argv[5]) == "wrong_tts") {
        auto invalid = std::make_shared<alojan::CallServiceBinding>(*tts_binding);
        invalid->lease = setup.agent()->lease;
        tts_binding = invalid;
    }
    {
        auto models = monitor ? std::make_shared<alojan::TurnModels>("synthetic") : nullptr;
        alojan::TurnSettings legacy_turn;
        if (calibration) {
            legacy_turn.vad_percent = 90;
            legacy_turn.open_ms = 1200;
        }
        alojan::SpeechBridge bridge(
            request.call_id(), asr_port, tts_port, monitor ? 500 : 50, "Synthetic response",
            deadline, models, alojan::QuestionContext::open, monitor, agent_port, "", legacy_turn,
            setup.recognition(), setup.agent(), tts_binding, setup.settings());
        bridge.start();
        std::array<char, 640> input{};
        input[0] = 1;
        std::array<char, 320> output{};
        unsigned turn = 0, sent = 0;
        while (!bridge.finished() && std::chrono::system_clock::now() < deadline) {
            if (bridge.recognitions_started.load() != turn) {
                turn = bridge.recognitions_started.load();
                sent = 0;
            }
            if (bridge.state() == alojan::SpeechBridge::State::recognizing &&
                sent < (monitor ? 500u : 50u)) {
                if (monitor)
                    for (unsigned i = 0; i < 320; ++i) {
                        input[2 * i] = 0;
                        input[2 * i + 1] = sent < 20 ? (calibration ? 32 : 64) : 0;
                    }
                bridge.receive(input.data());
                ++sent;
            } else if (monitor && bridge.state() == alojan::SpeechBridge::State::synthesizing) {
                input.fill(0);
                if (interrupt_calibration && turn == 1)
                    for (unsigned i = 0; i < 320; ++i)
                        input[2 * i + 1] = 32;
                bridge.receive(input.data());
            }
            bridge.render(output.data());
            if (cancel_stream && bridge.played.load())
                bridge.cancel();
            std::this_thread::sleep_for(monitor ? 5ms : 1ms);
        }
        success =
            bridge.finished() &&
            (limited || timed_out || output_rejected
                 ? bridge.state() == alojan::SpeechBridge::State::failed &&
                       bridge.error() == (limited ? alojan::SpeechBridge::Error::incomplete_turn
                                                  : alojan::SpeechBridge::Error::agent)
             : cancel_stream ? bridge.state() == alojan::SpeechBridge::State::cancelled
                             : bridge.state() == alojan::SpeechBridge::State::complete) &&
            bridge.recognitions_started.load() ==
                (cancel_stream || limited || timed_out || output_rejected ? 1u : 2u) &&
            (output_rejected || (timed_out ? bridge.played.load() == 0 : bridge.played.load() > 0));
        if (calibration)
            success = success && bridge.turn_silence_ms.load() >= setup.settings()->turn.open_ms;
        if (interrupt_calibration)
            success = success && bridge.interruptions.load() == 1;
        bridge.cancel();
    }
    setup.cancel(cancel_stream ? alojan::CallSetup::Outcome::disconnected
                 : success     ? alojan::CallSetup::Outcome::completed
                               : alojan::CallSetup::Outcome::failed);
    while (!setup.finished())
        std::this_thread::sleep_for(1ms);
    std::cout << "configured_turns=" << success << " released=" << setup.cleanup_confirmed()
              << '\n';
    return success && setup.cleanup_confirmed() ? 0 : 1;
}
