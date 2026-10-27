"""Real PostgreSQL ownership, idempotence and leased finalization boundaries."""

import asyncio
import uuid
from dataclasses import replace

import psycopg
import pytest
from psycopg.types.json import Jsonb

import test_number_routing as routing
from alojan.auth import connection
from alojan.profiles import Profiles
from alojan_agent.models import Note, Summary
from alojan_agent.records import CallRecords, CallSummaries, transaction
from alojan_agent.store import Store, call_uuid
from test_agent_drafts import content

accounts = routing.accounts
database = routing.database
author = routing.author
published = routing.published
dedicated = routing.dedicated


@pytest.fixture
def route(accounts, published):
    routing.bound(accounts, published)
    return routing.initialize(accounts, "scoped-records")


def summary():
    return Summary(
        caller_name=None,
        caller_number=None,
        subject="Sentetik konu",
        summary="Sentetik özet.",
        requested_action="Mesajı ilet",
        urgency="low",
        promised_action="none",
        confirmation_status="confirmed",
        unresolved_questions=[],
        confidence=0.8,
        privacy_flags=[],
    )


async def ended(records):
    await records.answered(records.route.call_id)
    await records.utterance(records.route.call_id, "turn", "caller", "Sentetik mesaj.")
    await records.end(records.route.call_id, "completed")


def test_call_writes_require_exact_pin_answer_and_open_call(accounts, route, dedicated):
    dsn = dedicated("records")
    records = CallRecords(dsn, route)

    async def run():
        with pytest.raises(ValueError, match="active"):
            await records.utterance(route.call_id, "g", "caller", "Too early")
        for changed in (
            replace(route, scope_id=str(uuid.uuid4())),
            replace(route, release_id=str(uuid.uuid4())),
            replace(route, node_id="other-node"),
            replace(route, manifest_digest="0" * 64),
        ):
            with pytest.raises(ValueError, match="ownership"):
                await CallRecords(dsn, changed).answered(route.call_id)
        with pytest.raises(ValueError, match="ownership"):
            await records.answered("other-call")
        await records.answered(route.call_id)
        await records.answered(route.call_id)
        await records.start(route.call_id, None)
        with pytest.raises(ValueError, match="metadata"):
            await records.start(route.call_id, "forged")
        await records.utterance(route.call_id, "g", "caller", "Sentetik mesaj.")
        await records.utterance(route.call_id, "g", "caller", "Sentetik mesaj.")
        with pytest.raises(ValueError, match="conflict"):
            await records.utterance(route.call_id, "g", "caller", "Changed")
        # Interrupted speech has no asserted transcript, but retains actual sent duration.
        await records.utterance(route.call_id, "g-p0", "assistant", "", 40)
        with pytest.raises(ValueError, match="invalid"):
            await records.utterance(route.call_id, "g-p1", "assistant", "Unsent", 0)
        note = Note(subject="Konu", message="Mesaj")
        assert await records.note(route.call_id, note, 1) == await records.note(
            route.call_id, note, 1
        )
        with pytest.raises(ValueError, match="conflict"):
            await records.note(route.call_id, note.model_copy(update={"message": "Changed"}), 1)
        await records.end(route.call_id, "completed")
        await records.end(route.call_id, "completed")
        with pytest.raises(ValueError, match="active"):
            await records.note(route.call_id, note, 2)
        with pytest.raises(ValueError, match="active"):
            await records.utterance(route.call_id, "late", "caller", "Late")

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM utterances").fetchone() == (2,)
        assert c.execute(
            "SELECT status,answered_at IS NOT NULL,duration_ms>=0 FROM calls"
        ).fetchone() == ("ended", True, True)
        assert c.execute("SELECT scope_id::text,release_id::text FROM summary_jobs").fetchone() == (
            route.scope_id,
            route.release_id,
        )
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def test_scoped_records_rls_hides_rows_without_correct_context(accounts, route, dedicated):
    dsn = dedicated("records")
    asyncio.run(ended(CallRecords(dsn, route)))
    for scope, count in ((None, 0), (str(uuid.uuid4()), 0), (route.scope_id, 1), (None, 0)):
        with transaction(dsn, scope) as c:
            for table in ("calls", "utterances", "summary_jobs"):
                assert c.execute(
                    psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
                ).fetchone() == (count,)
    for purpose in ("records", "summaries", "management"):
        role_dsn = dsn if purpose == "records" else dedicated(purpose)
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            transaction(role_dsn, route.scope_id) as c,
        ):
            c.execute(
                "INSERT INTO notification_outbox(id,call_id,target,payload_jsonb) VALUES(%s,%s,'test','{}')",
                (uuid.uuid4(), call_uuid(route.call_id)),
            )


