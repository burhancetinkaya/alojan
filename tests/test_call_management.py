"""Read-only call history under the real restricted management role and RLS."""

import asyncio
import json
import uuid

import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection
from alojan.calls import Calls
from alojan.profiles import Profiles
from alojan_agent.records import CallRecords
from test_action_delivery import finalize
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_action_delivery as delivery_tests
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
prepared = delivery_tests.prepared


@pytest.fixture
def history(prepared, dedicated):
    create, _, summaries = prepared
    one = create()
    return one, summaries, Calls(Accounts(dedicated("management")))


def test_detail_pins_history_and_does_not_expose_delivery_secrets(accounts, history):
    one, summaries, store = history
    author = one["author"]
    # The route API uses UUID identities, while records accept the original SIP identity.
    with connection(accounts.dsn) as c:
        call = str(c.execute("SELECT call_id FROM call_route_snapshots").fetchone()[0])
        c.execute(
            "INSERT INTO notes(id,call_id,note_version,text,confirmed) VALUES(%s,%s,1,%s,false)",
            (uuid.uuid4(), call, json.dumps(dict(subject="Older", message="Old note"))),
        )
        c.execute(
            "INSERT INTO notes(id,call_id,note_version,text,confirmed) VALUES(%s,%s,2,%s,true)",
            (
                uuid.uuid4(),
                call,
                json.dumps(dict(subject="Latest", message="<script>untrusted</script>")),
            ),
        )
    asyncio.run(finalize(summaries))
    Profiles(accounts).update(*author, one["config"] | {"agent_name": "Renamed"}, 1)
    with TestClient(create_app(store.accounts, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, author[0])
        base = f"/v1/workspaces/{author[1]}/calls"
        listing = client.get(base)
        assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
        assert listing.json()["calls"][0]["agent_name"] == "Assistant1"
        assert "summary" not in listing.json()["calls"][0]
        result = client.get(base + "/" + call)
        assert result.status_code == 200, result.text
        data = result.json()
        assert data["summary_status"] == "done" and data["summary"]["subject"] == "Sentetik konu"
        assert data["note"] == dict(
            caller_name=None,
            caller_number=None,
            subject="Latest",
            message="<script>untrusted</script>",
            confirmed=True,
            version=2,
        )
        assert data["deliveries"][0]["status"] == "pending"
        assert data["deliveries"][0]["attempts"] == 0
        for secret in (
            one["target"]["bot_token"],
            one["target"]["chat_id"],
            "claim_token",
            "sip_call_id",
            "instructions",
        ):
            assert secret not in result.text
        assert client.post(base + "/" + call).status_code == 405
        for query in ("limit=10000", "agent=no", "after=no", "after=", "after=a&after=b"):
            assert client.get(base + "?" + query).status_code == 400
        assert client.get(base + "/" + call + "?after=x").status_code == 400
        client.cookies.clear()
        assert client.get(base).status_code == 401


def test_workspace_and_legacy_isolation_and_read_only_grants(accounts, history):
    one, _, store = history
    token, scope, agent = one["author"]
    foreign = owner(accounts, "foreign.history")
    with connection(accounts.dsn) as c:
        call = str(c.execute("SELECT call_id FROM call_route_snapshots").fetchone()[0])
        legacy = uuid.uuid4()
        c.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status) VALUES(%s,'legacy-private','inbound','ended')",
            (legacy,),
        )
    assert store.list(*foreign)["calls"] == []
    for args in ((foreign[0], scope, call), (*foreign, call), (token, scope, legacy)):
        with pytest.raises(AuthError, match="not_found"):
            store.get(*args)
    with pytest.raises(AuthError, match="invalid_call_cursor"):
        store.list(*foreign, after=call)
    with pytest.raises(AuthError, match="not_found"):
        store.list(*foreign, agent=agent)
    with connection(store.accounts.dsn) as c:
        assert c.execute("SELECT id FROM calls").fetchall() == []
        assert c.execute("SELECT call_id FROM notes").fetchall() == []
    for sql in (
        "SELECT sip_call_id FROM calls",
        "UPDATE calls SET status='ended'",
        "UPDATE notes SET confirmed=true",
        "SELECT claim_token FROM summary_jobs",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            connection(store.accounts.dsn) as c,
        ):
            c.execute(sql)
    with connection(accounts.dsn) as c:
        c.execute("UPDATE workspace_memberships SET role='viewer' WHERE scope_id=%s", (scope,))
    assert store.get(token, scope, call)["agent_name"] == "Assistant1"


