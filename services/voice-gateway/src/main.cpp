#include "caller_identity.hpp"
#include "speech_media.hpp"

#include <algorithm>
#include <arpa/inet.h>
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <pjsua2.hpp>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;
static volatile std::sig_atomic_t stopping = 0;
static void stop(int) { stopping = 1; }

struct Options {
    unsigned port = 15060;
    unsigned rtp_port = 14000;
    unsigned rtp_port_range = 20;
    std::string bind_address = "127.0.0.1", public_address = "127.0.0.1";
    std::vector<std::string> allowed_sip_ips;
    unsigned answer_delay_ms = 100;
    unsigned max_call_seconds = 30;
    unsigned rtp_timeout_ms = 10000;
    unsigned test_max_calls = 1;
    unsigned speech_test_ms = 0, asr_port = 15071, tts_port = 15072, agent_port = 0;
    std::string turn_model_dir;
    bool barge_in = false, custom_turn_settings = false;
    alojan::TurnSettings turn_settings;
    alojan::QuestionContext turn_context = alojan::QuestionContext::open;
    std::shared_ptr<alojan::TurnModels> turn_models;
    std::string wav;
    std::string prompt_dir = "assets/prompts/tr-v3-ema";
    bool custom_wav = false, custom_prompt_dir = false;
    pj::StringVector playback_files;
    alojan::IdentityPolicy identity;
};

unsigned number(const std::string &text, unsigned low, unsigned high) {
    std::size_t end = 0;
    auto value = std::stoul(text, &end);
    if (end != text.size() || value < low || value > high)
        throw std::invalid_argument("numeric option out of range");
    return static_cast<unsigned>(value);
}

std::string unicast_ipv4(const std::string &value) {
    in_addr address{};
    if (inet_pton(AF_INET, value.c_str(), &address) != 1 || (ntohl(address.s_addr) >> 24) == 0 ||
        (ntohl(address.s_addr) >> 24) >= 224)
        throw std::invalid_argument("network address must be a unicast IPv4 literal");
    return value;
}

