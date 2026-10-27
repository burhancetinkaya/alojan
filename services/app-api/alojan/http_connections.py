"""Workspace-scoped immutable HTTP destinations; authoring never sends requests."""

import uuid
from alojan.auth import AuthError, audit
from alojan_contracts.mcp import endpoint
from alojan_contracts.secrets import SecretBox


class HTTPConnections:
    def __init__(self, accounts, secrets=None):
        self.accounts, self.secrets = accounts, secrets

    def create(self, token, scope, body):
        try:
            if body.keys() != {"label", "endpoint", "auth_type", "token"}:
                raise ValueError()
            label, url, auth, key = (
                body["label"],
                endpoint(body["endpoint"]),
                body["auth_type"],
                body["token"],
            )
            if (
                not isinstance(label, str)
                or not 1 <= len(label.strip()) <= 80
                or not label.isprintable()
                or auth not in {"none", "bearer"}
            ):
                raise ValueError()
            if auth == "bearer":
                SecretBox.validate(key)
            elif key is not None:
                raise ValueError()
        except (ValueError, TypeError):
            raise AuthError("invalid_http_connection", 400) from None
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if auth == "bearer" and self.secrets is None:
                raise AuthError("credential_storage_unavailable", 503)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,24))", (str(scope),))
            if (
                conn.execute(
                    "SELECT count(*) FROM http_connections WHERE scope_id=%s", (scope,)
                ).fetchone()[0]
                >= 100
            ):
                raise AuthError("connection_limit", 409)
            reference = uuid.uuid4()
            encrypted = (
                self.secrets.seal(scope, reference, key, purpose="http")
                if auth == "bearer"
                else None
            )
            conn.execute(
                "INSERT INTO http_connections(id,scope_id,label,endpoint,auth_type,ciphertext) VALUES(%s,%s,%s,%s,%s,%s)",
                (reference, scope, label.strip(), url, auth, encrypted),
            )
            audit(conn, user["id"], "http.created", scope=scope, target=reference)
        return dict(
            id=str(reference), label=label.strip(), endpoint=url, auth_type=auth, enabled=True
        )

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                "SELECT id,label,endpoint,auth_type,enabled FROM http_connections WHERE scope_id=%s ORDER BY created_at,id LIMIT 100",
                (scope,),
            ).fetchall()
        return [
            dict(id=str(r[0]), label=r[1], endpoint=r[2], auth_type=r[3], enabled=r[4])
            for r in rows
        ]

    def revoke(self, token, scope, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE http_connections SET enabled=false WHERE scope_id=%s AND id=%s RETURNING id",
                (scope, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "http.revoked", scope=scope, target=reference)
        return {"status": "revoked"}