def test_pending_failed_and_unanswered_calls_are_distinct(accounts, history):
    one, summaries, store = history
    token, scope, _ = one["author"]
    call = store.list(token, scope)["calls"][0]["id"]
    initial = store.get(token, scope, call)
    assert initial["summary_status"] == "pending" and initial["summary"] is None
    assert initial["note"] is None and initial["deliveries"] == []
    asyncio.run(finalize(summaries, result=False))
    failed = store.get(token, scope, call)
    assert failed["summary_status"] == "failed" and failed["summary"] is None
    assert failed["deliveries"][0]["status"] == "pending"
    routing.ready(accounts, scope, one["release"])
    route = routing.initialize(accounts, "unanswered-history")
    asyncio.run(CallRecords(accounts.dsn, route).end(route.call_id, "disconnected"))
    unanswered = store.list(token, scope)["calls"][0]
    assert unanswered["answered_at"] is None and unanswered["duration_ms"] is None
    assert unanswered["summary_status"] == "not_requested"


def test_keyset_pages_do_not_skip_equal_timestamps_or_include_new_calls(
    accounts, history, monkeypatch
):
    one, _, store = history
    token, scope, agent = one["author"]
    import alojan.calls

    monkeypatch.setattr(alojan.calls, "PAGE_SIZE", 2)
    routing.ready(accounts, scope, one["release"])
    for i in range(4):
        routing.initialize(accounts, f"page-{i}")
    # Bulk creation inside one transaction gives equal timestamps without mutating snapshots.
    with connection(accounts.dsn) as c:
        ids = [uuid.uuid4() for _ in range(3)]
        for call in ids:
            c.execute(
                "INSERT INTO calls(id,sip_call_id,direction,status) VALUES(%s,%s,'inbound','created')",
                (call, str(call)),
            )
            c.execute(
                """INSERT INTO call_route_snapshots(call_id,scope_id,number_id,binding_id,profile_id,release_id,node_id,called_e164,called_source,manifest_digest)
                SELECT %s,scope_id,number_id,binding_id,profile_id,release_id,node_id,called_e164,called_source,manifest_digest FROM call_route_snapshots LIMIT 1""",
                (call,),
            )
    first = store.list(token, scope, agent=agent)
    assert len(first["calls"]) == 2 and first["next_cursor"]
    routing.initialize(accounts, "new-after-page")
    seen = [v["id"] for v in first["calls"]]
    cursor = first["next_cursor"]
    while cursor:
        page = store.list(token, scope, agent=agent, after=cursor)
        seen.extend(v["id"] for v in page["calls"])
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 8
    other = Profiles(accounts).create(token, scope, one["config"])["id"]
    assert store.list(token, scope, agent=other)["calls"] == []
    with pytest.raises(AuthError, match="invalid_call_cursor"):
        store.list(token, scope, agent=other, after=seen[0])


@pytest.mark.parametrize(
    "status,code", [("sent", None), ("failed", "rejected"), ("delivery_unknown", "send_uncertain")]
)
def test_delivery_results_are_observed_without_replaying(
    accounts, prepared, dedicated, status, code
):
    from test_action_delivery import Transport
    from alojan_agent.telegram_delivery import Result

    create, worker, summaries = prepared
    one = create()
    asyncio.run(finalize(summaries))
    transport = Transport(Result(status, code, message_id=42 if status == "sent" else None))
    asyncio.run(worker.process_one(transport))
    store = Calls(Accounts(dedicated("management")))
    token, scope, _ = one["author"]
    call = store.list(token, scope)["calls"][0]["id"]
    for _ in range(2):
        result = store.get(token, scope, call)["deliveries"][0]
        assert result["status"] == status and result["failure_code"] == code
        assert result["attempts"] == 1 and not result["retry_queued"]
    assert len(transport.calls) == 1