Options options(int argc, char **argv) {
    Options result;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 >= argc)
            throw std::invalid_argument("options require values");
        const std::string key(argv[i]), value(argv[i + 1]);
        if (key == "--port")
            result.port = number(value, 1024, 65535);
        else if (key == "--rtp-port")
            result.rtp_port = number(value, 1024, 65500);
        else if (key == "--rtp-port-range")
            result.rtp_port_range = number(value, 0, 10000);
        else if (key == "--bind-address")
            result.bind_address = unicast_ipv4(value);
        else if (key == "--public-address")
            result.public_address = unicast_ipv4(value);
        else if (key == "--allow-sip-ip") {
            if (result.allowed_sip_ips.size() == 16)
                throw std::invalid_argument("maximum 16 allowed SIP sources");
            result.allowed_sip_ips.push_back(unicast_ipv4(value));
        } else if (key == "--answer-delay-ms")
            result.answer_delay_ms = number(value, 0, 5000);
        else if (key == "--max-call-seconds")
            result.max_call_seconds = number(value, 1, 300);
        else if (key == "--rtp-timeout-ms")
            result.rtp_timeout_ms = number(value, 100, 300000);
        else if (key == "--test-max-calls")
            result.test_max_calls = number(value, 1, 2);
        else if (key == "--speech-test-ms")
            result.speech_test_ms = number(value, 1000, 10000);
        else if (key == "--barge-in")
            result.barge_in = number(value, 0, 1) != 0;
        else if (key == "--turn-model-dir")
            result.turn_model_dir = value;
        else if (key == "--turn-partial-hint") {
            result.custom_turn_settings = true;
            result.turn_settings.partial_hint = number(value, 0, 1) != 0;
        } else if (key == "--turn-vad-percent" || key == "--turn-candidate-ms" ||
                   key == "--turn-yes-no-ms" || key == "--turn-open-ms" ||
                   key == "--turn-uncertain-ms" || key == "--turn-incomplete-ms") {
            result.custom_turn_settings = true;
            auto &settings = result.turn_settings;
            const auto parsed = number(value, 1, 5000);
            if (key == "--turn-vad-percent")
                settings.vad_percent = parsed;
            else if (key == "--turn-candidate-ms")
                settings.candidate_ms = parsed;
            else if (key == "--turn-yes-no-ms")
                settings.yes_no_ms = parsed;
            else if (key == "--turn-open-ms")
                settings.open_ms = parsed;
            else if (key == "--turn-uncertain-ms")
                settings.uncertain_ms = parsed;
            else
                settings.incomplete_ms = parsed;
        } else if (key == "--turn-context") {
            if (value != "open" && value != "yes-no")
                throw std::invalid_argument("turn context must be open or yes-no");
            result.turn_context =
                value == "open" ? alojan::QuestionContext::open : alojan::QuestionContext::yes_no;
        } else if (key == "--asr-port")
            result.asr_port = number(value, 1024, 65535);
        else if (key == "--agent-port")
            result.agent_port = number(value, 1024, 65535);
        else if (key == "--tts-port")
            result.tts_port = number(value, 1024, 65535);
        else if (key == "--trusted-identity-ip")
            result.identity.add_trusted_ip(value);
        else if (key == "--identity-precedence") {
            if (value != "pai-first" && value != "from-first")
                throw std::invalid_argument("identity precedence must be pai-first or from-first");
            result.identity.from_first = value == "from-first";
        } else if (key == "--caller-national-prefix") {
            if (value != "0" && value != "none")
                throw std::invalid_argument("caller national prefix must be 0 or none");
            result.identity.turkish_national = value == "0";
        } else if (key == "--wav") {
            result.wav = value;
            result.custom_wav = true;
        } else if (key == "--prompt-dir") {
            result.prompt_dir = value;
            result.custom_prompt_dir = true;
        } else
            throw std::invalid_argument("unknown option");
    }
    result.turn_settings.validate();
    if (result.custom_turn_settings && result.turn_model_dir.empty())
        throw std::invalid_argument("turn thresholds require turn models");
    if (result.speech_test_ms && (result.speech_test_ms % 20 || result.custom_wav))
        throw std::invalid_argument("speech test requires 20 ms alignment and standard prompts");
    if (!result.turn_model_dir.empty() && (result.speech_test_ms || result.custom_wav))
        throw std::invalid_argument(
            "adaptive turn test requires standard prompts and no fixed capture");
    if (result.agent_port && !result.speech_test_ms && !result.barge_in)
        throw std::invalid_argument("agent requires interruption or explicit fixed-capture test");
    if (result.barge_in && result.turn_model_dir.empty())
        throw std::invalid_argument("barge-in requires turn models");
    if (result.turn_context != alojan::QuestionContext::open && result.turn_model_dir.empty())
        throw std::invalid_argument("turn context requires turn models");
    if (result.rtp_port % 2 != 0 || result.rtp_port_range % 2 != 0 ||
        result.rtp_port + result.rtp_port_range + 1 > 65535)
        throw std::invalid_argument("RTP base/range must be even and leave room for RTCP");
    if ((!result.bind_address.starts_with("127.") || !result.public_address.starts_with("127.")) &&
        (result.allowed_sip_ips.empty() || result.public_address.starts_with("127.")))
        throw std::invalid_argument(
            "carrier networking requires public address and allowed SIP sources");
    if (result.custom_wav && result.custom_prompt_dir)
        throw std::invalid_argument("choose --wav or --prompt-dir");
    if (result.custom_wav)
        result.playback_files = {result.wav};
    else
        result.playback_files = {
            (std::filesystem::path(result.prompt_dir) / "greeting.wav").string(),
            (std::filesystem::path(result.prompt_dir) / "unavailable.wav").string()};
    for (const auto &file : result.playback_files) {
        std::error_code error;
        if (!std::filesystem::is_regular_file(file, error) ||
            std::filesystem::file_size(file, error) > 1024 * 1024 || error)
            throw std::invalid_argument("playback requires readable WAV files under 1 MiB");
    }
    return result;
}

