"""Real PostgreSQL fencing/consent isolation; synthetic network only, no external messages."""

import asyncio
from dataclasses import replace
import json
import os
import sys
import socket
import uuid

from cryptography.fernet import Fernet
import httpx2 as httpx
import psycopg
import pytest

from alojan.auth import connection
from alojan.action_grants import ActionGrants
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan.telegram_connections import TelegramConnections
from alojan_contracts.actions import ReviewedAction
from alojan_contracts.secrets import SecretBox
from alojan_agent.action_delivery import ActionDelivery
from alojan_contracts.delivery import project, render
from alojan_agent.records import CallRecords, CallSummaries
from alojan_agent.telegram_delivery import Telegram, Result, response
from test_action_grants import action, consent
from test_agent_drafts import content
from test_agent_releases import prepare_assets, qualify
from test_provider_connections import owner
from test_scoped_call_records import ended, summary
from test_telegram_connections import body
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated


@pytest.fixture
def prepared(accounts, dedicated, tmp_path):
    qualify(accounts)
    key = Fernet.generate_key()
    (tmp_path / "delivery.key").write_bytes(key)
    box = SecretBox(key)
    worker = ActionDelivery(dedicated("actions"), box)
    summaries = CallSummaries(dedicated("summaries"))
    records_dsn = dedicated("records")

    def create(index=1, fields=None, who=None):
        who = who or owner(accounts, f"owner{index}")
        target = body() | {
            "chat_id": str(-1000000000000 - index),
            "bot_token": f"{index}:synthetic_private_bot_token_for_tests",
        }
        reference = TelegramConnections(accounts, box).create(*who, target)["id"]
        selected = action(
            reference, fields=fields or ["agent_name", "summary_status", "summary.subject"]
        )
        config = content(f"Assistant{index}") | {"post_call_actions": [selected]}
        profile = Profiles(accounts).create(*who, config)["id"]
        author = (*who, profile)
        grant = consent(accounts, author)["id"]
        preparation, _, _ = prepare_assets(accounts, author, tmp_path)
        release = Releases(accounts).publish(*author, preparation["id"], 0)["id"]
        did = routing.DID if index == 1 else routing.OTHER_DID
        number = routing.verified(accounts, *who, did)
        routing.ready(accounts, who[1], release)
        from alojan.numbers import Numbers

        Numbers(accounts, routing.NODE).bind(*who, number, release, 2)
        route = routing.initialize(accounts, f"action-call-{index}", did)
        asyncio.run(ended(CallRecords(records_dsn, route)))
        return dict(
            author=author,
            reference=reference,
            grant=grant,
            route=route,
            target=target,
            config=config,
            release=release,
        )

    return create, worker, summaries


class Transport:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or Result("sent", message_id=42)

    async def resolve(self):
        return "149.154.167.220"

    async def send(self, address, token, chat_id, text):
        self.calls.append((token, chat_id, text))
        return self.result


def state(accounts):
    with connection(accounts.dsn) as c:
        return c.execute(
            "SELECT status,failure_code,attempts,remote_message_id FROM action_jobs ORDER BY created_at,id"
        ).fetchall()


def due(accounts, *, expire=False):
    with connection(accounts.dsn) as c:
        c.execute("UPDATE action_dispatch_clock SET next_dispatch_at='-infinity'")
        c.execute("UPDATE action_dispatch_scopes SET next_dispatch_at='-infinity'")
        if expire:
            c.execute(
                "UPDATE action_jobs SET lease_until=now()-interval '1 second' WHERE status IN ('leased','sending')"
            )


async def finalize(summaries, result=True):
    job = await summaries.claim()
    assert job is not None
    await summaries.finish(job, summary() if result else None)
    return job


@pytest.mark.parametrize("same_workspace", [False, True])
def test_original_scoped_targets_selected_fields_and_atomic_single_fanout(
    accounts, prepared, same_workspace
):
    create, worker, summaries = prepared
    one = create()
    two = create(
        2,
        fields=["call_id", "last_note.subject"],
        who=one["author"][:2] if same_workspace else None,
    )
    # Later identity/fields do not rewrite already pinned calls.
    Profiles(accounts).update(*one["author"], one["config"] | {"agent_name": "Changed"}, 1)

    async def run():
        first = await finalize(summaries)
        await finalize(summaries, False)
        with pytest.raises(ValueError, match="expired or replaced"):
            await summaries.finish(first, summary())
        transport = Transport()
        assert await worker.process_one(transport)
        due(accounts)
        assert await worker.process_one(transport)
        assert not await worker.process_one(transport)
        assert len(transport.calls) == 2
        by_chat = {chat: (token, text) for token, chat, text in transport.calls}
        assert by_chat[one["target"]["chat_id"]][0] == one["target"]["bot_token"]
        assert "Assistant1" in by_chat[one["target"]["chat_id"]][1]
        assert "Changed" not in by_chat[one["target"]["chat_id"]][1]
        assert by_chat[two["target"]["chat_id"]][0] == two["target"]["bot_token"]
        assert "null" in by_chat[two["target"]["chat_id"]][1]
        assert "Assistant2" not in by_chat[two["target"]["chat_id"]][1]

    asyncio.run(run())
    assert state(accounts) == [("sent", None, 1, 42)] * 2
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (2,)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        assert body()["bot_token"] not in str(c.execute("SELECT * FROM action_jobs").fetchall())


