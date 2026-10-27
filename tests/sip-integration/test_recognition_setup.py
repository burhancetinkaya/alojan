"""Native setup/bridge with real ASR/TTS RPC, scripted agent and inference."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

from alojan_asr.service import RecognitionService, create_server
from alojan_tts.service import SynthesisService, create_server as tts_server
from test_asr_configuration import VocabularyDecoder
from test_tts import SYNTHETIC_PROFILE
from test_prepared_setup import Service, DIDS, gateway, peer, connect, bye, wait_for, ROOT


class Recognition(RecognitionService):
    def __init__(self, mode="normal"):
        super().__init__(VocabularyDecoder(), require_agent_release=True)
        self.mode = mode
        self.entered = asyncio.Event()
        self.configured = []
        self.streams = []
        self.cancellations = []

    async def CancelGeneration(self, request, context):
        reply = await super().CancelGeneration(request, context)
        self.cancellations.append(request.generation_id)
        return reply

    async def OpenCall(self, request, context):
        if self.mode == "slow_open":
            await asyncio.sleep(2)
        reply = await super().OpenCall(request, context)
        if self.mode == "lost_open":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        return reply

    async def ConfigureCall(self, request, context):
        self.entered.set()
        if self.mode == "slow_configure":
            await asyncio.sleep(2)
        if self.mode == "budget":
            await asyncio.sleep(0.7)
        if self.mode in {"error_configure", "old_worker"}:
            await context.abort(
                grpc.StatusCode.UNAVAILABLE
                if self.mode == "error_configure"
                else grpc.StatusCode.UNIMPLEMENTED,
                "scripted failure",
            )
        if self.mode == "reject":
            return pb.AgentAck(accepted=False)
        reply = await super().ConfigureCall(request, context)
        self.configured.append(request)
        if self.mode == "lost_configure":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        return reply

    async def ReleaseCall(self, request, context):
        reply = await super().ReleaseCall(request, context)
        if self.mode == "lost_release":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        return reply

    async def StreamRecognize(self, iterator, context):
        async def observed():
            first = True
            async for frame in iterator:
                if first:
                    self.streams.append((frame.call_id, frame.generation_id))
                    first = False
                yield frame

        await super().StreamRecognize(observed(), context)


@asynccontextmanager
async def recognition(mode="normal"):
    service = Recognition(mode)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        yield service, port
    finally:
        service.close_leases()
        await server.stop(0)
        if service.inference:
            await asyncio.shield(service.inference)
        service.close()


def test_native_sip_configures_independent_service_leases_before_answer(tmp_path):
    async def run():
        async with recognition() as (asr, asr_port), synthesis() as (tts, tts_port):

            def scenario():
                with gateway(
                    tmp_path, recognition_port=asr_port, synthesis_port=tts_port, test_max_calls=2
                ) as (
                    port,
                    log,
                    _,
                    agent,
                ):
                    clients = [peer(port, i) for i in range(2)]
                    try:
                        for client in clients:
                            connect(client)
                        assert len(tts.configurations) == 2
                        assert all(
                            r.configuration == SYNTHETIC_PROFILE.to_proto() for r in tts.configured
                        )
                        assert len(asr.configurations) == 2
                        assert {
                            dict(r.configuration.replacements)["Merhaba dünya"]
                            for r in asr.configured
                        } == {"First Brand", "Second Brand"}
                        assert all(
                            asr.leases[cid][0] != token for cid, token in agent.leases.items()
                        )
                        assert all(
                            len({token, asr.leases[cid][0], tts.leases[cid][0]}) == 3
                            for cid, token in agent.leases.items()
                        )
                        for client in clients:
                            bye(client)
                        wait_for(lambda: not asr.leases and not agent.leases and not tts.leases)
                        wait_for(lambda: log.read_text().count("confirmed=1") == 2)
                        assert not asr.configurations
                    finally:
                        for client in clients:
                            client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode",
    [
        "error_configure",
        "old_worker",
        "reject",
        "lost_configure",
        "slow_configure",
        "slow_open",
        "budget",
        "bad_recognition",
    ],
)
def test_asr_setup_failure_cannot_answer_or_play_audio(tmp_path, mode):
    async def run():
        async with recognition(mode) as (asr, asr_port):

            def scenario():
                agent_mode = (
                    "total_deadline"
                    if mode == "budget"
                    else "bad_recognition"
                    if mode == "bad_recognition"
                    else "normal"
                )
                with gateway(tmp_path, agent_mode, recognition_port=asr_port) as (
                    port,
                    log,
                    _,
                    agent,
                ):
                    client = peer(port)
                    try:
                        started = time.monotonic()
                        client.invite()
                        client.response(503)
                        client.send("ACK")
                        assert time.monotonic() - started < 2.6
                        wait_for(lambda: "event=call_closed" in log.read_text())
                        assert not asr.leases and not asr.configurations and not agent.leases
                        assert "event=media_started" not in log.read_text()
                        assert "state=CONNECTING" not in log.read_text()
                        assert not any(name == "audio" for name, _ in agent.events)
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_cancel_interrupts_asr_configuration_and_releases_both_leases(tmp_path):
    async def run():
        async with recognition("slow_configure") as (asr, asr_port):

            def scenario():
                with gateway(tmp_path, recognition_port=asr_port) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        client.invite()
                        client.response(180)
                        wait_for(asr.entered.is_set)
                        started = time.monotonic()
                        client.send("CANCEL")
                        client.response(200, "CANCEL")
                        client.response(487)
                        client.send("ACK")
                        assert time.monotonic() - started < 0.3
                        wait_for(lambda: "confirmed=1" in log.read_text(), timeout=1)
                        assert not asr.leases and not agent.leases and not asr.configurations
                        assert "event=media_started" not in log.read_text()
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_uncertain_asr_release_is_not_reported_as_confirmed_cleanup(tmp_path):
    async def run():
        async with recognition("lost_release") as (asr, asr_port):

            def scenario():
                with gateway(tmp_path, recognition_port=asr_port) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        connect(client)
                        bye(client)
                        wait_for(lambda: "confirmed=0" in log.read_text())
                        assert not asr.leases and not agent.leases
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


class Conversation(Service):
    def __init__(self, mode="normal"):
        super().__init__("normal")
        self.conversation_mode = mode
        if mode in {"calibration", "interrupt_calibration"}:
            for did, pause in zip(DIDS, (900, 1200)):
                profile = pb.GatewayConfiguration()
                profile.CopyFrom(self.gateway_profiles[did])
                profile.calibration.vad_percent = 20
                profile.calibration.open_ms = pause
                profile.calibration.partial_hint = True
                profile.calibration.interrupt_vad_percent = 20
                profile.calibration.interrupt_min_voice_ms = 320
                self.gateway_profiles[did] = profile
        if mode.startswith("output_"):
            for did, width, count, total in zip(DIDS, (40, 80), (1, 2), (1024, 4096)):
                profile = pb.GatewayConfiguration()
                profile.CopyFrom(self.gateway_profiles[did])
                if mode in {"output_chars", "output_boundary"}:
                    profile.output.phrase_max_chars = width
                if mode == "output_count":
                    profile.output.max_phrases = count
                if mode == "output_total":
                    profile.output.turn_max_bytes = total
                self.gateway_profiles[did] = profile
        if mode == "limit":
            for did, turns in zip(DIDS, (1, 2)):
                profile = pb.GatewayConfiguration()
                profile.CopyFrom(self.gateway_profiles[did])
                profile.max_call_turns = turns
                self.gateway_profiles[did] = profile
        if mode == "deadline":
            for profile in self.gateway_profiles.values():
                profile.turn_timeout_seconds = 1
        self.texts = []
        self.deadlines = []
        self.playback = []
        self.cancellations = []

    def check_lease(self, request, context):
        metadata = [(k, v) for k, v in context.invocation_metadata() if k == "x-alojan-lease"]
        if metadata != [("x-alojan-lease", self.leases.get(request.call_id))]:
            self.errors.append("conversation_lease")
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "invalid conversation lease")

    def CancelGeneration(self, request, context):
        self.check_lease(request, context)
        self.cancellations.append(request.generation_id)
        return pb.CancelReply(cancelled=True)

    def RunTurn(self, request, context):
        self.check_lease(request, context)
        self.texts.append(request.final_user_text)
        self.deadlines.append(context.time_remaining())
        if self.conversation_mode == "deadline":
            until = time.monotonic() + 2
            while context.is_active() and time.monotonic() < until:
                time.sleep(0.01)
            return
        response = (
            "𐐀" * (40 if self.conversation_mode == "output_boundary" else 41)
            if self.conversation_mode in {"output_chars", "output_boundary"}
            else "ğ" * 240
            if self.conversation_mode == "output_total"
            else "Synthetic response"
        )
        for index in range(3 if self.conversation_mode == "output_total" else 2):
            yield pb.AgentEvent(
                call_id=request.call_id,
                generation_id=request.generation_id,
                type="text_delta",
                text=response,
                detail_json='{"phrase_index":%d}' % index,
            )
        yield pb.AgentEvent(
            call_id=request.call_id,
            generation_id=request.generation_id,
            type="end",
            detail_json=json_end(request.generation_id),
        )

    def ReportPlayback(self, request, context):
        self.check_lease(request, context)
        self.playback.append(request)
        return pb.AgentAck(accepted=True)


class Synthesis(SynthesisService):
    def __init__(self, mode="normal"):
        self.synthesis_profile = (
            replace(SYNTHETIC_PROFILE, model_revision="b" * 40)
            if mode == "wrong_revision"
            else SYNTHETIC_PROFILE
        )
        super().__init__(self, require_agent_release=True)
        self.configured = []
        self.configure_entered = asyncio.Event()
        self.mode = mode
        self.entered = asyncio.Event()
        self.opened = []
        self.requests = []
        self.cancellations = []

    def stream(self, text):
        time.sleep(0.15)
        for _ in range(
            100
            if self.mode == "cancel_stream"
            else 30
            if self.mode == "interrupt_calibration"
            else 2
        ):
            yield b"\x01\x00" * 160
            if self.mode in {"cancel_stream", "interrupt_calibration"}:
                time.sleep(0.02)

    async def OpenCall(self, request, context):
        self.entered.set()
        if self.mode in {"slow_open", "budget"}:
            await asyncio.sleep(2 if self.mode == "slow_open" else 0.7)
        if self.mode == "unavailable":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted unavailable worker")
        reply = await super().OpenCall(request, context)
        self.opened.append(reply.lease)
        if self.mode == "lost_open":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        if self.mode == "invalid_token":
            reply.lease = "invalid"
        return reply

    async def ConfigureCall(self, request, context):
        self.configure_entered.set()
        if self.mode in {"slow_configure", "configure_budget"}:
            await asyncio.sleep(2 if self.mode == "slow_configure" else 0.7)
        if self.mode == "old_worker":
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "old synthesis worker")
        if self.mode == "reject_configure":
            return pb.AgentAck(accepted=False)
        reply = await super().ConfigureCall(request, context)
        self.configured.append(request)
        if self.mode == "lost_configure":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        return reply

    async def ReleaseCall(self, request, context):
        reply = await super().ReleaseCall(request, context)
        if self.mode == "lost_release":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted lost acknowledgement")
        return reply

    async def StreamSynthesize(self, request, context):
        await self.require_lease(request.call_id, context)
        self.requests.append(request)
        await super().StreamSynthesize(request, context)

    async def CancelGeneration(self, request, context):
        reply = await super().CancelGeneration(request, context)
        self.cancellations.append(request.generation_id)
        return reply


@asynccontextmanager
async def synthesis(mode="normal"):
    service = Synthesis(mode)
    server = tts_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        yield service, port
    finally:
        service.close_leases()
        await server.stop(0)
        if service.inference:
            await asyncio.shield(service.inference)
        service.close()


def json_end(generation):
    return '{"finish_call":true}' if generation == "turn-2" else '{"finish_call":false}'


@contextmanager
def conversation(mode="normal"):
    service = Conversation(mode)
    with ThreadPoolExecutor(max_workers=4) as workers:
        server = grpc.server(workers)
        rpc.add_AgentServicer_to_server(service, server)
        rpc.add_GenerationControlServicer_to_server(service, server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            yield service, port
        finally:
            server.stop(0).wait()
            assert not service.errors


@pytest.mark.parametrize("mode", ["normal", "monitor", "cancel_stream"])
def test_native_bridge_keeps_service_leases_across_turns_phrases_and_cancellation(mode):
    monitor = mode == "monitor"
    cancelled = mode == "cancel_stream"

    async def run():
        async with recognition() as (asr, asr_port), synthesis(mode) as (tts, tts_port):
            with conversation() as (agent, agent_port):
                for did, expected in zip(DIDS, ("First Brand", "Second Brand")):
                    child = await asyncio.create_subprocess_exec(
                        str(ROOT / "build/local/recognition-setup-probe"),
                        str(agent_port),
                        str(asr_port),
                        str(tts_port),
                        did,
                        *(["cancel"] if cancelled else ["monitor"] if monitor else []),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        out, err = await asyncio.wait_for(child.communicate(), 10)
                    except BaseException:
                        child.kill()
                        await child.wait()
                        raise
                    assert child.returncode == 0, (out.decode(), err.decode())
                    assert b"configured_turns=1 released=1" in out
                    turns = 1 if cancelled else 2
                    assert agent.texts[-turns:] == [expected + ", 1234. Evet."] * turns
                    assert not tts.leases and not tts.generations and not tts.configurations
                    assert len(agent.ends) == 1
                    end = next(iter(agent.ends.values()))
                    assert end.reason == ("disconnected" if cancelled else "completed")
                    assert end.ended_at_unix_ms >= end.answered_at_unix_ms > 0
                    assert not asr.configurations and not asr.leases and not agent.leases
                expected_generations = (
                    ["turn-1", "turn-1-monitor", "turn-2", "turn-2-monitor"]
                    if monitor
                    else ["turn-1", "turn-2"]
                )
                if cancelled:
                    expected_generations = ["turn-1"]
                assert [generation for _, generation in asr.streams] == expected_generations * 2
                assert (
                    agent.cancellations == (["turn-1"] if cancelled else ["turn-1", "turn-2"]) * 2
                )
                assert [name for name, _ in agent.events].count("end") == 2
                assert [(r.generation_id, r.phrase_index) for r in agent.playback] == (
                    [("turn-1", 0)]
                    if cancelled
                    else [(f"turn-{turn}", index) for turn in (1, 2) for index in (0, 1)]
                ) * 2
                assert [r.generation_id for r in tts.requests] == (
                    ["turn-1-p0"]
                    if cancelled
                    else [f"turn-{turn}-p{index}" for turn in (1, 2) for index in (0, 1)]
                ) * 2
                assert (
                    tts.cancellations == (["turn-1-p0", "turn-1"] if cancelled else ["turn-1"]) * 2
                )
                assert all(r.completed != cancelled for r in agent.playback)
                if monitor:
                    assert asr.cancellations == ["turn-1-monitor", "turn-2-monitor"] * 2

    asyncio.run(run())


def test_lost_asr_open_reply_keeps_cleanup_uncertain_until_lease_expiry(tmp_path):
    async def run():
        async with recognition("lost_open") as (asr, asr_port):

            def scenario():
                with gateway(tmp_path, recognition_port=asr_port) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        client.invite()
                        client.response(503)
                        client.send("ACK")
                        wait_for(lambda: "confirmed=0" in log.read_text())
                        assert len(asr.leases) == 1 and not asr.configurations
                        assert not agent.leases and "event=media_started" not in log.read_text()
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode", ["unavailable", "slow_open", "budget", "lost_open", "invalid_token"]
)
def test_tts_setup_failure_cannot_answer_or_fetch_audio(tmp_path, mode):
    async def run():
        async with recognition() as (asr, asr_port), synthesis(mode) as (tts, tts_port):

            def scenario():
                with gateway(
                    tmp_path,
                    "total_deadline" if mode == "budget" else "normal",
                    recognition_port=asr_port,
                    synthesis_port=tts_port,
                ) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        started = time.monotonic()
                        client.invite()
                        client.response(503)
                        client.send("ACK")
                        assert time.monotonic() - started < 2.6
                        wait_for(lambda: "event=call_closed" in log.read_text())
                        assert not asr.leases and not agent.leases
                        assert "event=media_started" not in log.read_text()
                        assert not any(name == "audio" for name, _ in agent.events)
                        # An unsuccessful OpenCall cannot prove the server created no lease.
                        assert "confirmed=0" in log.read_text()
                        assert len(tts.leases) == int(mode in {"lost_open", "invalid_token"})
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_cancel_during_tts_open_is_nonblocking_and_cleans_known_leases(tmp_path):
    async def run():
        async with recognition() as (asr, asr_port), synthesis("slow_open") as (tts, tts_port):

            def scenario():
                with gateway(tmp_path, recognition_port=asr_port, synthesis_port=tts_port) as (
                    port,
                    log,
                    _,
                    agent,
                ):
                    client = peer(port)
                    try:
                        client.invite()
                        client.response(180)
                        wait_for(tts.entered.is_set)
                        started = time.monotonic()
                        client.send("CANCEL")
                        client.response(200, "CANCEL")
                        client.response(487)
                        client.send("ACK")
                        assert time.monotonic() - started < 0.3
                        wait_for(lambda: "confirmed=0" in log.read_text())
                        assert not asr.leases and not agent.leases and not tts.leases
                        assert "event=media_started" not in log.read_text()
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_lost_tts_release_reply_keeps_cleanup_uncertain(tmp_path):
    async def run():
        async with synthesis("lost_release") as (tts, tts_port):

            def scenario():
                with gateway(tmp_path, synthesis_port=tts_port) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        connect(client)
                        bye(client)
                        wait_for(lambda: "confirmed=0" in log.read_text())
                        assert not tts.leases and not agent.leases
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_agent_lease_cannot_authorize_tts_and_no_unleased_fallback():
    async def run():
        async with recognition() as (asr, asr_port), synthesis() as (tts, tts_port):
            with conversation() as (agent, agent_port):
                child = await asyncio.create_subprocess_exec(
                    str(ROOT / "build/local/recognition-setup-probe"),
                    str(agent_port),
                    str(asr_port),
                    str(tts_port),
                    DIDS[0],
                    "wrong_tts",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    out, err = await asyncio.wait_for(child.communicate(), 10)
                except BaseException:
                    child.kill()
                    await child.wait()
                    raise
                assert child.returncode == 1, (out.decode(), err.decode())
                assert b"configured_turns=0 released=1" in out
                assert not tts.requests and not tts.leases and not tts.generations
                assert not asr.leases and not agent.leases
                assert len(agent.playback) == 1
                assert agent.playback[0].sent_audio_ms == 0
                assert not agent.playback[0].completed
                assert len(agent.ends) == 1
                assert next(iter(agent.ends.values())).reason == "failed"

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode",
    [
        "wrong_revision",
        "old_worker",
        "reject_configure",
        "lost_configure",
        "slow_configure",
        "configure_budget",
        "bad_synthesis",
        "oversized_synthesis",
    ],
)
def test_tts_configuration_failure_never_answers_or_uses_prepared_audio(tmp_path, mode):
    async def run():
        async with recognition() as (asr, asr_port), synthesis(mode) as (tts, tts_port):

            def scenario():
                with gateway(
                    tmp_path,
                    "total_deadline"
                    if mode == "configure_budget"
                    else mode
                    if mode in {"bad_synthesis", "oversized_synthesis"}
                    else "normal",
                    recognition_port=asr_port,
                    synthesis_port=tts_port,
                ) as (port, log, _, agent):
                    client = peer(port)
                    try:
                        started = time.monotonic()
                        client.invite()
                        client.response(503)
                        client.send("ACK")
                        assert time.monotonic() - started < 2.6
                        wait_for(lambda: "confirmed=1" in log.read_text())
                        assert not tts.leases and not tts.configurations and not tts.requests
                        assert not asr.leases and not agent.leases
                        assert "event=media_started" not in log.read_text()
                        assert not any(name == "audio" for name, _ in agent.events)
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


def test_cancel_interrupts_tts_configuration_and_releases_all_known_leases(tmp_path):
    async def run():
        async with recognition() as (asr, asr_port), synthesis("slow_configure") as (tts, tts_port):

            def scenario():
                with gateway(tmp_path, recognition_port=asr_port, synthesis_port=tts_port) as (
                    port,
                    log,
                    _,
                    agent,
                ):
                    client = peer(port)
                    try:
                        client.invite()
                        client.response(180)
                        wait_for(tts.configure_entered.is_set)
                        started = time.monotonic()
                        client.send("CANCEL")
                        client.response(200, "CANCEL")
                        client.response(487)
                        client.send("ACK")
                        assert time.monotonic() - started < 0.3
                        wait_for(lambda: "confirmed=1" in log.read_text())
                        assert not tts.leases and not tts.configurations
                        assert not asr.leases and not agent.leases
                        assert "event=media_started" not in log.read_text()
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["limit", "deadline"])
def test_native_bridge_consumes_pinned_turn_limits(mode):
    async def run():
        async with recognition() as (asr, asr_port), synthesis() as (tts, tts_port):
            with conversation(mode) as (agent, agent_port):
                for index, did in enumerate(DIDS):
                    before = len(agent.texts)
                    child = await asyncio.create_subprocess_exec(
                        str(ROOT / "build/local/recognition-setup-probe"),
                        str(agent_port),
                        str(asr_port),
                        str(tts_port),
                        did,
                        mode,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        out, err = await asyncio.wait_for(child.communicate(), 10)
                    except BaseException:
                        child.kill()
                        await child.wait()
                        raise
                    assert child.returncode == 0, (out.decode(), err.decode())
                    assert b"configured_turns=1 released=1" in out
                    assert len(agent.texts) - before == (index + 1 if mode == "limit" else 1)
                    assert not asr.leases and not tts.leases and not agent.leases
                    if mode == "deadline":
                        assert 0.5 < agent.deadlines[-1] <= 1.1
                        assert not tts.requests and not agent.playback

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["calibration", "interrupt_calibration"])
def test_native_bridge_consumes_release_calibration_instead_of_legacy_settings(mode):
    async def run():
        async with recognition() as (asr, asr_port), synthesis(mode) as (tts, tts_port):
            with conversation(mode) as (agent, agent_port):
                for did in DIDS:
                    child = await asyncio.create_subprocess_exec(
                        str(ROOT / "build/local/recognition-setup-probe"),
                        str(agent_port),
                        str(asr_port),
                        str(tts_port),
                        did,
                        mode,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        out, err = await asyncio.wait_for(child.communicate(), 10)
                    except BaseException:
                        child.kill()
                        await child.wait()
                        raise
                    assert child.returncode == 0, (out.decode(), err.decode())
                    assert b"configured_turns=1 released=1" in out
                    assert not asr.leases and not tts.leases and not agent.leases
                    if mode == "interrupt_calibration":
                        assert "turn-1" in agent.cancellations
                        assert "turn-1-p0" in tts.cancellations

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode", ["output_chars", "output_boundary", "output_count", "output_total"]
)
def test_native_output_budget_is_call_local_and_rejects_before_tts(mode):
    async def run():
        async with recognition() as (asr, asr_port), synthesis() as (tts, tts_port):
            with conversation(mode) as (agent, agent_port):
                for index, did in enumerate(DIDS):
                    rejected = index == 0 and mode != "output_boundary"
                    before_requests, before_playback = len(tts.requests), len(agent.playback)
                    child = await asyncio.create_subprocess_exec(
                        str(ROOT / "build/local/recognition-setup-probe"),
                        str(agent_port),
                        str(asr_port),
                        str(tts_port),
                        did,
                        "output_rejected" if rejected else "normal",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        out, err = await asyncio.wait_for(child.communicate(), 10)
                    except BaseException:
                        child.kill()
                        await child.wait()
                        raise
                    assert child.returncode == 0, (out.decode(), err.decode())
                    assert b"configured_turns=1 released=1" in out
                    allowed = 0 if mode == "output_chars" else 1 if mode == "output_count" else 2
                    requests = tts.requests[before_requests:]
                    receipts = agent.playback[before_playback:]
                    if rejected:
                        assert len(requests) <= allowed
                        assert all(r.phrase_index < allowed for r in receipts)
                    else:
                        phrases = 3 if mode == "output_total" else 2
                        assert len(requests) == 2 * phrases
                        assert len(receipts) == 2 * phrases and all(r.completed for r in receipts)
                    assert not tts.leases and not tts.configurations and not agent.leases
                    assert not asr.leases and not asr.configurations

    asyncio.run(run())
