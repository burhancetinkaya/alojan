"""Real gRPC lifecycle tests with an explicitly fake PCM producer; no CUDA claim."""

import asyncio
from contextlib import asynccontextmanager
import threading

import grpc
import pytest
from alojan_contracts.audio import AudioStreamValidator
from alojan_contracts.synthesis import EMA_MODEL, EMA_VOICE, SynthesisProfile
from alojan_tts.outbox import CancellableOutbox
from alojan_tts.service import InvalidText, SynthesisService, create_server
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc


# Declared test capability only; Producer never loads EMA or claims CUDA readiness.
SYNTHETIC_PROFILE = SynthesisProfile(
    EMA_MODEL, "e7c96f2fc0ba843cd0f86e02786655bb56f50df8", EMA_VOICE
)


class Producer:
    def __init__(self):
        self.chunks = [b"\x01\x00" * 173, b"\x02\x00" * 154]
        self.started = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.block = False
        self.fail = None
        self.calls = []

    def stream(self, text):
        self.calls.append(text)
        self.started.set()
        try:
            if self.block:
                assert self.release.wait(5), "test producer was not released"
            if self.fail:
                raise self.fail("private input must never reach RPC details")
            yield from self.chunks
        finally:
            self.closed.set()


def request(**changes):
    return pb.SynthesisRequest(**(dict(call_id="a", generation_id="g", text="Merhaba") | changes))


@asynccontextmanager
async def running(backend=None, **options):
    backend = Producer() if backend is None else backend
    service = SynthesisService(backend, **options)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield service, backend, rpc.SynthesisStub(channel), rpc.GenerationControlStub(channel)
    finally:
        service.close()
        backend.release.set()
        await server.stop(0)
        if service.inference is not None:
            await asyncio.shield(service.inference)


async def error_code(call, expected):
    with pytest.raises(grpc.aio.AioRpcError) as caught:
        async for _ in call:
            pass
    assert caught.value.code() == expected
    assert "private" not in caught.value.details()


def test_tts_reframes_chunks_without_loss_and_isolates_calls():
    async def scenario():
        async with running() as (service, backend, synthesis, control):
            frames = [f async for f in synthesis.StreamSynthesize(request(), timeout=2)]
            validator = AudioStreamValidator()
            for f in frames:
                assert validator.accept(f) == ("a", "g")
                assert len(f.audio) == 320 and f.sample_rate_hz == 8000
            assert len(frames) == 3
            assert b"".join(f.audio for f in frames) == b"".join(backend.chunks).ljust(960, b"\0")
            assert backend.closed.is_set() and not service.active
            await error_code(
                synthesis.StreamSynthesize(request(), timeout=1), grpc.StatusCode.ALREADY_EXISTS
            )
            await control.CancelGeneration(pb.CancelRequest(call_id="a", generation_id="g"))
            other = [f async for f in synthesis.StreamSynthesize(request(call_id="b"), timeout=1)]
            assert len(other) == 3 and all(f.call_id == "b" for f in other)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"text": ""},
        {"text": " \n "},
        {"text": "!"},
        {"text": "a" * 513},
        {"text": "a\x00b"},
        {"text": "a\u202eb"},
        {"call_id": "bad id"},
    ],
)
def test_tts_rejects_invalid_requests(changes):
    async def scenario():
        async with running() as (_, backend, synthesis, _):
            await error_code(
                synthesis.StreamSynthesize(request(**changes), timeout=1),
                grpc.StatusCode.INVALID_ARGUMENT,
            )
            assert not backend.calls

    asyncio.run(scenario())


