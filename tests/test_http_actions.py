"""Typed HTTP actions with real scoped persistence and synthetic network peers."""

import asyncio
import json
import socket
import uuid

import httpx2 as httpx
import psycopg
import pytest
from cryptography.fernet import Fernet
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.http_connections import HTTPConnections
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.deliveries import Deliveries
from alojan.action_grants import ActionGrants
from alojan_agent.action_delivery import ActionDelivery
from alojan_agent.http_delivery import Webhook
from alojan_agent.records import CallRecords, CallSummaries
from alojan_agent.telegram_delivery import Result
from alojan_contracts.http_actions import HTTPAction, ReviewedHTTPAction, request_data
from alojan_contracts.actions import ActionReview
from alojan_contracts.delivery import project, render
from alojan_contracts.secrets import SecretBox
from test_action_delivery import Transport, due, finalize
from test_action_grants import consent
from test_agent_drafts import content
from test_agent_releases import qualify, prepare_assets
from test_provider_connections import owner
from test_scoped_call_records import ended
from test_native_auth import ORIGIN
from test_delivery_management import request as retry_request
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
URL = "https://hooks.example.test/calls"
TOKEN = "synthetic-http-token-never-sent"


def source(path, missing="null"):
    return dict(kind="source", source=path, on_missing=missing)


def config(reference, **changes):
    return (
        dict(
            alias="crm",
            adapter="http_request.v1",
            connection_id=reference,
            method="POST",
            body={
                "call": source("call_id", "fail"),
                "summary": source("summary.subject"),
                "summary_status": source("summary_status"),
            },
            query={"agent": source("agent_name")},
            headers={"X-Data-Team": "support"},
        )
        | changes
    )


@pytest.fixture
def prepared(accounts, dedicated, tmp_path):
    qualify(accounts)
    box = SecretBox(Fernet.generate_key())
    who = owner(accounts)
    scoped = Accounts(dedicated("management"))
    connections = HTTPConnections(scoped, box)
    ref = connections.create(
        *who, dict(label="CRM", endpoint=URL, auth_type="bearer", token=TOKEN)
    )["id"]
    worker = ActionDelivery(dedicated("actions"), box)
    summaries = CallSummaries(dedicated("summaries"))

    def create(selected=None):
        draft = content() | {"post_call_actions": selected or [config(ref)]}
        profile = Profiles(scoped).create(*who, draft)["id"]
        author = (*who, profile)
        consent(scoped, author)
        preparation, _, _ = prepare_assets(accounts, author, tmp_path)
        release = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
        number = routing.verified(accounts, *who, routing.DID)
        routing.ready(accounts, who[1], release)
        from alojan.numbers import Numbers

        Numbers(accounts, routing.NODE).bind(*who, number, release, 2)
        route = routing.initialize(accounts, "http-synthetic-call", routing.DID)
        asyncio.run(ended(CallRecords(dedicated("records"), route)))
        asyncio.run(finalize(summaries))
        return author, release

    return create, worker, connections, who, ref, scoped


class HTTPTransport:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or Result("sent", http_status=204)

    async def resolve(self, url):
        assert url == URL
        return "93.184.216.34"

    async def send(self, address, token, request, key):
        self.calls.append((token, request, str(key)))
        return self.result


def test_typed_mapping_null_omit_fail_encoding_and_closed_data_scope():
    ref = str(uuid.uuid4())
    a = ReviewedHTTPAction(**config(ref), connection_label="CRM", endpoint=URL, auth_type="bearer")
    event = dict(
        call_id="id", summary=None, summary_status="failed", agent_name="x&host=https://evil.test"
    )
    payload = project(a, event)
    req = request_data(a, payload)
    assert json.loads(req["body"])["summary"] is None
    assert req["url"].startswith(URL + "?agent=x%26host%3Dhttps%3A%2F%2Fevil.test")
    assert TOKEN not in render(a, payload)
    for missing in ("omit", "fail"):
        selected = config(ref)
        selected["body"]["summary"]["on_missing"] = missing
        b = ReviewedHTTPAction(**selected, connection_label="CRM", endpoint=URL, auth_type="none")
        if missing == "fail":
            with pytest.raises(ValueError):
                request_data(b, payload)
        else:
            assert "summary" not in json.loads(request_data(b, payload)["body"])
    for change in [
        dict(body={"x": source("secrets.token")}),
        dict(headers={"Host": "evil.test"}),
        dict(headers={"Authorization": "secret"}),
        dict(headers={"X-Data-Team": "a\r\nb"}),
        dict(method="GET"),
        dict(body={"x": source("caller_number")}),
        dict(body={"x": source("summary.summary")}),
        dict(body={"x": dict(kind="literal", value=float("nan"))}),
    ]:
        with pytest.raises(ValueError):
            HTTPAction(**config(ref, **change))
    with pytest.raises(ValueError):
        request_data(a, payload | {"call_id": True})
    with pytest.raises(ValueError):
        request_data(a, payload | {"secret": "not selected"})
    with pytest.raises(ValueError):
        ActionReview(scope_id=ref, profile_id=ref, actions=[a])
    assert (
        ActionReview(schema_version=2, scope_id=ref, profile_id=ref, actions=[a]).schema_version
        == 2
    )
    # Existing Telegram/no-action drafts retain their serialization.
    assert (
        validate_draft(content()).model_dump()
        == validate_draft(content() | {"post_call_actions": []}).model_dump()
    )


