"""Real API/database integration through the official Streamable HTTP SDK server."""

from urllib.parse import urlunsplit
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx2
from starlette.testclient import TestClient

from alojan.api import create_app
from alojan.auth import connection
from alojan_management_mcp.catalog import BY_NAME
from alojan_management_mcp.server import create_app as mcp_app
from test_agent_drafts import content
from test_native_auth import ORIGIN
from test_personal_tokens import setup
import test_native_auth

accounts, database = test_native_auth.accounts, test_native_auth.database

MCP_URL = urlunsplit(("https", "mcp.alojan.example.test", "/mcp", "", ""))


def rpc(client, token, method, params=None):
    response = client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def test_http_initialization_tools_and_scoped_creation(accounts):
    session, scope, created = setup(accounts, ["agents:read", "agents:write"])
    api = create_app(accounts, ORIGIN)
    with TestClient(
        mcp_app("http://management.test", MCP_URL, transport=httpx2.ASGITransport(app=api)),
        base_url=urlunsplit(("https", "mcp.alojan.example.test", "", "", "")),
    ) as client:
        token = created["token"]
        initialized = rpc(
            client,
            token,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "synthetic-test", "version": "1"},
            },
        )
        assert initialized["result"]["serverInfo"]["name"] == "alojan-management"
        tools = rpc(client, token, "tools/list")["result"]["tools"]
        names = {tool["name"] for tool in tools}
        assert "alojan_create_agent" in names and "alojan_publish_agent" not in names
        request = {
            "name": "alojan_create_agent",
            "arguments": {
                "configuration": content("MCP assistant")
                | {
                    "response_experience": {"enabled": True, "style": "natural"},
                },
                "operation_key": str(uuid.uuid4()),
            },
        }
        one = rpc(client, token, "tools/call", request)["result"]
        assert not one.get("isError"), one
        two = rpc(client, token, "tools/call", request)["result"]
        assert one["structuredContent"]["id"] == two["structuredContent"]["id"]
        from alojan.profiles import Profiles

        saved = Profiles(accounts).get(session, scope, one["structuredContent"]["id"])
        assert saved["content"]["response_experience"]["enabled"] is True
        assert saved["content"]["response_experience"]["style"] == "natural"
        listed = rpc(client, token, "tools/call", {"name": "alojan_list_agents"})["result"][
            "structuredContent"
        ]
        assert len(listed["agents"]) == 1
        denied = rpc(
            client, token, "tools/call", {"name": "alojan_publish_agent", "arguments": {}}
        )["result"]
        assert denied["isError"]
        # Invocation is checked even when the tool was omitted from discovery.
        assert denied["structuredContent"]["error"] == "insufficient_scope"
        from alojan.personal_tokens import PersonalTokens

        PersonalTokens(accounts).revoke(session, scope, created["id"])
        assert (
            client.post("/mcp", headers={"Authorization": "Bearer " + token}, json={}).status_code
            == 401
        )


def test_concurrent_http_retries_commit_once_and_reject_changed_payload(accounts):
    _, scope, created = setup(accounts, ["agents:write"])
    app = create_app(accounts, ORIGIN)
    key = str(uuid.uuid4())
    headers = {"Authorization": "Bearer " + created["token"], "Idempotency-Key": key}
    path = f"/v1/workspaces/{scope}/agents"
    with TestClient(app, base_url=ORIGIN) as client:

        def submit(_):
            response = client.post(path, headers=headers, json=content())
            return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(submit, range(2)))
    assert [r[0] for r in results] == [201, 201]
    assert results[0][1]["id"] == results[1][1]["id"]
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.post(path, headers=headers, json=content("different")).status_code == 409
        assert (
            client.post(
                path, headers={"Authorization": headers["Authorization"]}, json=content()
            ).status_code
            == 428
        )
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM assistant_profiles").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM management_operations").fetchone()[0] == 1
        assert conn.execute(
            "SELECT personal_token_id FROM management_audit WHERE event='agent.created'"
        ).fetchone()[0] == uuid.UUID(created["id"])


