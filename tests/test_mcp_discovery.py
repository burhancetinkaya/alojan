"""Synthetic discovery only: real SDK, restricted DB roles; no external requests/tool calls."""

from urllib.parse import urlunsplit
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from cryptography.fernet import Fernet
import httpx2 as httpx
import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.mcp_connections import MCPConnections
from alojan.mcp_roles import grant_discovery
from alojan.roles import grant_management
from alojan_contracts.secrets import SecretBox
from alojan_contracts.mcp import endpoint, public_address, manifest
from alojan_agent.mcp_discovery import PinnedTransport, discover
from alojan_agent.mcp_discovery_worker import claim, complete, process_one
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
URL = urlunsplit(("https", "mcp.example.test", "/tools", "", ""))
TOKEN = "synthetic_mcp_credential_never_sent"
TOOL = {
    "name": "lookup",
    "description": "Synthetic lookup",
    "inputSchema": {
        "type": "object",
        "properties": {"term": {"type": "string"}},
        "required": ["term"],
    },
    "annotations": {"readOnlyHint": True},
}


def body(**changes):
    return dict(label="Synthetic MCP", endpoint=URL, auth_type="bearer", token=TOKEN) | changes


@pytest.mark.parametrize(
    "value",
    [
        urlunsplit(("http", "mcp.example.test", "/tools", "", "")),
        "https://localhost/tools",
        "https://127.0.0.1/tools",
        "https://[::1]/tools",
        urlunsplit(("https", "mcp.example.test:443", "/tools", "", "")),
        urlunsplit(("https", "user@mcp.example.test", "/tools", "", "")),
        urlunsplit(("https", "mcp.example.test", "/tools", "token=secret", "")),
        urlunsplit(("https", "mcp.example.test", "/tools", "", "x")),
        urlunsplit(("https", "mcp.example.test", "/../tools", "", "")),
        urlunsplit(("https", "mcp.example.test", "/%2fadmin", "", "")),
        urlunsplit(("https", "mcp.example.test", "/tools", "", "")) + "\n",
        urlunsplit(("https", "mcp.example.test", "/tools", "", "")) + "?",
        urlunsplit(("https", "-mcp.example.test", "/tools", "", "")),
        None,
    ],
)
def test_endpoint_rejects_ambiguous_credentials_or_noncanonical_urls(value):
    with pytest.raises(ValueError):
        endpoint(value)


@pytest.mark.parametrize(
    "value",
    [
        "127.0.0.1",
        "10.2.3.4",
        "169.254.169.254",
        "100.64.0.1",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "ff02::1",
        "::ffff:8.8.8.8",
        "2002:0808:0808::1",
    ],
)
def test_private_transition_and_multicast_addresses_denied(value):
    with pytest.raises(ValueError):
        public_address(value)


def test_manifest_is_bounded_sorted_and_never_trusts_read_annotation():
    initial = manifest([TOOL])
    assert initial["tools"][0]["review_status"] == "unreviewed"
    assert initial["tools"][0]["read_only_hint"] is True
    changed = manifest([TOOL | {"description": "Changed instructions"}])
    assert initial["digest"] != changed["digest"]
    for tools in (
        [TOOL, TOOL],
        [TOOL | {"name": "bad tool"}],
        [TOOL | {"description": "x" * 4097}],
        [TOOL | {"inputSchema": {"type": "object", "$ref": "https://private/schema"}}],
        [TOOL] * 101,
    ):
        with pytest.raises(ValueError):
            manifest(tools)
    assert manifest([TOOL, TOOL | {"name": "a"}]) == manifest([TOOL | {"name": "a"}, TOOL])


