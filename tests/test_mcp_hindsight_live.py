"""Opt-in owner-authorized read acceptance; isolated DB, no remote writes or real call data."""

import asyncio
import json
import os
import time
import uuid

import pytest

from alojan.auth import Accounts, connection
from alojan.mcp_connections import MCPConnections
from alojan.mcp_grants import MCPGrants
from alojan.mcp_review import approve
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_agent.mcp_discovery_worker import process_one
from alojan_agent.mcp_runtime import MCPExecutor, invoke_remote
from alojan_agent.models import Call
from alojan_agent.records import CallRecords
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.runtime import compile_release
from test_agent_releases import prepare_assets, qualify
from test_mcp_tools import consent, content, owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
URL = os.environ.get("ALOJAN_HINDSIGHT_MCP_URL", "")
# Exact inspected discovery. Changed remote semantics require a new review, never auto-approve.
DIGEST = "c8b1ccfffd82acf2c6e4242c04ba6fe7e0b880a5e8cc7055b8626f683ecbfc43"
pytestmark = pytest.mark.skipif(
    os.environ.get("ALOJAN_HINDSIGHT_READ_ACCEPTANCE") != "1",
    reason="Requires explicit owner-authorized Hindsight read acceptance",
)


def test_real_discovery_granted_read_and_revocation(accounts, dedicated, tmp_path):
    assert URL, "Set ALOJAN_HINDSIGHT_MCP_URL privately before opting into the live test"
    who = owner(accounts)
    scoped = Accounts(dedicated("management"))
    store = MCPConnections(scoped)
    ref = store.create(
        *who, dict(label="Hindsight acceptance", endpoint=URL, auth_type="none", token=None)
    )["id"]
    store.discover(*who, ref, request=True)
    discovery_started = time.monotonic()
    assert asyncio.run(process_one(dedicated("mcp"), None))
    discovery_seconds = time.monotonic() - discovery_started
    state = store.discover(*who, ref)
    assert state["status"] == "ready", "Real discovery did not become ready"
    tool = next(t for t in state["manifest"]["tools"] if t["name"] == "list_banks")
    assert tool["digest"] == DIGEST, "Remote tool changed; inspect before qualification"
    review = approve(
        accounts.dsn,
        who[1],
        ref,
        DIGEST,
        reviewer="owner-authorized-integration-test",
        evidence="Official Hindsight MCP docs: list_banks is a paginated read. Random unmatched query; limit 1; offset 0. Disposable scope only.",
    )
    fixed = dict(query="alojan-acceptance-no-match-" + uuid.uuid4().hex, limit=1, offset=0)
    draft = content() | {
        "mcp_tools": [
            {
                "connection_id": ref,
                "review_id": review,
                "alias": "mcp_banks",
                "fixed_arguments": fixed,
            }
        ]
    }
    agent = Profiles(scoped).create(*who, draft)["id"]
    author = (*who, agent)
    grant = consent(scoped, author)
    qualify(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    release = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
    with connection(accounts.dsn) as conn:
        manifest = conn.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
    assert manifest["schema_version"] == 8
    routing.bound(accounts, (*author, release))
    route = routing.initialize(accounts, "hindsight-synthetic-call")
    asyncio.run(CallRecords(dedicated("records"), route).answered(route.call_id))
    call = Call(
        runtime=compile_release(json.dumps(manifest), canonical_digest(manifest), scope_id=who[1]),
        route=route,
        turns=1,
    )
    attempts = []

    async def observed(url, token, name, arguments):
        assert url == URL and token is None and name == "list_banks" and arguments == fixed
        attempts.append(name)
        return await invoke_remote(url, token, name, arguments)

    async def run():
        executor = MCPExecutor(dedicated("mcp-execution"), None, invoke=observed)
        try:
            await executor.prepare(call.runtime)
            assert not json.loads(await executor.execute(call, 1, "mcp_banks", '{"query":null}'))[
                "ok"
            ]
            assert not attempts
            start = time.monotonic()
            result = json.loads(await executor.execute(call, 1, "mcp_banks", "{}"))
            elapsed = time.monotonic() - start
            assert result.get("ok") is True, "Real granted read did not succeed"
            payload = json.loads(result["result"]["result"])
            assert (
                isinstance(payload, dict)
                and payload.get("banks") == []
                and payload.get("total") == 0
            ), "Unexpected matching bank data; do not print"
            MCPGrants(scoped).revoke(*author, grant["id"])
            with pytest.raises(ValueError):
                await executor.prepare(call.runtime)
            assert not json.loads(await executor.execute(call, 1, "mcp_banks", "{}"))["ok"]
            assert attempts == ["list_banks"]
            print(
                json.dumps(
                    dict(
                        discovery_tools=len(state["manifest"]["tools"]),
                        discovery_seconds=round(discovery_seconds, 3),
                        read_seconds=round(elapsed, 3),
                        real_read_calls=1,
                        returned_banks=0,
                        fixed_override_blocked=True,
                        revoked_grant_blocked=True,
                    )
                )
            )
        finally:
            await executor.close()

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        assert conn.execute(
            "SELECT status,count(*) FROM mcp_tool_executions GROUP BY status"
        ).fetchall() == [("succeeded", 1)]
        assert conn.execute("SELECT count(*) FROM action_jobs").fetchone() == (0,)
