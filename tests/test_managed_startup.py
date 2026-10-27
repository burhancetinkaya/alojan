"""Actual managed processes and PostgreSQL/RPC; speech inference is synthetic."""

import asyncio
from contextlib import asynccontextmanager
import json
import os
import socket
import sys
import uuid

from cryptography.fernet import Fernet
from alojan.connections import Connections
from alojan.profiles import Profiles
from alojan_contracts.secrets import SecretBox
from test_agent_drafts import content
from test_agent_releases import qualify
from test_native_auth import register

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc

from alojan.auth import connection
from alojan.numbers import Numbers
from alojan_agent.managed import Deployment
from alojan_asr.service import RecognitionService, create_server as asr_server
from alojan_tts.service import SynthesisService, create_server as tts_server
from test_answered_lifecycle import answer, ending
from test_call_initialization import setup, lease
from test_release_readiness import peer, VocabularyDecoder, producer
import test_number_routing as routing

accounts, database = routing.accounts, routing.database
published, dedicated = routing.published, routing.dedicated


@pytest.fixture
def author(accounts, tmp_path):
    qualify(accounts)
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    key = Fernet.generate_key()
    (tmp_path / "provider.key").write_bytes(key)
    reference = Connections(accounts, SecretBox(key)).create(
        token,
        scope,
        {
            "provider": "openrouter",
            "label": "Synthetic",
            "api_key": "synthetic-unused-key",
        },
    )["id"]
    agent = Profiles(accounts).create(token, scope, content() | {"model_connection": reference})[
        "id"
    ]
    return token, scope, agent


def configuration(tmp_path):
    return dict(
        schema_version=1,
        node_id=routing.NODE,
        asset_root=str(tmp_path),
        agent_port=15083,
        asr_port=15081,
        tts_port=15082,
        targets=[dict(scope_id=str(uuid.uuid4()), release_id=str(uuid.uuid4()))],
    )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"node_id": "bad/node"},
        {"asset_root": "."},
        {"agent_port": True},
        {"agent_port": 1023},
        {"agent_port": 65536},
        {"asr_port": 15083},
        {"targets": [{"scope_id": "bad", "release_id": "bad"}]},
        {"targets": [{"scope_id": str(uuid.uuid4())}]},
        {"unexpected": "ignored?"},
    ],
)
def test_invalid_configuration_is_rejected(tmp_path, change):
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(configuration(tmp_path) | change))
    with pytest.raises((ValueError, TypeError)):
        Deployment.load(path)


def test_configuration_is_bounded_unambiguous_and_immutable(tmp_path):
    path = tmp_path / "deployment.json"
    data = configuration(tmp_path)
    path.write_text(json.dumps(data))
    parsed = Deployment.load(path)
    assert parsed.targets == ((data["targets"][0]["scope_id"], data["targets"][0]["release_id"]),)
    for raw in (
        json.dumps(data | {"targets": data["targets"] * 2}),
        json.dumps(data | {"targets": data["targets"] * 17}),
        json.dumps(data)[:-1] + ',"schema_version":1}',
        " " * 65537,
    ):
        path.write_text(raw)
        with pytest.raises(ValueError):
            Deployment.load(path)


@asynccontextmanager
async def process(path, env):
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alojan_agent.managed",
        "--config",
        str(path),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield child
    finally:
        if child.returncode is None:
            child.terminate()
        try:
            await asyncio.wait_for(child.wait(), 8)
        except TimeoutError:
            child.kill()
            await child.wait()
            pytest.fail("managed process did not stop within its cleanup budget")


@asynccontextmanager
async def deployment(published, tmp_path, dedicated, *, tts_factory=SynthesisService):
    env = os.environ.copy()
    env.update(
        PYTHONPATH=os.pathsep.join(sys.path),
        OPENROUTER_API_KEY="must-not-be-used-global-key",
        ALOJAN_CREDENTIALS_DATABASE_URL=dedicated("credentials"),
        ALOJAN_CREDENTIAL_KEY_FILE=str(tmp_path / "provider.key"),
        ALOJAN_RECORDS_DATABASE_URL=dedicated("records"),
        ALOJAN_ROUTING_DATABASE_URL=dedicated("routing"),
        ALOJAN_READINESS_DATABASE_URL=dedicated("readiness"),
        # A valid legacy/admin DSN must never be needed by this entry point.
        ALOJAN_DATABASE_URL="invalid-legacy-dsn",
    )
    asr = RecognitionService(VocabularyDecoder(), require_agent_release=True)
    tts = tts_factory(producer(), require_agent_release=True)
    async with (
        peer(asr, asr_server, "voice.v1.Recognition") as (_, asr_port, _),
        peer(tts, tts_server, "voice.v1.Synthesis") as (_, tts_port, _),
    ):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        data = configuration(tmp_path) | dict(
            asset_root=str(tmp_path / "store"),
            agent_port=port,
            asr_port=asr_port,
            tts_port=tts_port,
            targets=[dict(scope_id=published[1], release_id=published[3])],
        )
        path = tmp_path / "deployment.json"
        path.write_text(json.dumps(data))
        yield path, env, data, asr, tts


async def started(child, channel):
    async with asyncio.timeout(10):
        while True:
            line = await child.stdout.readline()
            assert line and b"event=managed_agent_startup_failed" not in line, (
                "managed startup failed"
            )
            if line.startswith(b"event=managed_agent_ready"):
                break
    result = await health_pb2_grpc.HealthStub(channel).Check(
        health_pb2.HealthCheckRequest(service="voice.v1.Agent"), timeout=2
    )
    assert result.status == health_pb2.HealthCheckResponse.SERVING


