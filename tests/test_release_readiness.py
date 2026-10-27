"""Real readiness DB/RPC coordination with declared synthetic speech/provider peers."""

import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from types import SimpleNamespace
import time
import uuid

import grpc
import psycopg
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from voice.v1 import voice_pb2_grpc as rpc

from alojan.auth import connection
from alojan.numbers import Numbers
from alojan_agent.prepared import PreparedReleases, PreloadError
from alojan_agent.readiness import ReadinessRepository, ReleaseReadiness, ReadinessError
from alojan_agent.routing import CallRouter
from alojan_agent.service import AgentService, create_server
from alojan_agent.store import Store
from alojan_asr.service import RecognitionService, create_server as asr_server
from alojan_tts.service import SynthesisService, create_server as tts_server
from test_agent import Script, request
from test_answered_lifecycle import answer, ending
from test_call_initialization import setup, lease
from test_asr_configuration import VocabularyDecoder
from test_tts_configuration import producer
import test_number_routing as routing

accounts, database = routing.accounts, routing.database
author, published, dedicated = routing.author, routing.published, routing.dedicated


class SyntheticAgent(Script):
    def check_runtime(self, runtime):
        assert runtime.engine.model == "openai/gpt-oss-120b"


@asynccontextmanager
async def peer(service, factory, name):
    server = factory(service)
    state = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(state, server)
    await state.set(name, health_pb2.HealthCheckResponse.SERVING)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield channel, port, state
    finally:
        await server.stop(0)
        service.close_leases()
        if hasattr(service, "close"):
            service.close()


@asynccontextmanager
async def running_node(accounts, tmp_path, dedicated, *, tts_factory=SynthesisService):
    cache = PreparedReleases(tmp_path / "store")
    service = AgentService(
        SyntheticAgent(),
        Store(dedicated("records")),
        router=CallRouter(dedicated("routing"), routing.NODE),
        prepared=cache,
    )
    asr = RecognitionService(VocabularyDecoder(), require_agent_release=True)
    tts = tts_factory(producer(), require_agent_release=True)
    repo = ReadinessRepository(dedicated("readiness"), routing.NODE)
    async with AsyncExitStack() as stack:
        asr_channel, asr_port, asr_health = await stack.enter_async_context(
            peer(asr, asr_server, "voice.v1.Recognition")
        )
        tts_channel, tts_port, tts_health = await stack.enter_async_context(
            peer(tts, tts_server, "voice.v1.Synthesis")
        )
        coordinator = ReleaseReadiness(service, repo, asr_channel, tts_channel)
        channel, agent_port, _ = await stack.enter_async_context(
            peer(service, create_server, "voice.v1.Agent")
        )
        try:
            yield SimpleNamespace(
                service=service,
                cache=cache,
                asr=asr,
                tts=tts,
                repo=repo,
                coordinator=coordinator,
                asr_health=asr_health,
                tts_health=tts_health,
                agent_port=agent_port,
                asr_port=asr_port,
                tts_port=tts_port,
                stub=rpc.AgentStub(channel),
                control=rpc.GenerationControlStub(channel),
            )
        finally:
            await coordinator.close()
            await cache.close()


def test_preflight_enables_normal_service_and_expiry_only_blocks_new_calls(
    accounts, published, tmp_path, dedicated
):
    token, scope, _, release = published
    number = routing.verified(accounts, token, scope)

    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            candidate = await node.coordinator.activate(scope, release)

            async def no_reprepare(*args):
                raise AssertionError("Warm refresh must not reload assets or configure speech")

            node.coordinator.probe = no_reprepare
            node.cache.preload = no_reprepare
            node.cache.max_entries = 1
            assert await node.coordinator.activate(scope, release) == candidate
            with pytest.raises(ReadinessError, match="capacity"):
                await node.coordinator.activate(scope, str(uuid.uuid4()))
            assert not node.asr.leases and not node.tts.leases
            assert not node.asr.configurations and not node.tts.configurations
            assert not node.tts.backend.calls and not node.service.backend.contexts
            Numbers(accounts, routing.NODE).bind(token, scope, number, release, 2)
            headers = await lease(node.control)
            reply = await node.stub.InitializeCall(setup(), timeout=2, metadata=headers)
            assert reply.ready_for_answer
            answered = answer(reply)
            await node.stub.ReportCallAnswered(answered, timeout=2, metadata=headers)
            # Exact key and node are required; another workspace cannot reuse the receipt.
            route = node.service.routes["managed-setup"]
            from dataclasses import replace

            assert not node.coordinator.accepts(replace(route, node_id="other-node"))
            assert not node.coordinator.accepts(replace(route, scope_id=str(uuid.uuid4())))
            node.coordinator.expires = {
                key: time.monotonic() - 1 for key in node.coordinator.targets
            }
            second = await lease(node.control, "managed-next")
            declined = await node.stub.InitializeCall(
                setup("managed-next"), timeout=2, metadata=second
            )
            assert (
                not declined.ready_for_answer and "managed-next" not in node.service.answer_permits
            )
            events = [
                e
                async for e in node.stub.RunTurn(
                    request("managed-setup"), timeout=2, metadata=headers
                )
            ]
            assert events[-1].type == "end"
            await node.stub.EndCall(ending(answered), timeout=2, metadata=headers)
            await node.coordinator.refresh()
            assert node.coordinator.accepts(route)
            assert node.cache.pins  # Coordinator and active calls retain their immutable pack.
            await node.coordinator.close()
            assert not node.coordinator.accepts(route) and node.cache.pins

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT ready FROM release_readiness").fetchone() == (False,)
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)


