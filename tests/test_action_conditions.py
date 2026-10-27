"""Typed post-call filters, exact consent and atomic fan-out; no real sends."""

import asyncio
import copy
import json
import uuid

from cryptography.fernet import Fernet
import pytest

from alojan.auth import Accounts, AuthError, connection
from alojan.action_grants import ActionGrants
from alojan.http_connections import HTTPConnections
from alojan.telegram_connections import TelegramConnections
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.numbers import Numbers
from alojan_contracts.action_conditions import matches
from alojan_contracts.actions import ActionReview, ReviewedAction
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.routing import validated_release
from alojan_contracts.runtime import compile_release
from alojan_contracts.secrets import SecretBox
from alojan_agent.action_delivery import ActionDelivery
from alojan_agent.records import CallRecords, CallSummaries
from test_action_grants import action, consent
from test_action_delivery import Transport, due
from test_http_actions import config, HTTPTransport, URL
from test_agent_drafts import content
from test_agent_releases import qualify, prepare_assets
from test_provider_connections import owner
from test_scoped_call_records import summary
from test_telegram_connections import body
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated


def test_conditions_are_closed_and_require_answered_final_metadata():
    event = dict(answered_at="2026-10-26T10:00:00Z", ended_at="2026-10-26T10:01:00Z")
    for status, ready, failed in [("done", True, False), ("failed", False, True)]:
        final = event | {"summary_status": status}
        assert matches("answered", final)
        assert matches("summary_ready", final) is ready
        assert matches("summary_failed", final) is failed
        for field in ("answered_at", "ended_at"):
            assert not matches("answered", final | {field: None})
    for condition in ("busy", "summary.urgency == high", "always", None):
        with pytest.raises(ValueError):
            matches(condition, event | {"summary_status": "done"})
        with pytest.raises(AuthError):
            validate_draft(
                content() | {"post_call_actions": [action(str(uuid.uuid4()), condition=condition)]}
            )
    for status in (None, "pending", "processing", True):
        with pytest.raises(ValueError):
            matches("answered", event | {"summary_status": status})


def test_conditional_reviews_are_versioned_and_default_digests_stay_identical():
    ref = str(uuid.uuid4())
    base = ReviewedAction(**action(ref), connection_label="Synthetic", chat_id="-1234")
    legacy = ActionReview(scope_id=ref, profile_id=ref, actions=[base])
    explicit = ActionReview(
        scope_id=ref, profile_id=ref, actions=[base.model_copy(update={"condition": "answered"})]
    )
    assert legacy.model_dump() == explicit.model_dump() and legacy.digest() == explicit.digest()
    for condition in ("summary_ready", "summary_failed"):
        selected = base.model_copy(update={"condition": condition})
        for version in (1, 2, 3):
            with pytest.raises(ValueError, match="review v4"):
                ActionReview(
                    schema_version=version, scope_id=ref, profile_id=ref, actions=[selected]
                )
        review = ActionReview(schema_version=4, scope_id=ref, profile_id=ref, actions=[selected])
        assert review.digest() != legacy.digest()


@pytest.fixture
def prepared(accounts, dedicated, tmp_path):
    qualify(accounts)
    scoped = Accounts(dedicated("management"))
    who = owner(accounts)
    box = SecretBox(Fernet.generate_key())
    http = HTTPConnections(scoped, box).create(
        *who, dict(label="Conditional CRM", endpoint=URL, auth_type="none", token=None)
    )["id"]
    telegram = TelegramConnections(scoped, box).create(*who, body())["id"]
    actions = [
        config(http, alias="ready", condition="summary_ready"),
        config(http, alias="failed", condition="summary_failed"),
        action(telegram, alias="all", condition="answered"),
        action(telegram, alias="telegram_ready", condition="summary_ready"),
    ]

    def create(selected=None, *, answer=True, reason="completed", cancel=False):
        draft = content() | {"post_call_actions": selected or actions}
        agent = Profiles(scoped).create(*who, draft)["id"]
        author = (*who, agent)
        consent(scoped, author)
        preparation, _, _ = prepare_assets(accounts, author, tmp_path)
        release = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
        number = routing.verified(accounts, *who, routing.DID)
        routing.ready(accounts, who[1], release)
        Numbers(scoped, routing.NODE).bind(*who, number, release, 2)
        route = routing.initialize(accounts, "condition-synthetic-call", routing.DID)

        async def finish_call():
            records = CallRecords(dedicated("records"), route)
            if cancel:
                await routing.CallRouter(dedicated("routing"), routing.NODE).cancel_unanswered(
                    route.call_id
                )
            else:
                if answer:
                    await records.answered(route.call_id)
                await records.end(route.call_id, reason)

        asyncio.run(finish_call())
        return author, draft, release

    return (
        create,
        scoped,
        CallSummaries(dedicated("summaries")),
        ActionDelivery(dedicated("actions"), box),
        actions,
    )