bool complete_wave(const std::string &file) {
    std::error_code error;
    const auto bytes = std::filesystem::file_size(file, error);
    if (error || bytes < 12 || bytes > 1024 * 1024)
        return false;
    std::ifstream input(file, std::ios::binary);
    std::array<unsigned char, 12> header{};
    if (!input.read(reinterpret_cast<char *>(header.data()), header.size()))
        return false;
    const auto little32 = [](const unsigned char *p) {
        return std::uint32_t(p[0]) | std::uint32_t(p[1]) << 8 | std::uint32_t(p[2]) << 16 |
               std::uint32_t(p[3]) << 24;
    };
    if (std::memcmp(header.data(), "RIFF", 4) || std::memcmp(header.data() + 8, "WAVE", 4) ||
        std::uint64_t(little32(header.data() + 4)) + 8 != bytes)
        return false;
    std::uint64_t offset = 12;
    while (offset < bytes) {
        if (bytes - offset < 8)
            return false;
        input.seekg(static_cast<std::streamoff>(offset));
        if (!input.read(reinterpret_cast<char *>(header.data()), 8))
            return false;
        const auto size = little32(header.data() + 4);
        offset += 8 + std::uint64_t(size) + (size % 2);
        if (offset > bytes)
            return false;
    }
    return true;
}

void validate_playback(const Options &config) {
    unsigned total_samples = 0;
    for (const auto &file : config.playback_files) {
        // PJSIP tolerates truncated WAV payloads; announcements must be complete.
        if (!complete_wave(file))
            throw std::invalid_argument("WAV container is incomplete or malformed");
        pj::AudioMediaPlayer probe;
        probe.createPlayer(file, PJMEDIA_FILE_NO_LOOP);
        const auto info = probe.getInfo();
        const auto format = probe.getPortInfo().format;
        if (info.formatId != PJMEDIA_FORMAT_PCM || info.payloadBitsPerSample != 16 ||
            format.clockRate != 8000 || format.channelCount != 1 || info.sizeSamples < 160 ||
            info.sizeSamples > 8000 * 30 || info.sizeBytes != info.sizeSamples * 2)
            throw std::invalid_argument(
                "playback requires mono PCM16 8 kHz WAV, 20 ms to 30 seconds");
        total_samples += info.sizeSamples;
    }
    if (!config.custom_wav &&
        total_samples / 8 + config.answer_delay_ms + 1000 > config.max_call_seconds * 1000)
        throw std::invalid_argument("call duration must allow complete greeting and fallback");
}

class Playback : public pj::AudioMediaPlayer {
  public:
    std::atomic<bool> eof{false};
    void onEof2() override { eof.store(true, std::memory_order_relaxed); }
};

class Session : public pj::Call {
  public:
    bool disconnected = false, answered = false, media_started = false, ending = false;
    const unsigned serial;
    alojan::CallerIdentity identity;
    Clock::time_point created = Clock::now(), ringing_at{}, eof_at{}, last_rtp{}, next_rtp_check{};
    unsigned media_index = 0, received_packets = 0;
    unsigned lost_packets = 0, reordered_packets = 0, duplicate_packets = 0;
    int jitter_max_us = 0;
    std::array<Playback, 2> playback;
    unsigned playback_index = 0, playback_count = 0;
    // Ports die before their bridge; detached PJMEDIA callbacks cannot access freed work.
    std::unique_ptr<alojan::SpeechBridge> speech;
    SpeechInput input;
    SpeechOutput output;
    bool speech_started = false, speech_fallback = false, speech_reported = false;
    std::string speech_id;
    unsigned reported_reminders = 0, reported_clarifications = 0;
    unsigned reported_responses = 0, reported_interruptions = 0, reported_recognitions = 0;