def test_actual_launcher_restart_calls_and_exclusive_listener(
    accounts, published, tmp_path, dedicated
):
    number = routing.verified(accounts, published[0], published[1])

    async def run():
        async with deployment(published, tmp_path, dedicated) as (path, env, data, asr, tts):
            old_consumer = None
            for iteration in range(2):
                async with (
                    process(path, env) as child,
                    grpc.aio.insecure_channel(f"127.0.0.1:{data['agent_port']}") as channel,
                ):
                    await started(child, channel)
                    with connection(accounts.dsn) as c:
                        ready, consumer = c.execute(
                            "SELECT ready,consumer_id FROM release_readiness"
                        ).fetchone()
                        assert ready and consumer != old_consumer
                    old_consumer = consumer
                    if iteration:
                        async with asyncio.timeout(3):
                            while True:
                                with connection(accounts.dsn) as c:
                                    repaired = c.execute(
                                        "SELECT count(*) FROM calls WHERE failure_code='abandoned_initialization'"
                                    ).fetchone()[0]
                                if repaired:
                                    break
                                await asyncio.sleep(0.05)
                    if not iteration:
                        # Another process on the same endpoint must fail before claiming this row.
                        async with process(path, env) as duplicate:
                            assert await asyncio.wait_for(duplicate.wait(), 10) == 1
                        with connection(accounts.dsn) as c:
                            assert c.execute(
                                "SELECT consumer_id FROM release_readiness"
                            ).fetchone() == (consumer,)
                        Numbers(accounts, routing.NODE).bind(
                            published[0], published[1], number, published[3], 2
                        )
                    control, stub = rpc.GenerationControlStub(channel), rpc.AgentStub(channel)
                    cid = f"managed-launch-{iteration}"
                    headers = await lease(control, cid)
                    reply = await stub.InitializeCall(setup(cid), timeout=2, metadata=headers)
                    assert reply.ready_for_answer
                    answered = answer(reply, cid)
                    await stub.ReportCallAnswered(answered, timeout=2, metadata=headers)
                    await stub.EndCall(ending(answered), timeout=2, metadata=headers)
                    await control.ReleaseCall(
                        pb.CallLeaseRequest(call_id=cid, lease=headers[0][1]), timeout=2
                    )
                    # Leave another initialized call for shutdown to reclaim.
                    other = cid + "-unfinished"
                    metadata = await lease(control, other)
                    await stub.InitializeCall(setup(other), timeout=2, metadata=metadata)
                    if iteration:
                        reference = Profiles(accounts).get(*published[:3])["content"][
                            "model_connection"
                        ]
                        Connections(accounts).revoke(published[0], published[1], reference)
                        await asyncio.sleep(2.1)
                        rejected = cid + "-revoked"
                        revoked_headers = await lease(control, rejected)
                        refused = await stub.InitializeCall(
                            setup(rejected), timeout=2, metadata=revoked_headers
                        )
                        assert not refused.ready_for_answer
                assert child.returncode == 0
                with connection(accounts.dsn) as c:
                    assert c.execute("SELECT ready FROM release_readiness").fetchone() == (False,)
                    if not iteration:
                        c.execute(
                            "UPDATE calls SET started_at=now()-interval '11 minutes' WHERE status='initializing'"
                        )
                assert not asr.leases and not tts.leases
                assert not tts.backend.calls

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM summary_jobs WHERE status='pending'").fetchone() == (
            2,
        )
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


@pytest.mark.parametrize("failure", ["missing_credential", "routing_role", "cancel"])
def test_launcher_failure_and_stop_during_preflight_are_closed(
    accounts, published, tmp_path, dedicated, failure
):
    async def run():
        entered = asyncio.Event()

        class SlowTTS(SynthesisService):
            async def ConfigureCall(self, request, context):
                entered.set()
                if failure == "cancel":
                    await asyncio.sleep(3)
                return await super().ConfigureCall(request, context)

        async with deployment(published, tmp_path, dedicated, tts_factory=SlowTTS) as (
            path,
            env,
            data,
            asr,
            tts,
        ):
            if failure == "missing_credential":
                del env["ALOJAN_RECORDS_DATABASE_URL"]
            if failure == "routing_role":
                env["ALOJAN_ROUTING_DATABASE_URL"] = env["ALOJAN_READINESS_DATABASE_URL"]
            async with process(path, env) as child:
                if failure == "cancel":
                    await asyncio.wait_for(entered.wait(), 10)
                    child.terminate()
                assert await asyncio.wait_for(child.wait(), 10) == (0 if failure == "cancel" else 1)
                output = await child.stdout.read()
                assert b"event=managed_agent_ready" not in output
                assert b"synthetic-unused-key" not in output
            with connection(accounts.dsn) as c:
                assert c.execute(
                    "SELECT count(*) FROM release_readiness WHERE ready"
                ).fetchone() == (0,)
                assert c.execute("SELECT count(*) FROM call_route_snapshots").fetchone() == (0,)
            assert not asr.leases and not tts.leases
            with socket.socket() as reclaimed:
                reclaimed.bind(("127.0.0.1", data["agent_port"]))

    asyncio.run(run())
