#include "call_setup.hpp"
#include <algorithm>
#include <grpcpp/grpcpp.h>
#include <stdexcept>

namespace alojan {
using namespace std::chrono_literals;

CallSetup::CallSetup(std::shared_ptr<grpc::Channel> channel,
                     voice::v1::CallInitializationRequest request,
                     std::chrono::system_clock::time_point deadline,
                     std::shared_ptr<grpc::Channel> recognition_channel,
                     std::shared_ptr<grpc::Channel> synthesis_channel,
                     std::shared_ptr<grpc::Channel> conversation_channel)
    : channel_(std::move(channel)), recognition_channel_(std::move(recognition_channel)),
      synthesis_channel_(std::move(synthesis_channel)),
      conversation_channel_(std::move(conversation_channel)), request_(std::move(request)),
      deadline_(std::min(deadline, std::chrono::system_clock::now() + 1800ms)) {
    if (!channel_)
        throw std::invalid_argument("setup channel required");
    worker_ = std::thread([this] { run(); });
}

CallSetup::~CallSetup() {
    cancel();
    consumers_finished();
    if (worker_.joinable())
        worker_.join();
}

static std::int64_t unix_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

void CallSetup::answered() noexcept {
    if (cancelled_.load())
        return;
    std::int64_t missing = 0;
    answered_ms_.compare_exchange_strong(missing, unix_ms());
    wake_.fetch_add(1);
    wake_.notify_all();
}

void CallSetup::cancel(Outcome outcome) noexcept {
    if (cancelled_.load())
        return;
    ended_ms_.store(unix_ms());
    outcome_.store(outcome);
    cancelled_.store(true);
    wake_.fetch_add(1);
    wake_.notify_all();
    open_.TryCancel();
    initialize_.TryCancel();
    fetch_.TryCancel();
    recognition_open_.TryCancel();
    recognition_configure_.TryCancel();
    synthesis_open_.TryCancel();
    synthesis_configure_.TryCancel();
}

void CallSetup::run() noexcept {
    std::string lease;
    bool attempted = false;
    std::string recognition_lease;
    bool recognition_attempted = false;
    std::string synthesis_lease;
    bool synthesis_attempted = false;
    voice::v1::CallInitializationReply initialized;
    try {
        auto control = voice::v1::GenerationControl::NewStub(channel_);
        auto agent = voice::v1::Agent::NewStub(channel_);
        voice::v1::CallLeaseRequest opening;
        opening.set_call_id(request_.call_id());
        voice::v1::CallLeaseReply opened;
        open_.set_deadline(deadline_);
        if (!control->OpenCall(&open_, opening, &opened).ok() || opened.lease().size() != 32 ||
            opened.lease().find_first_not_of("0123456789abcdef") != std::string::npos)
            throw std::runtime_error("setup lease unavailable");
        lease = opened.lease();
        if (cancelled_.load())
            throw std::runtime_error("setup cancelled");
        initialize_.set_deadline(deadline_);
        initialize_.AddMetadata("x-alojan-lease", lease);
        attempted = true;
        if (!agent->InitializeCall(&initialize_, request_, &initialized).ok() ||
            !initialized.ready_for_answer() || cancelled_.load())
            throw std::runtime_error("setup not ready");
        settings_ = std::make_shared<const GatewaySettings>(
            GatewaySettings::from_proto(initialized.gateway()));
        if (recognition_channel_) {
            if (initialized.recognition().schema_version() != 1 ||
                initialized.recognition().ByteSizeLong() > 4096)
                throw std::runtime_error("unsupported recognition configuration");
            auto recognition_control = voice::v1::GenerationControl::NewStub(recognition_channel_);
            voice::v1::CallLeaseReply recognition_opened;
            recognition_open_.set_deadline(deadline_);
            recognition_attempted = true;
            if (!recognition_control->OpenCall(&recognition_open_, opening, &recognition_opened)
                     .ok() ||
                recognition_opened.lease().size() != 32 ||
                recognition_opened.lease().find_first_not_of("0123456789abcdef") !=
                    std::string::npos)
                throw std::runtime_error("recognition lease unavailable");
            recognition_lease = recognition_opened.lease();
            if (cancelled_.load())
                throw std::runtime_error("setup cancelled");
            auto recognition = voice::v1::Recognition::NewStub(recognition_channel_);
            voice::v1::RecognitionCallConfiguration configuration;
            configuration.set_call_id(request_.call_id());
            configuration.set_release_id(initialized.release_id());
            configuration.set_manifest_digest(initialized.manifest_digest());
            *configuration.mutable_configuration() = initialized.recognition();
            recognition_configure_.set_deadline(deadline_);
            recognition_configure_.AddMetadata("x-alojan-lease", recognition_lease);
            voice::v1::AgentAck configured;
            if (!recognition->ConfigureCall(&recognition_configure_, configuration, &configured)
                     .ok() ||
                !configured.accepted() || cancelled_.load())
                throw std::runtime_error("recognition configuration unavailable");
            recognition_ = std::make_shared<const CallServiceBinding>(
                CallServiceBinding{recognition_channel_, request_.call_id(), recognition_lease});
        }
        if (synthesis_channel_) {
            if (initialized.synthesis().schema_version() != 1 ||
                initialized.synthesis().ByteSizeLong() > 512)
                throw std::runtime_error("unsupported synthesis configuration");
            auto synthesis_control = voice::v1::GenerationControl::NewStub(synthesis_channel_);
            voice::v1::CallLeaseReply synthesis_opened;
            synthesis_open_.set_deadline(deadline_);
            synthesis_attempted = true;
            if (!synthesis_control->OpenCall(&synthesis_open_, opening, &synthesis_opened).ok() ||
                synthesis_opened.lease().size() != 32 ||
                synthesis_opened.lease().find_first_not_of("0123456789abcdef") != std::string::npos)
                throw std::runtime_error("synthesis lease unavailable");
            synthesis_lease = synthesis_opened.lease();
            if (cancelled_.load())
                throw std::runtime_error("setup cancelled");
            auto synthesis = voice::v1::Synthesis::NewStub(synthesis_channel_);
            voice::v1::SynthesisCallConfiguration configuration;
            configuration.set_call_id(request_.call_id());
            configuration.set_release_id(initialized.release_id());
            configuration.set_manifest_digest(initialized.manifest_digest());
            *configuration.mutable_configuration() = initialized.synthesis();
            synthesis_configure_.set_deadline(deadline_);
            synthesis_configure_.AddMetadata("x-alojan-lease", synthesis_lease);
            voice::v1::AgentAck configured;
            if (!synthesis->ConfigureCall(&synthesis_configure_, configuration, &configured).ok() ||
                !configured.accepted() || cancelled_.load())
                throw std::runtime_error("synthesis configuration unavailable");
            synthesis_ = std::make_shared<const CallServiceBinding>(
                CallServiceBinding{synthesis_channel_, request_.call_id(), synthesis_lease});
        }
        if (conversation_channel_)
            agent_ = std::make_shared<const CallServiceBinding>(
                CallServiceBinding{conversation_channel_, request_.call_id(), lease});
        voice::v1::PreparedAudioRequest expected;
        expected.set_call_id(request_.call_id());
        expected.set_release_id(initialized.release_id());
        expected.set_manifest_digest(initialized.manifest_digest());
        audio_ = fetch_prepared_audio(channel_, expected, lease, deadline_, fetch_, cancelled_);
        if (cancelled_.load() || std::chrono::system_clock::now() >= deadline_)
            throw std::runtime_error("setup expired");
        state_.store(State::ready);
        auto wake = wake_.load();
        while (!cancelled_.load() && !answered_ms_.load()) {
            wake_.wait(wake);
            wake = wake_.load();
        }
        if (answered_ms_.load()) {
            grpc::ClientContext context;
            context.set_deadline(std::chrono::system_clock::now() + 500ms);
            context.AddMetadata("x-alojan-lease", lease);
            voice::v1::CallAnswer request;
            request.set_call_id(request_.call_id());
            request.set_release_id(initialized.release_id());
            request.set_manifest_digest(initialized.manifest_digest());
            request.set_answered_at_unix_ms(answered_ms_.load());
            voice::v1::AgentAck reply;
            if (!agent->ReportCallAnswered(&context, request, &reply).ok() || !reply.accepted())
                throw std::runtime_error("answer persistence unavailable");
            answer_persisted_.store(true);
            wake = wake_.load();
            while (!cancelled_.load()) {
                wake_.wait(wake);
                wake = wake_.load();
            }
        }
    } catch (...) {
        state_.store(State::failed);
    }
    // Conversation cancellation/receipts finish while their leases still exist.
    while (consumers_active_.load())
        consumers_active_.wait(true);
    bool synthesis_released = !synthesis_attempted;
    if (!synthesis_lease.empty()) {
        try {
            auto control = voice::v1::GenerationControl::NewStub(synthesis_channel_);
            grpc::ClientContext context;
            context.set_deadline(std::chrono::system_clock::now() + 250ms);
            voice::v1::CallLeaseRequest request;
            request.set_call_id(request_.call_id());
            request.set_lease(synthesis_lease);
            voice::v1::AgentAck reply;
            synthesis_released =
                control->ReleaseCall(&context, request, &reply).ok() && reply.accepted();
        } catch (...) {
        }
    }
    bool recognition_released = !recognition_attempted;
    if (!recognition_lease.empty()) {
        try {
            auto control = voice::v1::GenerationControl::NewStub(recognition_channel_);
            grpc::ClientContext context;
            context.set_deadline(std::chrono::system_clock::now() + 250ms);
            voice::v1::CallLeaseRequest request;
            request.set_call_id(request_.call_id());
            request.set_lease(recognition_lease);
            voice::v1::AgentAck reply;
            recognition_released =
                control->ReleaseCall(&context, request, &reply).ok() && reply.accepted();
        } catch (...) {
        }
    }
    // A lost OpenCall reply cannot be released without its token; server lease expiry handles it.
    if (!lease.empty()) {
        try {
            auto agent = voice::v1::Agent::NewStub(channel_);
            auto control = voice::v1::GenerationControl::NewStub(channel_);
            bool cancelled = !attempted;
            if (answered_ms_.load()) {
                // Carry the ACK witness again: EndCall repairs an uncertain answer write
                // atomically.
                grpc::ClientContext context;
                context.set_deadline(std::chrono::system_clock::now() + 500ms);
                context.AddMetadata("x-alojan-lease", lease);
                voice::v1::CallEnd request;
                request.set_call_id(request_.call_id());
                request.set_release_id(initialized.release_id());
                request.set_manifest_digest(initialized.manifest_digest());
                request.set_answered_at_unix_ms(answered_ms_.load());
                request.set_ended_at_unix_ms(ended_ms_.load() ? ended_ms_.load() : unix_ms());
                const auto outcome = outcome_.load();
                request.set_reason(outcome == Outcome::completed      ? "completed"
                                   : outcome == Outcome::disconnected ? "disconnected"
                                                                      : "failed");
                voice::v1::AgentAck reply;
                cancelled = agent->EndCall(&context, request, &reply).ok() && reply.accepted();
            } else if (attempted) {
                grpc::ClientContext context;
                context.set_deadline(std::chrono::system_clock::now() + 250ms);
                context.AddMetadata("x-alojan-lease", lease);
                voice::v1::CallSetupCancellation request;
                request.set_call_id(request_.call_id());
                voice::v1::AgentAck reply;
                cancelled =
                    agent->CancelCallSetup(&context, request, &reply).ok() && reply.accepted();
            }
            grpc::ClientContext context;
            context.set_deadline(std::chrono::system_clock::now() + 250ms);
            voice::v1::CallLeaseRequest request;
            request.set_call_id(request_.call_id());
            request.set_lease(lease);
            voice::v1::AgentAck reply;
            const bool released =
                control->ReleaseCall(&context, request, &reply).ok() && reply.accepted();
            cleanup_confirmed_.store(cancelled && released && recognition_released &&
                                     synthesis_released);
        } catch (...) {
            // Reconciliation/lease expiry remains necessary when acknowledgement is lost.
        }
    }
    finished_.store(true);
}
} // namespace alojan
