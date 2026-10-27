#pragma once
#include "gateway_settings.hpp"

#include "call_service_binding.hpp"
#include "prepared_audio.hpp"
#include <thread>

namespace alojan {

// One bounded worker per admitted call; no network work on the signaling thread.
class CallSetup {
  public:
    enum class State { pending, ready, failed, cancelled };
    CallSetup(std::shared_ptr<grpc::Channel> channel, voice::v1::CallInitializationRequest request,
              std::chrono::system_clock::time_point deadline,
              std::shared_ptr<grpc::Channel> recognition_channel = {},
              std::shared_ptr<grpc::Channel> synthesis_channel = {},
              std::shared_ptr<grpc::Channel> conversation_channel = {});
    ~CallSetup();
    enum class Outcome { completed, disconnected, failed };
    void cancel(Outcome outcome = Outcome::disconnected) noexcept;
    void answered() noexcept;
    State state() const noexcept { return cancelled_.load() ? State::cancelled : state_.load(); }
    bool answer_persisted() const noexcept { return answer_persisted_.load(); }
    void hold_consumers() noexcept { consumers_active_.store(true); }
    void consumers_finished() noexcept {
        consumers_active_.store(false);
        consumers_active_.notify_all();
    }
    bool finished() const noexcept { return finished_.load(); }
    bool cleanup_confirmed() const noexcept { return cleanup_confirmed_.load(); }
    std::shared_ptr<const PreparedAudio> audio() const {
        return state() == State::ready ? audio_ : nullptr;
    }
    std::shared_ptr<const CallServiceBinding> recognition() const {
        return state() == State::ready ? recognition_ : nullptr;
    }

    std::shared_ptr<const CallServiceBinding> agent() const {
        return state() == State::ready ? agent_ : nullptr;
    }
    std::shared_ptr<const CallServiceBinding> synthesis() const {
        return state() == State::ready ? synthesis_ : nullptr;
    }
    std::shared_ptr<const GatewaySettings> settings() const {
        return state() == State::ready ? settings_ : nullptr;
    }

  private:
    const std::shared_ptr<grpc::Channel> channel_;
    const std::shared_ptr<grpc::Channel> recognition_channel_, synthesis_channel_,
        conversation_channel_;
    const voice::v1::CallInitializationRequest request_;
    const std::chrono::system_clock::time_point deadline_;
    grpc::ClientContext open_, initialize_, fetch_, recognition_open_, recognition_configure_,
        synthesis_open_, synthesis_configure_;
    std::atomic<bool> cancelled_{false}, finished_{false}, cleanup_confirmed_{false};
    std::atomic<bool> answer_persisted_{false}, consumers_active_{false};
    std::atomic<State> state_{State::pending};
    std::atomic<unsigned> wake_{0};
    std::atomic<std::int64_t> answered_ms_{0}, ended_ms_{0};
    std::atomic<Outcome> outcome_{Outcome::failed};
    std::shared_ptr<const PreparedAudio> audio_;
    std::shared_ptr<const GatewaySettings> settings_;
    std::shared_ptr<const CallServiceBinding> recognition_, agent_, synthesis_;
    std::thread worker_;
    void run() noexcept;
};

} // namespace alojan