@pytest.mark.parametrize("failure", ["health", "model", "workspace", "cache", "storage"])
def test_refresh_failure_revokes_local_admission(accounts, published, tmp_path, dedicated, failure):
    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            await node.coordinator.activate(published[1], published[3])
            if failure == "health":
                await node.tts_health.set(
                    "voice.v1.Synthesis", health_pb2.HealthCheckResponse.NOT_SERVING
                )
            elif failure == "cache":
                await node.cache.close()
            elif failure == "storage":
                node.service.store = Store(dedicated("readiness"))
            else:
                with connection(accounts.dsn) as c:
                    table = {"model": "model_catalog_status", "workspace": "recipient_scopes"}[
                        failure
                    ]
                    c.execute(
                        psycopg.sql.SQL("UPDATE {} SET enabled=false").format(
                            psycopg.sql.Identifier(table)
                        )
                    )
            try:
                await node.coordinator.refresh()
            except Exception:
                assert failure in {"health", "storage", "cache"}
            assert not node.coordinator.expires

    asyncio.run(run())


def test_replaced_consumer_cannot_renew_or_withdraw_successor(
    accounts, published, tmp_path, dedicated
):
    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            old = await node.coordinator.activate(published[1], published[3])
            successor = await node.repo.claim(published[1], published[3])
            assert successor.consumer_id != old.consumer_id
            assert await node.repo.renew(successor)
            await node.coordinator.refresh()
            assert (
                not node.coordinator.targets
                and not node.coordinator.expires
                and not node.cache.pins
            )
            await node.repo.withdraw(old)
            with connection(accounts.dsn) as c:
                assert c.execute("SELECT ready,consumer_id FROM release_readiness").fetchone() == (
                    True,
                    uuid.UUID(successor.consumer_id),
                )

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["asset", "voice", "cancel"])
def test_failed_preflight_never_acknowledges_and_reclaims_known_leases(
    accounts, published, tmp_path, dedicated, failure
):
    class TTS(SynthesisService):
        async def ConfigureCall(self, request, context):
            entered.set()
            if failure == "cancel":
                await asyncio.sleep(3)
            return await super().ConfigureCall(request, context)

    async def run():
        nonlocal entered
        entered = asyncio.Event()
        async with running_node(accounts, tmp_path, dedicated, tts_factory=TTS) as node:
            if failure == "asset":
                node.cache.root = tmp_path / "missing"
            if failure == "voice":
                node.tts.loaded_profile = None
            pending = asyncio.create_task(node.coordinator.activate(published[1], published[3]))
            if failure == "cancel":
                await asyncio.wait_for(entered.wait(), 2)
                pending.cancel()
            with pytest.raises((PreloadError, grpc.aio.AioRpcError, asyncio.CancelledError)):
                await pending
            assert not node.asr.leases and not node.tts.leases
            assert (
                not node.cache.pins
                and not node.coordinator.targets
                and not node.coordinator.expires
            )
            with connection(accounts.dsn) as c:
                assert c.execute("SELECT ready FROM release_readiness").fetchone() == (False,)

    entered = None
    asyncio.run(run())


def test_readiness_role_is_node_scoped_and_cannot_mutate_business_or_calls(
    accounts, published, dedicated
):
    dsn = dedicated("readiness")

    async def run():
        wrong = ReadinessRepository(dsn, "foreign-node")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await wrong.claim(published[1], published[3])
        repo = ReadinessRepository(dsn, routing.NODE)
        with pytest.raises(ReadinessError, match="release_unavailable"):
            await repo.claim(str(uuid.uuid4()), published[3])
        candidate = await repo.claim(published[1], published[3])
        assert await repo.renew(candidate)
        for sql in (
            "SELECT * FROM users",
            "SELECT * FROM calls",
            "UPDATE model_catalog_status SET enabled=false",
            "UPDATE phone_numbers SET enabled=false",
        ):
            with connection(dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)
        for role in ("management", "routing", "records"):
            with (
                connection(dedicated(role)) as c,
                pytest.raises(psycopg.errors.InsufficientPrivilege),
            ):
                c.execute("UPDATE release_readiness SET consumer_id=gen_random_uuid()")

    asyncio.run(run())


def test_background_stop_withdraws_and_releases_coordinator_pin(
    accounts, published, tmp_path, dedicated
):
    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            await node.coordinator.activate(published[1], published[3])
            stopping = asyncio.Event()
            task = asyncio.create_task(node.coordinator.run(stopping))
            await asyncio.sleep(0.05)
            stopping.set()
            await asyncio.wait_for(task, 2)
            assert node.coordinator.closed and not node.cache.pins

    asyncio.run(run())


def test_real_backend_structural_readiness_rejects_closed_or_injected_model():
    from openai import AsyncOpenAI
    from alojan_agent.backend import Backend
    from test_agent_runtime import configured

    async def run():
        client = AsyncOpenAI(api_key="synthetic-key", base_url="https://example.invalid")
        backend = Backend(client=client)
        backend.check_runtime(configured())
        backend.model_override = object()
        with pytest.raises(ValueError):
            backend.check_runtime(configured())
        backend.model_override = None
        await backend.close()
        with pytest.raises(ValueError):
            backend.check_runtime(configured())

    asyncio.run(run())
