"""Scoped reviewed tool selection; no secret reads or remote requests."""

from jsonschema.exceptions import SchemaError, ValidationError

from alojan.auth import AuthError
from alojan.mcp_connections import MCPConnections
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.mcp import SUPPORTED_PROTOCOLS
from alojan_contracts.mcp_tools import schema_binding, runtime_schema


from alojan_contracts.mcp_oauth_tokens import oauth_ready


def current_tools(conn, scope, reference):
    row = conn.execute(
        "SELECT endpoint,auth_type FROM mcp_connections WHERE scope_id=%s AND id=%s AND enabled FOR SHARE",
        (scope, reference),
    ).fetchone()
    if not row:
        raise AuthError("mcp_connection_unavailable", 409)
    if row[1] == "oauth" and not oauth_ready(conn, scope, reference):
        raise AuthError("oauth_reconnect_required", 409)
    state = MCPConnections.current(conn, scope, reference)
    snapshot = state["manifest"]
    if (
        state["status"] != "ready"
        or not snapshot
        or snapshot.get("protocol") not in SUPPORTED_PROTOCOLS
    ):
        raise AuthError("mcp_discovery_required", 409)
    if canonical_digest(snapshot["tools"]) != snapshot["digest"]:
        raise AuthError("invalid_mcp_manifest", 409)
    return row[0], state["id"], snapshot["tools"]


def validate_tool(tool):
    if tool.get("review_status") != "unreviewed" or canonical_digest(
        {k: v for k, v in tool.items() if k != "digest"}
    ) != tool.get("digest"):
        raise ValueError("MCP tool digest mismatch")
    return schema_binding(tool)


def selected_tools(conn, scope, configs):
    result, connections = [], {}
    # Stable ordering prevents cross-agent opposite-order row-lock acquisition.
    for reference in sorted({c.connection_id for c in configs}):
        connections[reference] = current_tools(conn, scope, reference)
    for config in configs:
        url, _, tools = connections[config.connection_id]
        row = conn.execute(
            """SELECT tool,capability FROM mcp_tool_reviews
            WHERE scope_id=%s AND connection_id=%s AND id=%s AND enabled FOR SHARE""",
            (scope, config.connection_id, config.review_id),
        ).fetchone()
        if not row or row[1] != "read":
            raise AuthError("mcp_tool_review_required", 409)
        tool = row[0]
        if not any(t == tool for t in tools):
            raise AuthError("mcp_tool_changed", 409)
        try:
            schemas = validate_tool(tool)
            exposed = runtime_schema(
                schemas.get("input_schema", tool["inputSchema"]),
                config.fixed_arguments,
                nullable=bool(schemas),
                formats=schemas.get("schema_policy") == "bounded.v2",
            )
        except (ValueError, TypeError, SchemaError, ValidationError):
            raise AuthError("unsupported_mcp_configuration", 409) from None
        result.append(
            config.model_dump()
            | {"endpoint": url, "capability": "read", "tool": tool, "runtime_schema": exposed}
            | schemas
        )
    return result


class MCPTools:
    def __init__(self, accounts):
        self.accounts = accounts

    def list(self, token, scope, reference):
        with self.accounts.workspace(token, scope) as (conn, _):
            _, _, tools = current_tools(conn, scope, reference)
            rows = conn.execute(
                "SELECT id,tool_digest FROM mcp_tool_reviews WHERE scope_id=%s AND connection_id=%s AND enabled",
                (scope, reference),
            ).fetchall()
            reviews = {digest: str(ref) for ref, digest in rows}
            return {
                "execution_available": False,
                "tools": [
                    {"tool": tool, "review_id": reviews.get(tool["digest"])}
                    | (validate_tool(tool) if tool["digest"] in reviews else {})
                    for tool in tools
                ],
            }
