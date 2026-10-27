#pragma once

#include "voice/v1/voice.grpc.pb.h"
#include <atomic>
#include <chrono>
#include <memory>
#include <string>

namespace alojan {

class PreparedAudio {
    const std::string greeting_, unavailable_, waiting_, waiting_text_;
    explicit PreparedAudio(const voice::v1::PreparedAudioReply &reply)
        : greeting_(reply.greeting_pcm()), unavailable_(reply.unavailable_pcm()),
          waiting_(reply.waiting_pcm()), waiting_text_(reply.waiting_text()) {}

  public:
    static std::shared_ptr<const PreparedAudio>
    validate(const voice::v1::PreparedAudioRequest &request,
             const voice::v1::PreparedAudioReply &reply);
    const std::string &greeting() const noexcept { return greeting_; }
    const std::string &unavailable() const noexcept { return unavailable_; }
    const std::string &waiting() const noexcept { return waiting_; }
    const std::string &waiting_text() const noexcept { return waiting_text_; }
};

// Prepared waiting audio never occupies the response/TTS queue. One render consumer.
class WaitingPlayback {
    static_assert(std::atomic<unsigned>::is_always_lock_free &&
                  std::atomic<bool>::is_always_lock_free);
    std::atomic<bool> active_{false}, completed_{false};
    std::atomic<unsigned> frames_{0};

  public:
    void reset() noexcept {
        active_.store(false);
        frames_.store(0);
        completed_.store(false);
    }
    // Called only between turns while inactive, then once to activate the prepared clip.
    void start() noexcept {
        frames_.store(0);
        completed_.store(false);
        active_.store(true);
    }
    void stop() noexcept { active_.store(false); }
    bool active() const noexcept { return active_.load(); }
    bool completed() const noexcept { return completed_.load(); }
    unsigned frames() const noexcept { return frames_.load(); }
    bool render(const std::string &pcm, char *frame) noexcept;
    void blend_response(const std::string &pcm, char *response) noexcept;
};

std::shared_ptr<grpc::Channel> prepared_audio_channel(unsigned port);

// Blocking setup-worker operation only, never a SIP or audio callback. The caller
// owns the context until return and uses TryCancel together with its stop flag.
std::shared_ptr<const PreparedAudio>
fetch_prepared_audio(const std::shared_ptr<grpc::Channel> &channel,
                     const voice::v1::PreparedAudioRequest &request, const std::string &lease,
                     std::chrono::system_clock::time_point deadline, grpc::ClientContext &context,
                     const std::atomic<bool> &cancelled);

// One render thread, independent cursor per call; no allocation, IO or mutex in render.
class PreparedPlayback {
    static_assert(std::atomic<unsigned>::is_always_lock_free &&
                  std::atomic<bool>::is_always_lock_free);
    const std::shared_ptr<const PreparedAudio> audio_;
    const bool greeting_;
    std::atomic<bool> cancelled_{false};
    std::atomic<unsigned> sent_frames_{0};

  public:
    PreparedPlayback(std::shared_ptr<const PreparedAudio> audio, bool greeting);
    bool render(char *frame) noexcept; // exactly 320 output bytes / 20 ms
    void cancel() noexcept { cancelled_.store(true); }
    unsigned sent_frames() const noexcept { return sent_frames_.load(); }
};

} // namespace alojan
