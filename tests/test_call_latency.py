"""Scoped latency reads and bounded private ingestion; no inference or carrier calls."""

import uuid

import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection
from alojan.latency import FIELDS, Latency, ingest, parse
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_action_delivery as fixtures
import test_number_routing as routing

accounts, database, dedicated, prepared = (
    fixtures.accounts,
    fixtures.database,
    fixtures.dedicated,
    fixtures.prepared,
)


def line(identity, generation="t1", **changes):
    fields = dict(
        event="turn_latency",
        call_trace=identity,
        generation=generation,
        status="completed",
        kind="response",
        error=0,
    )
    fields.update({key: 100 for key in FIELDS})
    fields.update(changes)
    return " ".join(f"{key}={value}" for key, value in fields.items())


@pytest.mark.parametrize(
    "change",
    [
        dict(status="bad"),
        dict(error=-1),
        dict(asr_finalize_ms=-2),
        dict(tts_first_chunk_ms="NaN"),
        dict(endpoint_to_audio_ms=600001),
        dict(generation="x.y"),
        dict(call_trace="x/y"),
    ],
)
def test_invalid_observations_rejected(change):
    with pytest.raises(ValueError):
        parse(line("synthetic", **change))


def test_parser_ignores_other_logs_and_never_retains_extras():
    assert parse("caller text") is None
    record = parse(line("synthetic", asr_finalize_ms=-1, private="never-retain"))
    assert "never-retain" not in str(record) and record[6] is None
    with pytest.raises(ValueError):
        parse(line("synthetic") + " error=0")


def test_import_distribution_isolation_and_role_permissions(accounts, prepared, dedicated):
    create, _, _ = prepared
    one, two = create(), create(2)
    ingest_dsn = dedicated("latency")
    identity = one["route"].call_id
    lines = [
        line(identity, "t1", endpoint_to_audio_ms=100),
        line(identity, "t2", endpoint_to_audio_ms=300, asr_finalize_ms=-1),
        line(identity, "t3", status="interrupted", endpoint_to_audio_ms=1),
        line(identity, "t4", kind="silence_timeout", endpoint_to_audio_ms=1),
        line(identity, "t5", status="failed", endpoint_to_audio_ms=1),
        line(identity, "t6", endpoint_to_audio_ms=-1),
        line(two["route"].call_id, "t1", endpoint_to_audio_ms=999),
        line("unowned-call"),
    ]
    result = ingest(ingest_dsn, routing.NODE, lines)
    assert result["imported"] == 7 and result["duplicate_or_unowned"] == 1
    assert ingest(ingest_dsn, routing.NODE, lines)["imported"] == 0
    assert ingest(ingest_dsn, "other-node", [line(identity, "t7")])["imported"] == 0
    restricted = Accounts(dedicated("management"))
    store = Latency(restricted)
    token, scope, agent = one["author"]
    report = store.get(token, scope, agent=agent)
    assert report["observed_turns"] == 6 and report["excluded_turns"] == 3
    assert report["metrics"]["endpoint_to_audio_ms"] == dict(
        samples=2, missing=1, p50_ms=200, p95_ms=300, max_ms=300
    )
    assert report["metrics"]["asr_finalize_ms"]["missing"] == 1
    other_token, other_scope = owner(accounts, "no-metrics")
    assert store.get(other_token, other_scope)["metrics"]["endpoint_to_audio_ms"]["p50_ms"] is None
    with pytest.raises(AuthError):
        store.get(token, two["author"][1])
    with pytest.raises(AuthError):
        store.get(token, scope, agent=two["author"][2])
    with connection(accounts.dsn) as c:
        c.execute("UPDATE workspace_memberships SET role='viewer' WHERE scope_id=%s", (scope,))
    assert store.get(token, scope)["observed_turns"] == 6
    with connection(ingest_dsn) as c:
        for query in (
            "SELECT sip_call_id FROM calls",
            "SELECT ciphertext FROM provider_connections",
            "SELECT called_e164 FROM call_route_snapshots",
            "SELECT status FROM call_latency",
            "UPDATE call_latency SET status='failed'",
            "DELETE FROM call_latency",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
                c.execute(query)
    with TestClient(create_app(restricted, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, token)
        url = f"/v1/workspaces/{scope}/performance"
        response = client.get(url)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        for private in (
            identity,
            "generation",
            "sip_call_id",
            "ciphertext",
            one["target"]["bot_token"],
        ):
            assert private not in response.text
        for query in ("agent=bad", "call=", "days=10000", "agent=a&agent=b"):
            assert client.get(url + "?" + query).status_code == 400
        assert client.post(url, json={}).status_code == 405
        assert client.get(url + "?call=" + str(uuid.uuid4())).status_code == 404
    with connection(restricted.dsn) as c:
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (scope,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("DELETE FROM call_latency")


def test_read_windows_and_batch_limits(accounts, prepared, dedicated, monkeypatch):
    create, _, _ = prepared
    one = create()
    identity = one["route"].call_id
    dsn = dedicated("latency")
    with pytest.raises(ValueError, match="10000"):
        ingest(dsn, routing.NODE, [line(identity)] + ["ignored"] * 10000)
    assert ingest(dsn, routing.NODE, [line(identity)])["imported"] == 1
    import alojan.latency

    monkeypatch.setattr(alojan.latency, "SAMPLE_LIMIT", 1)
    ingest(dsn, routing.NODE, [line(identity, "t2")])
    result = Latency(Accounts(dedicated("management"))).get(*one["author"][:2])
    assert result["truncated"] and result["observed_turns"] == 1
    routing.ready(accounts, one["author"][1], one["release"])
    newer = routing.initialize(accounts, "newer-timing-call")
    monkeypatch.setattr(alojan.latency, "CALL_LIMIT", 1)
    report = Latency(Accounts(dedicated("management"))).get(*one["author"][:2])
    assert report["calls_considered"] == 1 and report["has_older_calls"]
    assert report["observed_turns"] == 0
    with connection(accounts.dsn) as c:
        c.execute(
            """INSERT INTO call_latency(scope_id,call_id,release_id,generation,status,kind,error_code)
        SELECT scope_id,call_id,release_id,'cap-'||g,'completed','response',0
        FROM call_route_snapshots CROSS JOIN generate_series(1,1000) g
        WHERE call_id=%s""",
            (uuid.uuid5(uuid.NAMESPACE_URL, "alojan:call:" + newer.call_id),),
        )
    assert ingest(dsn, routing.NODE, [line(newer.call_id, "over-cap")])["imported"] == 0
