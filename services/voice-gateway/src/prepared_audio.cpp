#include "prepared_audio.hpp"
#include <algorithm>
#include <cstring>
#include <grpcpp/grpcpp.h>
#include <stdexcept>

namespace alojan {
namespace {
bool hex(const std::string &value, std::size_t length) {
    return value.size() == length &&
           value.find_first_not_of("0123456789abcdef") == std::string::npos;
}
bool identity(const voice::v1::PreparedAudioRequest &request) {
    const auto &call = request.call_id();
    const auto &release = request.release_id();
    if (!call.starts_with("managed-") || call.size() > 128 ||
        call.find_first_not_of(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-") !=
            std::string::npos ||
        release.size() != 36 || !hex(request.manifest_digest(), 64))
        return false;
    for (std::size_t i = 0; i < release.size(); ++i) {
        const bool separator = i == 8 || i == 13 || i == 18 || i == 23;
        if (separator ? release[i] != '-'
                      : std::string("0123456789abcdef").find(release[i]) == std::string::npos)
            return false;
    }
    return true;
}
bool pcm(const std::string &value) {
    return !value.empty() && value.size() <= 480000 && value.size() % 320 == 0;
}
} // namespace

std::shared_ptr<const PreparedAudio>
PreparedAudio::validate(const voice::v1::PreparedAudioRequest &request,
                        const voice::v1::PreparedAudioReply &reply) {
    if (!identity(request) || reply.call_id() != request.call_id() ||
        reply.release_id() != request.release_id() ||
        reply.manifest_digest() != request.manifest_digest() || !pcm(reply.greeting_pcm()) ||
        !pcm(reply.unavailable_pcm()) || reply.greeting_pad_ms() > 1000 ||
        reply.greeting_pad_ms() % 20 != 0)
        throw std::runtime_error("invalid prepared audio");
    if (reply.waiting_pcm().empty() != reply.waiting_text().empty() ||
        (!reply.waiting_pcm().empty() &&
         (!pcm(reply.waiting_pcm()) || reply.waiting_pcm().size() > 80000 ||
          reply.waiting_text().size() > 400 ||
          std::none_of(reply.waiting_pcm().begin(), reply.waiting_pcm().end(),
                       [](char c) { return c != 0; }))))
        throw std::runtime_error("invalid waiting audio");
    const auto pad = reply.greeting_pad_ms() * 16;
    if (pad >= reply.greeting_pcm().size() ||
        std::any_of(reply.greeting_pcm().begin(), reply.greeting_pcm().begin() + pad,
                    [](char c) { return c != 0; }) ||
        std::none_of(reply.greeting_pcm().begin() + pad, reply.greeting_pcm().end(),
                     [](char c) { return c != 0; }) ||
        std::none_of(reply.unavailable_pcm().begin(), reply.unavailable_pcm().end(),
                     [](char c) { return c != 0; }))
        throw std::runtime_error("invalid prepared audio padding");
    return std::shared_ptr<const PreparedAudio>(new PreparedAudio(reply));
}

std::shared_ptr<grpc::Channel> prepared_audio_channel(unsigned port) {
    if (!port || port > 65535)
        throw std::invalid_argument("invalid prepared audio port");
    grpc::ChannelArguments options;
    options.SetMaxReceiveMessageSize(1100000);
    return grpc::CreateCustomChannel("127.0.0.1:" + std::to_string(port),
                                     grpc::InsecureChannelCredentials(), options);
}

bool WaitingPlayback::render(const std::string &pcm, char *frame) noexcept {
    if (!active_.load())
        return false;
    const auto offset = frames_.load() * 320;
    if (offset + 320 > pcm.size()) {
        active_.store(false);
        return false;
    }
    std::memcpy(frame, pcm.data() + offset, 320);
    if (offset + 320 == pcm.size()) {
        completed_.store(true);
        active_.store(false);
    }
    frames_.fetch_add(1);
    return true;
}

void WaitingPlayback::blend_response(const std::string &pcm, char *response) noexcept {
    if (!active_.exchange(false))
        return;
    const auto offset = frames_.load() * 320;
    if (!offset || offset + 320 > pcm.size())
        return; // An unsent waiting clip never delays an already available response.
    // Crossfade inside the response's first frame; never insert a 20 ms filler frame.
    for (unsigned i = 0; i < 40; ++i) {
        const int weight = static_cast<int>(i);
        std::int16_t old_sample, new_sample;
        std::memcpy(&old_sample, pcm.data() + offset + i * 2, 2);
        std::memcpy(&new_sample, response + i * 2, 2);
        const auto mixed = static_cast<std::int16_t>(
            (static_cast<int>(old_sample) * (39 - weight) + static_cast<int>(new_sample) * weight) /
            39);
        std::memcpy(response + i * 2, &mixed, 2);
    }
    frames_.fetch_add(1); // The shared frame contains sent waiting and response samples.
}

std::shared_ptr<const PreparedAudio>
fetch_prepared_audio(const std::shared_ptr<grpc::Channel> &channel,
                     const voice::v1::PreparedAudioRequest &request, const std::string &lease,
                     std::chrono::system_clock::time_point deadline, grpc::ClientContext &context,
                     const std::atomic<bool> &cancelled) {
    if (!channel || !identity(request) || !hex(lease, 32) || cancelled.load())
        throw std::runtime_error("prepared audio setup rejected");
    context.set_deadline(
        std::min(deadline, std::chrono::system_clock::now() + std::chrono::milliseconds(1800)));
    context.AddMetadata("x-alojan-lease", lease);
    auto stub = voice::v1::Agent::NewStub(channel);
    voice::v1::PreparedAudioReply reply;
    if (!stub->GetPreparedAudio(&context, request, &reply).ok() || cancelled.load())
        throw std::runtime_error("prepared audio unavailable");
    auto audio = PreparedAudio::validate(request, reply);
    if (cancelled.load())
        throw std::runtime_error("prepared audio setup cancelled");
    return audio;
}

PreparedPlayback::PreparedPlayback(std::shared_ptr<const PreparedAudio> audio, bool greeting)
    : audio_(std::move(audio)), greeting_(greeting) {
    if (!audio_)
        throw std::invalid_argument("prepared audio required");
}

bool PreparedPlayback::render(char *frame) noexcept {
    const auto &pcm = greeting_ ? audio_->greeting() : audio_->unavailable();
    const auto sent = sent_frames_.load(std::memory_order_relaxed);
    if (cancelled_.load() || sent >= pcm.size() / 320) {
        std::memset(frame, 0, 320);
        return false;
    }
    std::memcpy(frame, pcm.data() + sent * 320, 320);
    if (cancelled_.load()) {
        std::memset(frame, 0, 320);
        return false;
    }
    sent_frames_.store(sent + 1);
    return true;
}
} // namespace alojan
