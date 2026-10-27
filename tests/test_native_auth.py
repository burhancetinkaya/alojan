import hashlib
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from starlette.testclient import TestClient

import test_database
from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, hash_password, verify_password
from alojan.migrate import migrate

database = test_database.database
PASSWORD = "synthetic password for tests"
ORIGIN = "https://alojan.example.test"


@pytest.fixture
def accounts(database):
    migrate(database)
    return Accounts(database)


def register(accounts, login="test.owner", peer="127.0.0.1"):
    return accounts.register(login, PASSWORD, "Synthetic Owner", peer=peer)


def test_password_hash_uses_unique_salt_and_handles_corrupt_records():
    one, two = hash_password(PASSWORD), hash_password(PASSWORD)
    assert one != two
    assert verify_password(PASSWORD, one)
    assert not verify_password("incorrect password", one)
    assert not verify_password(PASSWORD, None)
    assert not verify_password(PASSWORD, "scrypt$131072$8$1$xx$yy")
    assert not verify_password(PASSWORD, one.replace("131072", "999999999"))
    for value in ("x" * 7, "x" * 129, "\ud800" * 15):
        with pytest.raises(AuthError):
            hash_password(value)


@pytest.mark.parametrize("size", [8, 128])
def test_password_length_boundaries_are_accepted(size):
    password = "x" * size
    assert verify_password(password, hash_password(password))


def test_registration_enforces_eight_character_minimum(accounts):
    with pytest.raises(AuthError, match="password_requires_8_to_128_characters"):
        accounts.register("short.owner", "Seven7!", "Synthetic Owner", peer="127.0.0.1")
    token = accounts.register("short.owner", "Eight88!", "Synthetic Owner", peer="127.0.0.1")
    assert accounts.session(token)["user"]["login"] == "short.owner"


def test_anyone_can_register_with_independent_owner_workspace(accounts):
    first, second = register(accounts), register(accounts, "other.owner")
    first_session, second_session = accounts.session(first), accounts.session(second)
    first_scope = first_session["workspaces"][0]["id"]
    second_scope = second_session["workspaces"][0]["id"]
    assert first_scope != second_scope
    assert first_session["workspaces"][0]["role"] == "owner"
    assert len(first_session["workspaces"]) == 1
    with accounts.workspace(first, first_scope, roles=("owner",)) as (conn, user):
        assert (
            conn.execute("SELECT current_setting('alojan.scope_id')").fetchone()[0] == first_scope
        )
        assert user["id"] == first_session["user"]["id"]
    with pytest.raises(AuthError, match="not_found"):
        with accounts.workspace(first, second_scope):
            pytest.fail("Cross-workspace membership accepted")
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT current_setting('alojan.scope_id',true)").fetchone()[0] is None
        hashes = conn.execute("SELECT token_hash FROM auth_sessions").fetchall()
        assert {bytes(row[0]) for row in hashes} == {
            hashlib.sha256(first.encode()).digest(),
            hashlib.sha256(second.encode()).digest(),
        }
        assert conn.execute("SELECT count(*) FROM assistant_profiles").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0


def test_duplicate_registration_is_atomic_and_case_insensitive(accounts):
    register(accounts)
    with pytest.raises(AuthError, match="login_unavailable"):
        register(accounts, "TEST.OWNER")
    with connection(accounts.dsn) as conn:
        for table in ("users", "recipient_scopes", "workspace_memberships", "auth_sessions"):
            assert (
                conn.execute(
                    psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                        psycopg.sql.Identifier(table),
                    )
                ).fetchone()[0]
                == 1
            )


def test_login_rotation_logout_and_disabled_account(accounts):
    first = register(accounts)
    second = accounts.login("TEST.OWNER", PASSWORD, peer="127.0.0.1")
    assert first != second
    accounts.logout(first)
    with pytest.raises(AuthError, match="authentication_required"):
        accounts.session(first)
    assert accounts.session(second)["user"]["login"] == "test.owner"
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE users SET enabled=false")
    with pytest.raises(AuthError, match="authentication_required"):
        accounts.session(second)
    with pytest.raises(AuthError, match="invalid_credentials"):
        accounts.login("test.owner", PASSWORD, peer="127.0.0.1")


