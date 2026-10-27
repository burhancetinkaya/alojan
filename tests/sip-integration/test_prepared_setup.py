"""Actual SIP/RTP setup lifecycle with a scripted, private readiness peer; no inference."""

import math
import asyncio
import json
import re
import struct
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

from test_sip import ROOT, Peer, run_gateway, connect, pump_audio, assert_isolated_tone, drain_rtp
from test_speech import drive
from test_tts import SYNTHETIC_PROFILE
from alojan_contracts.configuration import EnginePreset
import test_call_initialization as initialization_tests

accounts = initialization_tests.accounts
database = initialization_tests.database
author = initialization_tests.author
published = initialization_tests.published
dedicated = initialization_tests.routing_tests.dedicated

DIDS = ("+908500000001", "+908500000002")
RELEASE = "00000000-0000-0000-0000-000000000001"


def wait_for(predicate, timeout=3):
    until = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < until, "setup lifecycle did not complete"
        time.sleep(0.01)


class Service(rpc.AgentServicer, rpc.GenerationControlServicer):
    def __init__(self, mode, gateway_profiles=None):
        self.mode = mode
        self.leases, self.routes, self.events, self.errors = {}, {}, [], []
        self.lock = threading.Lock()
        self.answers, self.ends = {}, {}
        self.gateway_profiles = gateway_profiles or dict.fromkeys(
            DIDS, EnginePreset(max_call_seconds=10, answer_delay_ms=100).gateway_configuration()
        )

    def event(self, name, request, context, leased=True):
        with self.lock:
            self.events.append((name, request.call_id))
            metadata = [(k, v) for k, v in context.invocation_metadata() if k == "x-alojan-lease"]
            valid = context.time_remaining() < 2 and (
                not leased or metadata == [("x-alojan-lease", self.leases.get(request.call_id))]
            )
            if not valid:
                self.errors.append(name)
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "invalid setup boundary")
        if self.mode == f"slow_{name}" or (
            self.mode == "total_deadline" and name in {"open", "initialize", "audio"}
        ):
            until = time.monotonic() + (0.7 if self.mode == "total_deadline" else 2)
            while context.is_active() and time.monotonic() < until:
                time.sleep(0.01)
        if self.mode == f"error_{name}":
            context.abort(grpc.StatusCode.UNAVAILABLE, "scripted failure")

    def OpenCall(self, request, context):
        self.event("open", request, context, leased=False)
        with self.lock:
            token = uuid.uuid4().hex
            self.leases[request.call_id] = token
        return pb.CallLeaseReply(lease=token)

    def InitializeCall(self, request, context):
        self.event("initialize", request, context)
        with self.lock:
            self.routes[request.call_id] = request
        return pb.CallInitializationReply(
            release_id=RELEASE,
            manifest_digest="a" * 64,
            ready_for_answer=self.mode != "not_ready",
            gateway=self.gateway_profiles[request.called_e164],
            synthesis=(
                pb.SynthesisConfiguration()
                if self.mode == "bad_synthesis"
                else pb.SynthesisConfiguration(schema_version=1, model="x" * 600)
                if self.mode == "oversized_synthesis"
                else SYNTHETIC_PROFILE.to_proto()
            ),
            recognition=pb.RecognitionConfiguration(
                schema_version=0 if self.mode == "bad_recognition" else 1,
                replacements={
                    "Merhaba dünya": "First Brand"
                    if request.called_e164 == DIDS[0]
                    else "Second Brand"
                },
            ),
        )

    def GetPreparedAudio(self, request, context):
        self.event("audio", request, context)
        with self.lock:
            route = self.routes[request.call_id]
        frequency = 440 if route.called_e164 == DIDS[0] else 880
        tone = b"".join(
            struct.pack("<h", int(9000 * math.sin(i * math.tau * frequency / 8000)))
            for i in range(8000)
        )
        return pb.PreparedAudioReply(
            call_id=request.call_id,
            release_id=request.release_id,
            manifest_digest="b" * 64 if self.mode == "wrong_digest" else request.manifest_digest,
            greeting_pcm=bytes(640) + tone * (10 if self.mode == "duration" else 2),
            unavailable_pcm=b"bad" if self.mode == "bad_audio" else tone,
            greeting_pad_ms=40,
        )

    def ReportCallAnswered(self, request, context):
        self.event("answered", request, context)
        with self.lock:
            self.answers[request.call_id] = request
        return pb.AgentAck(accepted=True)

    def EndCall(self, request, context):
        self.event("end", request, context)
        with self.lock:
            self.ends[request.call_id] = request
        return pb.AgentAck(accepted=True)

    def CancelCallSetup(self, request, context):
        self.event("cleanup", request, context)
        return pb.AgentAck(accepted=True)

    def ReleaseCall(self, request, context):
        self.event("release", request, context, leased=False)
        with self.lock:
            if self.leases.pop(request.call_id, None) != request.lease:
                self.errors.append("release_token")
        return pb.AgentAck(accepted=True)


