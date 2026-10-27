"""Pinned no-answer/interrupted delivery; real restricted DB roles, synthetic network only."""

import asyncio
import json
import uuid

import pytest

from alojan.auth import connection
from alojan.action_grants import ActionGrants
from alojan.profiles import Profiles
from alojan_contracts.action_conditions import matches
from alojan_contracts.actions import ActionReview
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.routing import validated_release
from alojan_contracts.http_actions import HTTPAction
import test_action_conditions as conditions
from test_action_delivery import Transport, due
from test_http_actions import config, source, HTTPTransport
from test_scoped_call_records import summary
from test_transcript_sharing import shared

prepared, accounts, database, dedicated = (
    conditions.prepared,
    conditions.accounts,
    conditions.database,
    conditions.dedicated,
)


def test_lifecycle_conditions_use_observed_metadata_not_model_text():
    for outcome in ("completed", "disconnected", "failed", "disconnected probably", None):
        for answered in (None, "2026-10-26T10:00:00Z"):
            for status in ("done", "failed", "not_requested"):
                event = dict(
                    ended_at="2026-10-26T10:01:00Z",
                    answered_at=answered,
                    summary_status=status,
                    outcome=outcome,
                )
                assert matches("no_answer", event) is (
                    answered is None and status == "not_requested"
                )
                assert matches("interrupted", event) is (
                    answered is not None
                    and status != "not_requested"
                    and outcome in ("disconnected", "failed")
                )
                if answered is None or status == "not_requested":
                    for condition in ("answered", "summary_ready", "summary_failed"):
                        assert not matches(condition, event)
                assert not matches("no_answer", event | {"ended_at": None})
    with pytest.raises(ValueError, match="disclosed"):
        HTTPAction(**shared(str(uuid.uuid4()), condition="no_answer"))


@pytest.mark.parametrize("cancel", [False, True])
def test_no_answer_finalizes_without_model_or_summary_and_only_selected_action(
    prepared, accounts, cancel
):
    create, scoped, summaries, worker, actions = prepared
    ref = actions[0]["connection_id"]
    selected = config(
        ref,
        condition="no_answer",
        body={
            "call": source("call_id", "fail"),
            "state": source("summary_status", "fail"),
            "summary": source("summary.summary"),
            "answer": source("answered_at"),
            "duration": source("duration_ms"),
        },
    )
    author, draft, release = create(
        [selected, config(ref, alias="answered")], answer=False, cancel=cancel
    )
    with connection(accounts.dsn) as c:
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
        assert manifest["schema_version"] == 7
        assert manifest["action_grant"]["review"]["schema_version"] == 6
    for version in (1, 2, 3, 4, 5, 6):
        changed = manifest | {"schema_version": version}
        with pytest.raises(ValueError):
            validated_release(changed, canonical_digest(changed))
    review = manifest["action_grant"]["review"]
    for version in (1, 2, 3, 4, 5):
        with pytest.raises(ValueError):
            ActionReview.model_validate(review | {"schema_version": version})
    draft["post_call_actions"][0]["condition"] = "answered"
    Profiles(scoped).update(*author, draft, 1)
    assert (
        ActionGrants(scoped).review(*author)["review_digest"]
        != ActionReview.model_validate(review).digest()
    )

    class NoModel:
        async def prepare_runtime(self, *_args):
            pytest.fail("Unanswered call prepared a model")

        async def summarize(self, *_args, **_kwargs):
            pytest.fail("Unanswered call invoked a model")

    async def run():
        assert await summaries.process_one(NoModel())
        assert not await summaries.process_one(NoModel())
        http = HTTPTransport()
        due(accounts)
        assert await worker.process_one(Transport(), http_transport=http)
        assert len(http.calls) == 1
        sent = json.loads(http.calls[0][1]["body"])
        assert sent["state"] == "not_requested"
        assert sent["summary"] is None and sent["answer"] is None and sent["duration"] is None
        assert not await worker.process_one(Transport(), http_transport=http)

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        event = c.execute("SELECT payload FROM call_finalizations").fetchone()[0]
        assert (
            event["schema_version"] == 4 and event["summary"] is None and event["last_note"] is None
        )
        assert c.execute("SELECT count(*) FROM call_summaries").fetchone()[0] == 0
        assert c.execute(
            "SELECT status,failure_code,claim_token,lease_until FROM summary_jobs"
        ).fetchone() == ("not_requested", None, None, None)
        assert c.execute("SELECT alias FROM action_jobs").fetchall() == [(selected["alias"],)]


@pytest.mark.parametrize("outcome,expected", [("completed", 0), ("disconnected", 1), ("failed", 1)])
def test_interrupted_uses_exact_native_outcome_and_preserves_summary(
    prepared, accounts, outcome, expected
):
    create, _, summaries, worker, actions = prepared
    create([config(actions[0]["connection_id"], condition="interrupted")], reason=outcome)

    async def run():
        await summaries.finish(await summaries.claim(), summary())
        http = HTTPTransport()
        due(accounts)
        assert await worker.process_one(Transport(), http_transport=http) is bool(expected)
        assert len(http.calls) == expected

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        event = c.execute("SELECT payload FROM call_finalizations").fetchone()[0]
        assert event["outcome"] == outcome and event["summary_status"] == "done"
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == expected