def test_tts_deadline_precancel_and_registry_bound():
    async def scenario():
        async with running() as (service, backend, synthesis, control):
            await error_code(
                synthesis.StreamSynthesize(request()), grpc.StatusCode.INVALID_ARGUMENT
            )
            key = pb.CancelRequest(call_id="a", generation_id="g")
            for _ in range(2):
                assert (await control.CancelGeneration(key, timeout=1)).cancelled
            await error_code(
                synthesis.StreamSynthesize(request(), timeout=1), grpc.StatusCode.CANCELLED
            )
            for i in range(4095):
                await control.CancelGeneration(
                    pb.CancelRequest(call_id="x", generation_id=str(i)), timeout=1
                )
            await error_code(
                synthesis.StreamSynthesize(request(call_id="b"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            assert len(service.generations) == 4096 and not backend.calls

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["explicit", "deadline", "transport"])
def test_tts_cancel_native_job_keeps_slot_until_cleanup(mode):
    async def scenario():
        async with running() as (service, backend, synthesis, control):
            backend.block = True
            call = synthesis.StreamSynthesize(request(), timeout=0.3 if mode == "deadline" else 3)
            assert await asyncio.to_thread(backend.started.wait, 1)
            if mode == "explicit":
                await control.CancelGeneration(
                    pb.CancelRequest(call_id="a", generation_id="g"), timeout=1
                )
                await error_code(call, grpc.StatusCode.CANCELLED)
            elif mode == "deadline":
                await error_code(call, grpc.StatusCode.DEADLINE_EXCEEDED)
            else:
                call.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await call.read()
            for _ in range(100):
                if not service.active:
                    break
                await asyncio.sleep(0.001)
            assert not service.active and not service.inference.done()
            await error_code(
                synthesis.StreamSynthesize(request(call_id="b"), timeout=1),
                grpc.StatusCode.RESOURCE_EXHAUSTED,
            )
            backend.release.set()
            await asyncio.wait_for(asyncio.shield(service.inference), 1)
            assert backend.closed.is_set()
            fresh = [f async for f in synthesis.StreamSynthesize(request(call_id="b"), timeout=1)]
            assert len(fresh) == 3 and all(f.call_id == "b" for f in fresh)
            assert backend.calls == ["Merhaba", "Merhaba"]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "chunks", [[], [b""], [b"x"], [None], [b"\0" * 80002], [b"\0" * 80000] * 7]
)
def test_tts_rejects_invalid_or_excess_model_audio(chunks):
    async def scenario():
        async with running() as (_, backend, synthesis, _):
            backend.chunks = chunks
            expected = (
                grpc.StatusCode.RESOURCE_EXHAUSTED if len(chunks) == 7 else grpc.StatusCode.INTERNAL
            )
            await error_code(synthesis.StreamSynthesize(request(), timeout=3), expected)
            assert backend.closed.is_set()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure,code",
    [(RuntimeError, grpc.StatusCode.INTERNAL), (InvalidText, grpc.StatusCode.INVALID_ARGUMENT)],
)
def test_tts_sanitizes_backend_errors_and_recovers(failure, code):
    async def scenario():
        async with running() as (service, backend, synthesis, _):
            backend.fail = failure
            await error_code(synthesis.StreamSynthesize(request(), timeout=1), code)
            await asyncio.shield(service.inference)
            backend.fail = None
            assert (
                len(
                    [
                        f
                        async for f in synthesis.StreamSynthesize(
                            request(generation_id="new"), timeout=1
                        )
                    ]
                )
                == 3
            )

    asyncio.run(scenario())


def test_tts_slow_write_stops_bounded_producer():
    class Abort(Exception):
        pass

    class Context:
        def invocation_metadata(self):
            return ()

        def time_remaining(self):
            return 10

        async def write(self, frame):
            await asyncio.sleep(10)

        async def abort(self, code, detail):
            assert code == grpc.StatusCode.RESOURCE_EXHAUSTED
            raise Abort()

    async def scenario():
        backend = Producer()
        backend.chunks = [b"\1\0" * 40000] * 6
        service = SynthesisService(backend)
        try:
            with pytest.raises(Abort):
                await asyncio.wait_for(service.StreamSynthesize(request(), Context()), 1)
            await asyncio.wait_for(asyncio.shield(service.inference), 1)
            assert backend.closed.is_set() and not service.active
            assert service.queue_peak == 8
        finally:
            service.close()

    asyncio.run(scenario())


def test_tts_upstream_outbox_cancellation_releases_blocked_scheduler():
    outbox = CancellableOutbox()
    outbox.put("first")
    thread = threading.Thread(target=outbox.put, args=("blocked",))
    thread.start()
    thread.join(0.1)
    assert thread.is_alive() and outbox.qsize() == 1
    outbox.stop()
    thread.join(1)
    assert not thread.is_alive() and outbox.peak == 1
    assert outbox.get_nowait() == "first"


def test_cancelled_generation_does_not_begin_another_write():
    from alojan_contracts.generation import Generation, GenerationControl

    class Abort(Exception):
        pass

    class Context:
        written = False

        async def write(self):
            self.written = True

        async def abort(self, code, detail):
            assert code == grpc.StatusCode.CANCELLED
            raise Abort()

    async def scenario():
        state = Generation()
        state.cancelled.set()
        context = Context()
        with pytest.raises(Abort):
            await GenerationControl().wait(context.write(), state, context)
        assert not context.written

    asyncio.run(scenario())