@contextmanager
def gateway(
    tmp_path, mode="normal", recognition_port=0, synthesis_port=0, gateway_profiles=None, **changes
):
    service = Service(
        mode,
        gateway_profiles
        or dict.fromkeys(
            DIDS,
            EnginePreset(
                max_call_seconds=10, answer_delay_ms=changes.get("answer_delay_ms", 100)
            ).gateway_configuration(),
        ),
    )
    with ThreadPoolExecutor(max_workers=4) as workers:
        server = grpc.server(workers, maximum_concurrent_rpcs=8)
        rpc.add_AgentServicer_to_server(service, server)
        rpc.add_GenerationControlServicer_to_server(service, server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        config = (
            dict(
                speech_profile=True,
                max_call_seconds=10,
                answer_delay_ms=100,
                identity_options=["--trusted-identity-ip", "127.0.0.1"],
                speech_options=["--setup-test-agent-port", str(port)],
            )
            | changes
        )
        config["speech_options"] += [
            "--called-source",
            config.pop("called_selection", "request_uri"),
        ]
        if recognition_port:
            config["speech_options"] += ["--setup-test-asr-port", str(recognition_port)]
        if synthesis_port:
            config["speech_options"] += ["--setup-test-tts-port", str(synthesis_port)]
        try:
            with contextmanager(run_gateway)(tmp_path, config) as result:
                yield *result, service
        finally:
            server.stop(0).wait()
            assert not service.errors


def peer(port, index=0, codec=8):
    result = Peer(port, codec)
    result.request_user = DIDS[index]
    result.remote = f"<sip:{DIDS[1 - index]}@127.0.0.1>"
    return result


def bye(client):
    client.send("BYE", 2, branch="z9hG4bKbye" + client.id)
    client.response(200, "BYE")


def test_two_agents_have_independent_rtp_and_cleanup(tmp_path):
    with gateway(tmp_path, test_max_calls=2) as (port, log, _, service):
        first, second = peer(port), peer(port, 1, 0)
        try:
            media1, media2 = connect(first), connect(second)
            captured = pump_audio([(first, media1, 0xD5), (second, media2, 0xFF)], 0.7)
            assert_isolated_tone(captured[first], 8, 440, 880)
            assert_isolated_tone(captured[second], 0, 880, 440)
            bye(first)
            wait_for(lambda: len(service.leases) == 1)
            drain_rtp(second)
            frames, _, ended = drive(second, media2, log, duration=5)
            assert ended and frames
            wait_for(lambda: not service.leases)
            assert sorted(r.called_e164 for r in service.routes.values()) == list(DIDS)
            assert all(r.called_source == "request_uri" for r in service.routes.values())
            assert log.read_text().count("confirmed=1") == 2
            assert len(service.answers) == len(service.ends) == 2
            for cid, end in service.ends.items():
                assert end.answered_at_unix_ms == service.answers[cid].answered_at_unix_ms
                assert end.ended_at_unix_ms >= end.answered_at_unix_ms
                assert end.release_id == RELEASE and end.manifest_digest == "a" * 64
            assert not any(name == "cleanup" for name, _ in service.events)
            assert "playback=prepared_setup_test" in log.read_text()
            assert all(did not in log.read_text() for did in DIDS)
        finally:
            first.close()
            second.close()


@pytest.mark.parametrize(
    "mode",
    [
        "not_ready",
        "error_open",
        "error_initialize",
        "wrong_digest",
        "bad_audio",
        "slow_initialize",
        "slow_audio",
        "total_deadline",
        "duration",
    ],
)
def test_failure_never_answers_and_releases_slot(tmp_path, mode):
    with gateway(tmp_path, mode) as (port, log, _, service):
        client = peer(port)
        try:
            started = time.monotonic()
            client.invite()
            client.response(503)
            client.send("ACK")
            assert time.monotonic() - started < 2.8
            wait_for(lambda: "event=call_closed" in log.read_text())
            assert not service.leases
            assert "event=media_started" not in log.read_text()
            assert "state=CONNECTING" not in log.read_text()
            if mode == "not_ready":
                assert not any(name == "audio" for name, _ in service.events)
            service.mode = "normal"
            replacement = peer(port, 1)
            try:
                connect(replacement)
                bye(replacement)
                wait_for(lambda: not service.leases)
            finally:
                replacement.close()
        finally:
            client.close()


@pytest.mark.parametrize("phase", ["initialize", "audio", "ready"])
def test_cancel_during_setup_or_ringing_never_answers(tmp_path, phase):
    with gateway(
        tmp_path, "normal" if phase == "ready" else f"slow_{phase}", answer_delay_ms=3000
    ) as (port, log, _, service):
        client = peer(port)
        try:
            client.invite()
            client.response(180)
            wait_for(
                lambda: any(
                    name == ("audio" if phase == "ready" else phase) for name, _ in service.events
                )
            )
            if phase == "ready":
                time.sleep(0.1)
            client.send("CANCEL")
            client.response(200, "CANCEL")
            client.response(487)
            client.send("ACK")
            wait_for(lambda: "event=call_closed" in log.read_text())
            assert not service.leases
            assert "state=CONNECTING" not in log.read_text()
            assert "event=media_started" not in log.read_text()
            assert log.read_text().count("confirmed=1") == 1
        finally:
            client.close()


def test_pending_call_and_cleanup_hold_capacity_without_blocking_signaling(tmp_path):
    with gateway(tmp_path, "slow_initialize") as (port, log, _, service):
        first, blocked = peer(port), peer(port, 1)
        try:
            first.invite()
            first.response(180)
            wait_for(lambda: any(name == "initialize" for name, _ in service.events))
            service.mode = "slow_cleanup"
            first.send("CANCEL")
            first.response(200, "CANCEL")
            first.response(487)
            first.send("ACK")
            wait_for(lambda: any(name == "cleanup" for name, _ in service.events))
            started = time.monotonic()
            blocked.invite()
            blocked.response(486)
            blocked.send("ACK")
            assert time.monotonic() - started < 0.2
            wait_for(lambda: "event=setup_released" in log.read_text())
            assert "confirmed=0" in log.read_text()
            assert not service.leases
        finally:
            first.close()
            blocked.close()


@pytest.mark.parametrize("selection", ["request_uri", "to"])
def test_explicit_called_field_has_no_implicit_fallback(tmp_path, selection):
    with gateway(tmp_path) as (port, _, _, service):
        client = peer(port)
        client.request_user = "not-a-number"
        try:
            client.invite()
            client.response(404)
            client.send("ACK")
            assert not service.events  # A valid To cannot repair invalid Request-URI.
        finally:
            client.close()
    target = tmp_path / "selected"
    target.mkdir()
    with gateway(target, called_selection=selection) as (port, _, _, service):
        client = peer(port)
        try:
            connect(client)
            bye(client)
            wait_for(lambda: not service.leases)
            route = next(iter(service.routes.values()))
            assert route.called_e164 == DIDS[0 if selection == "request_uri" else 1]
            assert route.called_source == selection
        finally:
            client.close()


def test_untrusted_peer_never_reaches_initialization(tmp_path):
    with gateway(tmp_path, identity_options=["--trusted-identity-ip", "127.0.0.2"]) as (
        port,
        _,
        _,
        service,
    ):
        client = peer(port)
        try:
            client.invite()
            client.response(404)
            client.send("ACK")
            assert not service.events
        finally:
            client.close()


def test_shutdown_cancels_pending_setup_without_waiting_for_rpc_deadline(tmp_path):
    with gateway(tmp_path, "slow_initialize") as (port, log, process, service):
        client = peer(port)
        try:
            client.invite()
            client.response(180)
            wait_for(lambda: any(name == "initialize" for name, _ in service.events))
            started = time.monotonic()
            process.terminate()
            client.response(603)
            client.send("ACK")
            process.wait(timeout=3)
            assert time.monotonic() - started < 2
            assert not service.leases
            assert "event=media_started" not in log.read_text()
        finally:
            client.close()


@pytest.mark.parametrize(
    "extra",
    [
        [
            "--bind-address",
            "192.0.2.1",
            "--public-address",
            "192.0.2.1",
            "--allow-sip-ip",
            "127.0.0.1",
        ],
        ["--agent-port", "15073", "--speech-test-ms", "1000"],
    ],
)
def test_setup_profile_cannot_use_carrier_or_legacy_runtime(extra):
    result = subprocess.run(
        [
            str(ROOT / "build/local/voice-gateway"),
            "--setup-test-agent-port",
            "15073",
            "--trusted-identity-ip",
            "127.0.0.1",
        ]
        + extra,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1 and "event=ready" not in result.stdout


def test_ready_setup_preserves_ringing_delay_and_waits_for_ack(tmp_path):
    with gateway(tmp_path, answer_delay_ms=3000) as (port, log, _, service):
        client = peer(port)
        client.sip.settimeout(5)
        try:
            started = time.monotonic()
            client.invite()
            answer = client.response(200)
            assert 3 <= time.monotonic() - started < 4
            time.sleep(0.2)
            assert "event=media_started" not in log.read_text()
            assert not service.answers
            client.send("ACK", branch="z9hG4bKack" + client.id)
            media = int(re.search(r"m=audio (\d+)", answer)[1])
            assert pump_audio([(client, media, 0xD5)], 0.3)[client]
            bye(client)
            wait_for(lambda: not service.leases)
        finally:
            client.close()


def test_actual_agent_and_database_refuse_answer_until_runtime_is_ready(
    accounts, published, tmp_path
):
    from alojan.auth import connection
    from alojan_agent.prepared import PreparedReleases
    from alojan_agent.routing import CallRouter
    from alojan_agent.service import AgentService, create_server
    from test_agent import Script, MemoryStore
    import test_number_routing as routing_tests

    routing_tests.bound(accounts, published)

    def exercise(port):
        config = dict(
            speech_profile=True,
            answer_delay_ms=100,
            identity_options=["--trusted-identity-ip", "127.0.0.1"],
            speech_options=["--setup-test-agent-port", str(port)],
        )
        with contextmanager(run_gateway)(tmp_path, config) as (sip_port, log, _):
            client = peer(sip_port)
            client.request_user = routing_tests.DID
            try:
                client.invite()
                client.response(503)
                client.send("ACK")
                wait_for(lambda: "event=call_closed" in log.read_text())
                assert "confirmed=1" in log.read_text()
                assert "event=media_started" not in log.read_text()
                assert "state=CONNECTING" not in log.read_text()
            finally:
                client.close()

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with connection(accounts.dsn) as conn:
            manifest, digest = conn.execute(
                "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (published[3],)
            ).fetchone()
        await cache.preload(published[1], published[3], json.dumps(manifest), digest)
        service = AgentService(
            Script(),
            MemoryStore(),
            router=CallRouter(accounts.dsn, routing_tests.NODE),
            prepared=cache,
        )
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            await asyncio.to_thread(exercise, port)
            assert not cache.pins and not service.prepared_calls and not service.leases
            assert not service.backend.contexts and not service.store.ended
        finally:
            service.close_leases()
            await server.stop(0)
            await cache.close()

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT status,answered_at FROM calls").fetchone() == ("ended", None)
        for table in ("summary_jobs", "notification_outbox", "utterances"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.parametrize("failure", [None, "answer", "end"])
def test_native_ack_and_end_persist_through_scoped_repositories(
    accounts, published, tmp_path, dedicated, failure
):
    import test_answered_lifecycle as lifecycle
    import test_number_routing as routing_tests
    from alojan.auth import connection

    class PeerService(lifecycle.ReadyService):
        async def ReportCallAnswered(self, request, context):
            if failure == "answer":
                await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted missing answer write")
            return await super().ReportCallAnswered(request, context)

        async def EndCall(self, request, context):
            if failure == "end":
                await context.abort(grpc.StatusCode.UNAVAILABLE, "scripted missing end write")
            return await super().EndCall(request, context)

    routing_tests.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    def exercise(port):
        config = dict(
            speech_profile=True,
            answer_delay_ms=100,
            identity_options=["--trusted-identity-ip", "127.0.0.1"],
            speech_options=["--setup-test-agent-port", str(port)],
        )
        with contextmanager(run_gateway)(tmp_path, config) as (sip_port, log, _):
            client = peer(sip_port)
            client.request_user = routing_tests.DID
            client.sip.settimeout(5)  # The published preset retains the 3-second ring interval.
            try:
                media = connect(client)
                if failure == "answer":
                    _, __, ended = drive(client, media, log, duration=3)
                    assert ended
                else:
                    pump_audio([(client, media, 0xD5)], 0.3)
                    assert "event=media_started" in log.read_text()
                    started = time.monotonic()
                    bye(client)
                    assert time.monotonic() - started < 0.2
                wait_for(lambda: "event=call_closed" in log.read_text())
                assert ("confirmed=0" if failure == "end" else "confirmed=1") in log.read_text()
            finally:
                client.close()

    async def run():
        async with lifecycle.running(
            accounts, published, tmp_path, record_dsn, router_dsn, PeerService
        ) as (svc, port, _, __):
            await asyncio.to_thread(exercise, port)
            assert not svc.leases and not svc.routes and not svc.prepared_calls
            assert not svc.backend.contexts
            with connection(accounts.dsn) as c:
                assert c.execute("SELECT status,answered_at IS NOT NULL FROM calls").fetchone() == (
                    "active" if failure == "end" else "ended",
                    True,
                )
                if failure == "end":
                    assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (0,)
                    c.execute("UPDATE calls SET started_at=now()-interval '10 minutes'")
            if failure == "end":
                assert await svc.reconcile_stale(300) == 1
                assert await svc.reconcile_stale(300) == 0

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        duration, failure_code = c.execute("SELECT duration_ms,failure_code FROM calls").fetchone()
        if failure == "end":
            assert duration is None and failure_code == "missing_end_event"
        else:
            assert duration >= 0 and failure_code is None


def test_answer_recording_does_not_delay_prepared_audio_or_sip_hangup(tmp_path):
    with gateway(tmp_path, "slow_answered") as (port, log, _, service):
        client = peer(port)
        try:
            media = connect(client)
            frames = pump_audio([(client, media, 0xD5)], 0.25)[client]
            assert frames and "event=media_started" in log.read_text()
            # A-law positive/negative silence must not masquerade as prompt audio.
            assert sum(byte not in (0xD5, 0x55) for frame in frames for byte in frame[12:]) > 320
            assert not service.answers  # The recording RPC is still waiting.
            started = time.monotonic()
            bye(client)
            assert time.monotonic() - started < 0.2
            wait_for(lambda: not service.leases)
            assert len(service.ends) == 1
            end = next(iter(service.ends.values()))
            assert 0 < end.answered_at_unix_ms <= end.ended_at_unix_ms
        finally:
            client.close()


@pytest.mark.parametrize("option", ["--setup-test-asr-port", "--setup-test-tts-port"])
def test_speech_setup_port_requires_isolated_agent_profile(option):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), option, "15072"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "isolated setup test profile" in result.stderr
    assert "event=ready" not in result.stdout


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 0),
        ("schema_version", 2),
        ("max_call_seconds", 9),
        ("max_call_seconds", 301),
        ("answer_delay_ms", 5001),
        ("closing_delay_ms", 5001),
        ("media_drain_ms", 1001),
        ("max_call_turns", 0),
        ("max_call_turns", 17),
        ("turn_timeout_seconds", 0),
        ("turn_timeout_seconds", 21),
        ("output", None),
        ("output.schema_version", 2),
        ("output.phrase_max_chars", 39),
        ("output.phrase_max_chars", 241),
        ("output.phrase_max_bytes", 159),
        ("output.phrase_max_bytes", 1025),
        ("output.phrase_max_bytes", 959),
        ("output.max_phrases", 0),
        ("output.max_phrases", 17),
        ("output.turn_max_bytes", 1023),
        ("output.turn_max_bytes", 4097),
        ("calibration", None),
        ("calibration.schema_version", 2),
        ("calibration.vad_percent", 19),
        ("calibration.candidate_ms", 99),
        ("calibration.yes_no_ms", 349),
        ("calibration.open_ms", 499),
        ("calibration.uncertain_ms", 2001),
        ("calibration.incomplete_ms", 5001),
        ("calibration.silence_reminder_ms", 7001),
        ("calibration.interrupt_vad_percent", 91),
        ("calibration.interrupt_min_voice_ms", 193),
        ("calibration.interrupt_sustained_voice_ms", 1312),
        ("calibration.interrupt_max_quiet_ms", 801),
        ("calibration.interrupt_sustained_quiet_ms", 340),
        ("calibration.open_ms", 1500),
    ],
)
def test_invalid_gateway_settings_never_answer_or_fetch_audio(tmp_path, field, value):
    with gateway(tmp_path) as (port, log, _, service):
        profile = service.gateway_profiles[DIDS[0]]
        if field in {"calibration", "output"}:
            profile.ClearField(field)
        elif "." in field:
            section, member = field.split(".")
            setattr(getattr(profile, section), member, value)
        else:
            setattr(profile, field, value)
        client = peer(port)
        try:
            client.invite()
            client.response(503)
            client.send("ACK")
            wait_for(lambda: "event=call_closed" in log.read_text())
            assert not service.leases and not service.answers
            assert not any(name == "audio" for name, _ in service.events)
            assert "event=media_started" not in log.read_text()
            assert "confirmed=1" in log.read_text()
        finally:
            client.close()