def test_default_unanswered_call_does_not_enqueue_new_work(prepared, accounts):
    create, _, _, _, actions = prepared
    create([config(actions[0]["connection_id"])], answer=False)
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM call_finalizations").fetchone()[0] == 0


def test_unanswered_claim_rejects_fabricated_summary_and_duplicate_cancellation(
    prepared, accounts, dedicated
):
    from alojan_agent.routing import CallRouter
    from test_number_routing import NODE

    create, _, summaries, _, actions = prepared
    create([config(actions[0]["connection_id"], condition="no_answer")], answer=False, cancel=True)

    async def run():
        router = CallRouter(dedicated("routing"), NODE)
        assert not await router.cancel_unanswered("condition-synthetic-call")
        job = await summaries.claim()
        with pytest.raises(ValueError, match="cannot have a summary"):
            await summaries.finish(job, summary())
        with pytest.raises(ValueError, match="cannot have a summary"):
            await summaries.finish(job, outputs={"invented": "text"})
        await summaries.finish(job)
        with pytest.raises(ValueError, match="expired"):
            await summaries.finish(job)
        assert not await router.cancel_unanswered("condition-synthetic-call")
        # A cancellation before any route has no recipient and cannot notify the configured agent.
        assert await router.cancel_unanswered("unknown-before-initialization")

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM call_finalizations").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 1


def test_reconciled_unanswered_route_queues_original_intent_once(prepared, accounts, dedicated):
    from alojan_agent.routing import CallRouter
    from alojan_agent.records import CallRecords
    from alojan_agent.store import call_uuid
    from test_number_routing import NODE, DID

    create, _, _, _, actions = prepared
    create([config(actions[0]["connection_id"], condition="no_answer")], answer=False)

    async def run():
        route = await CallRouter(dedicated("routing"), NODE).initialize(
            "lost-no-answer", DID, "request_uri"
        )
        with connection(accounts.dsn) as c:
            c.execute(
                "UPDATE calls SET started_at=now()-interval '10 minutes' WHERE id=%s",
                (call_uuid(route.call_id),),
            )
        records = CallRecords(dedicated("records"), route)
        assert await records.reconcile(300) == 1
        assert await records.reconcile(300) == 0
        with connection(accounts.dsn) as c:
            assert (
                c.execute(
                    "SELECT count(*) FROM summary_jobs WHERE call_id=%s AND scope_id=%s AND release_id=%s",
                    (call_uuid(route.call_id), route.scope_id, route.release_id),
                ).fetchone()[0]
                == 1
            )
            assert (
                c.execute(
                    "SELECT failure_code FROM calls WHERE id=%s", (call_uuid(route.call_id),)
                ).fetchone()[0]
                == "abandoned_initialization"
            )

    asyncio.run(run())


def test_readonly_lifecycle_examples_and_migration_readiness(accounts):
    from pathlib import Path

    with connection(accounts.dsn) as c:
        statements = Path("infra/examples/call-lifecycle-actions.sql").read_text().split(";")
        actions = [
            HTTPAction.model_validate(c.execute(s).fetchone()[0])
            for s in statements
            if "SELECT" in s
        ]
        assert [a.condition for a in actions] == ["no_answer", "interrupted"]
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0
    assert accounts.ready()
    with connection(accounts.dsn) as c:
        c.execute("DELETE FROM schema_migrations WHERE name='0025_call_lifecycle_actions.sql'")
    assert not accounts.ready()


@pytest.mark.parametrize("method", ["cancel", "end_without_answer"])
def test_private_grpc_unanswered_lifecycle_enqueues_pinned_action(
    prepared, accounts, dedicated, tmp_path, method
):
    from voice.v1 import voice_pb2 as pb
    from test_answered_lifecycle import running, answer, ending
    from test_call_initialization import setup, lease
    from alojan_agent.store import call_uuid

    create, _, _, _, actions = prepared
    author, _, release = create(
        [config(actions[0]["connection_id"], condition="no_answer")], answer=False
    )

    async def run():
        async with running(
            accounts, (*author, release), tmp_path, dedicated("records"), dedicated("routing")
        ) as (_, _, stub, control):
            cid = "managed-unanswered-action"
            metadata = await lease(control, cid)
            reply = await stub.InitializeCall(setup(cid), timeout=2, metadata=metadata)
            if method == "cancel":
                request = pb.CallSetupCancellation(call_id=cid)
                assert (await stub.CancelCallSetup(request, timeout=2, metadata=metadata)).accepted
            else:
                request = ending(answer(reply, cid), answered_at_unix_ms=0)
                assert (await stub.EndCall(request, timeout=2, metadata=metadata)).accepted
            with connection(accounts.dsn) as c:
                assert c.execute(
                    "SELECT status,answered_at FROM calls WHERE id=%s", (call_uuid(cid),)
                ).fetchone() == ("ended", None)
                assert c.execute(
                    "SELECT scope_id::text,release_id::text FROM summary_jobs WHERE call_id=%s",
                    (call_uuid(cid),),
                ).fetchone() == (author[1], release)

    asyncio.run(run())