def test_fanout_failure_rolls_back_summary_event_and_job(accounts, prepared):
    create, _, summaries = prepared
    create()

    async def run():
        job = await summaries.claim()
        with connection(accounts.dsn) as c:
            c.execute("ALTER TABLE action_jobs ADD CONSTRAINT injected_failure CHECK(false)")
        with pytest.raises(psycopg.errors.CheckViolation):
            await summaries.finish(job, summary())
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (0,)
            assert c.execute("SELECT count(*) FROM call_summaries").fetchone() == (0,)
            assert c.execute("SELECT status FROM summary_jobs").fetchone() == ("processing",)
            c.execute("ALTER TABLE action_jobs DROP CONSTRAINT injected_failure")
        await summaries.finish(job, summary())
        assert state(accounts) == [("pending", None, 0, None)]

    asyncio.run(run())


@pytest.mark.parametrize("revocation", ["grant", "target", "issuer", "membership", "workspace"])
def test_live_revocation_prevents_send_without_rerouting(accounts, prepared, revocation):
    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    if revocation == "grant":
        ActionGrants(accounts).revoke(*one["author"], one["grant"])
        consent(accounts, one["author"])  # Replacement authority must not resurrect old intent.
    elif revocation == "target":
        TelegramConnections(accounts).revoke(*one["author"][:2], one["reference"])
    else:
        with connection(accounts.dsn) as c:
            if revocation == "issuer":
                c.execute("UPDATE users SET enabled=false")
            elif revocation == "membership":
                c.execute("UPDATE workspace_memberships SET role='editor'")
            else:
                c.execute("UPDATE recipient_scopes SET enabled=false")
    transport = Transport()
    assert asyncio.run(worker.process_one(transport))
    assert not transport.calls
    assert state(accounts) == [("paused", "authority_revoked", 1, None)]


def test_claim_concurrency_fencing_crash_recovery_and_no_uncertain_replay(accounts, prepared):
    create, worker, summaries = prepared
    create()

    async def run():
        await finalize(summaries)
        claims = await asyncio.gather(*(worker.claim() for _ in range(4)))
        original = next(c for c in claims if c)
        assert sum(c is not None for c in claims) == 1
        due(accounts, expire=True)
        replacement = await worker.claim()
        assert replacement.token != original.token
        for stale in (original, replace(replacement, scope_id=str(uuid.uuid4()))):
            with pytest.raises(ValueError):
                await worker.begin(stale)
        dispatch = await worker.begin(replacement)
        assert dispatch and "synthetic_private" not in repr(dispatch)
        due(accounts, expire=True)
        assert await worker.claim() is None
        assert state(accounts) == [("delivery_unknown", "send_uncertain", 2, None)]
        with pytest.raises(ValueError):
            await worker.finish(replacement, Result("sent", message_id=3))
        with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE action_jobs SET status='pending'")

    asyncio.run(run())


def test_cancellation_during_send_is_unknown_and_not_retried(accounts, prepared):
    create, worker, summaries = prepared
    create()

    async def run():
        await finalize(summaries)
        entered = asyncio.Event()

        class Blocked(Transport):
            async def send(self, *args):
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(worker.process_one(Blocked()))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        due(accounts)
        assert await worker.claim() is None
        assert state(accounts) == [("delivery_unknown", "send_uncertain", 1, None)]

    asyncio.run(run())


def test_safe_retry_is_delayed_and_capped_and_quota_is_shared(accounts, prepared):
    create, worker, summaries = prepared
    create()

    async def run():
        await finalize(summaries)
        for attempt in range(1, 6):
            if attempt > 1:
                # Database time advances; retain transition constraints while shortening a pending delay.
                await asyncio.sleep(min(2 ** (attempt - 1), 16) + 0.05)
            assert await worker.process_one(Transport(Result("pending", "connect_failed")))
            assert await worker.claim() is None
        assert state(accounts) == [("failed", "attempts_exhausted", 5, None)]

    asyncio.run(run())


