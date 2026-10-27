"""Write-only Telegram credentials with immutable targets; never sends messages."""

import re
import uuid

from alojan.auth import AuthError, audit


def action_connections(conn, scope, actions):
    result = {}
    for action in sorted(actions, key=lambda a: a.connection_id):
        reference = action.connection_id
        if action.adapter == "http_request.v1":
            row = conn.execute(
                "SELECT label,endpoint,auth_type FROM http_connections WHERE scope_id=%s AND id=%s AND enabled FOR SHARE",
                (scope, reference),
            ).fetchone()
            if not row:
                raise AuthError("http_connection_unavailable", 409)
            target = dict(connection_label=row[0], endpoint=row[1], auth_type=row[2])
        else:
            row = conn.execute(
                "SELECT label,chat_id FROM telegram_connections WHERE scope_id=%s AND id=%s AND enabled FOR SHARE",
                (scope, reference),
            ).fetchone()
            if not row:
                raise AuthError("telegram_connection_unavailable", 409)
            target = dict(connection_label=row[0], chat_id=row[1])
        if reference in result and result[reference] != target:
            raise AuthError("invalid_action_intent", 409)
        result[reference] = target
    return result


class TelegramConnections:
    def __init__(self, accounts, secrets=None):
        self.accounts, self.secrets = accounts, secrets

    def create(self, token, scope, body):
        if body.keys() != {"label", "chat_id", "bot_token"}:
            raise AuthError("invalid_telegram_connection", 400)
        label, chat, key = body["label"], body["chat_id"], body["bot_token"]
        if (
            not isinstance(label, str)
            or not 1 <= len(label.strip()) <= 80
            or not label.isprintable()
            or not isinstance(chat, str)
            or not re.fullmatch(r"-?[1-9][0-9]{0,15}", chat)
            or abs(int(chat)) > 4503599627370495
            or not isinstance(key, str)
            or not re.fullmatch(r"[1-9][0-9]{0,19}:[A-Za-z0-9_-]{20,128}", key)
        ):
            raise AuthError("invalid_telegram_connection", 400)
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if self.secrets is None:
                raise AuthError("credential_storage_unavailable", 503)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714212))", (str(scope),))
            if (
                conn.execute(
                    "SELECT count(*) FROM telegram_connections WHERE scope_id=%s", (scope,)
                ).fetchone()[0]
                >= 100
            ):
                raise AuthError("connection_limit", 409)
            reference = uuid.uuid4()
            encrypted = self.secrets.seal(scope, reference, key, purpose="telegram")
            conn.execute(
                "INSERT INTO telegram_connections(id,scope_id,label,chat_id,ciphertext) VALUES (%s,%s,%s,%s,%s)",
                (reference, scope, label.strip(), chat, encrypted),
            )
            audit(conn, user["id"], "telegram.created", scope=scope, target=reference)
        return dict(id=str(reference), label=label.strip(), chat_id=chat, enabled=True)

    def list(self, token, scope):
        with self.accounts.workspace(token, scope) as (conn, _):
            rows = conn.execute(
                "SELECT id,label,chat_id,enabled FROM telegram_connections WHERE scope_id=%s ORDER BY created_at,id LIMIT 100",
                (scope,),
            ).fetchall()
        return [dict(id=str(r[0]), label=r[1], chat_id=r[2], enabled=r[3]) for r in rows]

    def revoke(self, token, scope, reference):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            if not conn.execute(
                "UPDATE telegram_connections SET enabled=false WHERE scope_id=%s AND id=%s RETURNING id",
                (scope, reference),
            ).fetchone():
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "telegram.revoked", scope=scope, target=reference)
        return {"status": "revoked"}