def test_api_scope_roles_credentials_queue_and_revocation(accounts, dedicated):
    one, two = owner(accounts), owner(accounts, "other.mcp")
    box = SecretBox(Fernet.generate_key())
    dsn = dedicated("management")
    store = MCPConnections(Accounts(dsn), box)
    other = store.create(*two, body(auth_type="none", token=None))
    app = create_app(Accounts(dsn), ORIGIN, secrets=box)
    with TestClient(app, base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, one[0])
        url = f"/v1/workspaces/{one[1]}/mcp-connections"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(one[0])}
        assert client.post(url, json=body()).status_code == 403
        response = client.post(url, json=body(), headers=headers)
        assert response.status_code == 201, response.text
        item = response.json()
        assert TOKEN not in response.text and "ciphertext" not in response.text
        assert client.get(url).json()["connections"] == [item]
        base = url + "/" + item["id"]
        assert client.get(base + "/discovery").json()["status"] == "missing"
        assert client.get(f"/v1/workspaces/{two[1]}/mcp-connections").status_code == 404
        assert (
            client.post(url + f"/{other['id']}/discovery", json={}, headers=headers).status_code
            == 404
        )
        for role in ("editor", "viewer"):
            with connection(accounts.dsn) as c:
                c.execute(
                    "UPDATE workspace_memberships SET role=%s WHERE scope_id=%s", (role, one[1])
                )
            assert client.get(url).status_code == 200
            assert client.post(url, json=body(), headers=headers).status_code == 403
            assert client.post(base + "/discovery", json={}, headers=headers).status_code == 403
            assert client.post(base + "/revoke", json={}, headers=headers).status_code == 403
        with connection(accounts.dsn) as c:
            c.execute("UPDATE workspace_memberships SET role='owner' WHERE scope_id=%s", (one[1],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = list(
                pool.map(lambda _: store.discover(*one, item["id"], request=True), range(2))
            )
        assert requests[0] == requests[1]
        assert client.post(base + "/discovery", json={}, headers=headers).json() == requests[0]
        assert client.post(base + "/revoke", json={}, headers=headers).status_code == 200
        assert client.post(base + "/discovery", json={}, headers=headers).status_code == 409
    with connection(accounts.dsn) as c:
        cipher = bytes(
            c.execute(
                "SELECT ciphertext FROM mcp_connections WHERE id=%s", (item["id"],)
            ).fetchone()[0]
        )
        assert box.open(one[1], item["id"], cipher, purpose="mcp") == TOKEN
        for scope, ref, purpose in (
            (two[1], item["id"], "mcp"),
            (one[1], other["id"], "mcp"),
            (one[1], item["id"], "telegram"),
        ):
            with pytest.raises(ValueError):
                box.open(scope, ref, cipher, purpose=purpose)
        assert TOKEN not in str(c.execute("SELECT * FROM management_audit").fetchall())
        assert c.execute("SELECT count(*) FROM mcp_discovery_jobs").fetchone() == (1,)
    with connection(dsn) as c:
        assert c.execute("SELECT id FROM mcp_connections").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT ciphertext FROM mcp_connections")
    for statement in (
        "UPDATE mcp_discovery_jobs SET status='running'",
        "INSERT INTO mcp_discovery_jobs(id,scope_id,connection_id,manifest) VALUES (gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),'{}')",
    ):
        with connection(dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(statement)


@pytest.fixture
def queued(accounts, dedicated):
    who = owner(accounts)
    box = SecretBox(Fernet.generate_key())
    store = MCPConnections(accounts, box)
    item = store.create(*who, body())
    store.discover(*who, item["id"], request=True)
    return who, box, store, item, dedicated("mcp")


def test_worker_persists_unreviewed_snapshot_and_cannot_read_call_data(accounts, queued):
    who, box, store, item, dsn = queued
    seen = []

    async def synthetic(url, token):
        seen.append((url, token))
        return manifest([TOOL])

    assert asyncio.run(process_one(dsn, box, discover_tools=synthetic))
    assert seen == [(URL, TOKEN)]
    state = store.discover(*who, item["id"])
    assert state["status"] == "ready" and state["manifest"] == manifest([TOOL])
    assert not asyncio.run(process_one(dsn, box, discover_tools=synthetic))
    for table in (
        "users",
        "calls",
        "utterances",
        "notes",
        "provider_connections",
        "telegram_connections",
    ):
        with connection(dsn) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(f"SELECT * FROM {table}")
    with connection(dsn) as c:
        assert c.execute("SELECT id FROM mcp_connections").fetchall() == []
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute("UPDATE mcp_discovery_jobs SET manifest='{}' WHERE id=%s", (state["id"],))


def test_worker_redacts_remote_failures_without_an_operator_allowlist(queued):
    who, box, store, item, dsn = queued

    async def failed(*args):
        raise ValueError(TOKEN)

    asyncio.run(process_one(dsn, box, discover_tools=failed))
    state = store.discover(*who, item["id"])
    assert state["failure_code"] == "discovery_failed" and TOKEN not in json.dumps(state)


def test_invalid_creation_and_pending_quota_do_not_enqueue_unbounded_work(accounts):
    who = owner(accounts)
    store = MCPConnections(accounts, SecretBox(Fernet.generate_key()))
    for changes in (
        {"token": "short"},
        {"auth_type": "oauth"},
        {"auth_type": "none"},
        {"label": "\n"},
        {"arbitrary": True},
        {"endpoint": "https://127.0.0.1/"},
    ):
        with pytest.raises(AuthError, match="invalid_mcp_connection"):
            store.create(*who, body(**changes))
    assert store.list(*who) == []
    with pytest.raises(AuthError, match="credential_storage_unavailable"):
        MCPConnections(accounts).create(*who, body())
    for _ in range(4):
        item = store.create(*who, body(auth_type="none", token=None))
        store.discover(*who, item["id"], request=True)
    last = store.create(*who, body(auth_type="none", token=None))
    with pytest.raises(AuthError, match="mcp_discovery_limit"):
        store.discover(*who, last["id"], request=True)
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM mcp_discovery_jobs").fetchone() == (4,)


def test_privilege_reprovisioning_rejects_credential_and_identity_overreach(accounts, dedicated):
    dsn = dedicated("management")
    with connection(dsn) as c:
        manager = c.execute("SELECT current_user").fetchone()[0]
    with connection(accounts.dsn) as c:
        c.execute(
            psycopg.sql.SQL("GRANT SELECT(ciphertext) ON mcp_connections TO {}").format(
                psycopg.sql.Identifier(manager)
            )
        )
    with pytest.raises(ValueError, match="MCP credentials"):
        grant_management(accounts.dsn, manager)
    worker = dedicated("mcp")
    with connection(worker) as c:
        role = c.execute("SELECT current_user").fetchone()[0]
    with connection(accounts.dsn) as c:
        c.execute(
            psycopg.sql.SQL("GRANT UPDATE(enabled) ON mcp_connections TO {}").format(
                psycopg.sql.Identifier(role)
            )
        )
    with pytest.raises(ValueError, match="connection identity"):
        grant_discovery(accounts.dsn, role)


def test_management_cannot_be_provisioned_with_forged_discovery_insert_rights(accounts, dedicated):
    dsn = dedicated("management")
    with connection(dsn) as c:
        role = c.execute("SELECT current_user").fetchone()[0]
    with connection(accounts.dsn) as c:
        c.execute(
            psycopg.sql.SQL("GRANT INSERT(manifest) ON mcp_discovery_jobs TO {}").format(
                psycopg.sql.Identifier(role)
            )
        )
    with pytest.raises(ValueError, match="forge MCP"):
        grant_management(accounts.dsn, role)


def test_disabled_workspace_does_not_contact_server(accounts, queued):
    who, box, store, item, dsn = queued
    with connection(accounts.dsn) as c:
        c.execute("UPDATE recipient_scopes SET enabled=false WHERE id=%s", (who[1],))

    async def forbidden(*args):
        pytest.fail("Disabled workspace must not contact MCP")

    asyncio.run(process_one(dsn, box, discover_tools=forbidden))
    with connection(accounts.dsn) as c:
        assert c.execute(
            "SELECT status,failure_code,manifest FROM mcp_discovery_jobs"
        ).fetchone() == ("failed", "connection_revoked", None)


def test_revocation_during_discovery_discards_snapshot(queued):
    who, box, store, item, dsn = queued

    async def revoked(*args):
        store.revoke(*who, item["id"])
        return manifest([TOOL])

    asyncio.run(process_one(dsn, box, discover_tools=revoked))
    state = store.discover(*who, item["id"])
    assert state["failure_code"] == "connection_revoked" and state["manifest"] is None


def test_expired_claim_is_fenced_and_requires_explicit_new_discovery(accounts, queued):
    who, box, store, item, dsn = queued
    job = claim(dsn)
    assert claim(dsn) is None
    # Advance the test clock without weakening the production terminal-state trigger.
    with connection(accounts.dsn) as c:
        c.execute("ALTER TABLE mcp_discovery_jobs DISABLE TRIGGER pin_mcp_discovery")
        c.execute(
            "UPDATE mcp_discovery_jobs SET lease_until=now()-interval '1 second' WHERE id=%s",
            (job[0],),
        )
        c.execute("ALTER TABLE mcp_discovery_jobs ENABLE TRIGGER pin_mcp_discovery")
    assert claim(dsn) is None
    complete(dsn, job, manifest([TOOL]), None)
    assert store.discover(*who, item["id"])["failure_code"] == "lease_expired"
    fresh = store.discover(*who, item["id"], request=True)
    assert fresh["id"] != str(job[0]) and fresh["status"] == "queued"


def install_transport(monkeypatch, handler, addresses=("8.8.8.8",)):
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))

    async def resolve(self, *args, **kwargs):
        return [(2, 1, 6, "", (address, 443)) for address in addresses]

    monkeypatch.setattr(asyncio.BaseEventLoop, "getaddrinfo", resolve)


def test_cancelled_discovery_never_publishes_a_partial_manifest(queued):
    who, box, store, item, dsn = queued

    async def scenario():
        started = asyncio.Event()

        async def blocked(*args):
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(process_one(dsn, box, discover_tools=blocked))
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    state = store.discover(*who, item["id"])
    assert state["status"] == "running" and state["manifest"] is None


@pytest.mark.parametrize("problem", ["credential_echo", "schema", "cursor_cycle", "protocol"])
def test_untrusted_protocol_results_fail_closed(monkeypatch, problem):
    credential = TOKEN + '\\"'

    def server(request):
        data = json.loads(request.content)
        if "id" not in data:
            return httpx.Response(202)
        if data["method"] == "initialize":
            result = {
                "protocolVersion": "2025-03-26" if problem == "protocol" else "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "synthetic", "version": "1"},
            }
        else:
            result = {"tools": [TOOL]}
            if problem == "credential_echo":
                result["tools"] = [TOOL | {"description": credential}]
            elif problem == "schema":
                result["tools"] = [
                    TOOL
                    | {
                        "inputSchema": {
                            "type": "object",
                            "properties": {"value": {"type": "invalid"}},
                        }
                    }
                ]
            elif problem == "cursor_cycle":
                result = {"tools": [], "nextCursor": "same"}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": data["id"], "result": result})

    install_transport(monkeypatch, server)
    with pytest.raises(ExceptionGroup):
        asyncio.run(discover(URL, credential))


@pytest.mark.parametrize("encoding", ["json", "sse"])
@pytest.mark.parametrize("protocol", ["2025-06-18", "2025-11-25"])
def test_real_sdk_discovers_pages_without_tool_calls_and_pins_tls(monkeypatch, encoding, protocol):
    methods = []

    def server(request):
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "mcp.example.test"
        assert request.extensions["sni_hostname"] == "mcp.example.test"
        assert request.headers["authorization"] == "Bearer " + TOKEN
        data = json.loads(request.content)
        methods.append(data["method"])
        if "id" not in data:
            return httpx.Response(202)
        if data["method"] == "initialize":
            result = {
                "protocolVersion": protocol,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "synthetic", "version": "1"},
            }
        else:
            assert data["method"] == "tools/list"
            result = (
                {"tools": [TOOL], "nextCursor": "next"}
                if not data.get("params", {}).get("cursor")
                else {"tools": [TOOL | {"name": "second"}]}
            )
        payload = {"jsonrpc": "2.0", "id": data["id"], "result": result}
        if encoding == "sse":
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=("event: message\ndata: " + json.dumps(payload) + "\n\n").encode(),
            )
        return httpx.Response(200, json=payload)

    install_transport(monkeypatch, server)
    result = asyncio.run(discover(URL, TOKEN))
    assert result["protocol"] == protocol
    assert [t["name"] for t in result["tools"]] == ["lookup", "second"]
    assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/list"]


@pytest.mark.parametrize("mode", ["mixed_dns", "redirect", "compressed", "oversized"])
def test_transport_denies_egress_and_response_bypasses(monkeypatch, mode):
    seen = []

    def server(request):
        seen.append(request)
        if mode == "redirect":
            return httpx.Response(307, headers={"location": URL})
        if mode == "compressed":
            return httpx.Response(200, headers={"content-encoding": "gzip"}, content=b"bad")
        return httpx.Response(200, content=b"x" * 262145)

    install_transport(
        monkeypatch, server, ("8.8.8.8", "127.0.0.1") if mode == "mixed_dns" else ("8.8.8.8",)
    )

    async def run():
        async with httpx.AsyncClient(transport=PinnedTransport(URL)) as client:
            await client.post(URL, json={})

    with pytest.raises((ValueError, httpx.DecodingError)):
        asyncio.run(run())
    assert len(seen) == (0 if mode == "mixed_dns" else 1)