def test_connection_api_owner_csrf_isolation_and_secret_storage(accounts, dedicated):
    who = owner(accounts)
    box = SecretBox(Fernet.generate_key())
    scoped = Accounts(dedicated("management"))
    body = dict(label="CRM", endpoint=URL, auth_type="bearer", token=TOKEN)
    with TestClient(create_app(scoped, ORIGIN, secrets=box), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, who[0])
        url = f"/v1/workspaces/{who[1]}/http-connections"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(who[0])}
        assert client.post(url, json=body).status_code == 403
        created = client.post(url, json=body, headers=headers)
        assert created.status_code == 201, created.text
        ref = created.json()["id"]
        assert TOKEN not in created.text + client.get(url).text
        assert (
            client.post(
                url, json=body | {"endpoint": "http://127.0.0.1/"}, headers=headers
            ).status_code
            == 400
        )
        assert client.post(url + f"/{ref}/revoke", json={}, headers=headers).status_code == 200
    other = owner(accounts, "foreign-http")
    assert HTTPConnections(scoped).list(*other) == []
    with pytest.raises(AuthError):
        Profiles(scoped).create(*other, content() | {"post_call_actions": [config(ref)]})
    with connection(accounts.dsn) as c:
        encrypted = bytes(
            c.execute("SELECT ciphertext FROM http_connections WHERE id=%s", (ref,)).fetchone()[0]
        )
        assert TOKEN.encode() not in encrypted
        assert box.open(who[1], ref, encrypted, purpose="http") == TOKEN
    with pytest.raises(psycopg.errors.InsufficientPrivilege), scoped.workspace(*who) as (c, _):
        c.execute("SELECT ciphertext FROM http_connections")
    with pytest.raises(psycopg.errors.CheckViolation), connection(accounts.dsn) as c:
        c.execute("UPDATE http_connections SET enabled=true WHERE id=%s", (ref,))


def test_release_finalization_and_exact_http_dispatch(prepared, accounts):
    create, worker, connections, who, ref, scoped = prepared
    author, release = create()
    review = ActionGrants(scoped).review(*author)["review"]
    assert review["schema_version"] == 2 and review["actions"][0]["endpoint"] == URL
    http = HTTPTransport()
    telegram = Transport()
    assert asyncio.run(worker.process_one(telegram, http_transport=http))
    assert not telegram.calls and len(http.calls) == 1
    token, request, key = http.calls[0]
    assert token == TOKEN and request["url"].startswith(URL)
    assert json.loads(request["body"])["summary_status"] == "done"
    with connection(accounts.dsn) as c:
        row = c.execute(
            "SELECT id,status,http_status,remote_message_id,http_target_id,telegram_target_id FROM action_jobs"
        ).fetchone()
        assert (str(row[0]), *row[1:]) == (key, "sent", 204, None, uuid.UUID(ref), None)
    due(accounts)
    assert not asyncio.run(worker.process_one(telegram, http_transport=http))


def test_unknown_is_not_replayed_and_reviewed_retry_reuses_exact_idempotency_key(
    prepared, accounts
):
    create, worker, _, _, _, scoped = prepared
    author, _ = create()
    http = HTTPTransport(Result("delivery_unknown", "send_uncertain"))
    asyncio.run(worker.process_one(Transport(), http_transport=http))
    due(accounts)
    assert not asyncio.run(worker.process_one(Transport(), http_transport=http))
    job = http.calls[0][2]
    store = Deliveries(scoped)
    review = store.review(*author, job)
    assert review["can_retry"] and TOKEN not in str(review)
    assert URL in review["review"]["message_text"] and "iki kez" in review["warning"]
    body = retry_request(review)
    store.retry(*author, job, body)
    store.retry(*author, job, body)
    http.result = Result("sent", http_status=202)
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert http.calls[0] == http.calls[1]
    assert store.get(*author, job)["http_status"] == 202


