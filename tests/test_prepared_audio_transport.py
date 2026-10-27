"""Real private gRPC and native PCM rendering; synthetic speech, no SIP/GPU claims."""

import asyncio
from pathlib import Path

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

from alojan_agent.prepared import PreparedReleases
from test_call_initialization import running, setup, lease
from test_prepared_releases import release, preload

PROBE = Path(__file__).resolve().parents[1] / "build/local/prepared-audio-probe"


class Router:
    def __init__(self, route):
        self.route = route

    async def initialize(self, *args):
        return self.route

    async def cancel_unanswered(self, *args):
        return True


def audio_request(route, cid="managed-setup", **changes):
    return pb.PreparedAudioRequest(
        **(
            dict(call_id=cid, release_id=route.release_id, manifest_digest=route.manifest_digest)
            | changes
        )
    )


async def native(port, request, token, mode="success"):
    assert PROBE.exists(), "Build prepared-audio-probe on Linux before this suite"
    child = await asyncio.create_subprocess_exec(
        str(PROBE),
        str(port),
        mode,
        request.call_id,
        token,
        request.release_id,
        request.manifest_digest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(child.communicate(), 5)
    except BaseException:
        child.kill()
        await child.wait()
        raise
    assert child.returncode == 0, (stdout.decode(), stderr.decode())
    return stdout.decode()


def test_real_service_requires_exact_initialized_live_lease_and_never_reads_disk(tmp_path):
    fixture = release(tmp_path)
    route = fixture[0]

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        pack = await preload(cache, fixture)
        async with running(Router(route), cache) as (stub, control, service):
            headers = await lease(control)
            with pytest.raises(grpc.aio.AioRpcError):
                await stub.GetPreparedAudio(audio_request(route), timeout=1, metadata=headers)
            await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            (fixture[2] / "greeting.wav").unlink()
            for request, metadata, timeout in (
                (audio_request(route), (), 1),
                (audio_request(route), headers + headers, 1),
                (audio_request(route), (("x-alojan-lease", "wrong"),), 1),
                (audio_request(route), headers, None),
                (audio_request(route, "managed-other"), headers, 1),
                (audio_request(route, manifest_digest="0" * 64), headers, 1),
                (
                    audio_request(route, release_id="00000000-0000-0000-0000-000000000000"),
                    headers,
                    1,
                ),
            ):
                with pytest.raises(grpc.aio.AioRpcError):
                    await stub.GetPreparedAudio(request, timeout=timeout, metadata=metadata)
            received = await stub.GetPreparedAudio(
                audio_request(route), timeout=1, metadata=headers
            )
            assert received.greeting_pcm == pack.greeting_pcm
            assert received.unavailable_pcm == pack.unavailable_pcm
            assert received.greeting_pad_ms == 400
            assert not service.backend.contexts and not service.store.utterances
            await stub.CancelCallSetup(
                pb.CallSetupCancellation(call_id="managed-setup"), timeout=1, metadata=headers
            )
            with pytest.raises(grpc.aio.AioRpcError):
                await stub.GetPreparedAudio(audio_request(route), timeout=1, metadata=headers)
            assert not cache.pins
        await cache.close()

    asyncio.run(run())


def test_native_consumes_real_pinned_python_audio_for_two_agents(tmp_path):
    from alojan_agent.service import AgentService, create_server
    from test_agent import Script, MemoryStore

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        fixtures = [release(tmp_path, name=n) for n in ("First", "Second")]
        packs = [await preload(cache, f) for f in fixtures]
        router = Router(fixtures[0][0])
        service = AgentService(Script(), MemoryStore(), router=router, prepared=cache)
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub, control = rpc.AgentStub(channel), rpc.GenerationControlStub(channel)
                for index, (fixture, pack) in enumerate(zip(fixtures, packs)):
                    router.route = fixture[0]
                    cid = f"managed-native-{index}"
                    headers = await lease(control, cid)
                    result = await stub.InitializeCall(setup(cid), timeout=2, metadata=headers)
                    assert not result.ready_for_answer
                    output = await native(port, audio_request(fixture[0], cid), headers[0][1])
                    assert output.strip() == (
                        f"played={len(pack.greeting_pcm)},{len(pack.unavailable_pcm)} "
                        f"sums={sum(pack.greeting_pcm)},{sum(pack.unavailable_pcm)}"
                    )
                    await control.ReleaseCall(
                        pb.CallLeaseRequest(call_id=cid, lease=headers[0][1]), timeout=1
                    )
                assert not cache.pins and not service.prepared_calls
        finally:
            service.close_leases()
            await server.stop(0)
            await cache.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "damage",
    [
        "call",
        "release",
        "digest",
        "empty",
        "odd",
        "unaligned",
        "oversize",
        "clip_limit",
        "pad",
        "pad_alignment",
        "pad_audio",
        "silent",
        "rpc_error",
        "deadline",
        "cancel",
    ],
)
def test_native_rejects_malformed_or_late_reply_before_playback(tmp_path, damage):
    fixture = release(tmp_path)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        pack = await preload(cache, fixture)
        request = audio_request(fixture[0])
        called = asyncio.Event()

        class Peer(rpc.AgentServicer):
            async def GetPreparedAudio(self, incoming, context):
                assert incoming == request
                assert [
                    (k, v) for k, v in context.invocation_metadata() if k == "x-alojan-lease"
                ] == [("x-alojan-lease", "1" * 32)]
                assert 0 < context.time_remaining() <= 1.9
                called.set()
                if damage in {"deadline", "cancel"}:
                    await asyncio.sleep(2)
                if damage == "rpc_error":
                    await context.abort(grpc.StatusCode.UNAVAILABLE, "synthetic error")
                reply = pb.PreparedAudioReply(
                    call_id=request.call_id,
                    release_id=request.release_id,
                    manifest_digest=request.manifest_digest,
                    greeting_pcm=pack.greeting_pcm,
                    unavailable_pcm=pack.unavailable_pcm,
                    greeting_pad_ms=400,
                )
                if damage == "call":
                    reply.call_id = "managed-other"
                if damage == "release":
                    reply.release_id = "00000000-0000-0000-0000-000000000000"
                if damage == "digest":
                    reply.manifest_digest = "0" * 64
                if damage == "empty":
                    reply.unavailable_pcm = b""
                if damage == "odd":
                    reply.greeting_pcm = reply.greeting_pcm[:-1]
                if damage == "unaligned":
                    reply.greeting_pcm = reply.greeting_pcm[:-2]
                if damage == "oversize":
                    reply.greeting_pcm = b"x" * 1000001
                if damage == "clip_limit":
                    reply.unavailable_pcm = b"x" * 480320
                if damage == "pad":
                    reply.greeting_pad_ms = 1020
                if damage == "pad_alignment":
                    reply.greeting_pad_ms = 401
                if damage == "pad_audio":
                    reply.greeting_pcm = b"x" + reply.greeting_pcm[1:]
                if damage == "silent":
                    reply.unavailable_pcm = bytes(len(reply.unavailable_pcm))
                return reply

        server = grpc.aio.server()
        rpc.add_AgentServicer_to_server(Peer(), server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            assert (
                await native(
                    port,
                    request,
                    "1" * 32,
                    damage if damage in {"deadline", "cancel"} else "reject",
                )
            ).strip() == "prepared_audio_rejected"
            assert called.is_set()
        finally:
            await server.stop(0)
            await cache.close()

    asyncio.run(run())


def test_maximum_valid_pair_fits_actual_server_and_native_transport():
    from alojan_agent.service import create_server

    request = pb.PreparedAudioRequest(
        call_id="managed-maximum",
        release_id="00000000-0000-0000-0000-000000000001",
        manifest_digest="a" * 64,
    )

    class Peer(rpc.AgentServicer, rpc.GenerationControlServicer):
        async def GetPreparedAudio(self, incoming, context):
            assert incoming == request
            return pb.PreparedAudioReply(
                call_id=request.call_id,
                release_id=request.release_id,
                manifest_digest=request.manifest_digest,
                greeting_pcm=b"\x01\x00" * 240000,
                unavailable_pcm=b"\x02\x00" * 240000,
            )

    async def run():
        server = create_server(Peer())
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            assert (await native(port, request, "1" * 32)).strip() == (
                "played=480000,480000 sums=240000,480000"
            )
        finally:
            await server.stop(0)

    asyncio.run(run())
