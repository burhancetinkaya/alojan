"""Token-delegated setup, with secret entry bound to the same human account."""

import re
import uuid

from psycopg.types.json import Jsonb

from alojan.auth import AuthError, _management_transaction, audit
from alojan.personal_tokens import BearerCredential
from alojan_contracts.mcp import endpoint


class ConnectionSetups:
    def __init__(self, accounts, stores, origin):
        self.accounts, self.stores, self.origin = accounts, stores, origin

    def create(self, token, scope, body):
        if not isinstance(token, BearerCredential):
            raise AuthError("personal_token_required", 403)
        try:
            if body.keys() != {"kind", "configuration"}:
                raise ValueError()
            kind, config = body["kind"], body["configuration"]
            keys = {
                "provider": {"label", "provider"},
                "telegram": {"label", "chat_id"},
                "http": {"label", "endpoint", "auth_type"},
                "mcp": {"label", "endpoint", "auth_type"},
            }
            if (
                not isinstance(kind, str)
                or kind not in keys
                or not isinstance(config, dict)
                or config.keys() != keys[kind]
            ):
                raise ValueError()
            if (
                not isinstance(config["label"], str)
                or not 1 <= len(config["label"].strip()) <= 80
                or not config["label"].isprintable()
            ):
                raise ValueError()
            if kind == "provider" and config["provider"] != "openrouter":
                raise ValueError()
            if kind == "telegram" and (
                not isinstance(config["chat_id"], str)
                or not re.fullmatch(r"-?[1-9][0-9]{0,15}", config["chat_id"])
            ):
                raise ValueError()
            if kind in {"http", "mcp"}:
                endpoint(config["endpoint"])
                if config["auth_type"] not in {"none", "bearer"}:
                    raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise AuthError("invalid_connection_setup", 400) from None
        if kind in {"http", "mcp"} and config["auth_type"] == "none":
            result = self.stores[kind].create(token, scope, config | {"token": None})
            return {"status": "complete", "connection": result}
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714207))", (user["id"],))
            count = conn.execute(
                "SELECT count(*) FROM management_connection_setups WHERE user_id=%s AND scope_id=%s AND expires_at>now() AND connection_id IS NULL",
                (user["id"], scope),
            ).fetchone()[0]
            if count >= 5:
                raise AuthError("connection_setup_limit", 429)
            identifier = uuid.uuid4()
            conn.execute(
                "INSERT INTO management_connection_setups(id,user_id,scope_id,personal_token_id,kind,configuration) VALUES (%s,%s,%s,%s,%s,%s)",
                (identifier, user["id"], scope, user["personal_token_id"], kind, Jsonb(config)),
            )
            audit(conn, user["id"], "connection_setup.created", scope=scope, target=identifier)
        return {
            "id": str(identifier),
            "status": "needs_secret",
            "setup_url": f"{self.origin}/baglanti-kur/{scope}/{identifier}",
            "instructions": "The same user must sign in and enter the credential on this page. Never paste credentials into chat. The link alone grants no access.",
        }

    def get(self, token, scope, identifier):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            row = conn.execute(
                "SELECT kind,configuration,connection_id,expires_at>now() FROM management_connection_setups WHERE id=%s AND user_id=%s AND scope_id=%s",
                (identifier, user["id"], scope),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
        return {
            "id": str(identifier),
            "kind": row[0],
            "configuration": row[1],
            "connection_id": str(row[2]) if row[2] else None,
            "status": "complete" if row[2] else "needs_secret" if row[3] else "expired",
        }

    def complete(self, token, scope, identifier, body):
        if isinstance(token, BearerCredential):
            raise AuthError("browser_session_required", 403)
        if body.keys() != {"secret"}:
            raise AuthError("invalid_fields", 400)
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            row = conn.execute(
                "SELECT kind,configuration,connection_id,expires_at>now(),personal_token_id FROM management_connection_setups WHERE id=%s AND user_id=%s AND scope_id=%s FOR UPDATE",
                (identifier, user["id"], scope),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            if row[2]:
                return {"status": "complete", "connection_id": str(row[2])}
            if not row[3]:
                raise AuthError("connection_setup_expired", 409)
            active = conn.execute(
                "SELECT 1 FROM personal_access_tokens t JOIN users u ON u.id=t.user_id WHERE t.id=%s AND t.revoked_at IS NULL AND t.expires_at>now() AND t.password_version=u.password_version AND 'connections:write'=ANY(t.permissions)",
                (row[4],),
            ).fetchone()
            if not active:
                raise AuthError("connection_setup_revoked", 403)
            key = {"provider": "api_key", "telegram": "bot_token", "http": "token", "mcp": "token"}[
                row[0]
            ]
            marker = _management_transaction.set((self.accounts.dsn, conn))
            try:
                result = self.stores[row[0]].create(token, scope, row[1] | {key: body["secret"]})
            finally:
                _management_transaction.reset(marker)
            conn.execute(
                "UPDATE management_connection_setups SET connection_id=%s WHERE id=%s",
                (result["id"], identifier),
            )
            audit(conn, user["id"], "connection_setup.completed", scope=scope, target=identifier)
        return {"status": "complete", "connection_id": result["id"]}