def test_pinned_summary_and_single_finalization_after_agent_change(
    accounts, published, route, dedicated
):
    record_dsn, summary_dsn = dedicated("records"), dedicated("summaries")
    token, scope, agent, _ = published
    Profiles(accounts).update(token, scope, agent, content("Changed Assistant", "Changed Owner"), 1)

    async def run():
        records = CallRecords(record_dsn, route)
        await records.answered(route.call_id)
        await records.note(route.call_id, Note(subject="Konu", message="Mesaj"), 1)
        await records.end(route.call_id, "completed")
        worker = CallSummaries(summary_dsn)
        jobs = await asyncio.gather(*(worker.claim() for _ in range(4)))
        job = next(x for x in jobs if x)
        assert sum(x is not None for x in jobs) == 1
        data = await worker.input(job)
        assert data["runtime"].name == "Example Assistant"
        assert "Example Owner" in data["runtime"].summary_instructions
        assert "Changed Owner" not in data["runtime"].summary_instructions
        await worker.finish(job, summary())
        with pytest.raises(ValueError, match="expired"):
            await worker.finish(job, summary())
        assert await worker.claim() is None

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        row = c.execute(
            "SELECT scope_id::text,release_id::text,payload FROM call_finalizations"
        ).fetchone()
        assert row[:2] == (route.scope_id, route.release_id)
        assert row[2]["summary"]["confirmation_status"] == "unconfirmed"
        assert row[2]["agent_name"] == "Example Assistant"
        assert c.execute(
            "SELECT status,attempts,claim_token,lease_until FROM summary_jobs"
        ).fetchone() == ("done", 1, None, None)
        assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def test_expired_claim_is_replaced_and_old_worker_cannot_finish(accounts, route, dedicated):
    asyncio.run(ended(CallRecords(dedicated("records"), route)))
    worker = CallSummaries(dedicated("summaries"))

    async def run():
        old = await worker.claim()
        with connection(accounts.dsn) as c:
            c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")
        new = await worker.claim()
        assert new.token != old.token
        with pytest.raises(ValueError, match="expired"):
            await worker.finish(old, summary())
        with pytest.raises(ValueError, match="expired"):
            await worker.input(replace(new, scope_id=str(uuid.uuid4())))
        await worker.finish(new)

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,attempts,failure_code FROM summary_jobs").fetchone() == (
            "failed",
            2,
            "summary_failed",
        )
        assert c.execute(
            "SELECT payload->'summary',summary_status FROM call_finalizations"
        ).fetchone() == (None, "failed")


@pytest.mark.parametrize("failure", [False, True, "oversized"])
def test_postcall_processing_bounds_output_and_uses_saved_confirmation(
    accounts, route, dedicated, failure
):
    class Backend:
        async def summarize(self, data, *, runtime):
            assert runtime.name == "Example Assistant" and data["last_note"][1]
            if failure is True:
                raise RuntimeError("provider detail must not be persisted")
            result = summary()
            if failure == "oversized":
                result.unresolved_questions = ["x" * 25000]
            return result

    async def run():
        records = CallRecords(dedicated("records"), route)
        await records.answered(route.call_id)
        await records.note(route.call_id, Note(subject="Konu", message="Mesaj", confirmed=True), 1)
        await records.end(route.call_id, "disconnected")
        worker = CallSummaries(dedicated("summaries"))
        assert await worker.process_one(Backend())
        assert not await worker.process_one(Backend())

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        status, payload = c.execute(
            "SELECT summary_status,payload FROM call_finalizations"
        ).fetchone()
        assert status == ("failed" if failure else "done")
        assert (
            payload["summary"] is None
            if failure
            else payload["summary"]["confirmation_status"] == "confirmed"
        )