def test_pinned_timing_is_call_local_and_overrides_legacy_cli(tmp_path):
    profiles = {
        DIDS[0]: EnginePreset(
            max_call_seconds=10, answer_delay_ms=800, media_drain_ms=0
        ).gateway_configuration(),
        DIDS[1]: EnginePreset(
            max_call_seconds=10, answer_delay_ms=0, media_drain_ms=1000
        ).gateway_configuration(),
    }
    with gateway(
        tmp_path,
        gateway_profiles=profiles,
        max_call_seconds=1,
        answer_delay_ms=0,
        test_max_calls=2,
    ) as (port, log, _, service):
        first, second = peer(port), peer(port, 1)
        try:
            started = time.monotonic()
            media1 = connect(first)
            assert 0.8 <= time.monotonic() - started < 1.5
            started = time.monotonic()
            media2 = connect(second)
            assert time.monotonic() - started < 0.5
            # Changing the source after admission cannot retime either active call.
            for profile in profiles.values():
                profile.media_drain_ms = 500
                profile.max_call_seconds = 300

            def finish(client, media):
                _, _, ended = drive(client, media, log, duration=6)
                assert ended
                return time.monotonic()

            with ThreadPoolExecutor(max_workers=2) as workers:
                one = workers.submit(finish, first, media1)
                two = workers.submit(finish, second, media2)
                first_end, second_end = one.result(), two.result()
            assert 0.7 < second_end - first_end < 1.5
            wait_for(lambda: not service.leases)
            assert "reason=max_duration" not in log.read_text()
            assert len(service.answers) == len(service.ends) == 2
        finally:
            first.close()
            second.close()


def test_pinned_call_duration_includes_wait_for_ack(tmp_path):
    with gateway(tmp_path, max_call_seconds=300) as (port, log, _, service):
        client = peer(port)
        try:
            started = time.monotonic()
            client.invite()
            answer = client.response(200)
            service.gateway_profiles[DIDS[0]].max_call_seconds = 300
            # Delayed ACK consumes the original call budget, not a fresh media budget.
            time.sleep(7.5)
            assert "event=media_started" not in log.read_text()
            client.send("ACK", branch="z9hG4bKack" + client.id)
            media = int(re.search(r"m=audio (\d+)", answer)[1])
            _, _, ended = drive(client, media, log, duration=4)
            assert ended and 9.8 < time.monotonic() - started < 11
            assert "reason=max_duration" in log.read_text()
            wait_for(lambda: not service.leases)
        finally:
            client.close()
