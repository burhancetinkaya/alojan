"""Separate worker lifecycle with real scoped claims and synthetic model responses."""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest
import httpx2 as httpx
from openai import AuthenticationError, RateLimitError

from alojan.auth import connection
from alojan.connections import Connections
from alojan.profiles import Profiles
from alojan_contracts.secrets import SecretBox
from alojan_agent.backend import Backend
from alojan_agent.records import CallRecords, CallSummaries, summary_retry_delay
from alojan_agent.summary_worker import process_one
from test_managed_startup import author as author
from test_agent_drafts import content
from test_scoped_call_records import ended, summary
import test_number_routing as routing

accounts, database = routing.accounts, routing.database
published, dedicated = routing.published, routing.dedicated


@pytest.fixture
def route(accounts, published):
    routing.bound(accounts, published)
    return routing.initialize(accounts, "managed-worker")


def test_worker_uses_historical_connection_and_summary_instructions(
    accounts, published, route, dedicated, tmp_path, monkeypatch
):
    box = SecretBox.from_file(tmp_path / "provider.key")
    original = Profiles(accounts).get(*published[:3])["content"]
    other = Connections(accounts, box).create(
        published[0],
        published[1],
        dict(
            provider="openrouter",
            label="New connection",
            api_key="different-synthetic-provider-key",
        ),
    )["id"]
    Profiles(accounts).update(
        *published[:3], content("Different Assistant") | {"model_connection": other}, 1
    )
    seen = []

    async def summarize(self, data, *, runtime):
        seen.append(runtime)
        assert self.credentials.get(runtime).api_key == "synthetic-unused-key"
        assert runtime.model_connection == original["model_connection"]
        assert runtime.scope_id == route.scope_id
        return summary()

    monkeypatch.setattr(Backend, "summarize", summarize)

    async def run():
        await ended(CallRecords(dedicated("records"), route))
        store = CallSummaries(dedicated("summaries"))
        assert await process_one(store, dedicated("credentials"), box)
        assert not await process_one(store, dedicated("credentials"), box)

    asyncio.run(run())
    assert len(seen) == 1 and seen[0].name == original["agent_name"]
    with connection(accounts.dsn) as c:
        state, payload = c.execute(
            "SELECT summary_status,payload FROM call_finalizations"
        ).fetchone()
        assert state == "done" and payload["agent_name"] == original["agent_name"]
        assert payload["summary"]["confirmation_status"] == "unconfirmed"
        assert "synthetic-unused-key" not in str(payload)
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def test_worker_cancellation_preserves_claim_for_fenced_retry(
    accounts, route, dedicated, tmp_path, monkeypatch
):
    box = SecretBox.from_file(tmp_path / "provider.key")

    async def run():
        entered = asyncio.Event()
        clients = []

        async def summarize(self, data, *, runtime):
            clients.append(self.credentials)
            entered.set()
            await asyncio.sleep(20)

        monkeypatch.setattr(Backend, "summarize", summarize)
        await ended(CallRecords(dedicated("records"), route))
        store = CallSummaries(dedicated("summaries"))
        task = asyncio.create_task(process_one(store, dedicated("credentials"), box))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert clients[0].closed and not clients[0].clients
        assert await store.claim() is None
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (0,)
            c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")

        async def complete(self, data, *, runtime):
            return summary()

        monkeypatch.setattr(Backend, "summarize", complete)
        assert await process_one(store, dedicated("credentials"), box)
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT status,attempts FROM summary_jobs").fetchone() == ("done", 2)
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (1,)

    asyncio.run(run())


def test_real_worker_process_revoked_credential_finalizes_without_external_call(
    accounts, published, route, dedicated, tmp_path
):
    reference = Profiles(accounts).get(*published[:3])["content"]["model_connection"]
    Connections(accounts).revoke(published[0], published[1], reference)

    async def run():
        await ended(CallRecords(dedicated("records"), route))
        env = os.environ | dict(
            PYTHONPATH=os.pathsep.join(sys.path),
            ALOJAN_SUMMARIES_DATABASE_URL=dedicated("summaries"),
            ALOJAN_CREDENTIALS_DATABASE_URL=dedicated("credentials"),
            ALOJAN_CREDENTIAL_KEY_FILE=str(tmp_path / "provider.key"),
            OPENROUTER_API_KEY="must-not-fallback-to-this-global-key",
        )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alojan_agent.summary_worker",
            "--once",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            output, errors = await asyncio.wait_for(child.communicate(), 10)
            assert child.returncode == 0, "scoped worker process failed"
            assert b"must-not-fallback" not in output + errors
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,failure_code FROM summary_jobs").fetchone() == (
            "failed",
            "summary_failed",
        )
        status, payload = c.execute(
            "SELECT summary_status,payload FROM call_finalizations"
        ).fetchone()
        assert status == "failed" and payload["summary"] is None
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def provider_error(status=429, retry_after=None):
    response = httpx.Response(
        status,
        headers={} if retry_after is None else {"Retry-After": retry_after},
        request=httpx.Request("POST", "https://provider.example.test/responses"),
    )
    error = RateLimitError if status == 429 else AuthenticationError
    return error("Synthetic provider failure", response=response, body=None)


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 60),
        ("0", 60),
        ("15", 60),
        ("120", 120),
        ("120.5", 121),
        ("300", 300),
        ("301", None),
        ("-1", None),
        ("NaN", None),
        ("inf", None),
        ("1e999", None),
        ("invalid", None),
        ("", None),
    ],
)
def test_summary_retry_delay_bounds(value, expected):
    assert summary_retry_delay(value) == expected


