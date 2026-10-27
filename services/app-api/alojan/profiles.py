"""Scoped business configuration authoring; no live model or media work."""

import json
import uuid

from psycopg.types.json import Jsonb
from pydantic import ValidationError
from alojan_contracts.configuration import AgentDraft
from alojan_contracts.configuration import ToolConfig as ToolConfig

from alojan.auth import AuthError, audit
from alojan.connections import validate_connection
from alojan.telegram_connections import action_connections
from alojan_contracts.outputs import validate_tools


def validate_draft(content):
    try:
        draft = AgentDraft.model_validate(content)
        if len(json.dumps(draft.model_dump(), ensure_ascii=False).encode()) > 60000:
            raise ValueError("Configuration too large")
        return draft
    except (ValidationError, ValueError):
        # Validation exceptions include submitted input; never send/log them verbatim.
        raise AuthError("invalid_agent_configuration", 400) from None


def validate_output_tools(conn, scope, draft):
    if draft.mcp_tools:
        from alojan.mcp_tools import selected_tools

        tools = selected_tools(conn, scope, draft.mcp_tools)
    else:
        tools = []
    try:
        validate_tools(draft.outputs, tools)
    except ValueError:
        raise AuthError("invalid_output_configuration", 400) from None


def locked_draft(conn, scope, profile):
    row = conn.execute(
        "SELECT version,content FROM agent_drafts WHERE scope_id=%s AND profile_id=%s FOR UPDATE",
        (scope, profile),
    ).fetchone()
    if not row:
        raise AuthError("not_found", 404)
    return row[0], validate_draft(row[1])


class Profiles:
    def __init__(self, accounts):
        self.accounts = accounts

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                """SELECT p.id,p.label,d.version FROM assistant_profiles p
                JOIN agent_drafts d ON d.profile_id=p.id AND d.scope_id=p.scope_id
                WHERE p.scope_id=%s ORDER BY p.created_at,p.id LIMIT 100""",
                (scope,),
            ).fetchall()
        return [{"id": str(row[0]), "name": row[1], "version": row[2]} for row in rows]

    def create(self, token, scope, content):
        draft = validate_draft(content)
        profile_id = uuid.uuid4()
        with self.accounts.workspace(token, scope, roles=("owner", "editor")) as (conn, user):
            validate_connection(conn, scope, draft.model_connection)
            action_connections(conn, scope, draft.post_call_actions)
            validate_output_tools(conn, scope, draft)
            # Serialize admission against this workspace only.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714205))", (str(scope),))
            count = conn.execute(
                "SELECT count(*) FROM assistant_profiles WHERE scope_id=%s",
                (scope,),
            ).fetchone()[0]
            if count >= 100:
                raise AuthError("workspace_agent_limit", 409)
            conn.execute(
                "INSERT INTO assistant_profiles(id,scope_id,label) VALUES (%s,%s,%s)",
                (profile_id, scope, draft.agent_name),
            )
            conn.execute(
                "INSERT INTO agent_drafts(scope_id,profile_id,content,updated_by) VALUES (%s,%s,%s,%s)",
                (scope, profile_id, Jsonb(draft.model_dump()), user["id"]),
            )
            audit(conn, user["id"], "agent.created", scope=scope, target=profile_id)
        return {"id": str(profile_id), "version": 1, "content": draft.model_dump()}

    def get(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            row = conn.execute(
                "SELECT version,content FROM agent_drafts WHERE scope_id=%s AND profile_id=%s",
                (scope, profile),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
        return {"id": str(profile), "version": row[0], "content": row[1]}

    def update(self, token, scope, profile, content, version):
        draft = validate_draft(content)
        with self.accounts.workspace(token, scope, roles=("owner", "editor")) as (conn, user):
            current, _ = locked_draft(conn, scope, profile)
            if current != version:
                raise AuthError("stale_version", 412)
            validate_connection(conn, scope, draft.model_connection)
            action_connections(conn, scope, draft.post_call_actions)
            validate_output_tools(conn, scope, draft)
            row = conn.execute(
                """UPDATE agent_drafts SET content=%s,version=version+1,updated_by=%s,updated_at=now()
                WHERE scope_id=%s AND profile_id=%s AND version=%s RETURNING version""",
                (Jsonb(draft.model_dump()), user["id"], scope, profile, version),
            ).fetchone()
            if not row:
                exists = conn.execute(
                    "SELECT 1 FROM agent_drafts WHERE scope_id=%s AND profile_id=%s",
                    (scope, profile),
                ).fetchone()
                raise AuthError("stale_version" if exists else "not_found", 412 if exists else 404)
            conn.execute(
                "UPDATE assistant_profiles SET label=%s WHERE scope_id=%s AND id=%s",
                (draft.agent_name, scope, profile),
            )
            audit(conn, user["id"], "agent.draft_updated", scope=scope, target=profile)
        return {"id": str(profile), "version": row[0], "content": draft.model_dump()}

    def preview(self, token, scope, profile):
        result = self.get(token, scope, profile)
        draft = validate_draft(result["content"])
        return {
            "version": result["version"],
            "digest": draft.digest(),
            "greeting": draft.greeting(),
            "tool_aliases": [tool.alias for tool in (*draft.tools, *draft.mcp_tools)],
            "readiness": "draft",
            "can_receive_calls": False,
        }