def test_dispatch_roles_and_immutable_intent(accounts, dedicated, prepared):
    create, worker, summaries = prepared
    create()
    asyncio.run(finalize(summaries))
    for query in (
        "SELECT password_hash FROM users",
        "SELECT * FROM auth_sessions",
        "SELECT ciphertext FROM provider_connections",
        "SELECT * FROM utterances",
        "SELECT * FROM call_finalizations",
        "UPDATE action_grants SET enabled=false",
        "UPDATE action_jobs SET payload='{}'",
        "INSERT INTO action_jobs(id) SELECT id FROM action_jobs",
    ):
        with connection(worker.dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(query)
    for purpose in ("management", "routing", "records", "summaries", "readiness", "credentials"):
        dsn = dedicated(purpose)
        for query in (
            "SELECT ciphertext FROM telegram_connections",
            "UPDATE action_jobs SET status='sent'",
        ):
            with connection(dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(query)
    with connection(worker.dsn) as c:
        assert c.execute("SELECT count(*) FROM telegram_connections").fetchone() == (0,)
    for change in ("payload='{}'", "alias='other'", "grant_id=gen_random_uuid()"):
        with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute(f"UPDATE action_jobs SET {change}")


def test_projection_and_rendering_bound_unicode_and_omit_unselected_data():
    selected = ReviewedAction(
        **action(str(uuid.uuid4())), connection_label="Target", chat_id="-123"
    )
    event = {
        "agent_name": "😀" * 20000,
        "summary_status": "failed",
        "summary": None,
        "transcript": "private ignored content",
        "credential": "must never appear",
    }
    projected = project(selected, event)
    assert projected["summary.subject"] is None
    text = render(selected, projected)
    assert len(text.encode("utf-16-le")) // 2 <= 4000 and "…" in text and "null" in text
    assert "private" not in text and "credential" not in text
    with pytest.raises(ValueError):
        render(selected, projected | {"credential": "injected"})


@pytest.mark.parametrize(
    "status,data,expected",
    [
        (200, {"ok": True, "result": {"message_id": 12, "chat": {"id": -123}}}, "sent"),
        (200, {"ok": True, "result": {"message_id": 0, "chat": {"id": -123}}}, "delivery_unknown"),
        (200, {"ok": True, "result": {"message_id": 12, "chat": {"id": -456}}}, "delivery_unknown"),
        (
            200,
            {"ok": True, "result": {"message_id": True, "chat": {"id": -123}}},
            "delivery_unknown",
        ),
        (429, {"ok": False, "error_code": 429, "parameters": {"retry_after": 7}}, "pending"),
        (429, {"ok": False, "error_code": 429, "parameters": {"retry_after": True}}, "failed"),
        (
            400,
            {"ok": False, "error_code": 400, "parameters": {"migrate_to_chat_id": -456}},
            "failed",
        ),
        (403, {"ok": False, "error_code": 403}, "failed"),
        (500, {"ok": False, "error_code": 500}, "delivery_unknown"),
        (302, {"ok": False, "error_code": 302}, "delivery_unknown"),
        (200, [], "delivery_unknown"),
    ],
)
def test_telegram_requires_exact_receipt_and_only_retries_proven_failures(status, data, expected):
    assert response(status, data, "-123").status == expected


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1", "::ffff:127.0.0.1", "ff02::1"]
)
def test_dns_private_and_special_addresses_are_denied(monkeypatch, address):
    async def run():
        async def lookup(*args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", lookup)
        with pytest.raises(ValueError, match="denied"):
            await Telegram().resolve()

    asyncio.run(run())


def test_transport_pins_tls_origin_disables_proxy_and_bounds_response(monkeypatch):
    captured = []
    client = httpx.AsyncClient

    async def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            stream=httpx.ByteStream(
                json.dumps(
                    {"ok": True, "result": {"message_id": 11, "chat": {"id": -123}}}
                ).encode()
            ),
        )

    def configured(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", configured)

    async def run():
        result = await Telegram().send(
            "149.154.167.220", body()["bot_token"], "-123", "<b>plain</b>"
        )
        assert result == Result("sent", message_id=11)

    asyncio.run(run())
    request = captured[0]
    assert request.url.host == "149.154.167.220"
    assert request.headers["host"] == "api.telegram.org"
    assert request.extensions["sni_hostname"] == "api.telegram.org"
    payload = json.loads(request.content)
    assert payload == {
        "chat_id": "-123",
        "text": "<b>plain</b>",
        "link_preview_options": {"is_disabled": True},
    }


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("connect", "pending"),
        ("read", "delivery_unknown"),
        ("write", "delivery_unknown"),
        ("oversize", "delivery_unknown"),
        ("malformed", "delivery_unknown"),
        ("redirect", "delivery_unknown"),
        ("cancel", "cancelled"),
    ],
)
def test_transport_failure_boundaries_and_close(monkeypatch, failure, expected):
    client = httpx.AsyncClient
    clients = []

    async def handler(request):
        if failure in ("connect", "read", "write"):
            error = {
                "connect": httpx.ConnectError,
                "read": httpx.ReadTimeout,
                "write": httpx.WriteError,
            }[failure]
            raise error("private token and payload must never be persisted", request=request)
        if failure == "cancel":
            raise asyncio.CancelledError()
        if failure == "redirect":
            return httpx.Response(
                302, headers={"Location": "https://example.test"}, stream=httpx.ByteStream(b"{}")
            )
        return httpx.Response(
            200, stream=httpx.ByteStream(b"x" * 65537 if failure == "oversize" else b"{")
        )

    def configured(**kwargs):
        instance = client(**kwargs, transport=httpx.MockTransport(handler))
        clients.append(instance)
        return instance

    monkeypatch.setattr(httpx, "AsyncClient", configured)

    async def run():
        if expected == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await Telegram().send("149.154.167.220", body()["bot_token"], "-123", "Synthetic")
        else:
            result = await Telegram().send(
                "149.154.167.220", body()["bot_token"], "-123", "Synthetic"
            )
            assert result.status == expected and "private" not in repr(result)

    asyncio.run(run())
    assert len(clients) == 1 and clients[0].is_closed


