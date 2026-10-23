#include "turn_detector.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

#ifdef ALOJAN_TURN_MODELS
#include <kiss_fftr.h>
#include <onnxruntime_cxx_api.h>

namespace alojan {
struct TurnModels::Impl {
    Ort::Env env{ORT_LOGGING_LEVEL_ERROR, "alojan-turn"};
    Ort::SessionOptions options;
    Ort::Session vad{nullptr}, turn{nullptr};
    Ort::MemoryInfo memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    explicit Impl(const std::string &directory) {
        options.SetIntraOpNumThreads(1);
        options.SetInterOpNumThreads(1);
        options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        vad = Ort::Session(env, (directory + "/silero-v6.2.onnx").c_str(), options);
        turn = Ort::Session(env, (directory + "/smart-turn-v3.2-cpu.onnx").c_str(), options);
    }
};

TurnModels::TurnModels(const std::string &directory) : impl_(std::make_unique<Impl>(directory)) {
    std::array<float, 576> silence{};
    std::array<float, 256> state{};
    vad(silence, state);
    complete(silence);
}
TurnModels::~TurnModels() = default;

namespace {
float probability(const Ort::Value &value) {
    if (!value.IsTensor() || value.GetTensorTypeAndShapeInfo().GetElementCount() != 1 ||
        value.GetTensorTypeAndShapeInfo().GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT)
        throw std::runtime_error("invalid detector output shape");
    const float result = value.GetTensorData<float>()[0];
    if (!std::isfinite(result) || result < 0 || result > 1)
        throw std::runtime_error("invalid detector probability");
    return result;
}
} // namespace

float TurnModels::vad(std::span<const float, 576> audio, std::array<float, 256> &state) {
    constexpr std::array<int64_t, 2> audio_shape{1, 576};
    constexpr std::array<int64_t, 3> state_shape{2, 1, 128};
    int64_t rate = 16000;
    std::array<Ort::Value, 3> inputs{
        Ort::Value::CreateTensor<float>(impl_->memory, const_cast<float *>(audio.data()),
                                        audio.size(), audio_shape.data(), 2),
        Ort::Value::CreateTensor<float>(impl_->memory, state.data(), state.size(),
                                        state_shape.data(), 3),
        Ort::Value::CreateTensor<int64_t>(impl_->memory, &rate, 1, nullptr, 0)};
    const char *names[] = {"input", "state", "sr"};
    const char *outputs[] = {"output", "stateN"};
    auto result = impl_->vad.Run(Ort::RunOptions{nullptr}, names, inputs.data(), 3, outputs, 2);
    const float value = probability(result[0]);
    const auto info = result[1].GetTensorTypeAndShapeInfo();
    if (info.GetShape() != std::vector<int64_t>{2, 1, 128} ||
        info.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT)
        throw std::runtime_error("invalid VAD state shape");
    const auto *next = result[1].GetTensorData<float>();
    if (!std::all_of(next, next + 256, [](float x) { return std::isfinite(x); }))
        throw std::runtime_error("non-finite VAD state");
    std::copy_n(next, 256, state.begin());
    return value;
}

std::vector<float> TurnModels::features(std::span<const float> audio) {
    constexpr unsigned count = 128000, bins = 201, bands = 80, frames = 800;
    if (audio.empty() || !std::all_of(audio.begin(), audio.end(),
                                      [](float x) { return std::isfinite(x) && std::abs(x) <= 1; }))
        throw std::invalid_argument("turn audio must be finite normalized mono PCM");
    std::vector<float> padded(count, 0);
    const auto take = std::min<std::size_t>(audio.size(), count);
    std::copy(audio.end() - take, audio.end(), padded.end() - take);
    // Upstream pads on the left BEFORE normalizing all 8 seconds (including padding).
    const double mean = std::accumulate(padded.begin(), padded.end(), 0.0) / count;
    double variance = 0;
    for (const auto x : padded)
        variance += (x - mean) * (x - mean);
    const double scale = std::sqrt(variance / count + 1e-7);
    for (auto &x : padded)
        x = static_cast<float>((x - mean) / scale);

    std::array<double, 82> edges{};
    const double log_step = std::log(6.4) / 27;
    const double max_mel = 15 + std::log(8.0) / log_step;
    for (unsigned i = 0; i < edges.size(); ++i) {
        const double mel = max_mel * i / 81;
        edges[i] = mel < 15 ? mel * 200 / 3 : 1000 * std::exp(log_step * (mel - 15));
    }
    std::array<std::array<double, bins>, bands> filters{};
    for (unsigned m = 0; m < bands; ++m)
        for (unsigned k = 0; k < bins; ++k) {
            const double hz = k * 40;
            filters[m][k] =
                std::max(0.0, std::min((hz - edges[m]) / (edges[m + 1] - edges[m]),
                                       (edges[m + 2] - hz) / (edges[m + 2] - edges[m + 1]))) *
                2 / (edges[m + 2] - edges[m]);
        }
    std::array<float, 400> window{}, input{};
    for (unsigned i = 0; i < window.size(); ++i)
        window[i] = static_cast<float>(0.5 - 0.5 * std::cos(2 * std::acos(-1.0) * i / 400));
    std::size_t fft_size = 0;
    kiss_fftr_alloc(400, 0, nullptr, &fft_size);
    std::vector<char> fft_memory(fft_size);
    auto fft = kiss_fftr_alloc(400, 0, fft_memory.data(), &fft_size);
    if (!fft)
        throw std::runtime_error("FFT allocation failed");
    std::array<kiss_fft_cpx, bins> spectrum{};
    std::array<double, bins> power{};
    std::vector<float> features(bands * frames);
    float maximum = -10;
    for (unsigned t = 0; t < frames; ++t) {
        for (int j = 0; j < 400; ++j) {
            int index = static_cast<int>(t * 160) + j - 200;
            if (index < 0)
                index = -index;
            if (index >= static_cast<int>(count))
                index = 2 * count - 2 - index;
            input[j] = padded[index] * window[j];
        }
        kiss_fftr(fft, input.data(), spectrum.data());
        for (unsigned k = 0; k < bins; ++k)
            power[k] = static_cast<double>(spectrum[k].r) * spectrum[k].r +
                       static_cast<double>(spectrum[k].i) * spectrum[k].i;
        for (unsigned m = 0; m < bands; ++m) {
            double energy = 0;
            for (unsigned k = 0; k < bins; ++k)
                energy += filters[m][k] * power[k];
            const float value = static_cast<float>(std::log10(std::max(1e-10, energy)));
            features[m * frames + t] = value;
            maximum = std::max(maximum, value);
        }
    }
    for (auto &x : features)
        x = (std::max(x, maximum - 8) + 4) / 4;
    return features;
}

float TurnModels::complete(std::span<const float> audio) {
    auto data = features(audio);
    constexpr std::array<int64_t, 3> shape{1, 80, 800};
    auto input = Ort::Value::CreateTensor<float>(impl_->memory, data.data(), data.size(),
                                                 shape.data(), shape.size());
    const char *name = "input_features", *output = "logits";
    auto result = impl_->turn.Run(Ort::RunOptions{nullptr}, &name, &input, 1, &output, 1);
    return probability(result[0]);
}
} // namespace alojan
#else
namespace alojan {
struct TurnModels::Impl {};
TurnModels::TurnModels(const std::string &) {
    throw std::runtime_error("configure ALOJAN_TURN_MODELS=ON before enabling turn detection");
}
TurnModels::~TurnModels() = default;
float TurnModels::vad(std::span<const float, 576>, std::array<float, 256> &) {
    throw std::runtime_error("turn models unavailable");
}
float TurnModels::complete(std::span<const float>) {
    throw std::runtime_error("turn models unavailable");
}
std::vector<float> TurnModels::features(std::span<const float>) {
    throw std::runtime_error("turn models unavailable");
}
} // namespace alojan
#endif
