"""Private admission RPC tests: real loopback transport, synthetic calls and inference."""

import asyncio
import json
from contextlib import asynccontextmanager

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

import test_number_routing as routing_tests
from alojan.auth import connection
from alojan_agent.prepared import PreparedReleases
from alojan_agent.routing import CallRouter
from alojan_agent.service import AgentService, create_server
from alojan_agent.store import Store, call_uuid
from test_agent import MemoryStore, Script, request

accounts = routing_tests.accounts
database = routing_tests.database
author = routing_tests.author
published = routing_tests.published


@asynccontextmanager
async def running(router, prepared=None):
    service = AgentService(Script(), MemoryStore(), router=router, prepared=prepared)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield rpc.AgentStub(channel), rpc.GenerationControlStub(channel), service
    finally:
        service.close_leases()
        await server.stop(0)


def setup(cid="managed-setup", **changes):
    values = dict(call_id=cid, called_e164=routing_tests.DID, called_source="request_uri")
    values.update(changes)
    return pb.CallInitializationRequest(**values)


async def lease(control, cid="managed-setup"):
    opened = await control.OpenCall(pb.CallLeaseRequest(call_id=cid), timeout=2)
    return (("x-alojan-lease", opened.lease),)


def test_rpc_is_disabled_on_legacy_service():
    async def run():
        async with running(None) as (stub, control, service):
            metadata = await lease(control)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            assert not service.routes and not service.initializations
            assert [e async for e in stub.RunTurn(request("legacy"), timeout=2)][-1].type == "end"

    asyncio.run(run())


def test_published_vocabulary_reaches_recognition_without_reading_changed_draft(accounts, tmp_path):
    from alojan.profiles import Profiles
    from alojan.releases import Releases
    from test_agent_drafts import content
    from test_agent_releases import prepare_assets, qualify
    from test_native_auth import register
    from alojan_contracts.configuration import NativeCalibration
    from test_asr import frames, running as recognition_worker
    from test_asr_configuration import VocabularyDecoder
    from test_tts import running as synthesis_worker, request as synthesis_request
    from test_tts_configuration import producer

    qualify(
        accounts,
        calibration=NativeCalibration(partial_hint=True, open_ms=900),
        output={"phrase_max_chars": 120, "phrase_max_bytes": 480, "max_phrases": 8},
    )
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    profiles = Profiles(accounts)
    agent = profiles.create(token, scope, content())["id"]
    author = token, scope, agent
    profiles.update(
        token, scope, agent, content() | {"asr_replacements": {"Merhaba dünya": "Pinned Brand"}}, 1
    )
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    release = Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"]
    routing_tests.bound(accounts, (token, scope, agent, release))
    profiles.update(
        token, scope, agent, content() | {"asr_replacements": {"Merhaba dünya": "Changed Brand"}}, 2
    )

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with connection(accounts.dsn) as conn:
            manifest, digest = conn.execute(
                "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (release,)
            ).fetchone()
        await cache.preload(scope, release, json.dumps(manifest), digest)
        async with running(CallRouter(accounts.dsn, routing_tests.NODE), cache) as (
            stub,
            control,
            _,
        ):
            metadata = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert not reply.ready_for_answer
            assert dict(reply.recognition.replacements) == {"Merhaba dünya": "Pinned Brand"}
            assert reply.gateway.schema_version == 1
            for field, value in manifest["model"]["preset"]["output"].items():
                assert getattr(reply.gateway.output, field) == value
            assert reply.gateway.calibration.partial_hint
            assert reply.gateway.calibration.open_ms == 900
            for field, value in manifest["model"]["preset"]["calibration"].items():
                assert getattr(reply.gateway.calibration, field) == value
            for field in (
                "max_call_seconds",
                "answer_delay_ms",
                "closing_delay_ms",
                "media_drain_ms",
                "max_call_turns",
                "turn_timeout_seconds",
            ):
                assert getattr(reply.gateway, field) == manifest["model"]["preset"][field]
            async with recognition_worker(VocabularyDecoder(), require_agent_release=True) as (
                _,
                _,
                asr,
                asr_control,
            ):
                asr_metadata = await lease(asr_control)
                await asr.ConfigureCall(
                    pb.RecognitionCallConfiguration(
                        call_id="managed-setup",
                        release_id=reply.release_id,
                        manifest_digest=reply.manifest_digest,
                        configuration=reply.recognition,
                    ),
                    timeout=1,
                    metadata=asr_metadata,
                )
                events = [
                    e
                    async for e in asr.StreamRecognize(
                        frames(call_id="managed-setup"), timeout=1, metadata=asr_metadata
                    )
                ]
                assert events[-1].text == "Pinned Brand, 1234. Evet."
            assert reply.synthesis.model == manifest["voice_assets"]["model"]
            assert (
                reply.synthesis.model_revision
                == manifest["model"]["preset"]["voice_model_revision"]
            )
            assert reply.synthesis.voice == manifest["content"]["voice"]
            async with synthesis_worker(producer(), require_agent_release=True) as (
                _,
                _,
                tts,
                tts_control,
            ):
                tts_metadata = await lease(tts_control)
                configured = await tts.ConfigureCall(
                    pb.SynthesisCallConfiguration(
                        call_id="managed-setup",
                        release_id=reply.release_id,
                        manifest_digest=reply.manifest_digest,
                        configuration=reply.synthesis,
                    ),
                    timeout=1,
                    metadata=tts_metadata,
                )
                assert configured.accepted
                synthesis_frames = [
                    f
                    async for f in tts.StreamSynthesize(
                        synthesis_request(call_id="managed-setup"),
                        timeout=1,
                        metadata=tts_metadata,
                    )
                ]
                assert len(synthesis_frames) == 3
                assert all(
                    f.sample_rate_hz == reply.synthesis.sample_rate_hz for f in synthesis_frames
                )
            await stub.CancelCallSetup(
                pb.CallSetupCancellation(call_id="managed-setup"), timeout=2, metadata=metadata
            )

    asyncio.run(run())


