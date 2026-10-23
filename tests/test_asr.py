"""Real gRPC ASR lifecycle tests with an explicitly fake decoder (no model claims)."""

import asyncio
from contextlib import asynccontextmanager
import struct
import threading

import grpc
import pytest
from alojan_asr.service import RecognitionService, create_server
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc


class Decoder:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False
        self.fail = False

    def transcribe(self, audio, sample_format):
        self.calls.append((len(audio), sample_format))
        self.started.set()
        if self.block:
            assert self.release.wait(5), "test decoder was not released"
        if self.fail:
            raise RuntimeError("private transcript must never reach RPC details")
        if audio[:2] == b"\x02\x00":
            return "Other call"
        return "Merhaba" if len(audio) == 32000 else "Merhaba dünya"


def frame(sequence=0, **changes):
    return pb.AudioFrame(
        **(
            dict(
                call_id="a",
                generation_id="g",
                sequence=sequence,
                sample_rate_hz=16000,
                channels=1,
                format="pcm_s16le",
                audio=b"\x01\x00" * 320,
            )
            | changes
        )
    )


async def frames(count=1, **changes):
    for sequence in range(count):
        yield frame(sequence, **changes)


@asynccontextmanager
async def running():
    decoder = Decoder()
    service = RecognitionService(decoder)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield service, decoder, rpc.RecognitionStub(channel), rpc.GenerationControlStub(channel)
    finally:
        decoder.release.set()
        await server.stop(0)
        if service.inference is not None:
            await asyncio.shield(service.inference)
        service.close()


async def error_code(call, expected):
    with pytest.raises(grpc.aio.AioRpcError) as caught:
        async for _ in call:
            pass
    assert caught.value.code() == expected
    assert "private" not in caught.value.details()


def test_asr_partial_replacement_final_and_call_isolation():
    async def scenario():
        async with running() as (service, decoder, recognition, control):
            events = [e async for e in recognition.StreamRecognize(frames(60), timeout=3)]
            assert [(e.text, e.is_final) for e in events] == [
                ("Merhaba", False),
                ("Merhaba dünya", True),
            ]
            assert all((e.call_id, e.generation_id) == ("a", "g") for e in events)
            assert [e.processed_audio_ms for e in events] == [1000, 1200]
            assert decoder.calls == [(32000, "pcm_s16le"), (38400, "pcm_s16le")]
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1), grpc.StatusCode.ALREADY_EXISTS
            )
            await control.CancelGeneration(pb.CancelRequest(call_id="a", generation_id="g"))
            other = [
                e
                async for e in recognition.StreamRecognize(
                    frames(call_id="b", audio=b"\x02\x00" * 320), timeout=1
                )
            ]
            assert len(other) == 1 and other[0].is_final and other[0].text == "Other call"
            assert other[0].processed_audio_ms == 20
            assert not service.active

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_rate_hz": 8000, "audio": b"\x00" * 320},
        {"channels": 2},
        {"audio": b""},
        {"audio": b"x"},
        {"audio": b"x" * 642},
        {"call_id": "not an opaque id"},
        {"format": "pcm_f32le", "audio": struct.pack("<f", float("nan"))},
    ],
)
def test_asr_rejects_invalid_audio_before_decode(changes):
    async def scenario():
        async with running() as (_, decoder, recognition, _):
            await error_code(
                recognition.StreamRecognize(frames(**changes), timeout=1),
                grpc.StatusCode.INVALID_ARGUMENT,
            )
            assert decoder.calls == []

    asyncio.run(scenario())


def test_asr_empty_deadline_float_and_stream_identity():
    async def scenario():
        async with running() as (_, decoder, recognition, _):
            await error_code(
                recognition.StreamRecognize(frames()), grpc.StatusCode.INVALID_ARGUMENT
            )
            await error_code(
                recognition.StreamRecognize(frames(0), timeout=1), grpc.StatusCode.INVALID_ARGUMENT
            )

            async def switched():
                yield frame()
                yield frame(1, call_id="b")

            await error_code(
                recognition.StreamRecognize(switched(), timeout=1), grpc.StatusCode.INVALID_ARGUMENT
            )
            assert decoder.calls == []
            events = [
                e
                async for e in recognition.StreamRecognize(
                    frames(call_id="float", format="pcm_f32le", audio=struct.pack("<f", 0.5)),
                    timeout=1,
                )
            ]
            assert len(events) == 1 and events[0].is_final
            assert decoder.calls == [(4, "pcm_f32le")]

    asyncio.run(scenario())