@pytest.mark.parametrize(
    "expiry", ["expires_at=now()-interval '1 second'", "last_seen_at=now()-interval '31 minutes'"]
)
def test_session_expiry_is_server_enforced(accounts, expiry):
    token = register(accounts)
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE auth_sessions SET " + expiry)
    with pytest.raises(AuthError, match="authentication_required"):
        accounts.session(token)


def test_revocation_and_role_downgrade_take_effect_on_next_operation(accounts):
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE workspace_memberships SET role='viewer'")
    with pytest.raises(AuthError, match="forbidden"):
        with accounts.workspace(token, scope, roles=("owner", "editor")):
            pytest.fail("Viewer write accepted")
    with connection(accounts.dsn) as conn:
        conn.execute("DELETE FROM workspace_memberships")
    with pytest.raises(AuthError, match="not_found"):
        with accounts.workspace(token, scope):
            pytest.fail("Revoked membership accepted")


def test_password_change_and_recovery_revoke_all_sessions(accounts):
    one = register(accounts)
    two = accounts.login("test.owner", PASSWORD, peer="127.0.0.1")
    accounts.change_password(one, PASSWORD, "Change8!", peer="127.0.0.1")
    for token in (one, two):
        with pytest.raises(AuthError):
            accounts.session(token)
    with pytest.raises(AuthError, match="invalid_credentials"):
        accounts.login("test.owner", PASSWORD, peer="127.0.0.1")
    fresh = accounts.login("test.owner", "Change8!", peer="127.0.0.1")
    accounts.reset_password("test.owner", "Reset88!")
    with pytest.raises(AuthError):
        accounts.session(fresh)
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 0
        assert (
            conn.execute(
                "SELECT count(*) FROM management_audit WHERE event='password.operator_reset'",
            ).fetchone()[0]
            == 1
        )


def test_rate_limits_commit_rejections_and_survive_new_instances(accounts):
    with ThreadPoolExecutor(max_workers=4) as pool:

        def attempt(_):
            try:
                accounts.rate_limit("register", "synthetic-peer")
                return True
            except AuthError as exc:
                assert exc.status == 429
                return False

        results = list(pool.map(attempt, range(12)))
    assert sum(results) == 5
    with pytest.raises(AuthError, match="try_again_later"):
        Accounts(accounts.dsn).rate_limit("register", "synthetic-peer")
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE auth_rate_limits SET expires_at=now()-interval '1 second'")
    accounts.rate_limit("register", "synthetic-peer")


def test_http_registration_cookie_csrf_and_cross_workspace(accounts):
    app = create_app(accounts, ORIGIN)
    with TestClient(app, base_url=ORIGIN) as client:
        data = {"login": "web.owner", "password": PASSWORD, "display_name": "Web Owner"}
        assert client.post("/v1/auth/register", json=data).status_code == 403
        response = client.post("/v1/auth/register", json=data, headers={"Origin": ORIGIN})
        assert response.status_code == 201
        cookie = response.headers["set-cookie"]
        assert all(flag in cookie for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"))
        assert "Domain=" not in cookie and COOKIE in cookie
        assert response.headers["cache-control"] == "no-store"
        assert "password" not in response.text
        session = response.json()
        scope = session["workspaces"][0]["id"]
        assert client.get(f"/v1/workspaces/{scope}").status_code == 200
        other_token = register(accounts, "second.owner", peer="another-peer")
        other_scope = accounts.session(other_token)["workspaces"][0]["id"]
        assert client.get(f"/v1/workspaces/{other_scope}").status_code == 404
        assert (
            client.post("/v1/auth/logout", json={}, headers={"Origin": ORIGIN}).status_code == 403
        )
        assert client.get("/v1/auth/session").status_code == 200
        assert (
            client.post(
                "/v1/auth/logout",
                json={},
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": session["csrf_token"],
                },
            ).status_code
            == 200
        )
        assert client.get("/v1/auth/session").status_code == 401


