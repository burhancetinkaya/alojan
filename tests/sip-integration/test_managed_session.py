"""Full native Session with scoped agent/records and synthetic inference/readiness."""

import asyncio
import json
import time
from contextlib import contextmanager

import pytest

from alojan.auth import connection
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_agent.models import Note
from test_agent_drafts import content
from test_agent_releases import prepare_assets
from test_native_auth import register
import test_number_routing as routing
from test_answered_lifecycle import ReadyService, running
from test_recognition_setup import recognition, synthesis
from test_sip import Peer, connect, run_gateway
from test_speech import drive
from test_prepared_setup import wait_for

accounts = routing.accounts
database = routing.database
author = routing.author
published = routing.published
dedicated = routing.dedicated


class ObservedReady(ReadyService):
    async def ReportPlayback(self, request, context):
        reply = await super().ReportPlayback(request, context)
        self.playback.append((request, time.monotonic()))
        return reply

    async def EndCall(self, request, context):
        # Leases must survive until all native generation cancellations finish.
        assert self.backend.closed == self.backend.started
        self.ended.append(request)
        return await super().EndCall(request, context)


class Script:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.started = self.closed = 0
        self.runtimes = []
        self.entered = asyncio.Event()

    async def stream(self, call, save_note):
        self.started += 1
        self.runtimes.append(call.runtime)
        self.entered.set()
        try:
            if self.mode == "failure":
                raise ValueError("synthetic failure")
            if self.mode == "blocked":
                await asyncio.sleep(60)
            call.finish = call.turns == 2
            if call.turns == 1:
                note = Note(subject=call.runtime.name, message="Synthetic managed request.")
                version = call.take_note(note)
                call.note_id = await save_note(note, version)
                yield call.runtime.name + " sizi dinliyor."
            else:
                yield call.runtime.speech.farewell
        finally:
            self.closed += 1


def config(agent, asr, tts, **changes):
    return (
        dict(
            speech_profile=True,
            identity_options=["--trusted-identity-ip", "127.0.0.1"],
            speech_options=[
                "--setup-test-agent-port",
                str(agent),
                "--setup-test-asr-port",
                str(asr),
                "--setup-test-tts-port",
                str(tts),
                "--setup-test-conversation",
                "1",
                "--speech-test-ms",
                "1000",
            ],
        )
        | changes
    )


def bind(accounts, published, did):
    token, scope, _, release = published
    number = routing.verified(accounts, token, scope, did)
    routing.ready(accounts, scope, release)
    routing.Numbers(accounts, routing.NODE).bind(token, scope, number, release, 2)