def test_transcript_filters_unsent_and_partial_speech_and_binds_cursors(
    accounts, history, monkeypatch
):
    import alojan.calls

    one, _, store = history
    token, scope, _ = one["author"]
    call = store.list(token, scope)["calls"][0]["id"]
    with connection(accounts.dsn) as c:
        # All fixture rows share a timestamp; UUID is the deterministic tie-breaker.
        rows = []
        for speaker, text, final, sent in (
            ("caller", "<script>caller</script>", True, None),
            ("assistant", "Sent words", True, 400),
            ("assistant", "", True, 200),
            ("assistant", "Unsent secret", True, 0),
            ("caller", "Partial secret", False, None),
        ):
            key = uuid.uuid4()
            c.execute(
                """INSERT INTO utterances(id,call_id,speaker,text,is_final,audio_sent_start_ms,audio_sent_end_ms)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (key, call, speaker, text, final, 0 if sent is not None else None, sent),
            )
            rows.append(key)
        c.execute("UPDATE utterances SET source_generation_id='turn-1-w0' WHERE id=%s", (rows[1],))
    monkeypatch.setattr(alojan.calls, "PAGE_SIZE", 2)
    result = store.transcript(token, scope, call)
    all_rows = result["utterances"]
    while result["next_cursor"]:
        result = store.transcript(token, scope, call, after=result["next_cursor"])
        all_rows += result["utterances"]
    assert len(all_rows) == 4  # Includes the original synthetic caller utterance.
    assert len({r["id"] for r in all_rows}) == 4
    assert next(r for r in all_rows if r["text"] == "Sent words")["kind"] == "waiting"
    assert {r["text"] for r in all_rows} == {
        "Sentetik mesaj.",
        "<script>caller</script>",
        "Sent words",
        "",
    }
    assert all_rows == sorted(all_rows, key=lambda r: (r["created_at"], r["id"]))
    for hidden in rows[-2:]:
        with pytest.raises(AuthError, match="invalid_transcript_cursor"):
            store.transcript(token, scope, call, after=hidden)
    foreign = owner(accounts, "other.transcript")
    with pytest.raises(AuthError, match="not_found"):
        store.transcript(*foreign, call)
    routing.ready(accounts, scope, one["release"])
    routing.initialize(accounts, "other-transcript-call")
    other = store.list(token, scope)["calls"][0]["id"]
    assert store.transcript(token, scope, other) == dict(utterances=[], next_cursor=None)
    with pytest.raises(AuthError, match="invalid_transcript_cursor"):
        store.transcript(token, scope, other, after=all_rows[0]["id"])
    with connection(store.accounts.dsn) as c:
        assert c.execute("SELECT id FROM utterances").fetchall() == []
        assert c.execute("SELECT source_generation_id FROM utterances").fetchall() == []
    assert all("source_generation_id" not in row for row in all_rows)
    for statement in (
        "SELECT * FROM utterances",
        "UPDATE utterances SET text='overwrite'",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            connection(store.accounts.dsn) as c,
        ):
            c.execute(statement)
    with TestClient(create_app(store.accounts, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, token)
        base = f"/v1/workspaces/{scope}/calls/{call}/transcript"
        response = client.get(base)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        for query in (
            "after=no",
            "after=",
            "after=a&after=b",
            "limit=1000",
            "agent=" + str(uuid.uuid4()),
        ):
            assert client.get(base + "?" + query).status_code == 400
        assert client.post(base).status_code == 405
        client.cookies.clear()
        assert client.get(base).status_code == 401