def test_round_robin_workspace_fairness_and_provider_cooldown(accounts, prepared):
    create, worker, summaries = prepared
    create()
    create(2)
    extra = routing.initialize(accounts, "another-call-same-owner", routing.DID)
    asyncio.run(ended(CallRecords(accounts.dsn, extra)))

    async def run():
        for _ in range(3):
            await finalize(summaries)
        first = await worker.claim()
        assert await worker.claim() is None  # Aggregate rate gate applies across worker instances.
        due(accounts)
        second = await worker.claim()
        assert first.scope_id != second.scope_id  # One owner's backlog cannot starve another.
        assert await worker.begin(first)
        await worker.finish(first, Result("pending", "rate_limited", retry_after=60))
        with connection(accounts.dsn) as c:
            assert c.execute(
                "SELECT next_dispatch_at>now()+interval '55 seconds' FROM action_dispatch_clock"
            ).fetchone() == (True,)
            assert c.execute(
                "SELECT next_attempt_at>now()+interval '55 seconds' FROM action_jobs WHERE id=%s",
                (first.id,),
            ).fetchone() == (True,)
        assert await worker.claim() is None

    asyncio.run(run())


def test_runtime_readiness_requires_delivery_migration(accounts):
    assert accounts.ready()
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE schema_migrations SET name='held-0014' WHERE name='0014_action_delivery.sql'"
        )
    assert not accounts.ready()


def test_job_cannot_substitute_a_new_grant_for_the_original_release(accounts, prepared):
    create, _, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    ActionGrants(accounts).revoke(*one["author"], one["grant"])
    replacement = consent(accounts, one["author"])["id"]
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.ForeignKeyViolation):
        c.execute(
            """INSERT INTO action_jobs(id,scope_id,call_id,release_id,profile_id,grant_id,
            connection_id,alias,action,payload)
            SELECT gen_random_uuid(),scope_id,call_id,release_id,profile_id,%s,
            connection_id,'forged',action,payload FROM action_jobs""",
            (replacement,),
        )


def test_real_delivery_process_coalesces_stop_and_does_not_replay(accounts, prepared, tmp_path):
    create, worker, summaries = prepared
    create()
    asyncio.run(finalize(summaries))
    script = """
import asyncio
from alojan_agent.telegram_delivery import Telegram
from alojan_agent.delivery_worker import main
async def resolve(self):
    return "149.154.167.220"
async def send(self, *args):
    print("synthetic_send_started", flush=True)
    await asyncio.Event().wait()
Telegram.resolve = resolve
Telegram.send = send
main()
"""

    async def run():
        env = os.environ | dict(
            PYTHONPATH=os.pathsep.join(sys.path),
            ALOJAN_ACTIONS_DATABASE_URL=worker.dsn,
            ALOJAN_CREDENTIAL_KEY_FILE=str(tmp_path / "delivery.key"),
        )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert await asyncio.wait_for(child.stdout.readline(), 8) == b"synthetic_send_started\n"
            child.terminate()
            child.terminate()
            output, errors = await asyncio.wait_for(child.communicate(), 8)
            assert child.returncode == 0
            assert b"synthetic_private" not in output + errors
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()
        assert state(accounts) == [("delivery_unknown", "send_uncertain", 1, None)]
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            "--once",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, errors = await asyncio.wait_for(child.communicate(), 8)
            assert child.returncode == 0 and b"synthetic_send_started" not in output
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()

    asyncio.run(run())
