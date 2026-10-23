#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <numbers>
#include <pjlib.h>
#include <pjmedia/alaw_ulaw.h>
#include <pjmedia/resample.h>
#include <stdexcept>
#include <vector>

namespace {
void require(bool condition, const char *label) {
    if (!condition)
        throw std::runtime_error(label);
}

void codec_vectors() {
    // Independent CPython 3.12 audioop vectors, including both signs and saturation.
    constexpr std::array<pj_uint8_t, 11> codes{0x00, 0x10, 0x2a, 0x55, 0x7f, 0x80,
                                               0x90, 0xaa, 0xd5, 0xfe, 0xff};
    constexpr std::array<int, 11> alaw{-5504, -2752, -32256, -8,  -848, 5504,
                                       2752,  32256, 8,      880, 848};
    constexpr std::array<int, 11> ulaw{-32124, -15996, -5372, -716, 0, 32124,
                                       15996,  5372,   716,   8,    0};
    constexpr std::array<pj_int16_t, 11> pcm{-32768, -32124, -10000, -1000, -8,   0,
                                             8,      1000,   10000,  32124, 32767};
    constexpr std::array<pj_uint8_t, 11> encoded_a{0x2a, 0x2a, 0x36, 0x7a, 0x55, 0xd5,
                                                   0xd5, 0xfa, 0xb6, 0xaa, 0xaa};
    constexpr std::array<pj_uint8_t, 11> encoded_u{0x00, 0x00, 0x1c, 0x4e, 0x7e, 0xff,
                                                   0xfe, 0xce, 0x9c, 0x80, 0x80};
    for (unsigned i = 0; i < codes.size(); ++i) {
        require(pjmedia_alaw2linear(codes[i]) == alaw[i], "PCMA decode reference");
        require(pjmedia_ulaw2linear(codes[i]) == ulaw[i], "PCMU decode reference");
        require(pjmedia_linear2alaw(pcm[i]) == encoded_a[i], "PCMA encode reference");
        require(pjmedia_linear2ulaw(pcm[i]) == encoded_u[i], "PCMU encode reference");
    }
    for (unsigned code = 0; code < 256; ++code) {
        require(pjmedia_linear2alaw(pjmedia_alaw2linear(code)) == code, "PCMA code roundtrip");
        // Mu-law has two zero codewords; encoding canonicalizes negative zero.
        require(pjmedia_linear2ulaw(pjmedia_ulaw2linear(code)) == (code == 0x7f ? 0xff : code),
                "PCMU code roundtrip");
    }
    int max_a = 0, max_u = 0;
    for (int sample = -32768; sample <= 32767; ++sample) {
        max_a =
            std::max(max_a, std::abs(sample - pjmedia_alaw2linear(pjmedia_linear2alaw(sample))));
        max_u =
            std::max(max_u, std::abs(sample - pjmedia_ulaw2linear(pjmedia_linear2ulaw(sample))));
    }
    std::cout << "codec_vectors=44 codeword_roundtrips=512 pcm16_inputs=65536 max_alaw_error="
              << max_a << " max_ulaw_error=" << max_u << '\n';
    // PJSIP 2.16 uses 14-bit lookup indices; its A-law boundary differs from audioop.
    require(max_a <= 515 && max_u <= 644, "PCM16 full-range quantization error");
}

std::vector<pj_int16_t> convert(pj_pool_t *pool, unsigned rate_in, unsigned rate_out,
                                const std::vector<pj_int16_t> &input) {
    const unsigned in_size = rate_in / 50, out_size = rate_out / 50;
    require(input.size() % in_size == 0, "whole 20 ms input frames");
    pjmedia_resample *resampler = nullptr, *silent_call = nullptr;
    require(pjmedia_resample_create(pool, PJ_TRUE, PJ_TRUE, 1, rate_in, rate_out, in_size,
                                    &resampler) == PJ_SUCCESS,
            "large-filter resampler creation");
    require(pjmedia_resample_create(pool, PJ_TRUE, PJ_TRUE, 1, rate_in, rate_out, in_size,
                                    &silent_call) == PJ_SUCCESS,
            "isolated resampler creation");
    require(pjmedia_resample_get_input_size(resampler) == in_size, "20 ms input size");
    constexpr pj_int16_t guard = 23456;
    std::vector<pj_int16_t> block(out_size + 2, guard), silence(in_size), isolated(out_size);
    std::vector<pj_int16_t> output;
    for (std::size_t offset = 0; offset < input.size(); offset += in_size) {
        std::fill(block.begin() + 1, block.end() - 1, guard);
        pjmedia_resample_run(resampler, input.data() + offset, block.data() + 1);
        require(block.front() == guard && block.back() == guard, "output frame bounds");
        output.insert(output.end(), block.begin() + 1, block.end() - 1);
        pjmedia_resample_run(silent_call, silence.data(), isolated.data());
        require(std::all_of(isolated.begin(), isolated.end(), [](auto v) { return v == 0; }),
                "separate call has no filter history or crosstalk");
    }
    pjmedia_resample_destroy(resampler);
    pjmedia_resample_destroy(silent_call);
    return output;
}

std::vector<pj_int16_t> tone(unsigned rate, unsigned frequency) {
    std::vector<pj_int16_t> samples(rate);
    for (unsigned i = 0; i < rate; ++i)
        samples[i] =
            static_cast<pj_int16_t>(12000 * std::sin(2 * std::numbers::pi * frequency * i / rate));
    return samples;
}

double rms(const std::vector<pj_int16_t> &samples, unsigned skip) {
    double energy = 0;
    for (std::size_t i = skip; i < samples.size(); ++i)
        energy += double(samples[i]) * samples[i];
    return std::sqrt(energy / (samples.size() - skip));
}

void resampling(pj_pool_t *pool, unsigned rate_in, unsigned rate_out) {
    const auto input = tone(rate_in, 1000);
    const auto output = convert(pool, rate_in, rate_out, input);
    require(output.size() == rate_out, "one second retains duration across 50 frames");
    // Ignore 40 ms startup settling; fit unknown filter phase, not a presumed zero delay.
    const unsigned skip = rate_out / 25;
    double sine = 0, cosine = 0, energy = 0;
    for (unsigned i = skip; i < output.size(); ++i) {
        const double angle = 2 * std::numbers::pi * 1000 * i / rate_out;
        sine += output[i] * std::sin(angle);
        cosine += output[i] * std::cos(angle);
        energy += double(output[i]) * output[i];
    }
    const double count = output.size() - skip;
    const double amplitude = 2 * std::hypot(sine, cosine) / count;
    const double residual = std::sqrt(std::max(0.0, energy / count - amplitude * amplitude / 2));
    require(amplitude > 11800 && amplitude < 12200, "1 kHz passband amplitude");
    require(residual < 30, "tone frequency and continuity across frame boundaries");
    require(convert(pool, rate_in, rate_out, input) == output,
            "new call starts with fresh history");
    std::vector<pj_int16_t> impulse(rate_in / 50 * 4);
    impulse[rate_in / 50 - 1] = 12000;
    const auto tail = convert(pool, rate_in, rate_out, impulse);
    const auto next_frame = tail.begin() + rate_out / 50;
    require(std::any_of(next_frame, tail.end(), [](auto v) { return std::abs(v) > 100; }),
            "boundary impulse retains filter tail in subsequent frame");
    require(std::all_of(tail.end() - rate_out / 50, tail.end(), [](auto v) { return v == 0; }),
            "filter tail drains with silence");
    std::cout << "resample=" << rate_in << "->" << rate_out
              << " frames=50 samples=" << output.size() << " amplitude=" << amplitude
              << " residual_rms=" << residual << '\n';
}
} // namespace

int main() {
    pj_caching_pool cache;
    pj_pool_t *pool = nullptr;
    if (pj_init() != PJ_SUCCESS)
        return 1;
    pj_log_set_level(0);
    pj_caching_pool_init(&cache, nullptr, 0);
    int result = 0;
    try {
        pool = pj_pool_create(&cache.factory, "audio-test", 4096, 4096, nullptr);
        require(pool != nullptr, "test pool");
        codec_vectors();
        resampling(pool, 8000, 16000);
        resampling(pool, 16000, 8000);
        const auto rejected = convert(pool, 16000, 8000, tone(16000, 6000));
        const double alias_rms = rms(rejected, 320);
        require(alias_rms < 85, "6 kHz tone rejected before downsampling to 8 kHz");
        std::cout << "downsample_alias_rms=" << alias_rms << " audio_conversion=pass\n";
    } catch (const std::exception &error) {
        std::cerr << "audio_conversion=fail reason=" << error.what() << '\n';
        result = 1;
    }
    if (pool)
        pj_pool_release(pool);
    pj_caching_pool_destroy(&cache);
    pj_shutdown();
    return result;
}