def test_real_router_pins_release_but_cannot_use_legacy_backend(accounts, published, tmp_path):
    routing_tests.bound(accounts, published)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with connection(accounts.dsn) as conn:
            manifest, digest = conn.execute(
                "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (published[3],)
            ).fetchone()
        pack = await cache.preload(published[1], published[3], json.dumps(manifest), digest)
        async with running(CallRouter(accounts.dsn, routing_tests.NODE), cache) as (
            stub,
            control,
            svc,
        ):
            metadata = await lease(control)
            reply = await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            again = await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert reply == again and reply.release_id == published[3]
            assert not reply.ready_for_answer and len(reply.manifest_digest) == 64
            assert svc.routes["managed-setup"].scope_id == published[1]
            assert svc.prepared_calls["managed-setup"] is pack
            assert cache.pins[pack.key] == 1
            for req in (request("managed-setup"), request("unmanaged")):
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await stub.RunTurn(req, timeout=2, metadata=metadata).read()
                assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.InitializeCall(
                    setup(called_e164=routing_tests.OTHER_DID), timeout=2, metadata=metadata
                )
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            assert svc.calls["managed-setup"].runtime.name == "Example Assistant"
            assert not svc.backend.contexts and not svc.store.ended
            await stub.EndCall(
                pb.CallEnd(call_id="managed-setup", reason="failed"), timeout=2, metadata=metadata
            )
            await stub.CancelCallSetup(
                pb.CallSetupCancellation(call_id="managed-setup"), timeout=2, metadata=metadata
            )
            assert not svc.routes and not svc.store.ended
            assert not svc.prepared_calls and not cache.pins
            with pytest.raises(grpc.aio.AioRpcError):
                await stub.InitializeCall(setup(), timeout=2, metadata=metadata)

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT status,answered_at FROM calls").fetchone() == ("ended", None)
        for table in ("summary_jobs", "notification_outbox", "utterances"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_rpc_identity_deadline_and_lease_boundaries(accounts, published):
    routing_tests.bound(accounts, published)

    async def run():
        async with running(CallRouter(accounts.dsn, routing_tests.NODE)) as (stub, control, svc):
            metadata = await lease(control)
            for req, headers, timeout, status in (
                (setup(), (), 2, grpc.StatusCode.FAILED_PRECONDITION),
                (setup(), (("x-alojan-lease", "forged"),), 2, grpc.StatusCode.FAILED_PRECONDITION),
                (setup(), metadata + metadata, 2, grpc.StatusCode.FAILED_PRECONDITION),
                (setup(), metadata, None, grpc.StatusCode.INVALID_ARGUMENT),
                (setup("ordinary"), metadata, 2, grpc.StatusCode.INVALID_ARGUMENT),
                (setup(called_source="from"), metadata, 2, grpc.StatusCode.INVALID_ARGUMENT),
                (setup(caller_e164="not-a-number"), metadata, 2, grpc.StatusCode.INVALID_ARGUMENT),
                (
                    setup(called_e164=" " + routing_tests.DID),
                    metadata,
                    2,
                    grpc.StatusCode.INVALID_ARGUMENT,
                ),
            ):
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await stub.InitializeCall(req, timeout=timeout, metadata=headers)
                assert error.value.code() == status
            assert not svc.routes and not svc.initializations

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 0


class WaitingRouter:
    """A cancellable repository boundary; no synthetic readiness acknowledgement."""

    def __init__(self):
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()
        self.cancelled = []

    async def initialize(self, *args):
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()

    async def cancel_unanswered(self, cid):
        self.cancelled.append(cid)
        return True


@pytest.mark.parametrize("action", ["cancel_setup", "release", "client_cancel", "deadline"])
def test_pending_initialization_cancellation_reclaims_memory(action):
    async def run():
        router = WaitingRouter()
        async with running(router) as (stub, control, svc):
            metadata = await lease(control)
            pending = stub.InitializeCall(
                setup(), timeout=0.15 if action == "deadline" else 3, metadata=metadata
            )
            await asyncio.wait_for(router.started.wait(), 1)
            with pytest.raises(grpc.aio.AioRpcError) as duplicate:
                await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert duplicate.value.code() == grpc.StatusCode.ABORTED
            if action == "cancel_setup":
                await stub.CancelCallSetup(
                    pb.CallSetupCancellation(call_id="managed-setup"), timeout=2, metadata=metadata
                )
            elif action == "release":
                await control.ReleaseCall(
                    pb.CallLeaseRequest(call_id="managed-setup", lease=metadata[0][1]), timeout=2
                )
            elif action == "client_cancel":
                pending.cancel()
            with pytest.raises((grpc.aio.AioRpcError, asyncio.CancelledError)):
                await pending
            await asyncio.wait_for(router.stopped.wait(), 1)
            for _ in range(50):
                if not svc.initializations:
                    break
                await asyncio.sleep(0.01)
            assert not svc.initializations and not svc.routes and not svc.calls
            assert not svc.backend.contexts and not svc.store.ended
            if action == "cancel_setup":
                assert router.cancelled == ["managed-setup"]

    asyncio.run(run())


def test_cancel_before_initialize_and_old_lease_cannot_reopen(accounts, published):
    routing_tests.bound(accounts, published)

    async def run():
        async with running(CallRouter(accounts.dsn, routing_tests.NODE)) as (stub, control, svc):
            metadata = await lease(control)
            await stub.CancelCallSetup(
                pb.CallSetupCancellation(call_id="managed-setup"), timeout=2, metadata=metadata
            )
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-setup", lease=metadata[0][1]), timeout=2
            )
            fresh = await lease(control)
            for headers in (metadata, fresh):
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await stub.InitializeCall(setup(), timeout=2, metadata=headers)
                assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            assert not svc.routes

    asyncio.run(run())


