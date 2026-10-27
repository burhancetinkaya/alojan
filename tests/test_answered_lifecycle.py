"""Private SIP lifecycle reports with real scoped repositories and restricted roles."""

import asyncio
import json
import time
from contextlib import asynccontextmanager

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

import test_number_routing as routing
from alojan.auth import connection
from alojan_agent.prepared import PreparedReleases
from alojan_agent.records import CallRecords
from alojan_agent.routing import CallRouter
from alojan_agent.service import AgentService, create_server
from alojan_agent.store import Store, call_uuid
from test_agent import Script
from test_call_initialization import setup, lease

accounts = routing.accounts
database = routing.database
author = routing.author
published = routing.published
dedicated = routing.dedicated


class ReadyService(AgentService):
    """Scripted readiness for isolated tests only; does not prove voice/model readiness."""

    async def InitializeCall(self, request, context):
        reply = await super().InitializeCall(request, context)
        self.answer_permits.add(request.call_id)
        reply.ready_for_answer = True
        return reply


@asynccontextmanager
async def running(
    accounts, published, tmp_path, record_dsn, router_dsn, service_class=ReadyService
):
    cache = PreparedReleases(tmp_path / "store")
    with connection(accounts.dsn) as c:
        manifest, digest = c.execute(
            "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (published[3],)
        ).fetchone()
    await cache.preload(published[1], published[3], json.dumps(manifest), digest)
    service = service_class(
        Script(), Store(record_dsn), router=CallRouter(router_dsn, routing.NODE), prepared=cache
    )
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield service, port, rpc.AgentStub(channel), rpc.GenerationControlStub(channel)
    finally:
        service.close_leases()
        await server.stop(0)
        await cache.close()


def answer(reply, cid="managed-setup", **changes):
    return pb.CallAnswer(
        **(
            dict(
                call_id=cid,
                release_id=reply.release_id,
                manifest_digest=reply.manifest_digest,
                answered_at_unix_ms=time.time_ns() // 1000000,
            )
            | changes
        )
    )


def ending(request, **changes):
    return pb.CallEnd(
        **(
            dict(
                call_id=request.call_id,
                release_id=request.release_id,
                manifest_digest=request.manifest_digest,
                answered_at_unix_ms=request.answered_at_unix_ms,
                ended_at_unix_ms=time.time_ns() // 1000000,
                reason="disconnected",
            )
            | changes
        )
    )


def test_answer_is_fenced_idempotent_and_end_enqueues_once(
    accounts, published, tmp_path, dedicated
):
    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn) as (
            svc,
            _,
            stub,
            control,
        ):
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            req = answer(reply)
            for request, metadata, deadline in (
                (req, (), 2),
                (req, (("x-alojan-lease", "wrong"),), 2),
                (req, headers, None),
                (answer(reply, manifest_digest="b" * 64), headers, 2),
                (answer(reply, answered_at_unix_ms=0), headers, 2),
                (answer(reply, answered_at_unix_ms=time.time_ns() // 1000000 + 60000), headers, 2),
            ):
                with pytest.raises(grpc.aio.AioRpcError):
                    await stub.ReportCallAnswered(request, timeout=deadline, metadata=metadata)
            for _ in range(2):
                assert (await stub.ReportCallAnswered(req, timeout=2, metadata=headers)).accepted
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.CancelCallSetup(
                    pb.CallSetupCancellation(call_id=req.call_id), timeout=2, metadata=headers
                )
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            assert svc.prepared_calls and svc.routes
            invalid = answer(reply, answered_at_unix_ms=req.answered_at_unix_ms + 1)
            with pytest.raises(grpc.aio.AioRpcError):
                await stub.ReportCallAnswered(invalid, timeout=2, metadata=headers)
            end = ending(req)
            for _ in range(2):
                assert (await stub.EndCall(end, timeout=2, metadata=headers)).accepted
            with pytest.raises(grpc.aio.AioRpcError):
                await stub.ReportCallAnswered(req, timeout=2, metadata=headers)
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id=req.call_id, lease=headers[0][1]), timeout=2
            )
            assert not svc.routes and not svc.answer_permits and not svc.lifecycle_locks
        return req, end

    req, end = asyncio.run(run())
    with connection(accounts.dsn) as c:
        row = c.execute(
            "SELECT status,extract(epoch FROM answered_at)*1000,duration_ms FROM calls"
        ).fetchone()
        assert row == (
            "ended",
            req.answered_at_unix_ms,
            end.ended_at_unix_ms - req.answered_at_unix_ms,
        )
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


@pytest.mark.parametrize("observed", [False, True])
def test_end_repairs_lost_answer_but_unanswered_call_has_no_summary(
    accounts, published, tmp_path, dedicated, observed
):
    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn) as (
            _,
            __,
            stub,
            control,
        ):
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            req = answer(reply)
            await stub.EndCall(
                ending(req, answered_at_unix_ms=req.answered_at_unix_ms if observed else 0),
                timeout=2,
                metadata=headers,
            )

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,answered_at IS NOT NULL FROM calls").fetchone() == (
            "ended",
            observed,
        )
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (int(observed),)


def test_ordinary_readiness_cannot_accept_answer_witness(accounts, published, tmp_path, dedicated):
    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn, AgentService) as (
            _,
            __,
            stub,
            control,
        ):
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            assert not reply.ready_for_answer
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.ReportCallAnswered(answer(reply), timeout=2, metadata=headers)
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,answered_at FROM calls").fetchone() == (
            "initializing",
            None,
        )