def test_legacy_queue_and_destination_never_take_routed_work(accounts, route, dedicated):
    async def run():
        await ended(CallRecords(dedicated("records"), route))
        legacy = Store(accounts.dsn)
        assert await legacy.pending() is None
        with pytest.raises(ValueError, match="scoped claim"):
            await legacy.summary_result(call_uuid(route.call_id), summary())
        await legacy.start("legacy", None)
        await legacy.end("legacy", "completed")
        assert await legacy.pending() == (call_uuid("legacy"),)
        await legacy.summary_result(call_uuid("legacy"), summary())

    asyncio.run(run())
    with pytest.raises(psycopg.errors.CheckViolation), connection(accounts.dsn) as c:
        c.execute(
            "INSERT INTO notification_outbox(id,call_id,target,payload_jsonb) VALUES(%s,%s,'telegram:test',%s)",
            (uuid.uuid4(), call_uuid(route.call_id), Jsonb({})),
        )
    with pytest.raises(psycopg.errors.CheckViolation), connection(accounts.dsn) as c:
        c.execute(
            "UPDATE summary_jobs SET scope_id=NULL,release_id=NULL WHERE call_id=%s",
            (call_uuid(route.call_id),),
        )


def test_failed_finalization_rolls_back_summary_and_job(accounts, route, dedicated):
    asyncio.run(ended(CallRecords(dedicated("records"), route)))
    worker = CallSummaries(dedicated("summaries"))

    async def run():
        job = await worker.claim()
        with connection(accounts.dsn) as c:
            c.execute("ALTER TABLE call_finalizations ADD CONSTRAINT injected_failure CHECK(false)")
        with pytest.raises(psycopg.errors.CheckViolation):
            await worker.finish(job, summary())
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT count(*) FROM call_summaries").fetchone() == (0,)
            assert c.execute("SELECT status FROM summary_jobs").fetchone() == ("processing",)
            c.execute("ALTER TABLE call_finalizations DROP CONSTRAINT injected_failure")
        await worker.finish(job, summary())

    asyncio.run(run())


def test_two_workspaces_finalize_independently(accounts, route, published, dedicated, tmp_path):
    token = routing.register(accounts, "second.records.owner")
    scope = accounts.session(token)["workspaces"][0]["id"]
    agent = Profiles(accounts).create(token, scope, content("Second Assistant", "Second Owner"))[
        "id"
    ]
    preparation, _, _ = routing.prepare_assets(accounts, (token, scope, agent), tmp_path)
    release = routing.Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"]
    number = routing.verified(accounts, token, scope, routing.OTHER_DID)
    routing.ready(accounts, scope, release)
    routing.Numbers(accounts, routing.NODE).bind(token, scope, number, release, 2)
    second = routing.initialize(accounts, "second-records", routing.OTHER_DID)
    dsn = dedicated("records")

    async def run():
        await asyncio.gather(*(ended(CallRecords(dsn, r)) for r in (route, second)))
        worker = CallSummaries(dedicated("summaries"))
        jobs = await asyncio.gather(worker.claim(), worker.claim())
        assert {j.scope_id for j in jobs} == {route.scope_id, scope}
        await asyncio.gather(*(worker.finish(j, summary()) for j in jobs))

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        events = c.execute("SELECT scope_id::text,payload FROM call_finalizations").fetchall()
        assert {e[0] for e in events} == {route.scope_id, scope}
        for event_scope, payload in events:
            assert payload["owner_name"] == (
                "Second Owner" if event_scope == scope else "Example Owner"
            )
            assert payload["outcome"] == "completed"
            assert payload["duration_ms"] >= 0
            assert payload["answered_at"] <= payload["ended_at"]
    for r in (route, second):
        with transaction(dsn, r.scope_id) as c:
            assert c.execute("SELECT id FROM calls").fetchall() == [(call_uuid(r.call_id),)]


