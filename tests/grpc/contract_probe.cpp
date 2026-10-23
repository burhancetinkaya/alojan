#include "voice/v1/voice.grpc.pb.h"
#include <chrono>
#include <grpcpp/grpcpp.h>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace std::chrono_literals;
namespace contract = ::voice::v1;

void require(bool condition, const char *message) {
    if (!condition)
        throw std::runtime_error(message);
}

void deadline(grpc::ClientContext &context, std::chrono::milliseconds timeout = 3000ms) {
    context.set_deadline(std::chrono::system_clock::now() + timeout);
}

contract::AudioFrame audio() {
    contract::AudioFrame frame;
    frame.set_call_id("cpp-call");
    frame.set_generation_id("cpp-generation");
    frame.set_sample_rate_hz(8000);
    frame.set_channels(1);
    frame.set_format("pcm_s16le");
    std::string bytes;
    for (int i = 0; i < 320; ++i)
        bytes += static_cast<char>(i % 160);
    frame.set_audio(bytes);
    return frame;
}

std::string hex(const std::string &bytes) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result;
    for (unsigned char value : bytes) {
        result += digits[value >> 4];
        result += digits[value & 15];
    }
    return result;
}

void roundtrip(const std::shared_ptr<grpc::Channel> &channel) {
    auto synthesis = contract::Synthesis::NewStub(channel);
    grpc::ClientContext synth_context;
    deadline(synth_context);
    contract::SynthesisRequest request;
    request.set_call_id(audio().call_id());
    request.set_generation_id(audio().generation_id());
    request.set_text("one");
    auto reader = synthesis->StreamSynthesize(&synth_context, request);
    contract::AudioFrame received;
    require(reader->Read(&received), "missing synthetic frame");
    require(received.audio() == audio().audio() && received.call_id() == request.call_id() &&
                received.generation_id() == request.generation_id() && received.sequence() == 0 &&
                received.sample_rate_hz() == 8000 && received.channels() == 1 &&
                received.format() == "pcm_s16le",
            "synthesis PCM or metadata corrupted");
    require(!reader->Read(&received) && reader->Finish().ok(), "synthesis did not finish");

    auto recognition = contract::Recognition::NewStub(channel);
    grpc::ClientContext context;
    deadline(context);
    auto stream = recognition->StreamRecognize(&context);
    auto frame = audio();
    contract::RecognitionEvent event;
    // One in-flight frame: this probe never accumulates an unbounded application queue.
    for (int i = 0; i < 3; ++i) {
        frame.set_sequence(i);
        require(stream->Write(frame) && stream->Read(&event), "stream stopped early");
        require(event.call_id() == frame.call_id() &&
                    event.generation_id() == frame.generation_id() &&
                    event.text() == hex(frame.audio()) && !event.is_final(),
                "recognition echo corrupted");
    }
    require(stream->WritesDone(), "half-close failed");
    require(stream->Read(&event) && event.is_final(), "missing final event after half-close");
    require(!stream->Read(&event) && stream->Finish().ok(), "recognition did not finish");
}

void expires(const std::shared_ptr<grpc::Channel> &channel) {
    auto stub = contract::Recognition::NewStub(channel);
    grpc::ClientContext context;
    deadline(context, 100ms);
    context.AddMetadata("x-test-delay", "yes");
    auto stream = stub->StreamRecognize(&context);
    require(stream->Write(audio()), "deadline request failed to write");
    contract::RecognitionEvent event;
    require(!stream->Read(&event), "received expired output");
    require(stream->Finish().error_code() == grpc::StatusCode::DEADLINE_EXCEEDED,
            "expected deadline exceeded");
}

void cancel(const std::shared_ptr<grpc::Channel> &channel) {
    auto recognition = contract::Recognition::NewStub(channel);
    auto control = contract::GenerationControl::NewStub(channel);
    grpc::ClientContext context;
    deadline(context);
    auto stream = recognition->StreamRecognize(&context);
    auto frame = audio();
    contract::RecognitionEvent event;
    require(stream->Write(frame) && stream->Read(&event), "stream did not start");
    contract::CancelRequest request;
    request.set_call_id(frame.call_id());
    request.set_generation_id(frame.generation_id());
    for (int i = 0; i < 2; ++i) {
        grpc::ClientContext cancel_context;
        deadline(cancel_context);
        contract::CancelReply reply;
        require(control->CancelGeneration(&cancel_context, request, &reply).ok() &&
                    reply.cancelled(),
                "idempotent cancellation failed");
    }
    // The input stream remains open: cancellation must interrupt an idle server read.
    require(!stream->Read(&event), "received output after cancellation");
    require(stream->Finish().error_code() == grpc::StatusCode::CANCELLED,
            "active generation did not cancel");
    grpc::ClientContext stale_context;
    deadline(stale_context);
    auto stale = recognition->StreamRecognize(&stale_context);
    stale->Write(frame);
    stale->WritesDone();
    require(!stale->Read(&event), "cancelled generation was revived");
    require(stale->Finish().error_code() == grpc::StatusCode::CANCELLED,
            "stale generation did not cancel");
}

int main(int argc, char **argv) {
    try {
        require(argc == 3, "usage: voice-contract-probe 127.0.0.1:PORT roundtrip|deadline|cancel");
        const std::string address = argv[1], mode = argv[2];
        require(address.starts_with("127.0.0.1:"), "test probe only permits loopback");
        grpc::ChannelArguments arguments;
        arguments.SetMaxReceiveMessageSize(16384);
        arguments.SetMaxSendMessageSize(16384);
        auto channel =
            grpc::CreateCustomChannel(address, grpc::InsecureChannelCredentials(), arguments);
        if (mode == "roundtrip")
            roundtrip(channel);
        else if (mode == "deadline")
            expires(channel);
        else if (mode == "cancel")
            cancel(channel);
        else
            throw std::runtime_error("unknown probe mode");
        std::cout << mode << ": passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
