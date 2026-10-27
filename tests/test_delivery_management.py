"""Owner retry review with real roles/RLS and a synthetic delivery transport."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import create_app, COOKIE
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.action_grants import ActionGrants
from alojan.deliveries import Deliveries
from alojan.profiles import Profiles
from alojan.telegram_connections import TelegramConnections
from alojan_agent.records import CallRecords
from alojan_agent.telegram_delivery import Result
from test_action_grants import consent
from test_action_delivery import Transport, finalize, due
import test_action_delivery as delivery_tests
from test_scoped_call_records import ended
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
prepared = delivery_tests.prepared


@pytest.fixture
def case(accounts, prepared, dedicated):
    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    asyncio.run(worker.process_one(Transport(Result("delivery_unknown", "send_uncertain"))))
    due(accounts)
    with connection(accounts.dsn) as c:
        job = str(c.execute("SELECT id FROM action_jobs").fetchone()[0])
    store = Deliveries(Accounts(dedicated("management")))
    return one, job, store, worker


def request(review, **changes):
    return (
        dict(
            request_id=str(uuid.uuid4()),
            review_digest=review["review_digest"],
            accept_duplicate_risk=True,
        )
        | changes
    )


def test_api_status_privacy_csrf_and_exact_review(accounts, case):
    one, job, store, worker = case
    author = one["author"]
    with TestClient(create_app(store.accounts, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, author[0])
        base = f"/v1/workspaces/{author[1]}/agents/{author[2]}/deliveries"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(author[0])}
        listing = client.get(base)
        assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
        item = listing.json()["deliveries"][0]
        assert item["status"] == "delivery_unknown" and not item["retry_queued"]
        assert not {"action", "payload", "claim_token", "message_text"} & item.keys()
        detail = client.get(base + "/" + job).json()
        assert detail["retries"] == []
        preview = client.get(base + "/" + job + "/retry-review")
        assert preview.status_code == 200
        review = preview.json()
        assert (
            review["can_retry"]
            and review["review"]["duplicate_warning"] == "duplicate_delivery_possible"
        )
        assert "iki kez" in review["warning"] and "Assistant1" in review["review"]["message_text"]
        assert review["review"]["action"]["chat_id"] == one["target"]["chat_id"]
        assert one["target"]["bot_token"] not in listing.text + preview.text
        body = request(review)
        Profiles(accounts).update(*author, one["config"] | {"agent_name": "Different"}, 1)
        assert (
            client.get(base + "/" + job + "/retry-review").json()["review_digest"]
            == review["review_digest"]
        )
        assert client.post(base + "/" + job + "/retry", json=body).status_code == 403
        for invalid in (
            {"accept_duplicate_risk": False},
            {"accept_duplicate_risk": 1},
            {"message_text": "Replacement"},
            {"request_id": 1},
            {"connection_id": str(uuid.uuid4())},
        ):
            assert (
                client.post(
                    base + "/" + job + "/retry", json=body | invalid, headers=headers
                ).status_code
                == 400
            )
        result = client.post(base + "/" + job + "/retry", json=body, headers=headers)
        assert result.status_code == 202, result.text
        assert client.get(base + "/" + job).json()["retry_queued"]
        # Approval queues a request, never sends HTTP or rewrites the outcome itself.
        assert store.get(*author, job)["status"] == "delivery_unknown"
        assert (
            client.post(base + "/" + job + "/retry", json=body, headers=headers).json()
            == result.json()
        )
        assert (
            client.get(base + "/" + job + "/retry-review").json()["blocked_reason"]
            == "retry_already_requested"
        )
        for params in ("limit=100000", "status=unknown", "status=sent&status=failed", "after=bad"):
            assert client.get(base + "?" + params).status_code == 400
    transport = Transport()
    assert asyncio.run(worker.process_one(transport))
    assert transport.calls == [
        (one["target"]["bot_token"], one["target"]["chat_id"], review["review"]["message_text"])
    ]
    final = store.get(*author, job)
    assert (
        final["status"] == "sent" and final["retry_generation"] == 1 and not final["retry_queued"]
    )
    assert final["retries"][0]["previous_status"] == "delivery_unknown"
    assert (
        store.retry(*author, job, body) == result.json()
    )  # Lost-response replay after completion is inert.
    assert not asyncio.run(worker.process_one(transport))
    assert len(transport.calls) == 1


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_members_read_metadata_but_cannot_review_or_retry(accounts, case, role):
    one, job, store, _ = case
    review = store.review(*one["author"], job)
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE workspace_memberships SET role=%s WHERE scope_id=%s", (role, one["author"][1])
        )
    assert store.list(*one["author"])["deliveries"][0]["id"] == job
    assert store.get(*one["author"], job)["status"] == "delivery_unknown"
    for invoke in (
        lambda: store.review(*one["author"], job),
        lambda: store.retry(*one["author"], job, request(review)),
    ):
        with pytest.raises(AuthError, match="forbidden"):
            invoke()


def test_foreign_workspace_agent_cursor_and_request_id_are_not_interchangeable(accounts, case):
    one, job, store, _ = case
    foreign = owner(accounts, "foreign.owner")
    other_agent = Profiles(accounts).create(*one["author"][:2], one["config"])["id"]
    for author in ((*foreign, one["author"][2]), (*one["author"][:2], other_agent)):
        with pytest.raises(AuthError, match="not_found"):
            store.get(*author, job)
        with pytest.raises(AuthError, match="not_found"):
            store.review(*author, job)
    with pytest.raises(AuthError, match="invalid_delivery_cursor"):
        store.list(*one["author"][:2], other_agent, after=job)
    with connection(store.accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM action_retry_requests").fetchone() == (0,)


def test_concurrent_duplicate_consent_audits_once_and_fences_old_reviews(accounts, case):
    one, job, store, worker = case
    review = store.review(*one["author"], job)
    body = request(review)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.retry(*one["author"], job, body), range(2)))
    assert results[0] == results[1]
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM action_retry_requests").fetchone() == (1,)
        assert c.execute(
            "SELECT count(*) FROM management_audit WHERE event='delivery.retry_requested'"
        ).fetchone() == (1,)
    asyncio.run(worker.process_one(Transport(Result("delivery_unknown", "send_uncertain"))))
    due(accounts)
    # Same status, payload and attempt count after a round are still a different generation.
    with pytest.raises(AuthError, match="stale_retry_review"):
        store.retry(*one["author"], job, request(review))
    with pytest.raises(AuthError, match="retry_request_conflict"):
        store.retry(*one["author"], job, body | {"review_digest": "0" * 64})
    for generation in (2, 3):
        store.retry(*one["author"], job, request(store.review(*one["author"], job)))
        assert asyncio.run(
            worker.process_one(Transport(Result("delivery_unknown", "send_uncertain")))
        )
        due(accounts)
        assert store.get(*one["author"], job)["retry_generation"] == generation
    assert store.review(*one["author"], job)["blocked_reason"] == "manual_retry_limit"
    with pytest.raises(AuthError, match="manual_retry_limit"):
        store.retry(*one["author"], job, request(store.review(*one["author"], job)))


@pytest.mark.parametrize("timing", ["before_approval", "before_dispatch"])
@pytest.mark.parametrize("kind", ["grant", "target", "issuer"])
def test_original_authority_is_required_at_approval_and_dispatch(accounts, case, timing, kind):
    one, job, store, worker = case
    body = request(store.review(*one["author"], job))
    if timing == "before_dispatch":
        store.retry(*one["author"], job, body)
    if kind == "grant":
        ActionGrants(accounts).revoke(*one["author"], one["grant"])
        consent(accounts, one["author"])
    elif kind == "target":
        TelegramConnections(accounts).revoke(*one["author"][:2], one["reference"])
    else:
        with connection(accounts.dsn) as c:
            c.execute(
                "UPDATE workspace_memberships SET role='editor' WHERE scope_id=%s",
                (one["author"][1],),
            )
    if timing == "before_approval":
        with pytest.raises(AuthError):
            store.retry(*one["author"], job, body)
    transport = Transport()
    asyncio.run(worker.process_one(transport))
    assert transport.calls == []
    with connection(accounts.dsn) as c:
        status = c.execute("SELECT status FROM action_jobs").fetchone()[0]
    assert status == ("paused" if timing == "before_dispatch" else "delivery_unknown")


def test_retry_requester_remains_owner_independently_of_original_issuer(accounts, case):
    one, job, store, worker = case
    other = owner(accounts, "retry.owner")
    with connection(accounts.dsn) as c:
        actor = c.execute(
            "SELECT user_id FROM workspace_memberships WHERE scope_id=%s", (other[1],)
        ).fetchone()[0]
        c.execute(
            "INSERT INTO workspace_memberships(scope_id,user_id,role) VALUES(%s,%s,'owner')",
            (one["author"][1], actor),
        )
    author = (other[0], *one["author"][1:])
    store.retry(*author, job, request(store.review(*author, job)))
    claim = asyncio.run(worker.claim())
    assert claim is not None
    with connection(accounts.dsn) as c:
        c.execute("UPDATE users SET enabled=false WHERE id=%s", (actor,))
    assert asyncio.run(worker.begin(claim)) is None
    assert store.get(*one["author"], job)["status"] == "paused"


def test_roles_cannot_fabricate_delivery_or_mutate_retry_intent(accounts, dedicated, case):
    one, job, store, worker = case
    for dsn in (store.accounts.dsn, worker.dsn):
        with connection(dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("INSERT INTO action_jobs(id) SELECT id FROM action_jobs")
    with connection(store.accounts.dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("UPDATE action_jobs SET status='pending'")
    with connection(worker.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute(
            "UPDATE action_jobs SET status='pending',retry_generation=1,attempts=0,failure_code=NULL"
        )
    accepted = store.retry(*one["author"], job, request(store.review(*one["author"], job)))
    for query in (
        "UPDATE action_retry_requests SET review='{}'",
        "DELETE FROM action_retry_requests",
    ):
        with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute(query)
    for purpose in ("actions", "summaries", "credentials", "records", "routing", "readiness"):
        with (
            connection(dedicated(purpose)) as c,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            c.execute("INSERT INTO action_retry_requests SELECT * FROM action_retry_requests")
    assert accepted["generation"] == 1


def test_delivery_history_pagination_and_status_filter(accounts, prepared, dedicated):
    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    asyncio.run(worker.process_one(Transport()))

    async def populate():
        for index in range(51):
            routing.ready(accounts, one["author"][1], one["release"])
            route = await routing.CallRouter(accounts.dsn, routing.NODE).initialize(
                f"page-call-{index}", routing.DID, "request_uri"
            )
            await ended(CallRecords(accounts.dsn, route))
            await finalize(summaries)

    asyncio.run(populate())
    store = Deliveries(Accounts(dedicated("management")))
    first = store.list(*one["author"])
    assert len(first["deliveries"]) == 50 and first["next_cursor"] is not None
    second = store.list(*one["author"], after=first["next_cursor"])
    assert len(second["deliveries"]) == 2 and second["next_cursor"] is None
    assert len({r["id"] for r in first["deliveries"] + second["deliveries"]}) == 52
    sent = store.list(*one["author"], status="sent")["deliveries"]
    assert len(sent) == 1 and sent[0]["remote_message_id"] == 42
    assert store.review(*one["author"], sent[0]["id"])["blocked_reason"] == "delivery_not_retryable"


def test_readiness_requires_retry_migration(accounts):
    assert accounts.ready()
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE schema_migrations SET name='held-0015' WHERE name='0015_action_retries.sql'"
        )
    assert not accounts.ready()


@pytest.mark.parametrize("status", ["pending", "leased", "sending"])
def test_active_delivery_cannot_be_retried(accounts, prepared, dedicated, status):
    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    if status != "pending":
        claim = asyncio.run(worker.claim())
        if status == "sending":
            assert asyncio.run(worker.begin(claim))
    with connection(accounts.dsn) as c:
        job = str(c.execute("SELECT id FROM action_jobs").fetchone()[0])
    store = Deliveries(Accounts(dedicated("management")))
    preview = store.review(*one["author"], job)
    assert preview["blocked_reason"] == "delivery_not_retryable"
    with pytest.raises(AuthError, match="delivery_not_retryable"):
        store.retry(*one["author"], job, request(preview))


@pytest.mark.parametrize("status", ["failed", "paused"])
def test_failed_or_paused_job_retries_with_original_live_authority(
    accounts, prepared, dedicated, status
):
    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    if status == "failed":
        asyncio.run(worker.process_one(Transport(Result("failed", "rejected"))))
    else:
        claim = asyncio.run(worker.claim())
        with connection(accounts.dsn) as c:
            c.execute("UPDATE users SET enabled=false")
        assert asyncio.run(worker.begin(claim)) is None
        with connection(accounts.dsn) as c:
            c.execute("UPDATE users SET enabled=true")
    with connection(accounts.dsn) as c:
        job = str(c.execute("SELECT id FROM action_jobs").fetchone()[0])
    store = Deliveries(Accounts(dedicated("management")))
    preview = store.review(*one["author"], job)
    assert preview["can_retry"] and preview["review"]["job"]["status"] == status
    store.retry(*one["author"], job, request(preview))
    due(accounts)
    assert asyncio.run(worker.process_one(Transport()))
    assert store.get(*one["author"], job)["status"] == "sent"


def test_retry_and_audit_are_atomic_and_consumer_consumption_is_irreversible(accounts, case):
    one, job, store, worker = case
    body = request(store.review(*one["author"], job))
    with connection(accounts.dsn) as c:
        c.execute(
            "ALTER TABLE management_audit ADD CONSTRAINT reject_retry_audit CHECK(event<>'delivery.retry_requested')"
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        store.retry(*one["author"], job, body)
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM action_retry_requests").fetchone() == (0,)
        c.execute("ALTER TABLE management_audit DROP CONSTRAINT reject_retry_audit")
    accepted = store.retry(*one["author"], job, body)
    claim = asyncio.run(worker.claim())
    assert claim is not None
    with connection(accounts.dsn) as c:
        assert c.execute(
            "SELECT consumed_at IS NOT NULL FROM action_retry_requests WHERE id=%s",
            (accepted["id"],),
        ).fetchone() == (True,)
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute("UPDATE action_retry_requests SET consumed_at=NULL")
    with connection(store.accounts.dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("UPDATE action_retry_requests SET consumed_at=now()")


def test_distinct_concurrent_requests_consume_once(accounts, case):
    one, job, store, worker = case
    preview = store.review(*one["author"], job)

    def approve(_):
        try:
            return store.retry(*one["author"], job, request(preview))["status"]
        except AuthError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))
    assert sorted(results) == ["accepted", "retry_already_requested"]

    async def consume():
        claims = await asyncio.gather(worker.claim(), worker.claim())
        claimed = [c for c in claims if c is not None]
        assert len(claimed) <= 1
        if not claimed:
            # A peer can hold the dispatch gate while the retry consumer holds the job.
            # Both skip locked work; the next poll must still claim that single reopened job.
            claimed = [await worker.claim()]
        assert claimed[0] is not None and str(claimed[0].id) == job

    asyncio.run(consume())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT retry_generation,attempts FROM action_jobs").fetchone() == (1, 1)
        assert c.execute(
            "SELECT count(*) FROM action_retry_requests WHERE consumed_at IS NOT NULL"
        ).fetchone() == (1,)


def test_retry_consumed_under_busy_dispatch_gate_remains_claimable(accounts, case):
    one, job, store, worker = case
    store.retry(*one["author"], job, request(store.review(*one["author"], job)))
    with connection(accounts.dsn) as blocker:
        blocker.execute("SELECT 1 FROM action_dispatch_clock FOR UPDATE")
        assert asyncio.run(worker.claim()) is None
        assert blocker.execute(
            "SELECT status,retry_generation,attempts FROM action_jobs"
        ).fetchone() == ("pending", 1, 0)
        assert blocker.execute(
            "SELECT count(*) FROM action_retry_requests WHERE consumed_at IS NOT NULL"
        ).fetchone() == (1,)
    claim = asyncio.run(worker.claim())
    assert claim is not None and str(claim.id) == job
    assert asyncio.run(worker.claim()) is None
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT retry_generation,attempts FROM action_jobs").fetchone() == (1, 1)


def test_changed_renderer_fails_closed_after_approval(accounts, case, monkeypatch):
    one, job, store, worker = case
    store.retry(*one["author"], job, request(store.review(*one["author"], job)))
    monkeypatch.setattr("alojan_agent.action_delivery.render", lambda *_: "Unreviewed replacement")
    transport = Transport()
    assert asyncio.run(worker.process_one(transport))
    assert not transport.calls
    assert store.get(*one["author"], job)["failure_code"] == "invalid_intent"


def test_provisioning_rejects_existing_queue_or_consent_write_privileges(accounts, case):
    from alojan.roles import grant_actions, grant_management
    from psycopg import sql

    one, job, store, worker = case
    with connection(store.accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (one["author"][1],))
        c.execute("UPDATE action_jobs SET id=gen_random_uuid() WHERE id=%s", (job,))
    for dsn, table, column, provision in (
        (store.accounts.dsn, "action_jobs", "status", grant_management),
        (worker.dsn, "action_retry_requests", "review", grant_actions),
    ):
        with connection(dsn) as c:
            role = c.execute("SELECT current_user").fetchone()[0]
        with connection(accounts.dsn) as c:
            c.execute(
                sql.SQL("GRANT UPDATE({}) ON {} TO {}").format(
                    sql.Identifier(column), sql.Identifier(table), sql.Identifier(role)
                )
            )
        with pytest.raises(ValueError):
            provision(accounts.dsn, role)