def test_two_workspaces_complete_managed_calls_with_pinned_identity_and_records(
    accounts, published, tmp_path, dedicated
):
    token = register(accounts, "second.owner")
    scope = accounts.session(token)["workspaces"][0]["id"]
    agent = Profiles(accounts).create(token, scope, content("Other Assistant", "Other Owner"))["id"]
    other_author = token, scope, agent
    preparation, _, _ = prepare_assets(accounts, other_author, tmp_path)
    other = (
        *other_author,
        Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"],
    )
    for profile, did in zip((published, other), (routing.DID, routing.OTHER_DID)):
        bind(accounts, profile, did)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with (
            running(accounts, published, tmp_path, record_dsn, router_dsn, ObservedReady) as (
                service,
                agent_port,
                _,
                __,
            ),
            recognition() as (asr, asr_port),
            synthesis() as (tts, tts_port),
        ):
            with connection(accounts.dsn) as c:
                manifest, digest = c.execute(
                    "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (other[3],)
                ).fetchone()
            await service.prepared.preload(other[1], other[3], json.dumps(manifest), digest)
            service.backend = Script()
            service.playback, service.ended = [], []

            def scenario():
                with contextmanager(run_gateway)(
                    tmp_path, config(agent_port, asr_port, tts_port)
                ) as (port, log, _):
                    for did, codec in ((routing.DID, 8), (routing.OTHER_DID, 0)):
                        client = Peer(port, codec)
                        client.request_user = did
                        client.sip.settimeout(5)
                        try:
                            media = connect(client)
                            _, _, ended = drive(client, media, log, duration=15)
                            assert ended, log.read_text()
                            assert 3 <= time.monotonic() - service.playback[-1][1] < 4
                            wait_for(
                                lambda: not service.leases and not asr.leases and not tts.leases
                            )
                        finally:
                            client.close()
                    assert log.read_text().count("event=speech_test_capture") == 2
                    assert log.read_text().count("event=speech_test_complete") == 2
                    assert "event=speech_fallback" not in log.read_text()
                    wait_for(lambda: log.read_text().count("confirmed=1") == 2)
                    assert all(
                        did not in log.read_text() for did in (routing.DID, routing.OTHER_DID)
                    )

            await asyncio.to_thread(scenario)
            assert [r.name for r in service.backend.runtimes] == ["Example Assistant"] * 2 + [
                "Other Assistant"
            ] * 2
            assert [r.text for r in tts.requests] == [
                "Example Assistant sizi dinliyor.",
                "Rica ederim, iyi günler.",
                "Other Assistant sizi dinliyor.",
                "Rica ederim, iyi günler.",
            ]
            assert len(service.ended) == 2 and all(r.reason == "completed" for r in service.ended)
            assert all(r.completed and r.sent_audio_ms == 40 for r, _ in service.playback)
            assert not service.calls and not service.routes and not service.answered_calls
            assert not tts.configurations and not asr.configurations

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        rows = c.execute(
            "SELECT s.scope_id,s.release_id,c.status,n.text::jsonb->>'subject' FROM calls c JOIN call_route_snapshots s ON s.call_id=c.id JOIN notes n ON n.call_id=c.id ORDER BY n.text::jsonb->>'subject'"
        ).fetchall()
        assert [
            (str(scope), str(release), status, name) for scope, release, status, name in rows
        ] == [
            (str(published[1]), str(published[3]), "ended", "Example Assistant"),
            (str(other[1]), str(other[3]), "ended", "Other Assistant"),
        ]
        assert c.execute(
            "SELECT count(*) FROM utterances WHERE speaker='assistant' AND audio_sent_end_ms=40"
        ).fetchone() == (4,)
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (2,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


@pytest.mark.parametrize("mode", ["failure", "blocked", "greeting", "answer_failure"])
def test_managed_session_failure_and_disconnect_preserve_cleanup(
    accounts, published, tmp_path, dedicated, mode
):
    bind(accounts, published, routing.DID)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    class Service(ObservedReady):
        async def ReportCallAnswered(self, request, context):
            if mode == "answer_failure":
                await asyncio.sleep(0.8)
            return await super().ReportCallAnswered(request, context)

    async def run():
        async with (
            running(accounts, published, tmp_path, record_dsn, router_dsn, Service) as (
                service,
                agent_port,
                _,
                __,
            ),
            recognition() as (asr, asr_port),
            synthesis() as (tts, tts_port),
        ):
            service.backend = Script(mode)
            service.playback, service.ended = [], []

            def scenario():
                with contextmanager(run_gateway)(
                    tmp_path, config(agent_port, asr_port, tts_port)
                ) as (port, log, _):
                    client = Peer(port)
                    client.sip.settimeout(5)
                    client.request_user = routing.DID
                    try:
                        media = connect(client)
                        if mode in {"failure", "answer_failure"}:
                            _, _, ended = drive(client, media, log, duration=10)
                            assert ended, log.read_text()
                            if mode == "failure":
                                assert "event=speech_fallback" in log.read_text()
                                assert "reason=dependencies_unavailable" in log.read_text()
                            else:
                                assert "event=speech_test_capture" not in log.read_text()
                        else:
                            drive(
                                client,
                                media,
                                log,
                                duration=5,
                                until="event=speech_speaking"
                                if mode == "blocked"
                                else "event=media_started",
                            )
                            if mode == "blocked":
                                wait_for(service.backend.entered.is_set)
                            started = time.monotonic()
                            client.send("BYE", 2, branch="z9hG4bKbye" + client.id)
                            client.response(200, "BYE")
                            assert time.monotonic() - started < 0.3
                        wait_for(lambda: "confirmed=1" in log.read_text())
                        assert not service.leases and not asr.leases and not tts.leases
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)
            assert (
                service.backend.started
                == service.backend.closed
                == int(mode in {"failure", "blocked"})
            )
            assert len(service.ended) == 1
            assert service.ended[0].reason == (
                "failed" if mode in {"failure", "answer_failure"} else "disconnected"
            )
            assert not service.turn_tasks and not service.answered_calls and not service.calls
            assert not service.playback and not tts.requests

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,answered_at IS NOT NULL FROM calls").fetchone() == (
            "ended",
            True,
        )
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


