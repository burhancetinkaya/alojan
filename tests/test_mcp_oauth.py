"""OAuth protocol, scoped persistence and rotation with synthetic peers only."""

from urllib.parse import urlunsplit
import asyncio
import json
from urllib.parse import parse_qs, urlsplit
import uuid

from cryptography.fernet import Fernet
import httpx2 as httpx
import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.mcp_connections import MCPConnections
from alojan.mcp_oauth import MCPOAuth
from alojan.profiles import Profiles
from alojan_agent.mcp_runtime import MCPExecutor
from alojan_agent import mcp_oauth_refresh as refresh_worker
from alojan_contracts import mcp_oauth as protocol
from alojan_contracts.mcp_oauth_tokens import oauth_ready
from alojan_contracts.secrets import SecretBox
from test_agent_drafts import content
from test_mcp_discovery import URL
from test_mcp_tools import TOOL, rediscover, operator_review
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_number_routing as routing
import test_mcp_runtime as runtime_tests

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
released, call = runtime_tests.released, runtime_tests.call
CONFIG = dict(
    id="synthetic",
    label="Synthetic MCP",
    resource=URL,
    resource_metadata=urlunsplit(
        ("https", "mcp.example.test", "/.well-known/oauth-protected-resource/tools", "", "")
    ),
    issuer="https://auth.example.test",
    server_metadata="https://auth.example.test/.well-known/oauth-authorization-server",
    authorization_endpoint="https://auth.example.test/authorize",
    token_endpoint="https://auth.example.test/token",
    client_id="synthetic-public-client",
    scopes=["records:read"],
)
ACCESS, REFRESH = "synthetic-access-token-never-sent", "synthetic-refresh-token-never-sent"


async def metadata(config):
    assert config == CONFIG


async def exchange(config, **fields):
    assert config == CONFIG
    if "refresh" in fields:
        return ACCESS + "-rotated", REFRESH + "-rotated", 3600
    assert fields["redirect"] == ORIGIN + "/mcp-donus"
    assert len(fields["verifier"]) >= 43
    return ACCESS, REFRESH, 3600


@pytest.fixture
def service(accounts, dedicated):
    who = owner(accounts)
    box = SecretBox(Fernet.generate_key())
    restricted = Accounts(dedicated("management"))
    oauth = MCPOAuth(
        restricted, box, {CONFIG["id"]: CONFIG}, ORIGIN, metadata=metadata, exchange_tokens=exchange
    )
    return oauth, who, box, restricted


def begin(oauth, who):
    response = oauth.start(*who, {"provider_id": CONFIG["id"], "label": "Synthetic OAuth"})
    query = parse_qs(urlsplit(response["authorization_url"]).query)
    return dict(
        state=query["state"][0], code="synthetic-authorization-code", issuer=CONFIG["issuer"]
    )


@pytest.fixture
def connected(service):
    oauth, who, box, restricted = service
    body = begin(oauth, who)
    ref = oauth.complete(*who, body)["connection_id"]
    return ref, body, oauth, who, box, restricted


@pytest.fixture
def configured(connected, accounts):
    ref, _, _, who, _, restricted = connected
    rediscover(accounts, who, ref, [TOOL])
    review = operator_review(accounts, who[1], ref)
    draft = content() | {
        "mcp_tools": [
            dict(
                connection_id=ref,
                review_id=review,
                alias="mcp_search",
                fixed_arguments={"project": 7},
            )
        ]
    }
    profile = Profiles(restricted).create(*who, draft)["id"]
    return restricted, (*who, profile), draft


def due(accounts, ref):
    # Move the synthetic clock through valid fixture transitions, without sleeping.
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE mcp_oauth_credentials SET status='refreshing',claim_token=%s,lease_until=now()+interval '30 seconds' WHERE connection_id=%s",
            (uuid.uuid4(), ref),
        )
        c.execute(
            "UPDATE mcp_oauth_credentials SET status='active',generation=generation+1,refresh_after=now()-interval '1 second',expires_at=now()+interval '60 seconds',lease_until=NULL,claim_token=NULL WHERE connection_id=%s",
            (ref,),
        )