def test_http_boundaries_reject_untrusted_fields_and_large_bodies(accounts):
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        headers = {"Origin": ORIGIN}
        data = {"login": "web.owner", "password": PASSWORD, "display_name": "Web Owner"}
        assert (
            client.post(
                "/v1/auth/register", json={**data, "role": "admin"}, headers=headers
            ).status_code
            == 400
        )
        assert client.post("/v1/auth/register", content="x", headers=headers).status_code == 415
        assert (
            client.post("/v1/auth/register", json={"x": "x" * 65536}, headers=headers).status_code
            == 413
        )
        assert (
            client.post(
                "/v1/auth/register", json=data, headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.get("/v1/auth/register").status_code == 405
        assert client.get("/v1/auth/session?token=forged").status_code == 401


def test_cleanup_removes_only_expired_tokens_and_limits(accounts):
    token = register(accounts)
    accounts.rate_limit("login", "expiring-peer", "unused.login")
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE auth_rate_limits SET expires_at=now()-interval '1 second'")
    accounts.cleanup()
    assert accounts.session(token)["user"]["login"] == "test.owner"
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM auth_rate_limits").fetchone()[0] == 0
        conn.execute("UPDATE auth_sessions SET expires_at=now()-interval '1 second'")
    accounts.cleanup()
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 0


def test_http_readiness_requires_new_schema(accounts):
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        with connection(accounts.dsn) as conn:
            conn.execute("DELETE FROM schema_migrations WHERE name='0005_agent_drafts.sql'")
        assert client.get("/health/ready").status_code == 503


def test_forwarded_address_trusted_only_from_configured_proxy(accounts, monkeypatch):
    peers = []

    def capture(*args, peer):
        peers.append(peer)
        raise AuthError("captured", 429)

    monkeypatch.setattr(accounts, "register", capture)
    data = {"login": "test.owner", "password": PASSWORD, "display_name": "Test Owner"}
    for trusted, expected in [((), "127.0.0.1"), (("127.0.0.1",), "192.0.2.1")]:
        with TestClient(
            create_app(accounts, ORIGIN, trusted_proxy_ips=trusted),
            base_url=ORIGIN,
            client=("127.0.0.1", 50000),
        ) as client:
            assert (
                client.post(
                    "/v1/auth/register",
                    json=data,
                    headers={
                        "Origin": ORIGIN,
                        "CF-Connecting-IP": "192.0.2.1",
                    },
                ).status_code
                == 429
            )
            assert peers[-1] == expected
    with TestClient(
        create_app(accounts, ORIGIN, trusted_proxy_ips=("127.0.0.1",)),
        base_url=ORIGIN,
        client=("127.0.0.1", 50000),
    ) as client:
        assert (
            client.post(
                "/v1/auth/register",
                json=data,
                headers={
                    "Origin": ORIGIN,
                    "CF-Connecting-IP": "192.0.2.1, 192.0.2.2",
                },
            ).status_code
            == 400
        )


def test_email_login_is_case_insensitive_without_implicit_ownership(accounts):
    token = register(accounts, "Owner.Name+test@Example.test")
    session = accounts.session(token)
    assert session["user"]["login"] == "owner.name+test@example.test"
    with pytest.raises(AuthError, match="login_unavailable"):
        register(accounts, "OWNER.NAME+TEST@EXAMPLE.TEST")
    signed_in = accounts.login("owner.name+test@example.test", PASSWORD, peer="127.0.0.1")
    assert accounts.session(signed_in)["user"]["id"] == session["user"]["id"]
    assert accounts.session(signed_in)["workspaces"] == session["workspaces"]
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM assistant_profiles").fetchone()[0] == 0


def test_login_database_and_application_validation_agree(accounts):
    from alojan.auth import login_name

    candidates = [
        "legacy.owner",
        "owner@example.test",
        "x@y.co",
        "a..b",
        "a..b@example.test",
        "a.@example.test",
        "a@-host.test",
        "a@host-.test",
        "a@host",
        "a@@host.test",
        "a@host..test",
        "a@host.12",
        "a@höst.test",
        "a" * 65 + "@example.test",
        "a@" + "x" * 64 + ".test",
        " owner@example.test",
        "owner@example.test\n",
        "a@" + ".".join(["a" * 60] * 5) + ".test",
        "a\n",
        "ı@example.test",
    ]
    with connection(accounts.dsn) as conn:
        for value in candidates:
            try:
                login_name(value)
                valid = True
            except AuthError:
                valid = False
            assert conn.execute("SELECT valid_account_login(%s)", (value,)).fetchone()[0] == valid
