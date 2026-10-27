"""Owner consent for exact reviewed MCP selections; execution requires node readiness."""

import json
import re
import uuid

from psycopg.types.json import Jsonb

from alojan.auth import AuthError, audit
from alojan.mcp_tools import selected_tools
from alojan.profiles import locked_draft
from alojan_contracts.configuration import canonical_digest


def review_tools(conn, scope, profile, draft):
    if not draft.mcp_tools:
        raise AuthError("no_mcp_tools", 409)
    review = {
        "schema_version": 1,
        "scope_id": str(scope),
        "profile_id": str(profile),
        "tools": selected_tools(conn, scope, draft.mcp_tools),
    }
    if any("schema_policy" in t for t in review["tools"]):
        review["schema_version"] = 2
    if any(t.get("schema_policy") == "bounded.v2" for t in review["tools"]):
        review["schema_version"] = 3
    if len(json.dumps(review, ensure_ascii=False).encode()) > 262144:
        raise AuthError("mcp_review_limit", 409)
    return review


def live_grant(conn, scope, profile, review, *, reference=None):
    row = conn.execute(
        """SELECT g.id,g.review FROM mcp_tool_grants g
        JOIN users u ON u.id=g.granted_by AND u.enabled
        JOIN workspace_memberships m ON m.scope_id=g.scope_id AND m.user_id=g.granted_by AND m.role='owner'
        WHERE g.scope_id=%s AND g.profile_id=%s AND g.enabled AND g.review_digest=%s
        AND (%s::uuid IS NULL OR g.id=%s) FOR SHARE OF g""",
        (scope, profile, canonical_digest(review), reference, reference),
    ).fetchone()
    if not row or row[1] != review:
        raise AuthError("mcp_grant_required", 409)
    return {"id": str(row[0]), "review": review}


def publication_grant(conn, scope, profile, draft, *, previous=None):
    if not draft.mcp_tools:
        if previous is not None:
            raise AuthError("invalid_mcp_grant", 409)
        return None
    from alojan_contracts.mcp_release import authorization

    review = review_tools(conn, scope, profile, draft)
    if previous is not None:
        try:
            authorization(previous, draft)
        except (ValueError, TypeError, KeyError):
            raise AuthError("invalid_mcp_grant", 409) from None
        if previous["review"] != review:
            raise AuthError("invalid_mcp_grant", 409)
    result = live_grant(
        conn, scope, profile, review, reference=previous["id"] if previous else None
    )
    try:
        authorization(result, draft)
    except (ValueError, TypeError, KeyError):
        raise AuthError("unsupported_mcp_release", 409) from None
    return result


class MCPGrants:
    def __init__(self, accounts):
        self.accounts = accounts

    def review(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            version, draft = locked_draft(conn, scope, profile)
            review = review_tools(conn, scope, profile, draft)
        return {
            "draft_version": version,
            "review_digest": canonical_digest(review),
            "review": review,
            "execution_available": False,
        }

    def authorize(self, token, scope, profile, body):
        if (
            body.keys() != {"draft_version", "review_digest"}
            or type(body["draft_version"]) is not int
            or not 1 <= body["draft_version"] <= 999999999
            or not isinstance(body["review_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", body["review_digest"])
        ):
            raise AuthError("invalid_mcp_authorization", 400)
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            version, draft = locked_draft(conn, scope, profile)
            if version != body["draft_version"]:
                raise AuthError("stale_version", 412)
            review = review_tools(conn, scope, profile, draft)
            digest = canonical_digest(review)
            if digest != body["review_digest"]:
                raise AuthError("stale_mcp_review", 409)
            existing = conn.execute(
                "SELECT id FROM mcp_tool_grants WHERE scope_id=%s AND profile_id=%s AND review_digest=%s AND enabled",
                (scope, profile, digest),
            ).fetchone()
            if existing:
                reference = live_grant(conn, scope, profile, review, reference=existing[0])["id"]
            else:
                if (
                    conn.execute(
                        "SELECT count(*) FROM mcp_tool_grants WHERE scope_id=%s AND profile_id=%s",
                        (scope, profile),
                    ).fetchone()[0]
                    >= 1000
                ):
                    raise AuthError("mcp_grant_limit", 409)
                reference = uuid.uuid4()
                conn.execute(
                    """INSERT INTO mcp_tool_grants(id,scope_id,profile_id,review,review_digest,granted_by)
                    VALUES(%s,%s,%s,%s,%s,%s)""",
                    (reference, scope, profile, Jsonb(review), digest, user["id"]),
                )
                audit(conn, user["id"], "mcp.tools_authorized", scope=scope, target=reference)
        return {"id": str(reference), "review_digest": digest, "enabled": True}

    def list(self, token, scope, profile):
        with self.accounts.workspace(token, scope) as (conn, _):
            locked_draft(conn, scope, profile)
            rows = conn.execute(
                "SELECT id,review_digest,enabled FROM mcp_tool_grants WHERE scope_id=%s AND profile_id=%s ORDER BY created_at DESC,id LIMIT 1000",
                (scope, profile),
            ).fetchall()
        return [dict(id=str(r[0]), review_digest=r[1], enabled=r[2]) for r in rows]

    def revoke(self, token, scope, profile, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE mcp_tool_grants SET enabled=false WHERE scope_id=%s AND profile_id=%s AND id=%s RETURNING id",
                (scope, profile, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "mcp.tools_revoked", scope=scope, target=reference)
        return {"status": "revoked"}