def test_pkce_resource_and_metadata_pins(monkeypatch):
    assert protocol.provider(CONFIG) == CONFIG
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    url = protocol.authorization_url(CONFIG, ORIGIN + "/mcp-donus", "synthetic-state", verifier)
    query = parse_qs(urlsplit(url).query)
    assert query["code_challenge"] == ["E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"]
    assert query["resource"] == [URL] and query["scope"] == ["records:read"]
    resource = dict(
        resource=URL, authorization_servers=[CONFIG["issuer"]], scopes_supported=CONFIG["scopes"]
    )
    server = dict(
        issuer=CONFIG["issuer"],
        authorization_endpoint=CONFIG["authorization_endpoint"],
        token_endpoint=CONFIG["token_endpoint"],
        code_challenge_methods_supported=["S256"],
        response_types_supported=["code"],
        token_endpoint_auth_methods_supported=["none"],
        authorization_response_iss_parameter_supported=True,
    )
    seen = []

    async def request(url, fields=None):
        seen.append((url, fields))
        return resource if url == CONFIG["resource_metadata"] else server

    asyncio.run(protocol.validate_metadata(CONFIG, request=request))
    assert [url for url, _ in seen] == [CONFIG["resource_metadata"], CONFIG["server_metadata"]]
    for key, value in [
        ("issuer", "https://evil.example.test"),
        ("token_endpoint", "https://evil.example.test/token"),
        ("code_challenge_methods_supported", []),
        ("code_challenge_methods_supported", "S256"),
        ("authorization_response_iss_parameter_supported", False),
    ]:
        old = server[key]
        server[key] = value
        with pytest.raises(protocol.OAuthError):
            asyncio.run(protocol.validate_metadata(CONFIG, request=request))
        server[key] = old
    resource["authorization_servers"] = ["https://evil.example.test"]
    with pytest.raises(protocol.OAuthError):
        asyncio.run(protocol.validate_metadata(CONFIG, request=request))


def test_token_exchange_minimal_scopes_rotation_and_no_token_in_url():
    seen = []

    async def request(url, fields):
        seen.append((url, fields))
        return dict(
            access_token=ACCESS,
            refresh_token=REFRESH,
            expires_in=3600,
            token_type="Bearer",
            scope="records:read",
        )

    assert asyncio.run(
        protocol.exchange(
            CONFIG,
            code="code",
            verifier="verifier",
            redirect=ORIGIN + "/mcp-donus",
            request=request,
        )
    ) == (ACCESS, REFRESH, 3600)
    assert seen[0][0] == CONFIG["token_endpoint"] and seen[0][1]["resource"] == URL
    assert "scope" not in seen[0][1] and "client_secret" not in seen[0][1]
    with pytest.raises(protocol.OAuthError):
        asyncio.run(protocol.exchange(CONFIG, refresh=REFRESH, request=request))
    base = dict(
        access_token=ACCESS,
        refresh_token=REFRESH,
        expires_in=3600,
        token_type="Bearer",
        scope="records:read",
    )
    for change in (
        {"scope": "records:read records:write"},
        {"expires_in": True},
        {"expires_in": 30},
        {"resource": urlunsplit(("https", "other.example.test", "/mcp", "", ""))},
        {"access_token": "bad\nheader"},
        {"token_type": "MAC"},
    ):
        with pytest.raises(protocol.OAuthError):
            protocol.tokens(base | change, CONFIG)


def test_bounded_json_transport_rejects_redirects_bad_media_and_oversize(monkeypatch):
    responses = [
        httpx.Response(302, headers={"location": "https://evil.example.test/"}),
        httpx.Response(200, text="{}"),
        httpx.Response(200, headers={"content-type": "application/json"}, content=b" " * 32769),
    ]
    for response in responses:
        monkeypatch.setattr(
            protocol, "PinnedTransport", lambda url: httpx.MockTransport(lambda request: response)
        )
        with pytest.raises(protocol.OAuthError):
            asyncio.run(protocol.request_json(CONFIG["token_endpoint"], {"code": "synthetic"}))
    monkeypatch.setattr(
        protocol,
        "PinnedTransport",
        lambda url: httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True})),
    )
    assert asyncio.run(protocol.request_json(CONFIG["server_metadata"])) == {"ok": True}


