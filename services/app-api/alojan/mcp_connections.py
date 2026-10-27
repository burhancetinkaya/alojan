"""Workspace MCP authoring and explicit discovery queue; no network in HTTP handlers."""

import uuid

from alojan.auth import AuthError, audit
from alojan_contracts.mcp import endpoint
from alojan_contracts.secrets import SecretBox


from alojan_contracts.mcp_oauth_tokens import oauth_ready


class MCPConnections:
    def __init__(self, accounts, secrets=None):
        self.accounts, self.secrets = accounts, secrets

    def create(self, token, scope, body):
        try:
            if body.keys() != {"label", "endpoint", "auth_type", "token"}:
                raise ValueError()
            label, url, kind, key = (
                body["label"],
                endpoint(body["endpoint"]),
                body["auth_type"],
                body["token"],
            )
            if (
                not isinstance(label, str)
                or not 1 <= len(label.strip()) <= 80
                or not label.isprintable()
            ):
                raise ValueError()
            if kind not in {"none", "bearer"} or (kind == "none" and key is not None):
                raise ValueError()
            if kind == "bearer":
                SecretBox.validate(key)
        except (ValueError, TypeError):
            raise AuthError("invalid_mcp_connection", 400) from None
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,20))", (str(scope),))
            if (
                conn.execute(
                    "SELECT count(*) FROM mcp_connections WHERE scope_id=%s", (scope,)
                ).fetchone()[0]
                >= 50
            ):
                raise AuthError("connection_limit", 409)
            if kind == "bearer" and self.secrets is None:
                raise AuthError("credential_storage_unavailable", 503)
            reference = uuid.uuid4()
            encrypted = (
                self.secrets.seal(scope, reference, key, purpose="mcp")
                if kind == "bearer"
                else None
            )
            conn.execute(
                "INSERT INTO mcp_connections(id,scope_id,label,endpoint,auth_type,ciphertext) VALUES (%s,%s,%s,%s,%s,%s)",
                (reference, scope, label.strip(), url, kind, encrypted),
            )
            audit(conn, user["id"], "mcp.created", scope=scope, target=reference)
        return dict(
            id=str(reference), label=label.strip(), endpoint=url, auth_type=kind, enabled=True
        )

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                "SELECT c.id,c.label,c.endpoint,c.auth_type,c.enabled,CASE WHEN o.expires_at<=now()+interval '30 seconds' THEN 'reauth_required' ELSE o.status END FROM mcp_connections c LEFT JOIN mcp_oauth_credentials o ON (o.scope_id,o.connection_id)=(c.scope_id,c.id) WHERE c.scope_id=%s ORDER BY c.created_at,c.id LIMIT 50",
                (scope,),
            ).fetchall()
        return [
            dict(id=str(r[0]), label=r[1], endpoint=r[2], auth_type=r[3], enabled=r[4])
            | ({"auth_status": r[5]} if r[3] == "oauth" else {})
            for r in rows
        ]

    def revoke(self, token, scope, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE mcp_connections SET enabled=false WHERE scope_id=%s AND id=%s RETURNING id",
                (scope, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "mcp.revoked", scope=scope, target=reference)
        return {"status": "revoked"}

    @staticmethod
    def current(conn, scope, reference):
        row = conn.execute(
            "SELECT id,status,failure_code,manifest FROM mcp_discovery_jobs WHERE scope_id=%s AND connection_id=%s ORDER BY created_at DESC,id DESC LIMIT 1",
            (scope, reference),
        ).fetchone()
        return (
            dict(id=str(row[0]), status=row[1], failure_code=row[2], manifest=row[3])
            if row
            else {
                "id": None,
                "status": "missing",
                "failure_code": None,
                "manifest": None,
            }
        )

    def discover(self, token, scope, reference, *, request=False):
        with self.accounts.workspace(
            token, scope, roles=("owner",) if request else ("owner", "editor", "viewer")
        ) as (conn, user):
            if request:
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,20))", (str(scope),))
            row = conn.execute(
                "SELECT enabled,auth_type FROM mcp_connections WHERE scope_id=%s AND id=%s"
                + (" FOR UPDATE" if request else ""),
                (scope, reference),
            ).fetchone()
            if row is None:
                raise AuthError("not_found", 404)
            state = self.current(conn, scope, reference)
            if not request:
                return state
            if not row[0]:
                raise AuthError("mcp_connection_revoked", 409)
            if row[1] == "oauth" and not oauth_ready(conn, scope, reference):
                raise AuthError("oauth_reconnect_required", 409)
            if state["status"] in {"queued", "running"}:
                return state
            pending, recent, total = conn.execute(
                """SELECT count(*) FILTER(WHERE status IN ('queued','running')),
                count(*) FILTER(WHERE created_at>now()-interval '1 hour'),count(*)
                FROM mcp_discovery_jobs WHERE scope_id=%s""",
                (scope,),
            ).fetchone()
            if pending >= 4 or recent >= 10 or total >= 100:
                raise AuthError("mcp_discovery_limit", 429)
            job = uuid.uuid4()
            conn.execute(
                "INSERT INTO mcp_discovery_jobs(id,scope_id,connection_id) VALUES (%s,%s,%s)",
                (job, scope, reference),
            )
            audit(conn, user["id"], "mcp.discovery_requested", scope=scope, target=job)
            return dict(id=str(job), status="queued", failure_code=None, manifest=None)