def test_worker_roles_cannot_be_combined(accounts, dedicated):
    from alojan.roles import grant_call_records

    for purpose in ("records", "summaries"):
        dsn = dedicated(purpose)
        with connection(dsn) as c:
            role = c.execute("SELECT current_user").fetchone()[0]
        with pytest.raises(ValueError, match="unexpected"):
            grant_call_records(accounts.dsn, role, summaries=purpose == "records")


def test_cancelled_summary_keeps_claim_recoverable(accounts, route, dedicated):
    async def run():
        await ended(CallRecords(dedicated("records"), route))
        entered = asyncio.Event()

        class Backend:
            async def summarize(self, data, *, runtime):
                entered.set()
                await asyncio.Event().wait()

        worker = CallSummaries(dedicated("summaries"))
        task = asyncio.create_task(worker.process_one(Backend()))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with connection(accounts.dsn) as c:
            assert c.execute(
                "SELECT status,claim_token IS NOT NULL FROM summary_jobs"
            ).fetchone() == ("processing", True)
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (0,)
            c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")
        await worker.finish(await worker.claim())

    asyncio.run(run())


def test_call_end_is_atomic_with_summary_enqueue(accounts, route, dedicated):
    async def run():
        records = CallRecords(dedicated("records"), route)
        await records.answered(route.call_id)
        with connection(accounts.dsn) as c:
            c.execute("ALTER TABLE summary_jobs ADD CONSTRAINT injected_failure CHECK(false)")
        with pytest.raises(psycopg.errors.CheckViolation):
            await records.end(route.call_id, "completed")
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT status,ended_at FROM calls").fetchone() == ("active", None)
            c.execute("ALTER TABLE summary_jobs DROP CONSTRAINT injected_failure")
        await records.end(route.call_id, "completed")

    asyncio.run(run())