@pytest.mark.parametrize("carrier_profile", [False, True, "netgsm"])
def test_managed_session_interruption_uses_native_cpu_models_and_pinned_leases(
    accounts, published, tmp_path, dedicated, carrier_profile
):
    from test_turn import MODELS, phone

    if not MODELS.is_dir():
        pytest.skip("native CPU models required")
    bind(accounts, published, routing.DID)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with (
            running(accounts, published, tmp_path, record_dsn, router_dsn, ObservedReady) as (
                service,
                agent_port,
                _,
                __,
            ),
            recognition() as (asr, asr_port),
            synthesis() as (tts, tts_port),
        ):
            service.backend = Script()
            service.playback, service.ended = [], []

            def synthetic_audio(text):
                for _ in range(400 if "sizi dinliyor" in text else 100):
                    yield b"\x01\x00" * 160
                    time.sleep(0.02)

            tts.stream = synthetic_audio
            options = config(agent_port, asr_port, tts_port)
            options["speech_options"] = options["speech_options"][:-2] + [
                "--turn-model-dir",
                str(MODELS),
                "--barge-in",
                "1",
            ]
            if carrier_profile:
                options["speech_options"] = [
                    "--managed-agent-port",
                    str(agent_port),
                    "--managed-asr-port",
                    str(asr_port),
                    "--managed-tts-port",
                    str(tts_port),
                    "--turn-model-dir",
                    str(MODELS),
                    "--barge-in",
                    "1",
                ]
                options["network_options"] = [
                    "--public-address",
                    "192.0.2.20",
                    "--allow-sip-ip",
                    "127.0.0.1",
                ]
                if carrier_profile == "netgsm":
                    options["identity_options"] += ["--called-national-prefix", "0"]

            def scenario():
                with contextmanager(run_gateway)(tmp_path, options) as (port, log, _):
                    client = Peer(port)
                    client.sip.settimeout(5)
                    client.request_user = (
                        routing.DID[3:] if carrier_profile == "netgsm" else routing.DID
                    )
                    try:
                        media = connect(client)
                        drive(
                            client,
                            media,
                            log,
                            source=phone(),
                            duration=15,
                            until="event=speech_speaking call=1 generation=turn-1",
                        )
                        _, _, ended = drive(client, media, log, source=phone(), duration=25)
                        assert ended and "event=speech_fallback" not in log.read_text(), (
                            log.read_text()
                        )
                        if carrier_profile:
                            assert "mode=managed" in log.read_text()
                        assert (
                            "event=speech_interrupted call=1 cancelled_generation=turn-1"
                            in log.read_text()
                        )
                        wait_for(lambda: "confirmed=1" in log.read_text())
                    finally:
                        client.close()

            await asyncio.to_thread(scenario)
            assert [r.name for r in service.backend.runtimes] == ["Example Assistant"] * 2
            assert len(service.playback) == 2
            assert not service.playback[0][0].completed and service.playback[1][0].completed
            assert "turn-1-p0" in tts.cancellations
            assert "turn-1-monitor" in asr.cancellations
            assert not service.leases and not asr.leases and not tts.leases
            assert not service.turn_tasks

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        text = c.execute(
            "SELECT text FROM utterances WHERE speaker='assistant' ORDER BY source_generation_id"
        ).fetchall()
        assert text == [("",), ("Rica ederim, iyi günler.",)]
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)