def test_callback_binds_session_workspace_issuer_state_and_replay(service, accounts):
    oauth, who, box, restricted = service
    body = begin(oauth, who)
    for change in ({"issuer": "https://evil.example.test"}, {"state": body["state"][:-1] + "!"}):
        with pytest.raises(AuthError):
            oauth.complete(*who, body | change)
    other = owner(accounts, "oauth.other")
    with pytest.raises(AuthError):
        oauth.complete(*other, body)
    new_session = accounts.register(
        "oauth.new@example.test", "Long synthetic password 123!", "Other", peer="test"
    )
    with pytest.raises(AuthError):
        oauth.complete(new_session, who[1], body)
    result = oauth.complete(*who, body)
    assert oauth.complete(*who, body) == result
    with pytest.raises(AuthError):
        oauth.complete(*who, body | {"code": "different-code"})
    item = MCPConnections(restricted).list(*who)[0]
    assert item["auth_type"] == "oauth" and item["auth_status"] == "active"
    assert "token" not in json.dumps(item) and "ciphertext" not in json.dumps(item)
    with connection(accounts.dsn) as c:
        raw = c.execute(
            "SELECT access_ciphertext,refresh_ciphertext FROM mcp_oauth_credentials WHERE connection_id=%s",
            (result["connection_id"],),
        ).fetchone()
        assert ACCESS.encode() not in bytes(raw[0])
        assert (
            box.open(who[1], result["connection_id"], bytes(raw[0]), purpose="mcp-oauth-access")
            == ACCESS
        )
        with pytest.raises(ValueError):
            box.open(who[1], result["connection_id"], bytes(raw[0]), purpose="mcp-oauth-refresh")
    with connection(restricted.dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("SELECT access_ciphertext FROM mcp_oauth_credentials")


def test_current_user_new_session_and_expired_or_lost_flow_fail_closed(service, accounts):
    oauth, who, _, _ = service
    body = begin(oauth, who)
    with connection(accounts.dsn) as c:
        user = c.execute(
            "SELECT user_id FROM workspace_memberships WHERE scope_id=%s", (who[1],)
        ).fetchone()[0]
        # Session change is represented by another legitimate session for the same account.
        login = c.execute("SELECT login FROM users WHERE id=%s", (user,)).fetchone()[0]
    from test_native_auth import PASSWORD

    fresh = accounts.login(login, PASSWORD, peer="test")
    with pytest.raises(AuthError, match="invalid_oauth_callback"):
        oauth.complete(fresh, who[1], body)
    calls = []

    async def uncertain(*args, **kwargs):
        calls.append(1)
        raise TimeoutError("remote secret not exposed")

    oauth.exchange = uncertain
    with pytest.raises(AuthError, match="oauth_exchange_failed"):
        oauth.complete(*who, body)
    with pytest.raises(AuthError, match="oauth_flow_consumed"):
        oauth.complete(*who, body)
    assert calls == [1]
    assert MCPConnections(oauth.accounts).list(*who) == []


def test_api_origin_csrf_and_owner_checks(service, monkeypatch):
    oauth, who, box, restricted = service
    monkeypatch.setattr("alojan.mcp_oauth.MCPOAuth", lambda *args: oauth)
    app = create_app(restricted, ORIGIN, secrets=box, oauth_registry={CONFIG["id"]: CONFIG})
    with TestClient(app, base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, who[0])
        url = f"/v1/workspaces/{who[1]}/mcp-oauth"
        body = {"provider_id": CONFIG["id"], "label": "Synthetic OAuth"}
        assert client.get(url).json()["providers"][0]["resource"] == URL
        assert client.post(url, json=body).status_code == 403
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(who[0])}
        assert client.post(url, json=body, headers=headers).status_code == 200
        assert client.post(url + "?scope=forged", json=body, headers=headers).status_code == 400