def test_reconcile_abandoned_setup_without_summary_or_delivery(accounts, published):
    routing_tests.bound(accounts, published)
    routing_tests.initialize(accounts, "abandoned")
    routing_tests.initialize(accounts, "recent")
    store = Store(accounts.dsn)
    asyncio.run(store.start("legacy-active", None))
    with connection(accounts.dsn) as conn:
        conn.execute(
            "UPDATE calls SET started_at=now()-interval '10 minutes' WHERE id IN (%s,%s)",
            (call_uuid("abandoned"), call_uuid("legacy-active")),
        )
    assert asyncio.run(store.reconcile_stale(300)) == 1
    recovery = AgentService(Script(), store, router=CallRouter(accounts.dsn, routing_tests.NODE))
    assert asyncio.run(recovery.reconcile_stale(300)) == 1
    assert asyncio.run(recovery.reconcile_stale(300)) == 0
    assert asyncio.run(store.reconcile_stale(300)) == 0
    with connection(accounts.dsn) as conn:
        assert conn.execute(
            "SELECT status,failure_code,answered_at FROM calls WHERE id=%s",
            (call_uuid("abandoned"),),
        ).fetchone() == ("ended", "abandoned_initialization", None)
        assert conn.execute(
            "SELECT status FROM calls WHERE id=%s", (call_uuid("recent"),)
        ).fetchone() == ("initializing",)
        assert conn.execute("SELECT call_id FROM summary_jobs").fetchall() == [
            (call_uuid("legacy-active"),)
        ]
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
    with pytest.raises(ValueError):
        asyncio.run(store.reconcile_stale(299))