@pytest.mark.parametrize(
    "changes",
    [
        ["--setup-test-asr-port", "0"],
        ["--public-address", "192.0.2.1", "--allow-sip-ip", "127.0.0.1"],
        ["--agent-port", "15074"],
        ["--setup-test-conversation", "0"],
    ],
)
def test_managed_conversation_test_cannot_escape_isolation(changes):
    import subprocess
    from test_sip import ROOT

    args = config(15073, 15071, 15072)
    result = subprocess.run(
        [
            str(ROOT / "build/local/voice-gateway"),
            *args["identity_options"],
            *args["speech_options"],
            *changes,
        ],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode != 0 and b"event=ready" not in result.stdout


@pytest.mark.parametrize(
    "changes",
    [
        ["--setup-test-conversation", "1"],
        ["--setup-test-agent-port", "15073"],
        ["--speech-test-ms", "1000"],
        ["--barge-in", "0"],
        ["--agent-port", "15073"],
        ["--managed-asr-port", "15073"],
        ["--turn-partial-hint", "1"],
        ["--prompt-dir", "assets/prompts/tr-v5-kubra"],
        ["--trusted-identity-ip", "192.0.2.55"],
    ],
)
def test_managed_carrier_rejects_mixed_untrusted_or_unpinned_configuration(changes):
    import subprocess
    from test_sip import ROOT
    from test_turn import MODELS

    result = subprocess.run(
        [
            str(ROOT / "build/local/voice-gateway"),
            "--managed-agent-port",
            "15073",
            "--managed-asr-port",
            "15173",
            "--managed-tts-port",
            "15072",
            "--turn-model-dir",
            str(MODELS),
            "--barge-in",
            "1",
            "--allow-sip-ip",
            "127.0.0.1",
            "--trusted-identity-ip",
            "127.0.0.1",
            *changes,
        ],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1 and b"event=ready" not in result.stdout


@pytest.mark.parametrize("missing", ["agent", "asr", "tts", "allow", "trust"])
def test_managed_carrier_requires_complete_services_and_transport_policy(missing):
    import subprocess
    from test_sip import ROOT
    from test_turn import MODELS

    required = {
        "agent": ["--managed-agent-port", "15073"],
        "asr": ["--managed-asr-port", "15173"],
        "tts": ["--managed-tts-port", "15072"],
        "allow": ["--allow-sip-ip", "127.0.0.1"],
        "trust": ["--trusted-identity-ip", "127.0.0.1"],
    }
    result = subprocess.run(
        [
            str(ROOT / "build/local/voice-gateway"),
            "--turn-model-dir",
            str(MODELS),
            "--barge-in",
            "1",
            *(arg for name, args in required.items() if name != missing for arg in args),
        ],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1 and b"event=ready" not in result.stdout


def test_native_session_uses_coordinator_without_scripted_ready_permit(
    accounts, published, tmp_path, dedicated
):
    from test_release_readiness import running_node

    class Dialogue(Script):
        def check_runtime(self, runtime):
            assert runtime.name == "Example Assistant"

    token, scope, _, release = published
    number = routing.verified(accounts, token, scope)

    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            node.service.backend = Dialogue()
            await node.coordinator.activate(scope, release)
            routing.Numbers(accounts, routing.NODE).bind(token, scope, number, release, 2)
            stopping = asyncio.Event()
            maintenance = asyncio.create_task(node.coordinator.run(stopping))
            try:

                def scenario():
                    with contextmanager(run_gateway)(
                        tmp_path, config(node.agent_port, node.asr_port, node.tts_port)
                    ) as (port, log, _):
                        client = Peer(port)
                        client.request_user = routing.DID
                        client.sip.settimeout(5)
                        try:
                            media = connect(client)
                            _, _, ended = drive(client, media, log, duration=15)
                            assert ended and "event=speech_fallback" not in log.read_text(), (
                                log.read_text()
                            )
                            wait_for(lambda: "confirmed=1" in log.read_text())
                        finally:
                            client.close()

                await asyncio.to_thread(scenario)
                assert node.service.backend.closed == 2
                assert not node.service.leases and not node.asr.leases and not node.tts.leases
                assert not node.service.answer_permits and not node.service.calls
            finally:
                stopping.set()
                await maintenance

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM notes").fetchone() == (1,)
        assert c.execute("SELECT ready FROM release_readiness").fetchone() == (False,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
