"""Human credential handoff is scoped, expiring and cannot outlive its delegation."""

import uuid

from cryptography.fernet import Fernet
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, connection, csrf_token
from alojan_contracts.secrets import SecretBox
from test_native_auth import ORIGIN, register
from test_personal_tokens import setup
import test_number_routing as fixtures

accounts, database, dedicated = fixtures.accounts, fixtures.database, fixtures.dedicated
CONFIG = dict(
    label="Synthetic protected hook",
    endpoint="https://hooks.example.test/calls",
    auth_type="bearer",
)
SECRET = "synthetic-credential-never-sent-over-network"


def begin(client, scope, token):
    result = client.post(
        f"/v1/workspaces/{scope}/connection-setups",
        json=dict(kind="http", configuration=CONFIG),
        headers={"Authorization": "Bearer " + token, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_same_user_secret_handoff_is_atomic_and_not_disclosed(accounts, dedicated):
    session, scope, created = setup(accounts, ["connections:write", "connections:read"])
    other = register(accounts, "other.setup.owner")
    with connection(accounts.dsn) as conn:
        conn.execute(
            "INSERT INTO workspace_memberships(scope_id,user_id,role) VALUES(%s,%s,'owner')",
            (scope, accounts.session(other)["user"]["id"]),
        )
    box = SecretBox(Fernet.generate_key())
    with TestClient(
        create_app(Accounts(dedicated("management")), ORIGIN, secrets=box), base_url=ORIGIN
    ) as client:
        started = begin(client, scope, created["token"])
        path = f"/v1/workspaces/{scope}/connection-setups/{started['id']}"
        assert started["setup_url"] == f"{ORIGIN}/baglanti-kur/{scope}/{started['id']}"
        client.cookies.set(COOKIE, other)
        assert client.get(path).status_code == 404
        assert (
            client.post(
                path + "/complete",
                json={"secret": SECRET},
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token(other)},
            ).status_code
            == 404
        )
        client.cookies.set(COOKIE, session)
        assert client.post(path + "/complete", json={"secret": SECRET}).status_code == 403
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(session)}
        first = client.post(path + "/complete", json={"secret": SECRET}, headers=headers)
        assert first.status_code == 200, first.text
        repeated = client.post(path + "/complete", json={"secret": SECRET}, headers=headers)
        assert repeated.json() == first.json()
        client.cookies.clear()
        headers = {"Authorization": "Bearer " + created["token"]}
        status = client.get(path, headers=headers)
        assert status.json()["status"] == "complete" and SECRET not in status.text
        assert (
            client.post(path + "/complete", json={"secret": SECRET}, headers=headers).status_code
            == 403
        )
    with connection(accounts.dsn) as conn:
        rows = conn.execute("SELECT id,ciphertext FROM http_connections").fetchall()
        assert len(rows) == 1 and SECRET.encode() not in bytes(rows[0][1])
        assert box.open(scope, rows[0][0], rows[0][1], purpose="http") == SECRET
        assert SECRET not in str(
            conn.execute("SELECT configuration FROM management_connection_setups").fetchall()
        )


@pytest.mark.parametrize("change,code", [("expiry", 409), ("revoked", 403), ("password", 403)])
def test_handoff_rechecks_expiry_and_original_token(accounts, change, code):
    session, scope, created = setup(accounts, ["connections:write"])
    with TestClient(
        create_app(accounts, ORIGIN, secrets=SecretBox(Fernet.generate_key())), base_url=ORIGIN
    ) as client:
        started = begin(client, scope, created["token"])
        with connection(accounts.dsn) as conn:
            if change == "expiry":
                conn.execute(
                    "UPDATE management_connection_setups SET expires_at=now()-interval '1 second'"
                )
            elif change == "revoked":
                conn.execute("UPDATE personal_access_tokens SET revoked_at=now()")
            else:
                # Revoke the originating token without invalidating the browser session fixture.
                conn.execute(
                    "UPDATE personal_access_tokens SET password_version=password_version+1"
                )
        client.cookies.set(COOKIE, session)
        result = client.post(
            f"/v1/workspaces/{scope}/connection-setups/{started['id']}/complete",
            json={"secret": SECRET},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token(session)},
        )
        assert result.status_code == code, result.text
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM http_connections").fetchone()[0] == 0
