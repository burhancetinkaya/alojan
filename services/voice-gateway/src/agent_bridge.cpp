#include "speech_bridge.hpp"
#include <algorithm>
#include <google/protobuf/struct.pb.h>
#include <google/protobuf/util/json_util.h>

namespace alojan {
using namespace std::chrono_literals;
namespace contract = ::voice::v1;

void SpeechBridge::read_agent() noexcept {
    try {
        agent_context_->set_deadline(
            std::min(deadline_, std::chrono::system_clock::now() +
                                    std::chrono::seconds(gateway_settings_.turn_timeout_seconds)));
        contract::AgentRequest request;
        request.set_call_id(call_);
        request.set_generation_id(generation_);
        request.set_final_user_text(final_text_);
        google::protobuf::Struct metadata;
        if (!input_event_.empty())
            (*metadata.mutable_fields())["input_event"].set_string_value(input_event_);
        if (!caller_number_.empty())
            (*metadata.mutable_fields())["caller_number"].set_string_value(caller_number_);
        if (!google::protobuf::util::MessageToJsonString(metadata, request.mutable_context_json())
                 .ok())
            throw std::runtime_error("agent context serialization failed");
        auto stub = contract::Agent::NewStub(agent_);
        agent_request_ms_.store(now_ms());
        auto stream = stub->RunTurn(agent_context_.get(), request);
        contract::AgentEvent event;
        bool ended = false;
        unsigned index = 0, bytes = 0, responses = 0;
        const auto &output = gateway_settings_.output;
        while (!stop_.load() && !interrupted_.load() && stream->Read(&event)) {
            google::protobuf::Struct detail;
            if (ended || event.call_id() != call_ || event.generation_id() != generation_ ||
                event.detail_json().size() > 1024 ||
                !google::protobuf::util::JsonStringToMessage(event.detail_json(), &detail).ok()) {
                fail(Error::agent);
                break;
            }
            if (event.type() == "end") {
                const auto it = detail.fields().find("finish_call");
                if (!event.text().empty() || !responses || it == detail.fields().end() ||
                    it->second.kind_case() != google::protobuf::Value::kBoolValue) {
                    fail(Error::agent);
                    break;
                }
                finish_call_.store(it->second.bool_value());
                ended = true;
                continue;
            }
            const auto it = detail.fields().find("phrase_index");
            const auto kind = detail.fields().find("kind");
            if (kind != detail.fields().end() &&
                (kind->second.kind_case() != google::protobuf::Value::kStringValue ||
                 (kind->second.string_value() != "response" &&
                  kind->second.string_value() != "waiting"))) {
                fail(Error::agent);
                break;
            }
            const bool waiting =
                kind != detail.fields().end() && kind->second.string_value() == "waiting";
            if (!waiting)
                bytes += event.text().size();
            // Protobuf strings are UTF-8; count scalars, not encoded bytes.
            const auto characters =
                std::count_if(event.text().begin(), event.text().end(),
                              [](unsigned char c) { return (c & 0xc0) != 0x80; });
            if (event.type() != "text_delta" || event.text().empty() ||
                event.text().size() > output.phrase_max_bytes ||
                (agent_binding_ && characters > output.phrase_max_chars) ||
                (waiting &&
                 (index != 0 || !prepared_ || event.text() != prepared_->waiting_text())) ||
                (!waiting && responses >= output.max_phrases) || bytes > output.turn_max_bytes ||
                it == detail.fields().end() ||
                it->second.kind_case() != google::protobuf::Value::kNumberValue ||
                it->second.number_value() != index) {
                fail(Error::agent);
                break;
            }
            if (!waiting && !agent_phrase_ms_.load())
                agent_phrase_ms_.store(now_ms());
            if (!waiting)
                ++responses;
            while (!stop_.load() && !interrupted_.load() && state() != State::failed) {
                {
                    std::lock_guard lock(phrases_mutex_);
                    if (phrases_.size() < 8) {
                        phrases_.push_back({event.text(), waiting, now_ms()});
                        break;
                    }
                }
                if (std::chrono::system_clock::now() >= deadline_) {
                    fail(Error::agent);
                    break;
                }
                std::this_thread::sleep_for(1ms);
            }
            ++index;
        }
        const auto status = stream->Finish();
        if (!stop_.load() && !interrupted_.load() && state() != State::failed &&
            (!ended || !status.ok()))
            fail(Error::agent);
    } catch (...) {
        fail(Error::agent);
    }
    agent_done_.store(true);
}

void SpeechBridge::report_playback(unsigned index, unsigned sent_ms, bool completed) {
    auto stub = contract::Agent::NewStub(agent_);
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + 1s);
    if (agent_binding_)
        context.AddMetadata("x-alojan-lease", agent_binding_->lease);
    contract::PlaybackReport report;
    report.set_call_id(call_);
    report.set_generation_id(generation_);
    report.set_phrase_index(index);
    report.set_sent_audio_ms(sent_ms);
    report.set_completed(completed);
    contract::AgentAck reply;
    if (!stub->ReportPlayback(&context, report, &reply).ok() || !reply.accepted())
        fail(Error::agent);
}

void SpeechBridge::end_agent() noexcept {
    if (!agent_)
        return;
    try {
        invalidate(agent_, generation_);
        // Routed call timestamps and finalization belong to CallSetup.
        if (agent_binding_)
            return;
        auto stub = contract::Agent::NewStub(agent_);
        grpc::ClientContext context;
        context.set_deadline(std::chrono::system_clock::now() + 1s);
        contract::CallEnd request;
        request.set_call_id(call_);
        request.set_reason(end_reason_);
        contract::AgentAck reply;
        stub->EndCall(&context, request, &reply);
    } catch (...) {
    }
}
} // namespace alojan