def test_revocation_between_dns_and_dispatch_blocks_send(prepared):
    create, worker, connections, who, ref, _ = prepared
    create()
    http = HTTPTransport()

    async def resolve(url):
        connections.revoke(*who, ref)
        return "93.184.216.34"

    http.resolve = resolve
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert http.calls == []


def test_missing_output_fails_only_that_action(prepared, accounts):
    create, worker, _, _, ref, _ = prepared
    create(
        [
            config(ref, body={"missing": source("last_note.caller_name", "fail")}),
            config(ref, alias="second", body={"static": dict(kind="literal", value=7)}),
        ]
    )
    http = HTTPTransport()
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    due(accounts)
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert len(http.calls) == 1 and json.loads(http.calls[0][1]["body"]) == {"static": 7}
    with connection(accounts.dsn) as c:
        assert set(c.execute("SELECT status FROM action_jobs").fetchall()) == {
            ("failed",),
            ("sent",),
        }


def test_dns_and_http_transport_pin_origin_reject_redirect_and_bound_failures(monkeypatch):
    webhook = Webhook()

    async def answers(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    async def denied():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answers)
        with pytest.raises(ValueError):
            await webhook.resolve(URL)

    asyncio.run(denied())
    seen = []
    real = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real(**kwargs, transport=httpx.MockTransport(handler))

    def handler(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34"
        assert (
            request.headers["Host"] == "hooks.example.test"
            and request.extensions["sni_hostname"] == "hooks.example.test"
        )
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert request.headers["Idempotency-Key"] == "fixed-key"
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(
            outcome, headers={"Location": "https://evil.test/"}, content=b"untrusted response"
        )

    monkeypatch.setattr("alojan_agent.http_delivery.httpx.AsyncClient", client)
    request = dict(method="POST", url=URL, headers={}, body='{"x":1}')
    for outcome, status in [
        (204, "sent"),
        (302, "failed"),
        (429, "failed"),
        (503, "delivery_unknown"),
        (httpx.ReadTimeout("lost"), "delivery_unknown"),
        (httpx.ConnectTimeout("unsent"), "pending"),
    ]:
        assert (
            asyncio.run(webhook.send("93.184.216.34", TOKEN, request, "fixed-key")).status == status
        )
    assert len(seen) == 6


def test_mixed_telegram_http_actions_keep_destinations_and_permissions_independent(
    prepared, accounts
):
    from alojan.telegram_connections import TelegramConnections
    from test_telegram_connections import body
    from test_action_grants import action

    create, worker, _, who, ref, scoped = prepared
    telegram_ref = TelegramConnections(scoped, worker.secrets).create(*who, body())["id"]
    author, _ = create([config(ref), action(telegram_ref)])
    telegram = Transport()
    http = HTTPTransport(Result("delivery_unknown", "send_uncertain"))
    asyncio.run(worker.process_one(telegram, http_transport=http))
    due(accounts)
    asyncio.run(worker.process_one(telegram, http_transport=http))
    due(accounts)
    assert len(telegram.calls) == len(http.calls) == 1
    assert not asyncio.run(worker.process_one(telegram, http_transport=http))
    rows = Deliveries(scoped).list(*author)["deliveries"]
    assert {r["status"] for r in rows} == {"sent", "delivery_unknown"}
    assert all("payload" not in r for r in rows)


def test_http_role_isolation_and_migration_guards(prepared, accounts, dedicated):
    create, worker, _, who, ref, _ = prepared
    create()
    for role in ("management", "routing", "summaries", "records", "mcp-execution", "mcp"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection(dedicated(role)) as c:
            c.execute("SELECT ciphertext FROM http_connections")
    with connection(worker.dsn) as c:
        assert c.execute("SELECT count(*) FROM http_connections").fetchone()[0] == 0
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (who[1],))
        assert c.execute("SELECT count(*) FROM http_connections").fetchone()[0] == 1
    for sql in (
        "UPDATE http_connections SET endpoint='https://evil.test/'",
        "DELETE FROM http_connections",
        "UPDATE action_jobs SET connection_id=gen_random_uuid()",
    ):
        with pytest.raises(psycopg.errors.CheckViolation), connection(accounts.dsn) as c:
            c.execute(sql)
    with pytest.raises(psycopg.errors.GeneratedAlways), connection(accounts.dsn) as c:
        c.execute("UPDATE action_jobs SET http_target_id=gen_random_uuid()")


@pytest.mark.parametrize(
    "address", ["::1", "::ffff:127.0.0.1", "169.254.169.254", "10.0.0.1", "fc00::1", "fe80::1"]
)
def test_http_resolution_rejects_mixed_public_private_answers(monkeypatch, address):
    async def answers(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 443)),
        ]

    async def run():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answers)
        with pytest.raises(ValueError):
            await Webhook().resolve(URL)

    asyncio.run(run())