def test_catalog_has_explicit_operation_schema_and_no_arbitrary_transport():
    assert len(BY_NAME) == len(set(BY_NAME))
    assert len(BY_NAME) >= 40
    for name, operation in BY_NAME.items():
        schema = operation.schema()
        assert schema["additionalProperties"] is False
        assert "url" not in schema["properties"]
        if operation.method != "GET":
            assert "operation_key" in schema["required"]


def test_unauthenticated_and_wrong_origin_requests_fail_before_api():
    async def unexpected(request):
        raise AssertionError("Upstream must not be contacted")

    with TestClient(
        mcp_app("http://management.test", MCP_URL, transport=httpx2.MockTransport(unexpected)),
        base_url=urlunsplit(("https", "mcp.alojan.example.test", "", "", "")),
    ) as client:
        assert client.post("/mcp", json={}).status_code == 401
        assert (
            client.post("/mcp", json={}, headers={"Origin": "https://evil.test"}).status_code == 403
        )


def test_failed_mutation_rolls_back_its_business_write_and_retry_record(accounts, monkeypatch):
    from alojan.profiles import Profiles

    _, scope, created = setup(accounts, ["agents:write"])
    original = Profiles.create

    def fail_after_write(self, *args):
        original(self, *args)
        from alojan.auth import AuthError

        raise AuthError("synthetic_failure", 409)

    monkeypatch.setattr(Profiles, "create", fail_after_write)
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        response = client.post(
            f"/v1/workspaces/{scope}/agents",
            json=content(),
            headers={
                "Authorization": "Bearer " + created["token"],
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 409
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM assistant_profiles").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM management_operations").fetchone()[0] == 0


def test_mcp_create_prepare_publish_activate_keeps_readiness_and_number_gates(accounts, tmp_path):
    from test_agent_releases import qualify, prepare_assets
    from test_number_routing import NODE, DID, ready, verified

    qualify(accounts)
    session, scope, created = setup(
        accounts, ["agents:read", "agents:write", "releases:publish", "numbers:manage"]
    )
    api = create_app(accounts, ORIGIN, voice_node_id=NODE, voice_asset_root=tmp_path / "store")
    with TestClient(
        mcp_app("http://management.test", MCP_URL, transport=httpx2.ASGITransport(app=api)),
        base_url=urlunsplit(("https", "mcp.alojan.example.test", "", "", "")),
    ) as client:

        def invoke(name, **arguments):
            if BY_NAME["alojan_" + name].method != "GET":
                arguments.setdefault("operation_key", str(uuid.uuid4()))
            return rpc(
                client,
                created["token"],
                "tools/call",
                {"name": "alojan_" + name, "arguments": arguments},
            )["result"]

        agent = invoke("create_agent", configuration=content())["structuredContent"]["id"]
        preparation = invoke("prepare_release", agent_id=agent, version=1)["structuredContent"]
        blocked = invoke(
            "publish_agent", agent_id=agent, version=0, preparation_id=preparation["id"]
        )
        assert (
            blocked["isError"] and blocked["structuredContent"]["error"] == "voice_assets_pending"
        )
        # Synthetic tones and operator fixtures prove control flow, not actual inference/carrier readiness.
        preparation, _, _ = prepare_assets(accounts, (session, scope, agent), tmp_path)
        audio = invoke("preview_voice", agent_id=agent, version=1, clip="greeting")
        assert not audio.get("isError"), audio
        assert audio["content"][0]["mimeType"] == "audio/wav"
        assert base64.b64decode(audio["content"][0]["data"]).startswith(b"RIFF")
        stale = invoke("preview_voice", agent_id=agent, version=2, clip="greeting")
        assert stale["isError"] and stale["structuredContent"]["error"] == "stale_version"
        publication = invoke(
            "publish_agent", agent_id=agent, version=0, preparation_id=preparation["id"]
        )
        assert not publication.get("isError"), publication
        release = publication["structuredContent"]["id"]
        status = invoke("get_release_status", agent_id=agent, release_id=release)[
            "structuredContent"
        ]
        assert status["status"] == "awaiting_node" and not status["node_ready"]
        number = verified(accounts, session, scope, DID)
        blocked = invoke("activate_number", number_id=number, release_id=release, version=2)
        assert (
            blocked["isError"]
            and blocked["structuredContent"]["error"] == "release_not_ready_on_node"
        )
        ready(accounts, scope, release)
        status = invoke("get_release_status", agent_id=agent, release_id=release)[
            "structuredContent"
        ]
        assert status["node_ready"] and status["current_publication"]
        activated = invoke("activate_number", number_id=number, release_id=release, version=2)
        assert not activated.get("isError"), activated
        current = invoke("list_numbers")["structuredContent"]["numbers"]
        assert len(current) == 1
        assert current[0]["release_id"] == release


def test_expired_retry_result_never_reexecutes_and_payload_is_compacted(accounts):
    session, scope, created = setup(accounts, ["agents:write"])
    key = str(uuid.uuid4())
    body = content()
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        path = f"/v1/workspaces/{scope}/agents"
        headers = {"Authorization": "Bearer " + created["token"], "Idempotency-Key": key}
        assert client.post(path, json=body, headers=headers).status_code == 201
        with connection(accounts.dsn) as conn:
            conn.execute("UPDATE management_operations SET created_at=now()-interval '8 days'")
        expired = client.post(path, json=body, headers=headers)
        assert expired.status_code == 410 and expired.json()["error"] == "operation_result_expired"
        assert (
            client.post(
                path, json=body, headers=headers | {"Idempotency-Key": str(uuid.uuid4())}
            ).status_code
            == 201
        )
        assert client.post(path, json=body, headers=headers).status_code == 410
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM assistant_profiles").fetchone()[0] == 2
        assert (
            conn.execute(
                "SELECT result FROM management_operations WHERE operation_key=%s", (key,)
            ).fetchone()[0]
            is None
        )


def test_transcript_tool_discovery_requires_both_read_permissions(accounts):
    _, _, created = setup(accounts, ["transcripts:read"])
    with TestClient(
        mcp_app(
            "http://management.test",
            MCP_URL,
            transport=httpx2.ASGITransport(app=create_app(accounts, ORIGIN)),
        ),
        base_url=urlunsplit(("https", "mcp.alojan.example.test", "", "", "")),
    ) as client:
        tools = rpc(client, created["token"], "tools/list")["result"]["tools"]
        assert "alojan_get_transcript" not in {t["name"] for t in tools}
        result = rpc(
            client,
            created["token"],
            "tools/call",
            {"name": "alojan_get_transcript", "arguments": {"call_id": str(uuid.uuid4())}},
        )["result"]
        assert result["isError"] and result["structuredContent"]["error"] == "insufficient_scope"


def test_official_client_negotiates_and_invokes_transport(accounts):
    import asyncio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    _, scope, created = setup(accounts, ["agents:read"])
    app = mcp_app(
        "http://management.test",
        MCP_URL,
        transport=httpx2.ASGITransport(app=create_app(accounts, ORIGIN)),
    )

    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={"Authorization": "Bearer " + created["token"]},
            ) as http:
                async with streamable_http_client(MCP_URL, http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        initialized = await session.initialize()
                        assert (
                            initialized.model_dump(by_alias=True)["serverInfo"]["name"]
                            == "alojan-management"
                        )
                        listing = await session.list_tools()
                        assert "alojan_list_agents" in {tool.name for tool in listing.tools}
                        result = await session.call_tool("alojan_get_context")
                        assert (
                            result.model_dump(by_alias=True)["structuredContent"]["scope_id"]
                            == scope
                        )

    asyncio.run(exercise())
