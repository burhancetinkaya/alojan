"""Real private gRPC with blocked synthetic inference; no CUDA/provider claims."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from alojan_contracts.maintenance import WorkerMaintenance, MAINTENANCE
from alojan_asr.service import RecognitionService, create_server as asr_server
from alojan_tts.service import SynthesisService, create_server as tts_server
from alojan_agent.service import AgentService, create_server as agent_server
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc
from test_asr import Decoder, frames
from test_tts import Producer, SYNTHETIC_PROFILE, request as synthesis_request
from test_agent import Script, MemoryStore, request as agent_request

KINDS = {
    "asr": (RecognitionService, Decoder, asr_server, "Recognition"),
    "tts": (SynthesisService, Producer, tts_server, "Synthesis"),
    "agent": (AgentService, Script, agent_server, "Agent"),
}


def state(path, text):
    temp = path.with_suffix(".next")
    temp.write_text(text)
    temp.replace(path)


async def until(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.01)


@asynccontextmanager
async def running(kind, tmp_path, backend=None, store=None):
    cls, factory, create, name = KINDS[kind]
    backend = backend or factory()
    service = cls(backend, store or MemoryStore()) if kind == "agent" else cls(backend)
    path = tmp_path / "state"
    gate = WorkerMaintenance(service, path)
    server = create(service, maintenance=gate)
    status = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(status, server)
    await status.set("voice.v1." + name, health_pb2.HealthCheckResponse.SERVING)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    gate.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield service, gate, channel, path, port
    finally:
        if hasattr(backend, "release"):
            backend.release.set()
        await gate.stop()
        await server.stop(0)
        future = getattr(service, "inference", None)
        if future is not None and not future.cancelled():
            await asyncio.gather(asyncio.shield(future), return_exceptions=True)
        service.close() if hasattr(service, "close") else service.close_leases()


async def ready(channel):
    reply = await health_pb2_grpc.HealthStub(channel).Check(
        health_pb2.HealthCheckRequest(service=MAINTENANCE), timeout=1
    )
    return reply.status == health_pb2.HealthCheckResponse.SERVING


@pytest.mark.parametrize("kind", KINDS)
def test_closed_startup_lease_fence_cleanup_and_resume(kind, tmp_path):
    async def run():
        async with running(kind, tmp_path) as (service, gate, channel, path, port):
            assert await ready(channel)
            control = rpc.GenerationControlStub(channel)
            req = pb.CallLeaseRequest(call_id="managed-maintenance")
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                await control.OpenCall(req, timeout=1)
            assert caught.value.code() == grpc.StatusCode.UNAVAILABLE
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                if kind == "asr":
                    call = rpc.RecognitionStub(channel).StreamRecognize(frames(), timeout=1)
                elif kind == "tts":
                    call = rpc.SynthesisStub(channel).StreamSynthesize(
                        synthesis_request(), timeout=1
                    )
                else:
                    call = rpc.AgentStub(channel).RunTurn(agent_request(), timeout=1)
                async for _ in call:
                    pytest.fail("closed worker produced output")
            assert caught.value.code() == grpc.StatusCode.UNAVAILABLE
            assert not service.generations and not service.active
            state(path, "open\n")
            await until(lambda: not gate.closed)
            assert not await ready(channel)
            lease = await control.OpenCall(req, timeout=1)
            state(path, "drained\n")
            await until(lambda: gate.closed)
            assert not await ready(channel)  # A live lease alone prevents an idle receipt.
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                await control.ReleaseCall(
                    pb.CallLeaseRequest(call_id=req.call_id, lease="wrong"), timeout=1
                )
            assert caught.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id=req.call_id, lease=lease.lease), timeout=1
            )
            assert await ready(channel)
            ordinary = await health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest(service="voice.v1." + KINDS[kind][3]), timeout=1
            )
            assert ordinary.status == health_pb2.HealthCheckResponse.SERVING
            state(path, "open\n")
            await until(lambda: not gate.closed)
            lease = await control.OpenCall(req, timeout=1)
            assert lease.lease

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["asr", "tts"])
def test_cancel_and_release_do_not_hide_running_native_inference(kind, tmp_path):
    async def run():
        backend = Decoder() if kind == "asr" else Producer()
        backend.synthesis_profile = SYNTHETIC_PROFILE
        async with running(kind, tmp_path, backend) as (service, gate, channel, path, port):
            state(path, "open\n")
            await until(lambda: not gate.closed)
            control = rpc.GenerationControlStub(channel)
            cid = "managed-native"
            lease = await control.OpenCall(pb.CallLeaseRequest(call_id=cid), timeout=1)
            metadata = (("x-alojan-lease", lease.lease),)
            if kind == "tts":
                await rpc.SynthesisStub(channel).ConfigureCall(
                    pb.SynthesisCallConfiguration(
                        call_id=cid,
                        release_id="11111111-1111-1111-1111-111111111111",
                        manifest_digest="a" * 64,
                        configuration=SYNTHETIC_PROFILE.to_proto(),
                    ),
                    metadata=metadata,
                    timeout=1,
                )
            service.backend.block = True
            if kind == "asr":
                call = rpc.RecognitionStub(channel).StreamRecognize(
                    frames(call_id=cid), timeout=4, metadata=metadata
                )
            else:
                call = rpc.SynthesisStub(channel).StreamSynthesize(
                    synthesis_request(call_id=cid), timeout=4, metadata=metadata
                )

            async def consume():
                return [item async for item in call]

            consumer = asyncio.create_task(consume())
            assert await asyncio.to_thread(service.backend.started.wait, 1)
            state(path, "drained\n")
            await until(lambda: gate.closed)
            await rpc.GenerationControlStub(channel).CancelGeneration(
                pb.CancelRequest(call_id=cid, generation_id="g"), timeout=1, metadata=metadata
            )
            with pytest.raises(grpc.aio.AioRpcError) as caught:
                await consumer
            assert caught.value.code() == grpc.StatusCode.CANCELLED
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id=cid, lease=lease.lease), timeout=1
            )
            assert not service.leases
            await until(lambda: not service.active and not gate.active_rpcs)
            assert not service.inference.done()
            assert not await ready(channel)
            service.backend.release.set()
            await asyncio.shield(service.inference)
            assert await ready(channel)

    asyncio.run(run())


def test_agent_turn_cleanup_and_end_rpc_are_both_observed(tmp_path):
    class ClosingScript(Script):
        def __init__(self):
            self.started = asyncio.Event()
            self.closing = asyncio.Event()
            self.release = asyncio.Event()

        async def stream(self, call, save_note):
            self.started.set()
            try:
                await asyncio.sleep(60)
                yield "Synthetic."
            finally:
                self.closing.set()
                await self.release.wait()

    class EndingStore(MemoryStore):
        def __init__(self):
            super().__init__()
            self.entered, self.release = asyncio.Event(), asyncio.Event()

        async def end(self, *args):
            self.entered.set()
            await self.release.wait()

    async def run():
        backend, store = ClosingScript(), EndingStore()
        async with running("agent", tmp_path, backend, store) as (
            service,
            gate,
            channel,
            path,
            port,
        ):
            state(path, "open\n")
            await until(lambda: not gate.closed)
            stub = rpc.AgentStub(channel)

            async def consume():
                return [event async for event in stub.RunTurn(agent_request(), timeout=4)]

            consumer = asyncio.create_task(consume())
            await asyncio.wait_for(backend.started.wait(), 1)
            state(path, "drained\n")
            await until(lambda: gate.closed)
            ending = stub.EndCall(pb.CallEnd(call_id="one", reason="disconnected"), timeout=3)
            await asyncio.wait_for(backend.closing.wait(), 1)
            await asyncio.wait_for(store.entered.wait(), 1)
            assert not await ready(channel)
            backend.release.set()
            with pytest.raises(grpc.aio.AioRpcError):
                await consumer
            await until(lambda: not service.active)
            assert not await ready(channel)  # End persistence is still inside an allowed RPC.
            store.release.set()
            assert (await ending).accepted
            await until(lambda: not gate.active_rpcs)
            assert await ready(channel)

    asyncio.run(run())


def test_legacy_summary_pauses_without_dropping_current_or_queued_jobs(tmp_path):
    class SummaryStore(MemoryStore):
        def __init__(self):
            super().__init__()
            self.claimed = 0
            self.entered, self.release = asyncio.Event(), asyncio.Event()
            self.completed = []

        async def pending(self):
            self.claimed += 1
            self.entered.set()
            await self.release.wait()
            return ("synthetic-job",)

        async def summary_input(self, job):
            return {"last_note": None}

        async def summary_result(self, job, *args):
            self.completed.append(job)

    class Summarizer(Script):
        async def summarize(self, data):
            raise ValueError("synthetic provider failure")

    async def run():
        store = SummaryStore()
        async with running("agent", tmp_path, Summarizer(), store) as (
            service,
            gate,
            channel,
            path,
            port,
        ):
            task = asyncio.create_task(service.summaries())
            try:
                await asyncio.sleep(0.3)
                assert not store.claimed and await ready(channel)
                state(path, "open\n")
                await asyncio.wait_for(store.entered.wait(), 1)
                state(path, "drained\n")
                await until(lambda: gate.closed)
                assert service.summary_active and not await ready(channel)
                store.release.set()
                await until(lambda: not service.summary_active)
                assert store.completed == ["synthetic-job"] and await ready(channel)
                await asyncio.sleep(1.1)
                assert store.claimed == 1
                state(path, "open\n")
                await until(lambda: store.claimed > 1)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_cancelled_future_cannot_prove_native_quiescence(tmp_path):
    async def run():
        async with running("tts", tmp_path) as (service, gate, channel, path, port):
            service.inference = asyncio.get_running_loop().create_future()
            service.inference.cancel()
            assert not await ready(channel)

    asyncio.run(run())


def test_invalid_operator_files_fail_closed(tmp_path):
    path = tmp_path / "state"
    gate = WorkerMaintenance(None, path)
    assert gate.read_closed()
    for text in ("open", "OPEN\n", "open\nextra", "x" * 10000):
        state(path, text)
        assert gate.read_closed()
    state(path, "open\n")
    assert not gate.read_closed()
    path.unlink()
    path.symlink_to(tmp_path / "target")
    (tmp_path / "target").write_text("open\n")
    assert gate.read_closed()
    path.unlink()
    os.mkfifo(path)
    assert gate.read_closed()


def test_operator_health_probe_distinguishes_open_and_idle_workers(tmp_path):
    async def run():
        async with running("tts", tmp_path) as (service, gate, channel, path, port):

            async def probe():
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "infra/docker/health.py"),
                    "tts",
                    "--maintenance",
                    env={**os.environ, "ALOJAN_SERVICE_PORT": str(port)},
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                output, error = await process.communicate()
                assert not output and not error
                return process.returncode

            assert await probe() == 0
            state(path, "open\n")
            await until(lambda: not gate.closed)
            assert await probe() == 1

    asyncio.run(run())


@pytest.mark.parametrize("failure", [None, "close", "synchronize", "drop"])
def test_ema_requires_successful_scheduler_and_cuda_cleanup(tmp_path, failure):
    from types import SimpleNamespace
    import threading
    from alojan_tts.model import EmaBackend

    def step(name):
        if name == failure:
            raise RuntimeError("synthetic cleanup failure")

    class EmptyStream:
        def __iter__(self):
            return self

        def __next__(self):
            raise StopIteration

        def close(self):
            step("close")

    # Exercise EMA adapter cleanup without constructing EMA or touching CUDA.
    backend = EmaBackend.__new__(EmaBackend)
    backend.synthesis_profile = SYNTHETIC_PROFILE
    backend.quiescence_confirmed = True
    backend.tts = SimpleNamespace(
        stream=lambda *args, **kwargs: EmptyStream(),
        _engine=SimpleNamespace(lock=threading.Lock()),
        _playhead=SimpleNamespace(_drop_closed=lambda: step("drop")),
        request=None,
    )
    backend.torch = SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: step("synchronize")))
    service = SynthesisService(backend)
    gate = WorkerMaintenance(service, tmp_path / "state")
    try:
        if failure:
            with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
                list(backend.stream("Synthetic"))
            assert not backend.quiescence_confirmed and not gate.quiescent
        else:
            assert list(backend.stream("Synthetic")) == []
            assert backend.quiescence_confirmed and gate.quiescent
    finally:
        service.close()


@pytest.mark.parametrize("kind", ["asr", "tts", "agent"])
def test_failed_inference_or_stream_cleanup_cannot_attest_idle(kind, tmp_path):
    class BrokenStream:
        def __iter__(self):
            return self

        def __next__(self):
            return b"\x01\x00" * 160

        def close(self):
            raise RuntimeError("synthetic close failure")

    class BrokenProducer(Producer):
        def stream(self, text):
            return BrokenStream()

    class BrokenAgent(Script):
        async def stream(self, call, save_note):
            try:
                yield "Synthetic response."
                await asyncio.sleep(60)
            finally:
                raise RuntimeError("synthetic close failure")

    async def run():
        backend = (
            Decoder() if kind == "asr" else BrokenProducer() if kind == "tts" else BrokenAgent()
        )
        if kind == "asr":
            backend.fail = True
        async with running(kind, tmp_path, backend) as (service, gate, channel, path, port):
            state(path, "open\n")
            await until(lambda: not gate.closed)
            if kind == "asr":
                call = rpc.RecognitionStub(channel).StreamRecognize(frames(), timeout=1)
            elif kind == "tts":
                call = rpc.SynthesisStub(channel).StreamSynthesize(synthesis_request(), timeout=1)
            else:
                call = rpc.AgentStub(channel).RunTurn(agent_request(), timeout=1)
            if kind != "asr":
                await call.read()
                cid, generation = ("one", "turn-1") if kind == "agent" else ("a", "g")
                await rpc.GenerationControlStub(channel).CancelGeneration(
                    pb.CancelRequest(call_id=cid, generation_id=generation), timeout=1
                )
            with pytest.raises(grpc.aio.AioRpcError):
                while await call.read() != grpc.aio.EOF:
                    pass
            if kind == "agent":
                await rpc.AgentStub(channel).EndCall(
                    pb.CallEnd(call_id="one", reason="failed"), timeout=1
                )
            state(path, "drained\n")
            await until(lambda: gate.closed and not gate.active_rpcs and not service.active)
            inference = getattr(service, "inference", None)
            if inference is not None:
                await asyncio.gather(asyncio.shield(inference), return_exceptions=True)
            assert not await ready(channel)
            if kind != "asr":
                assert service.cleanup_failed

    asyncio.run(run())


@pytest.mark.parametrize("finished", [False, True])
def test_cancellation_does_not_hide_cleanup_failure_when_completion_races(finished):
    from alojan_contracts.generation import Generation, GenerationControl

    class Aborted(Exception):
        pass

    class Context:
        async def abort(self, code, detail):
            assert code == grpc.StatusCode.CANCELLED
            raise Aborted()

    async def run():
        entered = asyncio.Event()

        async def operation():
            entered.set()
            try:
                if not finished:
                    await asyncio.sleep(60)
            finally:
                raise RuntimeError("synthetic cleanup failure")

        task = asyncio.create_task(operation())
        await entered.wait()
        state = Generation()
        state.cancelled.set()
        control = GenerationControl()
        with pytest.raises(Aborted):
            await control.wait(task, state, Context())
        assert task.done() and control.cleanup_failed

    asyncio.run(run())
