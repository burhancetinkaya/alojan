import asyncio
from pathlib import Path

import grpc
import pytest
from alojan_contracts.audio import AudioStreamValidator
from support.contract_server import start_peer
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc


def frame(**changes):
    fields = dict(
        call_id="call-a",
        generation_id="gen-a",
        sample_rate_hz=8000,
        channels=1,
        format="pcm_s16le",
        audio=b"\x01\x02" * 160,
    )
    return pb.AudioFrame(**(fields | changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"channels": 2},
        {"sample_rate_hz": 44100},
        {"format": "mp3"},
        {"audio": b""},
        {"audio": b"x"},
        {"audio": b"x" * 322},
        {"call_id": "private number +90"},
        {"generation_id": "x" * 65},
        {"sequence": 1},
        {"captured_at_unix_ms": -1},
        {"format": "pcm_f32le", "audio": b"\x00\x00\xc0\x7f"},
    ],
)
def test_invalid_pcm(changes):
    with pytest.raises(ValueError):
        AudioStreamValidator().accept(frame(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"call_id": "call-b"},
        {"generation_id": "gen-b"},
        {"sample_rate_hz": 16000},
        {"format": "pcm_f32le"},
        {"sequence": 0},
    ],
)
def test_stream_cannot_switch_identity_or_format(changes):
    validator = AudioStreamValidator()
    validator.accept(frame())
    with pytest.raises(ValueError):
        validator.accept(frame(**({"sequence": 1} | changes)))


def test_valid_float_pcm():
    import struct

    AudioStreamValidator().accept(frame(format="pcm_f32le", audio=struct.pack("<3f", -1, 0, 1)))


def test_rpc_validation_and_call_isolation():
    async def scenario():
        server, _, address = await start_peer()
        try:
            async with grpc.aio.insecure_channel(address) as channel:
                recognition = rpc.RecognitionStub(channel)
                control = rpc.GenerationControlStub(channel)
                key = pb.CancelRequest(call_id="call-a", generation_id="gen-a")
                assert (await control.CancelGeneration(key, timeout=1)).cancelled
                assert (await control.CancelGeneration(key, timeout=1)).cancelled

                async def frames(item):
                    yield item

                for item, expected in [
                    (frame(), grpc.StatusCode.CANCELLED),
                    (frame(call_id="other", audio=b"x"), grpc.StatusCode.INVALID_ARGUMENT),
                    (
                        frame(call_id="other", audio=b"x" * 20000),
                        grpc.StatusCode.RESOURCE_EXHAUSTED,
                    ),
                ]:
                    with pytest.raises(grpc.aio.AioRpcError) as error:
                        await recognition.StreamRecognize(frames(item), timeout=1).read()
                    assert error.value.code() == expected
                events = [
                    event
                    async for event in recognition.StreamRecognize(
                        frames(frame(call_id="call-b")), timeout=1
                    )
                ]
                assert len(events) == 2 and events[-1].is_final
                assert events[0].text == frame().audio.hex()
                assert all(event.call_id == "call-b" for event in events)
        finally:
            await server.stop(0)

    asyncio.run(scenario())


def test_slow_consumer_has_bounded_queue_and_stops_producer():
    async def scenario():
        server, peer, address = await start_peer()
        try:
            async with grpc.aio.insecure_channel(address) as channel:
                call = rpc.SynthesisStub(channel).StreamSynthesize(
                    pb.SynthesisRequest(call_id="slow", generation_id="g", text="flood"), timeout=15
                )
                await call.wait_for_connection()
                await asyncio.wait_for(peer.stopped.wait(), timeout=12)
                assert peer.queue_peak == 8
                assert peer.active_producers == 0
                assert 8 < peer.produced < 100000
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    async for _ in call:
                        pass
                assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        finally:
            await server.stop(0)

    asyncio.run(scenario())


def test_synthesis_cancellation_stops_queued_output_and_rejects_reuse():
    async def scenario():
        server, peer, address = await start_peer()
        try:
            async with grpc.aio.insecure_channel(address) as channel:
                synthesis = rpc.SynthesisStub(channel)
                control = rpc.GenerationControlStub(channel)
                request = pb.SynthesisRequest(call_id="cancel", generation_id="g", text="flood")
                call = synthesis.StreamSynthesize(request, timeout=5)
                assert (await call.read()).generation_id == "g"
                await control.CancelGeneration(
                    pb.CancelRequest(call_id="cancel", generation_id="g"), timeout=1
                )
                # Transport may already hold old frames. Consumers must discard their generation.
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    while await call.read() is not grpc.aio.EOF:
                        pass
                assert error.value.code() == grpc.StatusCode.CANCELLED
                await asyncio.wait_for(peer.stopped.wait(), timeout=1)
                assert peer.active_producers == 0
                assert peer.queue_peak <= 8
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await synthesis.StreamSynthesize(request, timeout=1).read()
                assert error.value.code() == grpc.StatusCode.CANCELLED
        finally:
            await server.stop(0)

    asyncio.run(scenario())


def test_deadline_required_and_completed_generation_cannot_restart():
    async def scenario():
        server, _, address = await start_peer()
        try:
            async with grpc.aio.insecure_channel(address) as channel:
                synthesis = rpc.SynthesisStub(channel)
                request = pb.SynthesisRequest(call_id="deadline", generation_id="g", text="one")
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await synthesis.StreamSynthesize(request).read()
                assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
                assert (
                    len([event async for event in synthesis.StreamSynthesize(request, timeout=1)])
                    == 1
                )
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await synthesis.StreamSynthesize(request, timeout=1).read()
                assert error.value.code() == grpc.StatusCode.ALREADY_EXISTS
        finally:
            await server.stop(0)

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["roundtrip", "deadline", "cancel"])
def test_cpp_python_transport(mode):
    binary = Path("build/local/voice-contract-probe").resolve()
    assert binary.is_file(), "build the C++ contract probe before running the suite"

    async def scenario():
        server, _, address = await start_peer()
        try:
            process = await asyncio.create_subprocess_exec(
                str(binary),
                address,
                mode,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            except TimeoutError:
                process.kill()
                await process.wait()
                raise
            assert process.returncode == 0, stderr.decode()
            assert stdout.decode().strip() == f"{mode}: passed"
        finally:
            await server.stop(0)

    asyncio.run(scenario())
