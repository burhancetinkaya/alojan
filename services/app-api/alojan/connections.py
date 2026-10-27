"""Owner-created, write-only provider credentials; no provider/network calls."""

import uuid

from alojan.auth import AuthError, audit
from alojan_contracts.secrets import SecretBox


def validate_connection(conn, scope, reference):
    if (
        reference is not None
        and not conn.execute(
            "SELECT id FROM provider_connections WHERE scope_id=%s AND id=%s AND enabled FOR SHARE",
            (scope, reference),
        ).fetchone()
    ):
        raise AuthError("provider_connection_unavailable", 409)


class Connections:
    def __init__(self, accounts, secrets=None):
        self.accounts, self.secrets = accounts, secrets

    def create(self, token, scope, body):
        if body.keys() != {"provider", "label", "api_key"} or body["provider"] != "openrouter":
            raise AuthError("invalid_connection", 400)
        label = body["label"]
        if (
            not isinstance(label, str)
            or not 1 <= len(label.strip()) <= 80
            or not label.isprintable()
        ):
            raise AuthError("invalid_connection", 400)
        try:
            SecretBox.validate(body["api_key"])
        except ValueError:
            raise AuthError("invalid_connection", 400) from None
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if self.secrets is None:
                raise AuthError("credential_storage_unavailable", 503)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714211))", (str(scope),))
            if (
                conn.execute(
                    "SELECT count(*) FROM provider_connections WHERE scope_id=%s", (scope,)
                ).fetchone()[0]
                >= 100
            ):
                raise AuthError("connection_limit", 409)
            reference = uuid.uuid4()
            encrypted = self.secrets.seal(scope, reference, body["api_key"])
            conn.execute(
                "INSERT INTO provider_connections(id,scope_id,provider,label,ciphertext) VALUES (%s,%s,'openrouter',%s,%s)",
                (reference, scope, label.strip(), encrypted),
            )
            audit(conn, user["id"], "provider.created", scope=scope, target=reference)
        return {
            "id": str(reference),
            "provider": "openrouter",
            "label": label.strip(),
            "enabled": True,
        }

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                "SELECT id,provider,label,enabled FROM provider_connections WHERE scope_id=%s ORDER BY created_at,id LIMIT 100",
                (scope,),
            ).fetchall()
        return [dict(id=str(row[0]), provider=row[1], label=row[2], enabled=row[3]) for row in rows]

    def revoke(self, token, scope, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE provider_connections SET enabled=false WHERE scope_id=%s AND id=%s RETURNING id",
                (scope, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "provider.revoked", scope=scope, target=reference)
        return {"status": "revoked"}
