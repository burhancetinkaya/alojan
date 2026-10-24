// Offline native denoiser probe. Input/output are mono float32 LE at 16 kHz.
#include <api/audio/audio_processing.h>
#include <rnnoise.h>
#include <speex/speex_preprocess.h>
#include <speex/speex_resampler.h>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <ctime>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}

int main(int argc, char **argv) try {
    static_assert(std::endian::native == std::endian::little && sizeof(float) == 4);
    require(argc == 4, "usage: probe PROFILE INPUT.f32 OUTPUT.f32");
    const std::string profile = argv[1];
    require(profile == "bypass" || profile == "webrtc-low" || profile == "webrtc-moderate" ||
                profile == "rnnoise" || profile == "speex",
            "unknown profile");
    require(std::string(argv[2]) != argv[3], "input/output must differ");
    std::ifstream input(argv[2], std::ios::binary | std::ios::ate);
    const auto bytes = input.tellg();
    require(input && bytes > 0 && bytes <= 16000 * 30 * 4 && bytes % 4 == 0,
            "expected 0-30 seconds of float32 audio");
    std::vector<float> samples(static_cast<std::size_t>(bytes) / 4);
    input.seekg(0);
    require(bool(input.read(reinterpret_cast<char *>(samples.data()), bytes)), "input read failed");
    require(std::all_of(samples.begin(), samples.end(),
                        [](float x) { return std::isfinite(x) && std::abs(x) <= 1; }),
            "samples must be finite and normalized");
    const auto original_size = samples.size();
    samples.resize((original_size + 159) / 160 * 160, 0);
    std::vector<float> output(samples.size());

    rtc::scoped_refptr<webrtc::AudioProcessing> apm;
    std::unique_ptr<DenoiseState, decltype(&rnnoise_destroy)> rn(nullptr, rnnoise_destroy);
    std::unique_ptr<SpeexPreprocessState, decltype(&speex_preprocess_state_destroy)> sp(
        nullptr, speex_preprocess_state_destroy);
    using Resampler = std::unique_ptr<SpeexResamplerState, decltype(&speex_resampler_destroy)>;
    Resampler up(nullptr, speex_resampler_destroy), down(nullptr, speex_resampler_destroy);
    double resampler_delay_ms = 0;
    if (profile.starts_with("webrtc")) {
        webrtc::AudioProcessing::Config config;
        config.noise_suppression.enabled = true;
        config.noise_suppression.level =
            profile == "webrtc-low" ? webrtc::AudioProcessing::Config::NoiseSuppression::kLow
                                    : webrtc::AudioProcessing::Config::NoiseSuppression::kModerate;
        // Leave AEC, AGC and high-pass disabled to isolate noise suppression.
        apm = webrtc::AudioProcessingBuilder().Create();
        require(bool(apm), "WebRTC allocation failed");
        apm->ApplyConfig(config);
        require(apm->Initialize() == 0, "WebRTC initialization failed");
    } else if (profile == "rnnoise") {
        rn.reset(rnnoise_create(nullptr));
        require(rn && rnnoise_get_frame_size() == 480, "RNNoise initialization failed");
        int error = 0;
        up.reset(speex_resampler_init(1, 16000, 48000, 5, &error));
        require(up && error == 0, "upsampler initialization failed");
        down.reset(speex_resampler_init(1, 48000, 16000, 5, &error));
        require(down && error == 0, "downsampler initialization failed");
        resampler_delay_ms = speex_resampler_get_input_latency(up.get()) / 16.0 +
                             speex_resampler_get_output_latency(down.get()) / 16.0;
    } else if (profile == "speex") {
        sp.reset(speex_preprocess_state_init(160, 16000));
        require(bool(sp), "Speex initialization failed");
        int enabled = 1, disabled = 0, attenuation = -15;
        require(speex_preprocess_ctl(sp.get(), SPEEX_PREPROCESS_SET_DENOISE, &enabled) == 0 &&
                    speex_preprocess_ctl(sp.get(), SPEEX_PREPROCESS_SET_AGC, &disabled) == 0 &&
                    speex_preprocess_ctl(sp.get(), SPEEX_PREPROCESS_SET_VAD, &disabled) == 0 &&
                    speex_preprocess_ctl(sp.get(), SPEEX_PREPROCESS_SET_NOISE_SUPPRESS,
                                         &attenuation) == 0,
                "Speex configuration failed");
    }

    std::vector<double> timings;
    timings.reserve(samples.size() / 160);
    const auto cpu_start = std::clock();
    for (std::size_t offset = 0; offset < samples.size(); offset += 160) {
        const auto begin = std::chrono::steady_clock::now();
        const float *src = samples.data() + offset;
        float *dst = output.data() + offset;
        if (apm) {
            const webrtc::StreamConfig format(16000, 1);
            require(apm->ProcessStream(&src, format, format, &dst) == 0,
                    "WebRTC processing failed");
        } else if (rn) {
            std::array<float, 480> wide{};
            spx_uint32_t in = 160, out = 480;
            require(speex_resampler_process_float(up.get(), 0, src, &in, wide.data(), &out) == 0 &&
                        in == 160 && out == 480,
                    "upsampler frame mismatch");
            for (auto &value : wide)
                value *= 32768;
            rnnoise_process_frame(rn.get(), wide.data(), wide.data());
            for (auto &value : wide)
                value /= 32768;
            in = 480;
            out = 160;
            require(speex_resampler_process_float(down.get(), 0, wide.data(), &in, dst, &out) ==
                            0 &&
                        in == 480 && out == 160,
                    "downsampler frame mismatch");
        } else if (sp) {
            std::array<spx_int16_t, 160> pcm{};
            for (unsigned i = 0; i < 160; ++i)
                pcm[i] = static_cast<spx_int16_t>(std::clamp(src[i] * 32768, -32768.0f, 32767.0f));
            speex_preprocess_run(sp.get(), pcm.data());
            for (unsigned i = 0; i < 160; ++i)
                dst[i] = pcm[i] / 32768.0f;
        } else {
            std::copy_n(src, 160, dst);
        }
        timings.push_back(
            std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - begin)
                .count());
    }
    const double cpu_ms = 1000.0 * (std::clock() - cpu_start) / CLOCKS_PER_SEC;
    require(std::all_of(output.begin(), output.end(), [](float x) { return std::isfinite(x); }),
            "nonfinite output");
    double sum_us = 0;
    std::size_t clipped = 0;
    for (auto &value : output) {
        clipped += std::abs(value) > 1;
        value = std::clamp(value, -1.0f, 1.0f);
    }
    for (auto value : timings)
        sum_us += value;
    std::sort(timings.begin(), timings.end());
    std::ofstream destination(argv[3], std::ios::binary | std::ios::trunc);
    destination.write(reinterpret_cast<const char *>(output.data()), original_size * 4);
    destination.close();
    require(bool(destination), "output write failed");
    std::cout << "{\"frames\":" << timings.size() << ",\"mean_us\":" << sum_us / timings.size()
              << ",\"p95_us\":" << timings[(timings.size() - 1) * 95 / 100]
              << ",\"max_us\":" << timings.back() << ",\"cpu_ms\":" << cpu_ms
              << ",\"resampler_delay_ms\":" << resampler_delay_ms
              << ",\"clipped_samples\":" << clipped << "}\n";
    return 0;
} catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
}
