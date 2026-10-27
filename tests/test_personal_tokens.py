"""Personal management credentials use real isolated PostgreSQL and HTTP boundaries."""

import uuid

import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import AuthError, connection, csrf_token
from alojan.personal_tokens import BearerCredential, PersonalTokens
from test_native_auth import ORIGIN, PASSWORD, register
import test_native_auth

accounts, database = test_native_auth.accounts, test_native_auth.database


def setup(accounts, permissions=None):
    session = register(accounts)
    scope = accounts.session(session)["workspaces"][0]["id"]
    result = PersonalTokens(accounts).create(
        session,
        scope,
        {
            "name": "Synthetic Codex",
            "permissions": permissions or ["agents:read"],
            "expires_in_days": 30,
            "current_password": PASSWORD,
        },
    )
    return session, scope, result


def test_token_secret_never_returned_again_and_revocation(accounts):
    session, scope, result = setup(accounts)
    rows = PersonalTokens(accounts).list(session, scope)
    assert len(rows) == 1 and rows[0]["id"] == result["id"]
    assert "token" not in rows[0] and "secret_hash" not in rows[0]
    credential = BearerCredential(result["token"], scope, frozenset({"agents:read"}))
    assert result["token"] not in repr(credential)
    with accounts.workspace(credential, scope) as (_, user):
        assert user["personal_token_id"] == result["id"]
    PersonalTokens(accounts).revoke(session, scope, result["id"])
    with pytest.raises(AuthError, match="authentication_required"):
        with accounts.workspace(credential, scope):
            pytest.fail("Revoked token accepted")


def test_bearer_permissions_and_workspace_are_enforced_by_api(accounts):
    session, scope, result = setup(accounts)
    other = register(accounts, "other.owner")
    other_scope = accounts.session(other)["workspaces"][0]["id"]
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        headers = {"Authorization": "Bearer " + result["token"]}
        assert client.get("/v1/mcp/context", headers=headers).json()["scope_id"] == scope
        assert client.get(f"/v1/workspaces/{scope}/agents", headers=headers).status_code == 200
        assert (
            client.get(f"/v1/workspaces/{other_scope}/agents", headers=headers).status_code == 404
        )
        assert (
            client.post(f"/v1/workspaces/{scope}/agents", headers=headers, json={}).status_code
            == 403
        )
        assert client.get(f"/v1/workspaces/{scope}/calls", headers=headers).status_code == 403
        assert (
            client.get(f"/v1/workspaces/{scope}/personal-tokens", headers=headers).status_code
            == 403
        )
        assert client.post("/v1/auth/logout", headers=headers, json={}).status_code == 403
        assert (
            client.get(
                "/v1/mcp/context", headers={**headers, "Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.get("/v1/mcp/context").status_code == 401
        client.cookies.set(COOKIE, session)
        assert client.get("/v1/mcp/context", headers=headers).status_code == 400


@pytest.mark.parametrize("change", ["expiry", "disabled", "membership", "password", "downgrade"])
def test_token_rechecks_live_authority(accounts, change):
    _, scope, result = setup(accounts, ["releases:publish"])
    with connection(accounts.dsn) as conn:
        if change == "expiry":
            conn.execute(
                "UPDATE personal_access_tokens SET created_at=now()-interval '2 days', expires_at=now()-interval '1 day'"
            )
        elif change == "disabled":
            conn.execute("UPDATE users SET enabled=false")
        elif change == "membership":
            conn.execute("DELETE FROM workspace_memberships")
        elif change == "password":
            conn.execute("UPDATE users SET password_version=password_version+1")
        else:
            conn.execute("UPDATE workspace_memberships SET role='viewer'")
    with pytest.raises(AuthError):
        with accounts.workspace(
            BearerCredential(result["token"], scope, frozenset({"releases:publish"})), scope
        ):
            pytest.fail("Stale authority accepted")


def test_issuance_requires_password_csrf_and_current_role(accounts):
    session = register(accounts)
    scope = accounts.session(session)["workspaces"][0]["id"]
    body = {
        "name": "test",
        "permissions": ["agents:read"],
        "expires_in_days": 1,
        "current_password": PASSWORD,
    }
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, session)
        path = f"/v1/workspaces/{scope}/personal-tokens"
        assert client.post(path, json=body).status_code == 403
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(session)}
        assert (
            client.post(
                path, headers=headers, json={**body, "current_password": "wrong"}
            ).status_code
            == 401
        )
        assert (
            client.post(path, headers=headers, json={**body, "expires_in_days": 91}).status_code
            == 400
        )
        assert (
            client.post(path, headers=headers, json={**body, "permissions": ["admin"]}).status_code
            == 400
        )
        assert client.post(path, headers=headers, json=body).status_code == 201
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE workspace_memberships SET role='viewer'")
    with pytest.raises(AuthError, match="insufficient_scope"):
        PersonalTokens(accounts).create(
            session, scope, {**body, "permissions": ["releases:publish"]}
        )


def test_other_user_cannot_revoke_even_in_shared_workspace(accounts):
    session, scope, result = setup(accounts)
    other = register(accounts, "other.owner")
    other_id = accounts.session(other)["user"]["id"]
    with connection(accounts.dsn) as conn:
        conn.execute(
            "INSERT INTO workspace_memberships(scope_id,user_id,role) VALUES (%s,%s,'owner')",
            (scope, other_id),
        )
    assert PersonalTokens(accounts).list(other, scope) == []
    with pytest.raises(AuthError, match="not_found"):
        PersonalTokens(accounts).revoke(other, scope, result["id"])
    with pytest.raises(AuthError):
        with accounts.workspace(
            BearerCredential(result["token"][:-1] + "!", scope, frozenset()), scope
        ):
            pytest.fail("Invalid secret accepted")
    with pytest.raises(AuthError):
        with accounts.workspace(
            BearerCredential(result["token"], str(uuid.uuid4()), frozenset()), scope
        ):
            pytest.fail("Wrong workspace accepted")


def test_active_token_stays_visible_after_many_revoked_tokens(accounts):
    session, scope, result = setup(accounts)
    with connection(accounts.dsn) as conn:
        for _ in range(101):
            conn.execute(
                """INSERT INTO personal_access_tokens(id,user_id,scope_id,name,secret_hash,permissions,password_version,created_at,expires_at,revoked_at)
                SELECT %s,user_id,scope_id,'Revoked synthetic',secret_hash,permissions,password_version,now(),now()+interval '1 day',now()
                FROM personal_access_tokens WHERE id=%s""",
                (uuid.uuid4(), result["id"]),
            )
    rows = PersonalTokens(accounts).list(session, scope)
    assert len(rows) == 100 and rows[0]["id"] == result["id"]