def test_rotation_is_fenced_and_failure_cannot_replay_refresh(connected, accounts, dedicated):
    ref, _, _, who, box, restricted = connected
    dsn = dedicated("mcp")
    due(accounts, ref)
    job = refresh_worker.claim(dsn)
    assert job and refresh_worker.claim(dsn) is None
    refresh_worker.complete(dsn, job, (ACCESS + "-new", REFRESH + "-new", 3600), box)
    refresh_worker.complete(dsn, job, None, box)
    with restricted.workspace(*who) as (c, _):
        assert oauth_ready(c, who[1], ref)
    due(accounts, ref)
    requests = []

    async def uncertain(*args, **kwargs):
        requests.append(1)
        raise TimeoutError()

    assert asyncio.run(
        refresh_worker.process_one(dsn, box, {CONFIG["id"]: CONFIG}, exchange_tokens=uncertain)
    )
    assert not asyncio.run(
        refresh_worker.process_one(dsn, box, {CONFIG["id"]: CONFIG}, exchange_tokens=uncertain)
    )
    assert requests == [1]
    with restricted.workspace(*who) as (c, _):
        assert not oauth_ready(c, who[1], ref)
    assert MCPConnections(restricted).list(*who)[0]["auth_status"] == "reauth_required"


def test_revocation_during_refresh_cannot_reactivate_connection(connected, accounts, dedicated):
    ref, _, _, who, box, restricted = connected
    due(accounts, ref)
    dsn = dedicated("mcp")
    job = refresh_worker.claim(dsn)
    MCPConnections(restricted).revoke(*who, ref)
    refresh_worker.complete(dsn, job, (ACCESS + "-new", REFRESH + "-new", 3600), box)
    with connection(accounts.dsn) as c:
        assert (
            c.execute(
                "SELECT status FROM mcp_oauth_credentials WHERE connection_id=%s", (ref,)
            ).fetchone()[0]
            == "reauth_required"
        )
    with pytest.raises(AuthError):
        MCPConnections(restricted).discover(*who, ref, request=True)


def test_runtime_refreshes_tokens_outside_calls_and_revocation_blocks(
    connected, call, accounts, dedicated
):
    ref, _, _, who, box, restricted = connected
    seen = []

    async def invoke(url, token, name, arguments):
        seen.append(token)
        return {"answer": "Synthetic result"}

    async def run():
        executor = MCPExecutor(dedicated("mcp-execution"), box, invoke=invoke)
        try:
            await executor.prepare(call.runtime)
            assert json.loads(
                await executor.execute(call, call.turns, "mcp_search", '{"query":"status"}')
            )["ok"]
            due(accounts, ref)
            assert await refresh_worker.process_one(
                dedicated("mcp"), box, {CONFIG["id"]: CONFIG}, exchange_tokens=exchange
            )
            await executor.prepare(call.runtime)
            call.turns += 1
            assert json.loads(
                await executor.execute(call, call.turns, "mcp_search", '{"query":"status"}')
            )["ok"]
            MCPConnections(restricted).revoke(*who, ref)
            with pytest.raises(ValueError):
                await executor.prepare(call.runtime)
            assert not json.loads(
                await executor.execute(call, call.turns, "mcp_search", '{"query":"status"}')
            )["ok"]
        finally:
            await executor.close()

    asyncio.run(run())
    assert seen == [ACCESS, ACCESS + "-rotated"]


def test_expired_callback_and_owner_loss_during_exchange_do_not_create_connections(
    service, accounts
):
    oauth, who, _, restricted = service
    body = begin(oauth, who)
    flow = body["state"].split(".")[1]
    with connection(accounts.dsn) as c:
        c.execute(
            """WITH old AS (DELETE FROM mcp_oauth_flows WHERE id=%s RETURNING *)
            INSERT INTO mcp_oauth_flows(id,scope_id,user_id,session_hash,state_hash,verifier,label,provider,redirect_uri,created_at,expires_at)
            SELECT id,scope_id,user_id,session_hash,state_hash,verifier,label,provider,redirect_uri,
            now()-interval '11 minutes',now()-interval '1 minute' FROM old""",
            (flow,),
        )
    with pytest.raises(AuthError, match="invalid_oauth_callback"):
        oauth.complete(*who, body)
    body = begin(oauth, who)

    async def revoked(config, **fields):
        with connection(accounts.dsn) as c:
            c.execute("UPDATE workspace_memberships SET role='viewer' WHERE scope_id=%s", (who[1],))
        return ACCESS, REFRESH, 3600

    oauth.exchange = revoked
    with pytest.raises(AuthError, match="forbidden"):
        oauth.complete(*who, body)
    assert MCPConnections(restricted).list(*who) == []