def test_upgrade_pins_existing_jobs_without_assigning_legacy_calls(database, tmp_path):
    from alojan.auth import Accounts
    from alojan.catalog import qualified_model
    from alojan.migrate import MIGRATIONS, migrate
    from alojan.profiles import validate_draft
    from alojan_contracts.configuration import canonical_digest
    from test_agent_releases import qualify

    old = tmp_path / "old-migrations"
    old.mkdir()
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if migration.name < "0009_scoped_call_records.sql":
            (old / migration.name).write_text(migration.read_text())
    migrate(database, old)
    account = Accounts(database)
    qualify(account)
    # Seed v8 rows directly: current authoring/auth APIs require later migrations.
    scope, user, agent, preparation, release, number, binding = (
        str(uuid.uuid4()) for _ in range(7)
    )
    routed_call = call_uuid("managed-upgrade")
    draft = validate_draft(content())
    speech_digest = canonical_digest({"synthetic": "historical voice assets"})
    with connection(database) as c:
        c.execute(
            "INSERT INTO recipient_scopes(id,display_name,enabled) VALUES(%s,'Synthetic',true)",
            (scope,),
        )
        c.execute(
            "INSERT INTO users(id,login,display_name,password_hash) "
            "VALUES(%s,'historical.owner','Synthetic',%s)",
            (user, "not-an-authenticating-hash" * 5),
        )
        c.execute(
            "INSERT INTO assistant_profiles(id,scope_id,label,enabled) "
            "VALUES(%s,%s,'Historical assistant',true)",
            (agent, scope),
        )
        c.execute(
            """INSERT INTO agent_preparations(id,scope_id,profile_id,draft_version,
            requested_by,model_id,model_revision,content,content_digest,speech_digest)
            VALUES(%s,%s,%s,1,%s,%s,1,%s,%s,%s)""",
            (
                preparation,
                scope,
                agent,
                user,
                draft.model,
                Jsonb(draft.model_dump()),
                canonical_digest(draft.model_dump()),
                speech_digest,
            ),
        )
        assets = {"synthetic": "historical voice assets"}
        c.execute(
            "INSERT INTO prepared_voice_assets(scope_id,speech_digest,manifest,manifest_digest) "
            "VALUES(%s,%s,%s,%s)",
            (scope, speech_digest, Jsonb(assets), canonical_digest(assets)),
        )
        manifest = dict(
            schema_version=1,
            content=draft.model_dump(),
            model=qualified_model(c, draft.model),
            voice_assets=assets,
        )
        c.execute(
            """INSERT INTO assistant_profile_revisions(scope_id,profile_id,revision,
            owner_display_name,agent_name,owner_address,owner_dative,owner_genitive,
            role_description,tone_description,greeting_template,availability_text)
            VALUES(%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                scope,
                agent,
                draft.owner_display_name,
                draft.agent_name,
                draft.owner_address,
                draft.owner_dative,
                draft.owner_genitive,
                draft.role_description,
                draft.tone_description,
                draft.greeting(),
                draft.availability_text,
            ),
        )
        c.execute(
            """INSERT INTO agent_releases(id,scope_id,profile_id,revision,preparation_id,
            speech_digest,manifest,manifest_digest,published_by)
            SELECT %s,scope_id,profile_id,1,id,speech_digest,%s,%s,requested_by
            FROM agent_preparations WHERE id=%s""",
            (release, Jsonb(manifest), canonical_digest(manifest), preparation),
        )
        c.execute(
            "INSERT INTO phone_numbers(id,scope_id,e164) VALUES(%s,%s,%s)",
            (number, scope, routing.DID),
        )
        c.execute(
            """INSERT INTO number_bindings(id,scope_id,number_id,revision,profile_id,
            release_id,node_id,created_by) VALUES(%s,%s,%s,1,%s,%s,%s,%s)""",
            (binding, scope, number, agent, release, routing.NODE, user),
        )
        c.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status) "
            "VALUES(%s,'managed-upgrade','inbound','ended')",
            (routed_call,),
        )
        c.execute(
            """INSERT INTO call_route_snapshots(call_id,scope_id,number_id,binding_id,
            profile_id,release_id,node_id,called_e164,called_source,manifest_digest)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'request_uri',%s)""",
            (
                routed_call,
                scope,
                number,
                binding,
                agent,
                release,
                routing.NODE,
                routing.DID,
                canonical_digest(manifest),
            ),
        )
        c.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status) VALUES(%s,'old-legacy','inbound','ended')",
            (call_uuid("old-legacy"),),
        )
        for cid in (routed_call, call_uuid("old-legacy")):
            c.execute("INSERT INTO summary_jobs(call_id) VALUES(%s)", (cid,))
    migrate(database)
    migrate(database)
    with connection(database) as c:
        jobs = dict(c.execute("SELECT call_id,scope_id FROM summary_jobs").fetchall())
        assert str(jobs[routed_call]) == scope
        assert jobs[call_uuid("old-legacy")] is None
        assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        assert c.execute(
            "SELECT action_grant_id FROM agent_releases WHERE id=%s", (release,)
        ).fetchone() == (None,)


def test_routed_service_never_falls_back_to_unscoped_store():
    from alojan_agent.service import AgentService

    store = Store("unused-test-dsn")
    legacy = AgentService(None, store)
    assert legacy.call_store("unknown") is store
    routed = AgentService(None, store, router=object())
    with pytest.raises(ValueError, match="route unavailable"):
        routed.call_store("unknown")