    Session(pj::Account &account, int id, unsigned serial_id)
        : pj::Call(account, id), serial(serial_id) {}
    void onCallState(pj::OnCallStateParam &) override {
        auto info = getInfo();
        // Local serials avoid logging telephone numbers or raw SIP headers.
        std::cout
            << "event=call_state call=" << serial << " state=" << info.stateText
            << " code=" << info.lastStatusCode << " elapsed_ms="
            << std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - created).count()
            << std::endl;
        if (info.state == PJSIP_INV_STATE_DISCONNECTED) {
            disconnected = true;
            if (speech)
                speech->cancel();
        }
    }
    void onCallMediaState(pj::OnCallMediaStateParam &) override {
        // Wire ports from the main loop, outside signaling callbacks.
    }
    void start_media(const Options &config) {
        if (media_started || !answered || disconnected)
            return;
        auto info = getInfo();
        if (info.state != PJSIP_INV_STATE_CONFIRMED)
            return;
        for (const auto &media : info.media) {
            if (media.type != PJMEDIA_TYPE_AUDIO || media.status != PJSUA_CALL_MEDIA_ACTIVE)
                continue;
            pj::MediaFormatAudio format;
            format.init(PJMEDIA_FORMAT_PCM, InputMeter::rate_hz, 1, 20000, 16);
            playback_count = static_cast<unsigned>(config.playback_files.size());
            for (unsigned i = 0; i < playback_count; ++i)
                playback[i].createPlayer(config.playback_files[i], PJMEDIA_FILE_NO_LOOP);
            auto audio = getAudioMedia(static_cast<int>(media.index));
            if (config.speech_test_ms || config.turn_models) {
                const auto remaining =
                    std::chrono::seconds(config.max_call_seconds) - (Clock::now() - created);
                speech = std::make_unique<alojan::SpeechBridge>(
                    speech_id, config.asr_port, config.tts_port,
                    config.turn_models ? 1000 : config.speech_test_ms / 20,
                    "Şu anda mesaj alamıyorum. Lütfen daha sonra tekrar arayın. Hoşça kalın.",
                    std::chrono::system_clock::now() +
                        std::chrono::duration_cast<std::chrono::system_clock::duration>(remaining),
                    config.turn_models, config.turn_context, config.barge_in, config.agent_port,
                    identity.trusted_source ? identity.caller.e164 : "", config.turn_settings);
                input.bridge = speech.get();
                output.create(*speech);
            }
            input.createPort("input-meter", format);
            audio.startTransmit(input);
            playback[0].startTransmit(audio);
            media_started = true;
            media_index = media.index;
            last_rtp = Clock::now();
            std::cout << "event=media_started call=" << serial
                      << " playback=" << (config.custom_wav ? "test_wav" : "ai_greeting_fallback")
                      << " invite_to_media_ms="
                      << std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() -
                                                                               created)
                             .count()
                      << " codec=" << getStreamInfo(media.index).codecName << std::endl;
            return;
        }
    }

    bool playback_finished() {
        if (speech && speech_started && !speech_fallback) {
            if (speech->recognitions_started.load() != reported_recognitions) {
                reported_recognitions = speech->recognitions_started.load();
                std::cout << "event=speech_listening call=" << serial
                          << " turn=" << reported_recognitions << std::endl;
            }
            if (speech->responses_started.load() != reported_responses) {
                reported_responses = speech->responses_started.load();
                std::cout << "event=speech_speaking call=" << serial << " generation=turn-"
                          << reported_responses << std::endl;
            }
            if (speech->silence_reminders.load() != reported_reminders) {
                reported_reminders = speech->silence_reminders.load();
                std::cout << "event=silence_reminder call=" << serial << std::endl;
            }
            if (speech->clarification_requests.load() != reported_clarifications) {
                reported_clarifications = speech->clarification_requests.load();
                std::cout << "event=clarification_requested call=" << serial << std::endl;
            }
            if (speech->interruptions.load() != reported_interruptions) {
                reported_interruptions = speech->interruptions.load();
                std::cout << "event=speech_interrupted call=" << serial
                          << " cancelled_generation=turn-" << speech->interrupted_turn.load()
                          << " decision_ms=" << speech->interrupt_ms.load()
                          << " waiting_music_ms=" << speech->waiting_music_frames.load() * 20
                          << " last_sent_ms=" << speech->last_sent_ms.load() << std::endl;
            }
            if (speech->state() == alojan::SpeechBridge::State::failed) {
                speech_fallback = true;
                auto audio = getAudioMedia(static_cast<int>(media_index));
                output.stopTransmit(audio);
                playback_index = playback_count - 1;
                playback[playback_index].startTransmit(audio);
                std::cout << "event=speech_fallback call=" << serial
                          << " error=" << static_cast<int>(speech->error()) << std::endl;
                return false;
            }
            if (speech->playout_finished()) {
                if (!speech_reported) {
                    speech_reported = true;
                    if (speech->finished())
                        for (const auto &entry : speech->sent_history())
                            std::cout
                                << "event=sent_speech call=" << serial
                                << " generation=" << entry.generation
                                << " sent_audio_ms=" << entry.sent_audio_ms
                                << " aligned_text_bytes=" << entry.text.size()
                                << " interrupted=" << entry.interrupted
                                << " kind=" << (entry.waiting ? "waiting" : "response")
                                << " endpoint_to_audio_ms=" << entry.endpoint_to_audio_ms
                                << " asr_finalize_ms=" << entry.asr_finalize_ms
                                << " phrase_ready_to_audio_ms=" << entry.phrase_ready_to_audio_ms
                                << " tts_first_chunk_ms=" << entry.tts_first_chunk_ms << std::endl;
                    std::cout << "event=speech_test_complete call=" << serial
                              << " asr_frames=" << speech->written.load()
                              << " asr_partials=" << speech->partials.load()
                              << " final_text_bytes=" << speech->final_bytes.load()
                              << " tts_frames=" << speech->generated.load()
                              << " output_port_ms=" << speech->played.load() * 20
                              << " waiting_music_ms=" << speech->waiting_music_frames.load() * 20
                              << " half_close_to_pcm_ms="
                              << speech->first_pcm_ms.load() - speech->half_close_ms.load()
                              << " half_close_to_playout_ms="
                              << speech->first_playout_ms.load() - speech->half_close_ms.load()
                              << " interruptions=" << speech->interruptions.load()
                              << " echo_frames=" << speech->echo_frames.load()
                              << " backchannels=" << speech->backchannels.load()
                              << " turn_silence_ms=" << speech->turn_silence_ms.load()
                              << " turn_probability_milli=" << speech->turn_probability_milli.load()
                              << " turn_inference_ms=" << speech->turn_inference_ms.load()
                              << std::endl;
                }
                return true;
            }
            return false;
        }
        if (!media_started || !playback[playback_index].eof.load(std::memory_order_relaxed))
            return false;
        if (playback_index + 1 == playback_count)
            return true;
        // Single-file EOF follows PCM consumption; PJSIP 2.16 playlist EOF does not.
        auto audio = getAudioMedia(static_cast<int>(media_index));
        playback[playback_index].stopTransmit(audio);
        if (speech && !speech_started) {
            speech_started = true;
            output.startTransmit(audio);
            speech->start();
            std::cout << "event=speech_test_capture call=" << serial << std::endl;
        } else
            playback[++playback_index].startTransmit(audio);
        return false;
    }
    bool rtp_expired(Clock::time_point now, unsigned timeout_ms) {
        if (!media_started || now < next_rtp_check)
            return false;
        next_rtp_check = now + std::chrono::milliseconds(100);
        auto info = getInfo();
        if (info.state != PJSIP_INV_STATE_CONFIRMED || media_index >= info.media.size() ||
            info.media[media_index].status != PJSUA_CALL_MEDIA_ACTIVE) {
            last_rtp = now;
            return false;
        }
        // PCM callbacks include jitter-buffer silence; only received packets prove transport
        // activity.
        // PJSUA2 2.16 maps reorder to loss; use the C stats until that upstream mapping is fixed.
        pjsua_stream_stat stream_stats{};
        if (pjsua_call_get_stream_stat(getId(), media_index, &stream_stats) != PJ_SUCCESS)
            throw std::runtime_error("RTP statistics unavailable");
        const auto &stats = stream_stats.rtcp.rx;
        lost_packets = stats.loss;
        reordered_packets = stats.reorder;
        duplicate_packets = stats.dup;
        jitter_max_us = stats.jitter.max;
        const auto packets = stats.pkt;
        if (packets != received_packets) {
            received_packets = packets;
            last_rtp = now;
        }
        return now - last_rtp >= std::chrono::milliseconds(timeout_ms);
    }
    void end(const char *reason) {
        if (disconnected || ending)
            return;
        ending = true;
        if (speech)
            speech->cancel();
        std::cout << "event=call_ending call=" << serial << " reason=" << reason << std::endl;
        pj::CallOpParam param;
        param.statusCode = PJSIP_SC_DECLINE;
        hangup(param);
    }
};

