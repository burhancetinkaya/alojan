"""Revocable credentials for the management audience, never voice-provider credentials."""

import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass, field

from alojan.auth import AuthError, audit, connection, verify_password

PERMISSIONS = frozenset(
    {
        "agents:read",
        "agents:write",
        "connections:read",
        "connections:write",
        "calls:read",
        "transcripts:read",
        "releases:publish",
        "numbers:manage",
        "grants:manage",
        "deliveries:retry",
    }
)
READ = frozenset({"agents:read", "connections:read", "calls:read", "transcripts:read"})
ROLE_PERMISSIONS = {
    "viewer": READ,
    "editor": READ | {"agents:write"},
    "owner": PERMISSIONS,
}
PATTERN = re.compile(r"alojan_pat_([a-f0-9]{32})_([A-Za-z0-9_-]{43})")


@dataclass(frozen=True)
class BearerCredential:
    value: str = field(repr=False)
    scope: str | None
    required: frozenset[str]


def authenticate(conn, credential):
    match = PATTERN.fullmatch(credential.value)
    if not match:
        raise AuthError("authentication_required")
    row = conn.execute(
        """SELECT t.id,t.user_id,t.scope_id,t.secret_hash,t.permissions,
        u.login,u.display_name,m.role FROM personal_access_tokens t
        JOIN users u ON u.id=t.user_id
        JOIN workspace_memberships m ON m.user_id=u.id AND m.scope_id=t.scope_id
        JOIN recipient_scopes s ON s.id=t.scope_id
        WHERE t.id=%s AND t.revoked_at IS NULL AND t.expires_at>now()
        AND u.enabled AND s.enabled AND t.password_version=u.password_version
        AND t.audience='alojan-management'""",
        (uuid.UUID(match[1]),),
    ).fetchone()
    if not row or not hmac.compare_digest(
        bytes(row[3]), hashlib.sha256(match[2].encode("ascii")).digest()
    ):
        raise AuthError("authentication_required")
    if credential.scope is not None and str(row[2]) != str(credential.scope):
        raise AuthError("not_found", 404)
    permissions = frozenset(row[4]) & ROLE_PERMISSIONS[row[7]]
    if not credential.required <= permissions:
        raise AuthError("insufficient_scope", 403)
    conn.execute(
        """UPDATE personal_access_tokens SET last_used_at=now() WHERE id=%s
        AND (last_used_at IS NULL OR last_used_at < now()-interval '1 minute')""",
        (row[0],),
    )
    conn.execute("SELECT set_config('alojan.personal_token_id',%s,true)", (str(row[0]),))
    return {
        "id": str(row[1]),
        "login": row[5],
        "display_name": row[6],
        "personal_token_id": str(row[0]),
        "scope_id": str(row[2]),
        "role": row[7],
        "permissions": sorted(permissions),
    }


class PersonalTokens:
    def __init__(self, accounts):
        self.accounts = accounts

    def list(self, session, scope):
        with self.accounts.workspace(session, scope) as (conn, user):
            rows = conn.execute(
                """SELECT id,name,permissions,created_at,expires_at,revoked_at,last_used_at
                FROM personal_access_tokens WHERE user_id=%s AND scope_id=%s
                ORDER BY (revoked_at IS NULL AND expires_at>now()) DESC,
                         created_at DESC,id LIMIT 100""",
                (user["id"], scope),
            ).fetchall()
        return [
            {
                "id": str(r[0]),
                "name": r[1],
                "permissions": r[2],
                **{
                    k: v.isoformat() if v else None
                    for k, v in zip(
                        ("created_at", "expires_at", "revoked_at", "last_used_at"), r[3:]
                    )
                },
            }
            for r in rows
        ]

    def create(self, session, scope, body):
        if body.keys() != {"name", "permissions", "expires_in_days", "current_password"}:
            raise AuthError("invalid_fields", 400)
        name, permissions, days = body["name"], body["permissions"], body["expires_in_days"]
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 80
            or not name.isprintable()
            or not isinstance(permissions, list)
            or not 1 <= len(permissions) <= len(PERMISSIONS)
            or any(not isinstance(p, str) or p not in PERMISSIONS for p in permissions)
            or len(set(permissions)) != len(permissions)
            or type(days) is not int
            or not 1 <= days <= 90
        ):
            raise AuthError("invalid_personal_token", 400)
        with connection(self.accounts.dsn) as conn:
            user = self.accounts.authenticate(conn, session)
        self.accounts.rate_limit("personal-token", user["id"])
        with self.accounts.workspace(session, scope) as (conn, user):
            row = conn.execute(
                "SELECT password_hash,password_version FROM users WHERE id=%s FOR UPDATE",
                (user["id"],),
            ).fetchone()
            if not verify_password(body["current_password"], row[0]):
                raise AuthError("invalid_credentials")
            role = conn.execute(
                "SELECT role FROM workspace_memberships WHERE scope_id=%s AND user_id=%s",
                (scope, user["id"]),
            ).fetchone()[0]
            if not set(permissions) <= ROLE_PERMISSIONS[role]:
                raise AuthError("insufficient_scope", 403)
            count = conn.execute(
                """SELECT count(*) FROM personal_access_tokens WHERE user_id=%s
                AND revoked_at IS NULL AND expires_at>now()""",
                (user["id"],),
            ).fetchone()[0]
            if count >= 20:
                raise AuthError("personal_token_limit", 409)
            identifier, secret = uuid.uuid4(), secrets.token_urlsafe(32)
            expires = conn.execute(
                """INSERT INTO personal_access_tokens
                (id,user_id,scope_id,name,secret_hash,permissions,password_version,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,now()+%s*interval '1 day') RETURNING expires_at""",
                (
                    identifier,
                    user["id"],
                    scope,
                    name.strip(),
                    hashlib.sha256(secret.encode()).digest(),
                    sorted(permissions),
                    row[1],
                    days,
                ),
            ).fetchone()[0]
            audit(conn, user["id"], "personal_token.created", scope=scope, target=identifier)
        return {
            "id": str(identifier),
            "token": f"alojan_pat_{identifier.hex}_{secret}",
            "expires_at": expires.isoformat(),
        }

    def revoke(self, session, scope, identifier):
        with self.accounts.workspace(session, scope) as (conn, user):
            row = conn.execute(
                """UPDATE personal_access_tokens SET revoked_at=COALESCE(revoked_at,now())
                WHERE id=%s AND user_id=%s AND scope_id=%s RETURNING id""",
                (identifier, user["id"], scope),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            audit(conn, user["id"], "personal_token.revoked", scope=scope, target=identifier)
        return {"status": "revoked"}


def request_budget(dsn, user):
    """Bound token and account traffic independently of browser login limits."""
    allowed = True
    with connection(dsn) as conn:
        for identity, maximum in (
            ("token:" + user["personal_token_id"], 240),
            ("user:" + user["id"], 480),
        ):
            count = conn.execute(
                """INSERT INTO auth_rate_limits(key_hash,attempts,expires_at)
                VALUES (%s,1,now()+interval '1 minute') ON CONFLICT(key_hash) DO UPDATE SET
                attempts=CASE WHEN auth_rate_limits.expires_at<=now() THEN 1 ELSE auth_rate_limits.attempts+1 END,
                expires_at=CASE WHEN auth_rate_limits.expires_at<=now() THEN now()+interval '1 minute' ELSE auth_rate_limits.expires_at END
                RETURNING attempts""",
                (hashlib.sha256(("mcp:" + identity).encode()).digest(),),
            ).fetchone()[0]
            allowed = allowed and count <= maximum
    if not allowed:
        raise AuthError("try_again_later", 429)