@pytest.mark.parametrize("succeeded", [True, False])
def test_atomic_mixed_fanout_uses_pinned_condition_and_durable_summary_status(
    prepared, accounts, succeeded
):
    create, scoped, summaries, worker, actions = prepared
    author, draft, release = create()
    review = ActionGrants(scoped).review(*author)["review"]
    assert review["schema_version"] == 4
    with connection(accounts.dsn) as c:
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
    assert manifest["schema_version"] == 5
    assert compile_release(
        validated_release(manifest, canonical_digest(manifest)),
        canonical_digest(manifest),
        scope_id=author[1],
    )
    for version in (1, 2, 3, 4):
        downgraded = manifest | {"schema_version": version}
        with pytest.raises(ValueError, match="capability version"):
            validated_release(downgraded, canonical_digest(downgraded))
    # Draft edits do not change the pinned release's condition or grant.
    changed = copy.deepcopy(draft)
    changed["post_call_actions"][0]["condition"] = "summary_failed"
    Profiles(scoped).update(*author, changed, 1)

    async def run():
        job = await summaries.claim()
        await summaries.finish(job, summary() if succeeded else None)
        with pytest.raises(ValueError, match="expired or replaced"):
            await summaries.finish(job, summary())
        http, telegram = HTTPTransport(), Transport()
        expected = {"ready", "all", "telegram_ready"} if succeeded else {"failed", "all"}
        with connection(accounts.dsn) as c:
            assert {r[0] for r in c.execute("SELECT alias FROM action_jobs")} == expected
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone()[0] == 1
        for _ in expected:
            due(accounts)
            assert await worker.process_one(telegram, http_transport=http)
        due(accounts)
        assert not await worker.process_one(telegram, http_transport=http)
        assert len(http.calls) == 1 and len(telegram.calls) == (2 if succeeded else 1)
        payload = json.loads(http.calls[0][1]["body"])
        assert payload["summary_status"] == ("done" if succeeded else "failed")
        if not succeeded:
            assert payload["summary"] is None

    asyncio.run(run())


def test_unmatched_condition_finalizes_without_job_dispatch_scope_or_replay(prepared, accounts):
    create, _, summaries, worker, actions = prepared
    create([actions[0]])

    async def run():
        job = await summaries.claim()
        await summaries.finish(job)
        assert not await summaries.claim()
        assert not await worker.process_one(Transport(), http_transport=HTTPTransport())

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT summary_status FROM call_finalizations").fetchone() == ("failed",)
        assert c.execute("SELECT status FROM summary_jobs").fetchone() == ("failed",)
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM action_dispatch_scopes").fetchone()[0] == 0


def test_condition_change_requires_fresh_consent_and_does_not_mutate_old_grant(
    prepared, accounts, tmp_path
):
    create, scoped, _, _, _ = prepared
    author, draft, release = create()
    grants = ActionGrants(scoped)
    before = grants.review(*author)
    changed = copy.deepcopy(draft)
    changed["post_call_actions"][0]["condition"] = "answered"
    Profiles(scoped).update(*author, changed, 1)
    after = grants.review(*author)
    assert before["review_digest"] != after["review_digest"]
    with pytest.raises(AuthError, match="stale_action_review"):
        grants.authorize(*author, dict(draft_version=2, review_digest=before["review_digest"]))
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, 2)
    with pytest.raises(AuthError, match="action_grant_required"):
        Releases(scoped).publish(*author, preparation["id"], 1)
    consent(scoped, author)
    Releases(scoped).publish(*author, preparation["id"], 1)
    with connection(accounts.dsn) as c:
        pinned = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
        assert pinned["action_grant"]["review"]["actions"][0]["condition"] == "summary_ready"


def test_readonly_condition_examples_match_contract(accounts):
    from pathlib import Path
    from alojan_contracts.http_actions import HTTPAction

    with connection(accounts.dsn) as c:
        examples = c.execute(Path("infra/examples/post-call-conditions.sql").read_text()).fetchall()
        assert {HTTPAction.model_validate(row[0]).condition for row in examples} == {
            "answered",
            "summary_ready",
            "summary_failed",
        }
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0
