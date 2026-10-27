"""Native accounts and bounded password work; never used by the voice process."""

import hashlib
import hmac
import re
import secrets
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

import psycopg

_management_transaction = ContextVar("management_transaction", default=None)

SCRYPT_N = 1 << 17
SCRYPT_R = 8
SCRYPT_P = 1
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}")
LOGIN_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{2,63}")
EMAIL_RE = re.compile(
    r"[a-z0-9]+([._+-][a-z0-9]+)*@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)


class AuthError(Exception):
    def __init__(self, code, status=401):
        self.code, self.status = code, status
        super().__init__(code)


def login_name(value):
    if not isinstance(value, str) or not value.isascii() or len(value) > 254:
        raise AuthError("invalid_login", 400)
    value = value.lower()
    if not LOGIN_RE.fullmatch(value) and not (
        len(value.split("@", 1)[0]) <= 64 and EMAIL_RE.fullmatch(value)
    ):
        raise AuthError("invalid_login", 400)
    return value


def display_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100 or not value.isprintable():
        raise AuthError("invalid_display_name", 400)
    return value.strip()


def password_bytes(value, *, new=False):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise AuthError("invalid_password", 400)
    try:
        data = value.encode("utf-8")
    except UnicodeEncodeError:
        raise AuthError("invalid_password", 400) from None
    if len(data) > 512 or (new and len(value) < 8):
        raise AuthError("password_requires_8_to_128_characters", 400)
    return data


def derive(password, salt):
    # OWASP scrypt profile; two concurrent operations fit the API's isolated budget.
    return hashlib.scrypt(
        password,
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=192 * 1024 * 1024,
        dklen=64,
    )


def hash_password(password):
    data = password_bytes(password, new=True)
    salt = secrets.token_bytes(16)
    return f"scrypt${SCRYPT_N}$8$1${salt.hex()}${derive(data, salt).hex()}"


def verify_password(password, encoded):
    data = password_bytes(password)
    salt, expected, valid = bytes(16), bytes(64), False
    if isinstance(encoded, str):
        parts = encoded.split("$")
        if len(parts) == 6 and parts[:4] == ["scrypt", str(SCRYPT_N), "8", "1"]:
            try:
                candidate_salt, candidate_hash = bytes.fromhex(parts[4]), bytes.fromhex(parts[5])
                if len(candidate_salt) == 16 and len(candidate_hash) == 64:
                    salt, expected, valid = candidate_salt, candidate_hash, True
            except ValueError:
                pass
    actual = derive(data, salt)
    return hmac.compare_digest(actual, expected) and valid


def token_hash(token):
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        raise AuthError("authentication_required")
    return hashlib.sha256(token.encode("ascii")).digest()


def csrf_token(token):
    token_hash(token)
    return hmac.new(token.encode("ascii"), b"alojan-csrf-v1", hashlib.sha256).hexdigest()


@contextmanager
def connection(dsn):
    active = _management_transaction.get()
    if active is not None and active[0] == dsn:
        yield active[1]
        return
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        conn.execute("SET LOCAL statement_timeout=3000")
        yield conn


def audit(conn, actor, event, *, scope=None, target=None):
    conn.execute(
        "INSERT INTO management_audit(actor_id,scope_id,event,target_id,personal_token_id) "
        "VALUES (%s,%s,%s,%s,NULLIF(current_setting('alojan.personal_token_id',true),'')::uuid)",
        (actor, scope, event, target),
    )


class Accounts:
    def __init__(self, dsn):
        self.dsn = dsn

    def ready(self):
        try:
            with connection(self.dsn) as conn:
                return (
                    conn.execute(
                        """SELECT count(*) FROM schema_migrations WHERE name IN
                    ('0004_native_auth.sql','0005_agent_drafts.sql','0006_agent_releases.sql','0007_email_login.sql','0008_number_routing.sql',
                     '0011_provider_connections.sql','0012_telegram_connections.sql','0013_action_grants.sql','0014_action_delivery.sql','0015_action_retries.sql','0016_voice_preparation_jobs.sql','0017_call_history.sql','0018_call_transcript.sql','0019_call_latency.sql','0020_mcp_discovery.sql','0021_mcp_tool_grants.sql','0022_mcp_execution.sql','0025_call_lifecycle_actions.sql','0026_publication_node.sql','0027_personal_access_tokens.sql','0028_management_operations.sql','0029_management_connection_setups.sql')"""
                    ).fetchone()[0]
                    == 22
                )
        except psycopg.Error:
            return False

    def cleanup(self):
        with connection(self.dsn) as conn:
            for table in ("auth_sessions", "auth_rate_limits", "workspace_invitations"):
                conn.execute(
                    psycopg.sql.SQL(
                        "DELETE FROM {table} WHERE ctid IN (SELECT ctid FROM {table} "
                        "WHERE expires_at<=now() ORDER BY expires_at LIMIT 1000)"
                    ).format(table=psycopg.sql.Identifier(table))
                )

    def rate_limit(self, operation, peer, login=""):
        keys = [(f"{operation}:peer:{peer}", 30 if operation == "login" else 5)]
        if login:
            keys.append((f"{operation}:login:{login}", 10))
        allowed = True
        with connection(self.dsn) as conn:
            for key, limit in keys:
                count = conn.execute(
                    """INSERT INTO auth_rate_limits(key_hash,attempts,expires_at)
                    VALUES (%s,1,now()+interval '5 minutes') ON CONFLICT(key_hash)
                    DO UPDATE SET
                        attempts=CASE WHEN auth_rate_limits.expires_at <= now()
                            THEN 1 ELSE auth_rate_limits.attempts+1 END,
                        expires_at=CASE WHEN auth_rate_limits.expires_at <= now()
                            THEN now()+interval '5 minutes' ELSE auth_rate_limits.expires_at END
                    RETURNING attempts""",
                    (hashlib.sha256(key.encode()).digest(),),
                ).fetchone()[0]
                allowed = allowed and count <= limit
                if not allowed:
                    break
        if not allowed:
            raise AuthError("try_again_later", 429)

    def _new_session(self, conn, user_id, version):
        token = secrets.token_urlsafe(32)
        # Bound retained sessions without relying on a separate cleanup worker.
        conn.execute(
            """DELETE FROM auth_sessions WHERE token_hash IN (
                SELECT token_hash FROM auth_sessions WHERE user_id=%s
                ORDER BY created_at DESC OFFSET 9)""",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO auth_sessions(token_hash,user_id,password_version) VALUES (%s,%s,%s)",
            (token_hash(token), user_id, version),
        )
        return token

    def register(self, login, password, name, *, peer):
        self.rate_limit("register", peer)
        login, name = login_name(login), display_name(name)
        encoded = hash_password(password)
        user_id, scope_id = uuid.uuid4(), uuid.uuid4()
        try:
            with connection(self.dsn) as conn:
                conn.execute(
                    "INSERT INTO users(id,login,display_name,password_hash) VALUES (%s,%s,%s,%s)",
                    (user_id, login, name, encoded),
                )
                conn.execute(
                    "INSERT INTO recipient_scopes(id,display_name,enabled) VALUES (%s,%s,true)",
                    (scope_id, name),
                )
                conn.execute(
                    "INSERT INTO workspace_memberships(scope_id,user_id,role) VALUES (%s,%s,'owner')",
                    (scope_id, user_id),
                )
                token = self._new_session(conn, user_id, 1)
                audit(conn, user_id, "account.registered", scope=scope_id)
        except psycopg.errors.UniqueViolation:
            raise AuthError("login_unavailable", 409) from None
        return token

    def login(self, login, password, *, peer):
        login = login_name(login)
        self.rate_limit("login", peer, login)
        with connection(self.dsn) as conn:
            row = conn.execute(
                "SELECT id,password_hash,password_version,enabled FROM users WHERE login=%s",
                (login,),
            ).fetchone()
        if not verify_password(password, row[1] if row else None) or not row or not row[3]:
            raise AuthError("invalid_credentials")
        with connection(self.dsn) as conn:
            current = conn.execute(
                """SELECT id FROM users WHERE id=%s AND enabled AND password_version=%s
                AND password_hash=%s FOR UPDATE""",
                (row[0], row[2], row[1]),
            ).fetchone()
            if not current:
                raise AuthError("invalid_credentials")
            token = self._new_session(conn, row[0], row[2])
            audit(conn, row[0], "session.created")
        return token

    def authenticate(self, conn, token):
        from alojan.personal_tokens import BearerCredential, authenticate

        if isinstance(token, BearerCredential):
            return authenticate(conn, token)
        row = conn.execute(
            """UPDATE auth_sessions s SET last_seen_at=now() FROM users u
            WHERE s.token_hash=%s AND u.id=s.user_id AND u.enabled
                AND s.password_version=u.password_version AND s.expires_at>now()
                AND s.last_seen_at>now()-interval '30 minutes'
            RETURNING u.id,u.login,u.display_name""",
            (token_hash(token),),
        ).fetchone()
        if not row:
            raise AuthError("authentication_required")
        return {"id": str(row[0]), "login": row[1], "display_name": row[2]}

    def session(self, token):
        with connection(self.dsn) as conn:
            user = self.authenticate(conn, token)
            scopes = conn.execute(
                """SELECT r.id,r.display_name,m.role FROM workspace_memberships m
                JOIN recipient_scopes r ON r.id=m.scope_id
                WHERE m.user_id=%s AND r.enabled ORDER BY r.created_at,r.id""",
                (user["id"],),
            ).fetchall()
        return {
            "user": user,
            "csrf_token": csrf_token(token),
            "workspaces": [{"id": str(row[0]), "name": row[1], "role": row[2]} for row in scopes],
        }

    @contextmanager
    def workspace(self, token, scope_id, *, roles=("owner", "editor", "viewer")):
        try:
            scope_id = uuid.UUID(str(scope_id))
        except ValueError:
            raise AuthError("not_found", 404) from None
        with connection(self.dsn) as conn:
            user = self.authenticate(conn, token)
            member = conn.execute(
                """SELECT m.role FROM workspace_memberships m
                JOIN recipient_scopes r ON r.id=m.scope_id
                WHERE m.scope_id=%s AND m.user_id=%s AND r.enabled FOR SHARE OF m,r""",
                (scope_id, user["id"]),
            ).fetchone()
            if not member:
                raise AuthError("not_found", 404)
            if member[0] not in roles:
                raise AuthError("forbidden", 403)
            conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope_id),))
            yield conn, user

    def logout(self, token):
        with connection(self.dsn) as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash=%s", (token_hash(token),))

    def change_password(self, token, current_password, new_password, *, peer):
        self.rate_limit("password", peer)
        with connection(self.dsn) as conn:
            user = self.authenticate(conn, token)
            row = conn.execute(
                "SELECT password_hash,password_version FROM users WHERE id=%s",
                (user["id"],),
            ).fetchone()
        if not verify_password(current_password, row[0]):
            raise AuthError("invalid_credentials")
        encoded = hash_password(new_password)
        with connection(self.dsn) as conn:
            # Lock the user before session deletion, as login does before session creation.
            updated = conn.execute(
                """UPDATE users SET password_hash=%s,password_version=password_version+1
                WHERE id=%s AND enabled AND password_version=%s RETURNING id""",
                (encoded, user["id"], row[1]),
            ).fetchone()
            if not updated:
                raise AuthError("authentication_required")
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (user["id"],))
            audit(conn, user["id"], "password.changed")

    def reset_password(self, login, new_password):
        """Operator-only recovery; intentionally unavailable over HTTP."""
        encoded = hash_password(new_password)
        with connection(self.dsn) as conn:
            row = conn.execute(
                """UPDATE users SET password_hash=%s,password_version=password_version+1
                WHERE login=%s RETURNING id""",
                (encoded, login_name(login)),
            ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            conn.execute("DELETE FROM auth_sessions WHERE user_id=%s", (row[0],))
            audit(conn, None, "password.operator_reset", target=row[0])