def test_refresh_lease_expiry_and_identity_guards(connected, accounts, dedicated):
    ref, body, _, who, _, _ = connected
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute(
            'UPDATE mcp_oauth_credentials SET provider=provider || \'{"id":"forged"}\'::jsonb WHERE connection_id=%s',
            (ref,),
        )
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute(
            "UPDATE mcp_oauth_flows SET session_hash=%s WHERE id=%s",
            ("f" * 64, body["state"].split(".")[1]),
        )
    with (
        connection(dedicated("mcp-execution")) as c,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        c.execute("SELECT refresh_ciphertext FROM mcp_oauth_credentials")
    # A worker died after claiming; it must not replay a potentially consumed refresh token.
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE mcp_oauth_credentials SET status='refreshing',claim_token=%s,lease_until=now()-interval '1 second' WHERE connection_id=%s",
            (uuid.uuid4(), ref),
        )
    assert refresh_worker.claim(dedicated("mcp")) is None
    with connection(accounts.dsn) as c:
        assert (
            c.execute(
                "SELECT status FROM mcp_oauth_credentials WHERE connection_id=%s", (ref,)
            ).fetchone()[0]
            == "reauth_required"
        )


def test_rotated_inflight_token_echo_never_reaches_model(connected, call, accounts, dedicated):
    ref, _, _, _, box, _ = connected

    async def run():
        executor = None

        async def invoke(url, token, name, arguments):
            due(accounts, ref)
            assert await refresh_worker.process_one(
                dedicated("mcp"), box, {CONFIG["id"]: CONFIG}, exchange_tokens=exchange
            )
            await executor.prepare(call.runtime)
            return {"answer": token}

        executor = MCPExecutor(dedicated("mcp-execution"), box, invoke=invoke)
        try:
            await executor.prepare(call.runtime)
            result = await executor.execute(call, call.turns, "mcp_search", '{"query":"status"}')
            assert not json.loads(result)["ok"] and ACCESS not in result
        finally:
            await executor.close()

    asyncio.run(run())


def test_short_lived_tokens_refresh_before_readiness_guard(service, accounts, dedicated):
    oauth, who, box, restricted = service

    async def short(config, **kwargs):
        return ACCESS, REFRESH, 60

    oauth.exchange = short
    ref = oauth.complete(*who, begin(oauth, who))["connection_id"]
    with connection(accounts.dsn) as c:
        expiry, refresh = c.execute(
            "SELECT expires_at,refresh_after FROM mcp_oauth_credentials WHERE connection_id=%s",
            (ref,),
        ).fetchone()
        assert (expiry - refresh).total_seconds() >= 49
    due(accounts, ref)
    job = refresh_worker.claim(dedicated("mcp"))
    refresh_worker.complete(dedicated("mcp"), job, (ACCESS + "-new", REFRESH + "-new", 60), box)
    with restricted.workspace(*who) as (c, _):
        assert oauth_ready(c, who[1], ref)
    with connection(accounts.dsn) as c:
        assert c.execute(
            "SELECT expires_at-refresh_after>=interval '49 seconds' FROM mcp_oauth_credentials WHERE connection_id=%s",
            (ref,),
        ).fetchone()[0]


def test_owner_loss_during_refresh_requires_reconnect(connected, accounts, dedicated):
    ref, _, _, who, box, _ = connected
    due(accounts, ref)
    dsn = dedicated("mcp")
    job = refresh_worker.claim(dsn)
    with connection(accounts.dsn) as c:
        c.execute("UPDATE workspace_memberships SET role='viewer' WHERE scope_id=%s", (who[1],))
    refresh_worker.complete(dsn, job, (ACCESS + "-new", REFRESH + "-new", 3600), box)
    with connection(accounts.dsn) as c:
        assert (
            c.execute(
                "SELECT status FROM mcp_oauth_credentials WHERE connection_id=%s", (ref,)
            ).fetchone()[0]
            == "reauth_required"
        )
