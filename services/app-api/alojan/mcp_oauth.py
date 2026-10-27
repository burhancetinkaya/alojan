"""Owner/session-bound OAuth consent. No network request runs in the voice process."""

import asyncio
import hmac
import re
import secrets
import uuid

from psycopg.types.json import Jsonb

from alojan.auth import AuthError, audit
from alojan_contracts.mcp_oauth import (
    authorization_url,
    digest,
    exchange,
    validate_metadata,
)


class MCPOAuth:
    def __init__(
        self,
        accounts,
        box,
        registry,
        origin,
        *,
        metadata=validate_metadata,
        exchange_tokens=exchange,
    ):
        self.accounts, self.box, self.registry = accounts, box, registry
        self.redirect = origin + "/mcp-donus"
        self.metadata, self.exchange = metadata, exchange_tokens

    def list(self, token, scope):
        with self.accounts.workspace(token, scope):
            return [
                {
                    k: c[k]
                    for k in (
                        "id",
                        "label",
                        "resource",
                        "issuer",
                        "authorization_endpoint",
                        "scopes",
                    )
                }
                for c in self.registry.values()
            ]

    def start(self, token, scope, body):
        if (
            body.keys() != {"provider_id", "label"}
            or not isinstance(body["label"], str)
            or not 1 <= len(body["label"].strip()) <= 80
            or not body["label"].isprintable()
            or not isinstance(body["provider_id"], str)
        ):
            raise AuthError("invalid_fields", 400)
        config = self.registry.get(body["provider_id"])
        if config is None or self.box is None:
            raise AuthError("oauth_provider_unavailable", 409)
        flow = uuid.uuid4()
        state = f"{scope}.{flow}.{secrets.token_urlsafe(32)}"
        verifier = secrets.token_urlsafe(48)
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,20))", (str(scope),))
            conn.execute(
                "DELETE FROM mcp_oauth_flows WHERE scope_id=%s AND created_at<now()-interval '1 day'",
                (scope,),
            )
            recent, pending = conn.execute(
                """SELECT count(*),count(*) FILTER(WHERE status='pending' AND expires_at>now())
                FROM mcp_oauth_flows WHERE scope_id=%s""",
                (scope,),
            ).fetchone()
            if recent >= 20 or pending >= 4:
                raise AuthError("oauth_flow_limit", 429)
            conn.execute(
                """INSERT INTO mcp_oauth_flows(id,scope_id,user_id,session_hash,state_hash,verifier,label,provider,redirect_uri)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    flow,
                    scope,
                    user["id"],
                    digest(token),
                    digest(state),
                    self.box.seal(scope, flow, verifier, purpose="mcp-oauth-verifier"),
                    body["label"].strip(),
                    Jsonb(config),
                    self.redirect,
                ),
            )
            audit(conn, user["id"], "mcp.oauth_started", scope=scope, target=flow)
        try:
            asyncio.run(self.metadata(config))
        except Exception:
            self.fail(token, scope, flow)
            raise AuthError("oauth_metadata_unavailable", 409) from None
        return {"authorization_url": authorization_url(config, self.redirect, state, verifier)}

    def fail(self, token, scope, flow):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, _):
            conn.execute(
                "UPDATE mcp_oauth_flows SET status='failed' WHERE scope_id=%s AND id=%s AND status IN ('pending','exchanging')",
                (scope, flow),
            )

    def complete(self, token, scope, body):
        if body.keys() != {"state", "code", "issuer"} or any(
            not isinstance(v, str) for v in body.values()
        ):
            raise AuthError("invalid_oauth_callback", 400)
        match = re.fullmatch(
            r"([a-f0-9-]{36})\.([a-f0-9-]{36})\.([A-Za-z0-9_-]{43})", body["state"]
        )
        if (
            not match
            or match[1] != str(scope)
            or not 1 <= len(body["code"]) <= 4096
            or any(not 33 <= ord(c) <= 126 for c in body["code"])
            or len(body["issuer"]) > 2048
        ):
            raise AuthError("invalid_oauth_callback", 400)
        try:
            flow = uuid.UUID(match[2])
        except ValueError:
            raise AuthError("invalid_oauth_callback", 400) from None
        fingerprint = digest(body["code"])
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            row = conn.execute(
                """SELECT user_id,session_hash,state_hash,verifier,label,provider,redirect_uri,status,code_hash,connection_id
                FROM mcp_oauth_flows WHERE scope_id=%s AND id=%s AND expires_at>now() FOR UPDATE""",
                (scope, flow),
            ).fetchone()
            if (
                not row
                or str(row[0]) != str(user["id"])
                or not hmac.compare_digest(row[1], digest(token))
                or not hmac.compare_digest(row[2], digest(body["state"]))
                or row[5]["issuer"] != body["issuer"]
                or self.registry.get(row[5]["id"]) != row[5]
                or row[6] != self.redirect
            ):
                raise AuthError("invalid_oauth_callback", 409)
            if row[7] == "complete" and row[8] == fingerprint:
                return {"connection_id": str(row[9])}
            if row[7] != "pending":
                raise AuthError("oauth_flow_consumed", 409)
            conn.execute(
                "UPDATE mcp_oauth_flows SET status='exchanging',code_hash=%s WHERE scope_id=%s AND id=%s",
                (fingerprint, scope, flow),
            )
        # Consume before I/O: an ambiguous exchange is never retried with the same code.
        try:
            verifier = self.box.open(scope, flow, bytes(row[3]), purpose="mcp-oauth-verifier")
            access, refresh, lifetime = asyncio.run(
                self.exchange(row[5], code=body["code"], verifier=verifier, redirect=row[6])
            )
        except Exception:
            self.fail(token, scope, flow)
            raise AuthError("oauth_exchange_failed", 409) from None
        reference = uuid.uuid4()
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,20))", (str(scope),))
            live = conn.execute(
                "SELECT id FROM mcp_oauth_flows WHERE scope_id=%s AND id=%s AND status='exchanging' AND expires_at>now() FOR UPDATE",
                (scope, flow),
            ).fetchone()
            if not live:
                raise AuthError("oauth_flow_consumed", 409)
            if (
                conn.execute(
                    "SELECT count(*) FROM mcp_connections WHERE scope_id=%s", (scope,)
                ).fetchone()[0]
                >= 50
            ):
                raise AuthError("connection_limit", 409)
            conn.execute(
                "INSERT INTO mcp_connections(id,scope_id,label,endpoint,auth_type) VALUES(%s,%s,%s,%s,'oauth')",
                (reference, scope, row[4], row[5]["resource"]),
            )
            conn.execute(
                """INSERT INTO mcp_oauth_credentials(connection_id,scope_id,authorized_by,provider,access_ciphertext,refresh_ciphertext,expires_at,refresh_after)
                VALUES(%s,%s,%s,%s,%s,%s,now()+%s*interval '1 second',now()+%s*interval '1 second')""",
                (
                    reference,
                    scope,
                    user["id"],
                    Jsonb(row[5]),
                    self.box.seal(scope, reference, access, purpose="mcp-oauth-access"),
                    self.box.seal(scope, reference, refresh, purpose="mcp-oauth-refresh")
                    if refresh
                    else None,
                    lifetime - 10,
                    max(1, lifetime - 70),
                ),
            )
            conn.execute(
                "UPDATE mcp_oauth_flows SET status='complete',connection_id=%s WHERE scope_id=%s AND id=%s",
                (reference, scope, flow),
            )
            audit(conn, user["id"], "mcp.oauth_connected", scope=scope, target=reference)
        return {"connection_id": str(reference)}