def test_asr_cancel_before_start_and_while_waiting_for_audio():
    async def scenario():
        async with running() as (service, _, recognition, control):
            key = pb.CancelRequest(call_id="a", generation_id="g")
            for _ in range(2):
                assert (await control.CancelGeneration(key, timeout=1)).cancelled
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1), grpc.StatusCode.CANCELLED
            )
            call = recognition.StreamRecognize(timeout=2)
            await call.write(frame(call_id="idle"))
            for _ in range(100):
                if service.active:
                    break
                await asyncio.sleep(0.005)
            assert service.active
            await control.CancelGeneration(pb.CancelRequest(call_id="idle", generation_id="g"))
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                await call.read()
            assert caught.value.code() == grpc.StatusCode.CANCELLED
            assert not service.active

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_mode", ["explicit", "deadline", "transport"])
def test_asr_native_decode_keeps_capacity_until_finished(cancel_mode):
    async def scenario():
        async with running() as (service, decoder, recognition, control):
            decoder.block = True
            call = recognition.StreamRecognize(
                frames(50), timeout=0.3 if cancel_mode == "deadline" else 3
            )
            assert await asyncio.to_thread(decoder.started.wait, 1)
            await error_code(
                recognition.StreamRecognize(frames(call_id="busy"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            if cancel_mode == "explicit":
                await control.CancelGeneration(pb.CancelRequest(call_id="a", generation_id="g"))
                await error_code(call, grpc.StatusCode.CANCELLED)
            elif cancel_mode == "deadline":
                await error_code(call, grpc.StatusCode.DEADLINE_EXCEEDED)
            else:
                assert call.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await call.read()
            for _ in range(100):
                if not service.active:
                    break
                await asyncio.sleep(0.005)
            assert not service.active and not service.inference.done()
            await error_code(
                recognition.StreamRecognize(frames(call_id="after"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            assert len(decoder.calls) == 1
            decoder.release.set()
            await asyncio.wait_for(asyncio.shield(service.inference), timeout=1)
            decoder.block = False
            events = [
                e
                async for e in recognition.StreamRecognize(
                    frames(call_id="after", audio=b"\x02\x00" * 320), timeout=1
                )
            ]
            assert len(events) == 1 and events[0].text == "Other call"
            assert len(decoder.calls) == 2
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1),
                grpc.StatusCode.CANCELLED
                if cancel_mode == "explicit"
                else grpc.StatusCode.ALREADY_EXISTS,
            )

    asyncio.run(scenario())


def test_asr_failure_is_sanitized_and_a_new_generation_can_retry():
    async def scenario():
        async with running() as (_, decoder, recognition, _):
            decoder.fail = True
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1), grpc.StatusCode.INTERNAL
            )
            decoder.fail = False
            assert (
                len(
                    [
                        e
                        async for e in recognition.StreamRecognize(
                            frames(generation_id="retry"), timeout=1
                        )
                    ]
                )
                == 1
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("successor", ["release", "cancel", "timeout"])
def test_same_call_handoff_waits_for_cancelled_native_decode_without_queueing(successor):
    async def scenario():
        async with running() as (service, decoder, recognition, control):
            decoder.block = True
            old = recognition.StreamRecognize(frames(50, generation_id="monitor"), timeout=4)
            assert await asyncio.to_thread(decoder.started.wait, 1)
            await control.CancelGeneration(pb.CancelRequest(call_id="a", generation_id="monitor"))
            await error_code(old, grpc.StatusCode.CANCELLED)
            assert not service.active and not service.inference.done()
            new = recognition.StreamRecognize(frames(generation_id="next"), timeout=3)
            read = asyncio.create_task(new.read())
            for _ in range(100):
                if service.active:
                    break
                await asyncio.sleep(0.005)
            assert service.active and len(decoder.calls) == 1
            await error_code(
                recognition.StreamRecognize(frames(call_id="other"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            if successor == "release":
                decoder.release.set()
                event = await asyncio.wait_for(read, 1)
                assert event.is_final and event.generation_id == "next"
                assert event.processed_audio_ms == 20 and event.text == "Merhaba dünya"
                assert len(decoder.calls) == 2
            else:
                if successor == "cancel":
                    await control.CancelGeneration(
                        pb.CancelRequest(call_id="a", generation_id="next")
                    )
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await asyncio.wait_for(read, 2)
                assert error.value.code() == (
                    grpc.StatusCode.CANCELLED
                    if successor == "cancel"
                    else grpc.StatusCode.RESOURCE_EXHAUSTED
                )
                assert len(decoder.calls) == 1 and not service.inference.done()
            assert not service.active

    asyncio.run(scenario())


def test_asr_audio_and_generation_capacity_fail_closed():
    async def scenario():
        async with running() as (service, decoder, recognition, control):
            await error_code(
                recognition.StreamRecognize(frames(1501), timeout=5),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            assert len(decoder.calls) == 30
            assert max(size for size, _ in decoder.calls) == 960000
            original = service.generations[("a", "g")]
            service.generations.update({(f"call-{i}", "g"): original for i in range(4095)})
            await error_code(
                recognition.StreamRecognize(frames(call_id="overflow"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                await control.CancelGeneration(
                    pb.CancelRequest(call_id="overflow", generation_id="g")
                )
            assert caught.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
            assert len(service.generations) == 4096
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1), grpc.StatusCode.ALREADY_EXISTS
            )

    asyncio.run(scenario())


def test_asr_stalled_output_is_bounded():
    class Abort(Exception):
        pass

    class Context:
        def time_remaining(self):
            return 2

        async def write(self, _):
            await asyncio.Event().wait()

        async def abort(self, code, message):
            assert code == grpc.StatusCode.RESOURCE_EXHAUSTED and message == "slow consumer"
            raise Abort()

    async def scenario():
        service = RecognitionService(Decoder())
        try:
            with pytest.raises(Abort):
                await asyncio.wait_for(service.StreamRecognize(frames(), Context()), timeout=1.5)
            assert not service.active
        finally:
            service.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("output", [None, "x" * 8193, "\ud800"])
def test_asr_invalid_model_output_is_rejected_without_leaking(output):
    async def scenario():
        async with running() as (_, decoder, recognition, _):
            decoder.transcribe = lambda *_: output
            await error_code(
                recognition.StreamRecognize(frames(), timeout=1), grpc.StatusCode.INTERNAL
            )

    asyncio.run(scenario())