def test_summary_retry_delay_http_dates():
    now = datetime.now(UTC)
    assert 119 <= summary_retry_delay(format_datetime(now + timedelta(seconds=120))) <= 120
    assert summary_retry_delay(format_datetime(now - timedelta(seconds=1))) == 60
    assert summary_retry_delay(format_datetime(now + timedelta(hours=1))) is None


@pytest.mark.parametrize("recover", [True, False])
def test_rate_limit_cooldown_recovers_or_finishes_once_at_attempt_limit(
    accounts, route, dedicated, tmp_path, monkeypatch, recover
):
    box = SecretBox.from_file(tmp_path / "provider.key")
    calls = []

    async def summarize(self, data, *, runtime):
        calls.append(runtime.model_connection)
        if len(calls) == 3 and recover:
            return summary()
        raise provider_error(retry_after="120")

    monkeypatch.setattr(Backend, "summarize", summarize)

    async def run():
        await ended(CallRecords(dedicated("records"), route))
        store = CallSummaries(dedicated("summaries"))
        for attempt in range(1, 4):
            assert await process_one(store, dedicated("credentials"), box)
            assert not await process_one(store, dedicated("credentials"), box)
            with connection(accounts.dsn) as c:
                state, count, delay = c.execute(
                    "SELECT status,attempts,EXTRACT(EPOCH FROM lease_until-clock_timestamp()) FROM summary_jobs"
                ).fetchone()
                assert count == attempt
                if attempt < 3:
                    assert state == "processing" and 115 < delay <= 120
                    assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (0,)
                    assert c.execute("SELECT count(*) FROM action_jobs").fetchone() == (0,)
                    c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")
                else:
                    assert state == ("done" if recover else "failed") and delay is None
                    assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (1,)
        assert len(calls) == 3 and len(set(calls)) == 1

    asyncio.run(run())


@pytest.mark.parametrize("error", [provider_error(401), provider_error(retry_after="3600")])
def test_auth_failure_or_excessive_retry_after_is_terminal(
    accounts, route, dedicated, tmp_path, monkeypatch, error
):
    async def summarize(self, data, *, runtime):
        raise error

    monkeypatch.setattr(Backend, "summarize", summarize)

    async def run():
        await ended(CallRecords(dedicated("records"), route))
        store = CallSummaries(dedicated("summaries"))
        assert await process_one(
            store, dedicated("credentials"), SecretBox.from_file(tmp_path / "provider.key")
        )
        assert not await store.claim()

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT status,attempts FROM summary_jobs").fetchone() == ("failed", 1)


def test_rate_limit_retry_rechecks_revoked_credentials(
    accounts, published, route, dedicated, tmp_path, monkeypatch
):
    calls = []

    async def summarize(self, data, *, runtime):
        calls.append(runtime.model_connection)
        raise provider_error()

    monkeypatch.setattr(Backend, "summarize", summarize)

    async def run():
        await ended(CallRecords(dedicated("records"), route))
        box = SecretBox.from_file(tmp_path / "provider.key")
        store = CallSummaries(dedicated("summaries"))
        assert await process_one(store, dedicated("credentials"), box)
        Connections(accounts).revoke(published[0], published[1], calls[0])
        with connection(accounts.dsn) as c:
            c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")
        assert await process_one(store, dedicated("credentials"), box)
        assert len(calls) == 1
        with connection(accounts.dsn) as c:
            assert c.execute("SELECT status,attempts FROM summary_jobs").fetchone() == ("failed", 2)

    asyncio.run(run())


def test_stale_claim_cannot_defer_a_new_worker(accounts, route, dedicated):
    async def run():
        await ended(CallRecords(dedicated("records"), route))
        store = CallSummaries(dedicated("summaries"))
        old = await store.claim()
        with connection(accounts.dsn) as c:
            c.execute("UPDATE summary_jobs SET lease_until=now()-interval '1 second'")
        new = await store.claim()
        with pytest.raises(ValueError, match="expired or replaced"):
            await store.defer_rate_limit(old, "120")
        await store.finish(new, summary())

    asyncio.run(run())


def test_rate_limited_job_does_not_block_another_call(
    accounts, route, dedicated, tmp_path, monkeypatch
):
    attempts = []
    other = routing.initialize(accounts, "another-managed-worker")

    async def summarize(self, data, *, runtime):
        attempts.append(True)
        if len(attempts) == 1:
            raise provider_error()
        return summary()

    monkeypatch.setattr(Backend, "summarize", summarize)

    async def run():
        box = SecretBox.from_file(tmp_path / "provider.key")
        store = CallSummaries(dedicated("summaries"))
        await ended(CallRecords(dedicated("records"), route))
        assert await process_one(store, dedicated("credentials"), box)
        await ended(CallRecords(dedicated("records"), other))
        assert await process_one(store, dedicated("credentials"), box)
        assert not await process_one(store, dedicated("credentials"), box)
        with connection(accounts.dsn) as c:
            assert set(c.execute("SELECT status,attempts FROM summary_jobs").fetchall()) == {
                ("processing", 1),
                ("done", 1),
            }
            assert c.execute("SELECT count(*) FROM call_finalizations").fetchone() == (1,)

    asyncio.run(run())