class LocalAccount : public pj::Account {
  public:
    std::vector<std::unique_ptr<Session>> calls;
    unsigned next_serial = 1;
    const unsigned admission_limit;
    const std::string speech_run = [] {
        std::random_device random;
        return std::to_string(random()) + "-" + std::to_string(random());
    }();
    const alojan::IdentityPolicy identity_policy;
    const std::vector<std::string> allowed_sip_ips;
    explicit LocalAccount(const Options &config)
        : admission_limit(config.test_max_calls), identity_policy(config.identity),
          allowed_sip_ips(config.allowed_sip_ips) {}
    void onIncomingCall(pj::OnIncomingCallParam &param) override {
        unsigned active = 0;
        for (const auto &call : calls)
            active += !call->disconnected;
        const bool busy = stopping != 0 || active >= admission_limit;
        auto call = std::make_unique<Session>(*this, param.callId, next_serial++);
        char source[PJ_INET6_ADDRSTRLEN]{};
        if (param.rdata.pjRxData)
            pj_sockaddr_print(
                &static_cast<pjsip_rx_data *>(param.rdata.pjRxData)->pkt_info.src_addr, source,
                sizeof(source), 0);
        const bool denied = !allowed_sip_ips.empty() &&
                            std::find(allowed_sip_ips.begin(), allowed_sip_ips.end(), source) ==
                                allowed_sip_ips.end();
        if (!busy && !denied && param.rdata.pjRxData)
            call->identity = alojan::read_identity(
                *static_cast<pjsip_rx_data *>(param.rdata.pjRxData), identity_policy);
        if (!busy && !denied)
            std::cout << "event=caller_identity call=" << call->serial << " "
                      << call->identity.log_fields() << std::endl;
        call->speech_id = "speech-" + speech_run + "-" + std::to_string(call->serial);
        auto *session = call.get();
        calls.push_back(std::move(call));
        pj::CallOpParam answer;
        answer.statusCode = denied ? PJSIP_SC_FORBIDDEN
                            : busy ? PJSIP_SC_BUSY_HERE
                                   : PJSIP_SC_RINGING;
        if (denied)
            std::cout << "event=call_rejected call=" << session->serial
                      << " reason=source_not_allowed" << std::endl;
        session->answer(answer);
        session->ringing_at = Clock::now();
        if (busy || denied)
            session->ending = true;
    }
    void tick(const Options &config) {
        for (auto &call : calls) {
            if (call->disconnected || call->ending)
                continue;
            auto now = Clock::now();
            if (stopping || now - call->created > std::chrono::seconds(config.max_call_seconds)) {
                call->end(stopping ? "shutdown" : "max_duration");
                continue;
            }
            if (!call->answered &&
                now - call->ringing_at >= std::chrono::milliseconds(config.answer_delay_ms)) {
                pj::CallOpParam answer;
                answer.statusCode = PJSIP_SC_OK;
                answer.opt.audioCount = 1;
                answer.opt.videoCount = 0;
                call->answered = true;
                call->answer(answer);
            }
            bool playback_done = false;
            try {
                call->start_media(config);
                playback_done = call->playback_finished();
            } catch (const pj::Error &error) {
                std::cout << "event=media_error call=" << call->serial << " code=" << error.status
                          << std::endl;
                call->end("playback_error");
                continue;
            } catch (const std::exception &) {
                call->end("speech_setup_error");
                continue;
            }
            if (call->rtp_expired(now, config.rtp_timeout_ms)) {
                call->end("rtp_inactivity");
                continue;
            }
            if (playback_done) {
                if (call->eof_at == Clock::time_point{})
                    call->eof_at = now;
                // Drain queued media, then leave three seconds after the agent closing.
                const auto closing_delay = config.agent_port && !call->speech_fallback ? 3150 : 150;
                if (now - call->eof_at > std::chrono::milliseconds(closing_delay))
                    call->end(config.custom_wav                       ? "playback_complete"
                              : call->speech && call->speech_reported ? "speech_test_complete"
                                                                      : "dependencies_unavailable");
            }
        }
        std::erase_if(calls, [](const auto &call) {
            if (!call->disconnected || (call->speech && !call->speech->finished()))
                return false;
            std::cout << "event=call_closed call=" << call->serial
                      << " input_frames=" << call->input.frames.load()
                      << " input_rate_hz=" << InputMeter::rate_hz
                      << " input_samples=" << call->input.samples.load()
                      << " input_bad_frames=" << call->input.bad_frames.load()
                      << " nonzero_samples=" << call->input.nonzero_samples.load()
                      << " rx_packets=" << call->received_packets
                      << " rx_loss=" << call->lost_packets
                      << " rx_reorder=" << call->reordered_packets
                      << " rx_duplicates=" << call->duplicate_packets
                      << " rx_jitter_max_us=" << call->jitter_max_us << " speech_input_frames="
                      << (call->speech ? call->speech->written.load() : 0)
                      << " speech_output_port_ms="
                      << (call->speech ? call->speech->played.load() * 20 : 0) << std::endl;
            return true;
        });
    }
};