def test_release_after_db_commit_cannot_install_late_route(accounts, published):
    routing_tests.bound(accounts, published)

    async def run():
        committed = asyncio.Event()
        finished = asyncio.Event()

        class LateRouter(CallRouter):
            async def initialize(self, *args):
                route = await super().initialize(*args)
                committed.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    finished.set()
                return route

        async with running(LateRouter(accounts.dsn, routing_tests.NODE)) as (stub, control, svc):
            metadata = await lease(control)
            pending = stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            await asyncio.wait_for(committed.wait(), 1)
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-setup", lease=metadata[0][1]), timeout=2
            )
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await pending
            assert error.value.code() == grpc.StatusCode.CANCELLED
            await asyncio.wait_for(finished.wait(), 1)
            assert not svc.routes and not svc.initializations and not svc.calls

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        # A lost setup-cancellation is recovered after the hard lease window, never summarized.
        assert conn.execute("SELECT status FROM calls").fetchone() == ("initializing",)
        conn.execute("UPDATE calls SET started_at=now()-interval '10 minutes'")
    recovery = AgentService(
        Script(), Store(accounts.dsn), router=CallRouter(accounts.dsn, routing_tests.NODE)
    )
    assert asyncio.run(recovery.reconcile_stale(300)) == 1
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 0


def test_unexpected_admission_failure_is_sanitized():
    class BrokenRouter:
        async def initialize(self, *args):
            raise RuntimeError("synthetic-private-value")

    async def run():
        async with running(BrokenRouter()) as (stub, control, svc):
            metadata = await lease(control)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert error.value.code() == grpc.StatusCode.UNAVAILABLE
            assert error.value.details() == "initialization unavailable"
            assert not svc.routes and not svc.initializations

    asyncio.run(run())


@pytest.mark.parametrize("cache_enabled", [False, True])
def test_ready_db_row_cannot_answer_without_local_preload(
    accounts, published, tmp_path, cache_enabled
):
    routing_tests.bound(accounts, published)

    async def run():
        cache = PreparedReleases(tmp_path / "store") if cache_enabled else None
        async with running(CallRouter(accounts.dsn, routing_tests.NODE), cache) as (
            stub,
            control,
            svc,
        ):
            metadata = await lease(control)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.InitializeCall(setup(), timeout=2, metadata=metadata)
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            assert error.value.details() == "release not preloaded"
            assert not svc.calls and not svc.routes and not svc.prepared_calls
            await stub.CancelCallSetup(
                pb.CallSetupCancellation(call_id="managed-setup"), timeout=2, metadata=metadata
            )
        if cache:
            await cache.close()

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT status,answered_at FROM calls").fetchone() == ("ended", None)
        assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 0


def test_shared_preloaded_release_is_reclaimed_only_after_last_call_release(
    accounts, published, tmp_path
):
    routing_tests.bound(accounts, published)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with connection(accounts.dsn) as conn:
            manifest, digest = conn.execute(
                "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (published[3],)
            ).fetchone()
        pack = await cache.preload(published[1], published[3], json.dumps(manifest), digest)
        async with running(CallRouter(accounts.dsn, routing_tests.NODE), cache) as (
            stub,
            control,
            svc,
        ):
            metadata = {}
            for cid in ("managed-first", "managed-second"):
                metadata[cid] = await lease(control, cid)
                reply = await stub.InitializeCall(setup(cid), timeout=2, metadata=metadata[cid])
                assert not reply.ready_for_answer
                assert svc.prepared_calls[cid] is pack
            assert cache.pins[pack.key] == 2
            for count, cid in ((1, "managed-first"), (0, "managed-second")):
                for _ in range(2):
                    await control.ReleaseCall(
                        pb.CallLeaseRequest(call_id=cid, lease=metadata[cid][0][1]), timeout=2
                    )
                    assert cache.pins.get(pack.key, 0) == count
            assert not svc.calls and not svc.routes and not svc.prepared_calls
        await cache.close()

    asyncio.run(run())