def test_mapping_bounds_do_not_truncate_or_guess_types():
    ref = str(uuid.uuid4())
    selected = config(
        ref,
        body={
            "duration": source("duration_ms", "fail"),
            "confirmed": source("last_note.confirmed"),
            "label": dict(kind="literal", value=7),
        },
    )
    a = ReviewedHTTPAction(**selected, endpoint=URL, connection_label="CRM", auth_type="none")
    result = request_data(
        a, {"duration_ms": 12, "last_note.confirmed": False, "agent_name": "Test"}
    )
    assert json.loads(result["body"]) == {"duration": 12, "confirmed": False, "label": 7}
    with pytest.raises(ValueError):
        request_data(a, {"duration_ms": True, "last_note.confirmed": False, "agent_name": "Test"})
    with pytest.raises(ValueError):
        request_data(a, {"duration_ms": 12, "last_note.confirmed": False, "agent_name": "x" * 5000})
    with pytest.raises(ValueError):
        HTTPAction(**config(ref, headers={"X-Data-Test": "a", "X-Data-test": "b"}))


@pytest.mark.parametrize("oversize", ["target", "query"])
def test_review_rejects_expanded_request_bounds_without_server_error(accounts, oversize):
    who = owner(accounts)
    target = URL + ("/" + "a" * 1850 if oversize == "target" else "")
    ref = HTTPConnections(accounts, SecretBox(Fernet.generate_key())).create(
        *who, dict(label="Bounded target", endpoint=target, auth_type="none", token=None)
    )["id"]

    def literal(value):
        return dict(kind="literal", value=value)

    selected = config(ref)
    if oversize == "target":
        selected["body"] = {"one": literal("a" * 1500), "two": literal("b" * 1000)}
    else:
        selected["query"] = {"encoded": literal("/" * 1600)}
    profile = Profiles(accounts).create(*who, content() | {"post_call_actions": [selected]})["id"]
    with TestClient(create_app(accounts, ORIGIN)) as client:
        client.cookies.set(COOKIE, who[0])
        response = client.get(f"/v1/workspaces/{who[1]}/agents/{profile}/action-review")
        assert response.status_code == 400
        assert response.json() == {"error": "invalid_action_intent"}
    with pytest.raises(AuthError) as error:
        ActionGrants(accounts).authorize(
            *who, profile, {"draft_version": 1, "review_digest": "0" * 64}
        )
    assert error.value.code == "invalid_action_intent"


def test_near_limit_escaped_request_can_be_reviewed_and_retried(prepared, accounts, monkeypatch):
    import test_action_delivery
    from test_scoped_call_records import summary

    sample = summary().model_copy(update={"summary": "\\" * 2000})
    monkeypatch.setattr(test_action_delivery, "summary", lambda: sample)
    create, worker, _, who, ref, scoped = prepared
    body = {f"copy_{i}": source("summary.summary") for i in range(15)}
    body["status"] = source("summary_status", "fail")
    author, _ = create([config(ref, body=body)])
    http = HTTPTransport(Result("delivery_unknown", "send_uncertain"))
    asyncio.run(worker.process_one(Transport(), http_transport=http))
    sent = http.calls[0][1]
    assert 60000 < len(sent["body"].encode()) < 65536
    deliveries = Deliveries(scoped)
    job = deliveries.list(*author)["deliveries"][0]["id"]
    review = deliveries.review(*author, job)
    assert len(json.dumps(review["review"]).encode()) > 196608
    assert deliveries.retry(*author, job, retry_request(review))["status"] == "accepted"
    due(accounts)
    asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert http.calls[0] == http.calls[1]


def test_http_sql_example_is_disabled_and_rolls_back(accounts):
    from pathlib import Path

    who = owner(accounts)
    script = Path("infra/examples/http-actions.sql").read_text()
    script = script.replace(":'workspace_id'", "'" + str(uuid.UUID(who[1])) + "'")
    with psycopg.connect(accounts.dsn, autocommit=True) as c:
        cursor = c.execute(script)
        while cursor.nextset():
            pass
        assert c.execute("SELECT count(*) FROM http_connections").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0