int main(int argc, char **argv) {
    try {
        auto config = options(argc, argv);
        if (!config.turn_model_dir.empty())
            config.turn_models = std::make_shared<alojan::TurnModels>(config.turn_model_dir);
        std::signal(SIGINT, stop);
        std::signal(SIGTERM, stop);
        pj_log_set_level(0);
        pj::Endpoint endpoint;
        endpoint.libCreate();
        pj::EpConfig ep;
        ep.uaConfig.threadCnt = 0;
        ep.uaConfig.mainThreadOnly = true;
        ep.uaConfig.maxCalls = 4; // Extra slots can receive and reject overload with 486.
        ep.logConfig.level = 0;
        ep.logConfig.consoleLevel = 0;
        ep.logConfig.msgLogging = false;
        ep.medConfig.clockRate = 8000;
        ep.medConfig.sndClockRate = 8000;
        ep.medConfig.audioFramePtime = 20;
        ep.medConfig.quality = 8; // PJMEDIA large-filter resampling for the 16 kHz receive port.
        ep.medConfig.noVad = true;
        endpoint.libInit(ep);
        validate_playback(config);
        pj::TransportConfig transport;
        transport.port = config.port;
        transport.boundAddress = config.bind_address;
        transport.publicAddress = config.public_address;
        endpoint.transportCreate(PJSIP_TRANSPORT_UDP, transport);
        endpoint.libStart();
        endpoint.audDevManager().setNullDev();
        for (const auto &codec : endpoint.codecEnum2()) {
            const auto priority = codec.codecId.starts_with("PCMA/")   ? 255
                                  : codec.codecId.starts_with("PCMU/") ? 254
                                                                       : 0;
            endpoint.codecSetPriority(codec.codecId, static_cast<pj_uint8_t>(priority));
        }
        {
            LocalAccount account(config);
            pj::AccountConfig ac;
            ac.idUri = "sip:alojan@" + config.public_address;
            ac.regConfig.registerOnAdd = false;
            ac.mediaConfig.transportConfig.port = config.rtp_port;
            ac.mediaConfig.transportConfig.portRange = config.rtp_port_range;
            ac.mediaConfig.transportConfig.boundAddress = config.bind_address;
            ac.mediaConfig.transportConfig.publicAddress = config.public_address;
            account.create(ac);
            std::cout << "event=ready mode="
                      << (config.turn_models      ? "adaptive_turn_test"
                          : config.speech_test_ms ? "speech_test"
                          : config.custom_wav     ? "local_wav"
                                                  : "dependency_fallback")
                      << " voice_pipeline_ready=0 sip_port=" << config.port
                      << " admission_limit=" << config.test_max_calls << std::endl;
            while (!stopping) {
                endpoint.libHandleEvents(10);
                account.tick(config);
            }
            const auto deadline = Clock::now() + std::chrono::seconds(2);
            while (!account.calls.empty() && Clock::now() < deadline) {
                account.tick(config);
                endpoint.libHandleEvents(10);
            }
            account.shutdown();
            account.calls.clear();
        }
        endpoint.libDestroy();
        return 0;
    } catch (const pj::Error &error) {
        std::cerr << "gateway_error status=" << error.status << '\n';
    } catch (const std::exception &error) {
        std::cerr << "gateway_error " << error.what() << '\n';
    }
    return 1;
}