def test_scoped_recovery_uses_original_node_and_only_summarizes_answered_calls(
    accounts, published, dedicated
):
    number = routing.bound(accounts, published)
    active = routing.initialize(accounts, "stale-active")
    waiting = routing.initialize(accounts, "stale-waiting")
    recent = routing.initialize(accounts, "recent-call")
    token, scope, _, release = published
    routing.ready(accounts, scope, release, node="other-node")
    routing.Numbers(accounts, "other-node").bind(token, scope, number, release, 3)
    other = routing.initialize(accounts, "other-node-call", node="other-node")
    records_dsn, router_dsn = dedicated("records"), dedicated("routing")
    asyncio.run(CallRecords(records_dsn, active).answered(active.call_id))
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE calls SET started_at=now()-interval '10 minutes' WHERE id=ANY(%s)",
            ([call_uuid(r.call_id) for r in (active, waiting, other)],),
        )
    svc = AgentService(Script(), Store(records_dsn), router=CallRouter(router_dsn, routing.NODE))
    assert asyncio.run(svc.reconcile_stale(300)) == 2
    assert asyncio.run(svc.reconcile_stale(300)) == 0
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT call_id FROM summary_jobs").fetchall() == [
            (call_uuid(active.call_id),)
        ]
        assert c.execute(
            "SELECT duration_ms,failure_code FROM calls WHERE id=%s", (call_uuid(active.call_id),)
        ).fetchone() == (None, "missing_end_event")
        assert set(
            c.execute("SELECT sip_call_id FROM calls WHERE status='initializing'").fetchall()
        ) == {(recent.call_id,), (other.call_id,)}
        assert c.execute("SELECT count(*) FROM call_events").fetchone() == (2,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def test_invalid_end_rolls_back_answer_and_valid_retry_recovers(
    accounts, published, tmp_path, dedicated
):
    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn) as (
            _,
            __,
            stub,
            control,
        ):
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            req = answer(reply)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.EndCall(
                    ending(req, ended_at_unix_ms=req.answered_at_unix_ms - 1),
                    timeout=2,
                    metadata=headers,
                )
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            with connection(accounts.dsn) as c:
                assert c.execute("SELECT status,answered_at,ended_at FROM calls").fetchone() == (
                    "initializing",
                    None,
                    None,
                )
                assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (0,)
            assert (await stub.EndCall(ending(req), timeout=2, metadata=headers)).accepted

    asyncio.run(run())


def test_routed_turn_requires_ready_pin_persisted_answer_and_original_caller(
    accounts, published, tmp_path, dedicated
):
    from test_agent import request

    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn) as (
            service,
            _,
            stub,
            control,
        ):
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            cid = "managed-setup"

            async def rejected(generation, status, context="{}"):
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    _ = [
                        event
                        async for event in stub.RunTurn(
                            request(cid, generation, context=context), timeout=2, metadata=headers
                        )
                    ]
                assert error.value.code() == status

            await rejected("before-answer", grpc.StatusCode.FAILED_PRECONDITION)
            assert not service.backend.contexts
            req = answer(reply)
            await stub.ReportCallAnswered(req, timeout=2, metadata=headers)
            assert service.answered_calls == {cid}
            await rejected(
                "forged-caller",
                grpc.StatusCode.INVALID_ARGUMENT,
                '{"caller_number":"+908500000099"}',
            )
            service.answer_permits.remove(cid)
            await rejected("revoked", grpc.StatusCode.FAILED_PRECONDITION)
            service.answer_permits.add(cid)
            events = [
                event
                async for event in stub.RunTurn(request(cid, "valid"), timeout=2, metadata=headers)
            ]
            assert [e.text for e in events[:-1]] == ["Merhaba.", "Mesajınızı alabilirim."]
            assert events[-1].type == "end" and len(service.backend.contexts) == 1
            await stub.EndCall(ending(req), timeout=2, metadata=headers)
            await rejected("after-end", grpc.StatusCode.FAILED_PRECONDITION)
            assert not service.answered_calls
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id=cid, lease=headers[0][1]), timeout=2
            )
            assert not service.calls and not service.routes and not service.answered_calls

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM utterances WHERE speaker='caller'").fetchone() == (
            1,
        )
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)


def test_routed_end_waits_for_cancelled_turn_cleanup_before_finalization(
    accounts, published, tmp_path, dedicated
):
    from test_agent import request

    routing.bound(accounts, published)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    async def run():
        async with running(accounts, published, tmp_path, record_dsn, router_dsn) as (
            service,
            _,
            stub,
            control,
        ):
            entered, draining, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

            class Script:
                async def stream(self, call, save_note):
                    entered.set()
                    try:
                        await asyncio.Event().wait()
                        yield "Unreachable"
                    finally:
                        draining.set()
                        await release.wait()

            service.backend = Script()
            headers = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=headers)
            req = answer(reply)
            await stub.ReportCallAnswered(req, timeout=2, metadata=headers)
            turn = stub.RunTurn(request("managed-setup"), timeout=3, metadata=headers)
            reading = asyncio.ensure_future(turn.read())
            await asyncio.wait_for(entered.wait(), 1)
            end = asyncio.ensure_future(stub.EndCall(ending(req), timeout=2, metadata=headers))
            try:
                await asyncio.wait_for(draining.wait(), 1)
                await asyncio.sleep(0.05)
                assert not end.done()
                with connection(accounts.dsn) as c:
                    assert c.execute("SELECT status FROM calls").fetchone() == ("active",)
                    assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (0,)
            finally:
                release.set()
            assert (await end).accepted
            with pytest.raises(grpc.aio.AioRpcError):
                await reading
            assert not service.turn_tasks and not service.active
            with connection(accounts.dsn) as c:
                assert c.execute("SELECT status FROM calls").fetchone() == ("ended",)
                assert c.execute("SELECT count(*) FROM summary_jobs").fetchone() == (1,)

    asyncio.run(run())
