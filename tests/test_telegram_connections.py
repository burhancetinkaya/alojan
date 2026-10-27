"""Telegram destination authoring only: real RLS/roles, synthetic tokens, no delivery."""

from concurrent.futures import ThreadPoolExecutor
import json
import uuid

from cryptography.fernet import Fernet
import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import create_app, COOKIE
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.roles import grant_credentials
from alojan.telegram_connections import TelegramConnections
from alojan_contracts.secrets import SecretBox
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated


def body():
    return dict(
        label="Synthetic destination",
        chat_id="-1001234567890",
        bot_token="123456789:synthetic_private_bot_token_for_tests",
    )


def test_credential_purpose_is_bound_and_existing_provider_envelopes_still_work():
    box = SecretBox(Fernet.generate_key())
    scope, reference = str(uuid.uuid4()), str(uuid.uuid4())
    key = body()["bot_token"]
    legacy = box.cipher.encrypt(json.dumps([[scope, reference, "openrouter"], key]).encode())
    assert box.open(scope, reference, legacy) == key
    telegram = box.seal(scope, reference, key, purpose="telegram")
    assert box.open(scope, reference, telegram, purpose="telegram") == key
    for s, r, value, purpose in (
        (scope, reference, legacy, "telegram"),
        (scope, reference, telegram, "openrouter"),
        (str(uuid.uuid4()), reference, telegram, "telegram"),
        (scope, str(uuid.uuid4()), telegram, "telegram"),
        (scope, reference, telegram[:-10], "telegram"),
    ):
        with pytest.raises(ValueError, match="unavailable"):
            box.open(s, r, value, purpose=purpose)
    with pytest.raises(ValueError, match="purpose"):
        box.seal(scope, reference, key, purpose="arbitrary")


def test_owner_api_and_rls_keep_targets_and_tokens_separate(accounts, dedicated):
    one, two = owner(accounts), owner(accounts, "second.owner")
    box = SecretBox(Fernet.generate_key())
    dsn = dedicated("management")
    restricted = Accounts(dsn)
    app = create_app(restricted, ORIGIN, secrets=box)
    other = TelegramConnections(restricted, box).create(*two, body() | {"chat_id": "12345"})
    with TestClient(app, base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, one[0])
        url = f"/v1/workspaces/{one[1]}/telegram-connections"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(one[0])}
        assert client.post(url, json=body()).status_code == 403
        response = client.post(url, json=body(), headers=headers)
        assert response.status_code == 201, response.text
        reference = response.json()["id"]
        assert set(response.json()) == {"id", "label", "chat_id", "enabled"}
        assert body()["bot_token"] not in response.text
        assert client.get(url).json() == {"connections": [response.json()]}
        assert client.get(f"/v1/workspaces/{two[1]}/telegram-connections").status_code == 404
        assert (
            client.post(url + f"/{other['id']}/revoke", json={}, headers=headers).status_code == 404
        )
        for role in ("editor", "viewer"):
            with connection(accounts.dsn) as c:
                c.execute(
                    "UPDATE workspace_memberships SET role=%s WHERE scope_id=%s", (role, one[1])
                )
            assert client.get(url).status_code == 200
            assert client.post(url, json=body(), headers=headers).status_code == 403
            assert (
                client.post(url + f"/{reference}/revoke", json={}, headers=headers).status_code
                == 403
            )
        with connection(accounts.dsn) as c:
            c.execute("UPDATE workspace_memberships SET role='owner' WHERE scope_id=%s", (one[1],))
        for _ in range(2):
            assert (
                client.post(url + f"/{reference}/revoke", json={}, headers=headers).status_code
                == 200
            )
        assert client.get(url).json()["connections"][0]["enabled"] is False
    with connection(accounts.dsn) as c:
        ciphertext = bytes(
            c.execute(
                "SELECT ciphertext FROM telegram_connections WHERE id=%s", (reference,)
            ).fetchone()[0]
        )
        assert box.open(one[1], reference, ciphertext, purpose="telegram") == body()["bot_token"]
        assert body()["bot_token"] not in str(
            c.execute("SELECT * FROM management_audit").fetchall()
        )
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM provider_connections").fetchone() == (0,)
    with connection(dsn) as c:
        assert c.execute("SELECT count(*) FROM telegram_connections").fetchone() == (0,)
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (one[1],))
        assert c.execute("SELECT id FROM telegram_connections").fetchall() == [
            (uuid.UUID(reference),)
        ]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("DELETE FROM telegram_connections")
    for purpose in ("management", "routing", "records", "summaries", "readiness", "credentials"):
        with (
            connection(dedicated(purpose)) as c,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            c.execute("SELECT ciphertext FROM telegram_connections")
    # A previously overprivileged provider reader must also be rejected on reprovisioning.
    reader = dedicated("credentials")
    with connection(reader) as c:
        role = c.execute("SELECT current_user").fetchone()[0]
    with connection(accounts.dsn) as c:
        c.execute(
            psycopg.sql.SQL("GRANT SELECT(ciphertext) ON telegram_connections TO {}").format(
                psycopg.sql.Identifier(role)
            )
        )
    with pytest.raises(ValueError, match="Telegram"):
        grant_credentials(accounts.dsn, role)


def test_invalid_destinations_and_missing_key_fail_without_storage(accounts):
    who = owner(accounts)
    store = TelegramConnections(accounts, SecretBox(Fernet.generate_key()))
    invalid = [
        {"chat_id": value}
        for value in (
            "@mutable_name",
            "0",
            "-0",
            "01",
            "+1",
            " 123",
            123,
            True,
            "1\n",
            "4503599627370496",
            "https://example.test",
        )
    ] + [
        {"bot_token": value}
        for value in (None, True, "short", "123:has whitespace", "123:" + "x" * 129)
    ]
    invalid += [
        {"label": "\n"},
        {"label": " "},
        {"label": "x" * 81},
        {"url": "https://example.test"},
    ]
    for change in invalid:
        with pytest.raises(AuthError, match="invalid_telegram_connection"):
            store.create(*who, body() | change)
    with pytest.raises(AuthError, match="credential_storage_unavailable"):
        TelegramConnections(accounts).create(*who, body())
    assert store.list(*who) == []


def test_destinations_cannot_be_retargeted_or_reenabled_even_by_database_writer(accounts):
    who = owner(accounts)
    store = TelegramConnections(accounts, SecretBox(Fernet.generate_key()))
    reference = store.create(*who, body())["id"]
    for assignment in (
        "chat_id='12345'",
        "label='Changed'",
        "ciphertext=repeat('x',64)::bytea",
        "id=gen_random_uuid()",
        "created_at=created_at+interval '1 second'",
    ):
        with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute(f"UPDATE telegram_connections SET {assignment} WHERE id=%s", (reference,))
    store.revoke(*who, reference)
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute("UPDATE telegram_connections SET enabled=true WHERE id=%s", (reference,))


def test_connection_limit_serializes_concurrent_creation_and_counts_revoked(accounts):
    who = owner(accounts)
    box = SecretBox(Fernet.generate_key())
    store = TelegramConnections(accounts, box)
    rows = []
    for _ in range(99):
        reference = uuid.uuid4()
        rows.append(
            (
                reference,
                who[1],
                box.seal(who[1], reference, body()["bot_token"], purpose="telegram"),
            )
        )
    with connection(accounts.dsn) as c:
        c.cursor().executemany(
            "INSERT INTO telegram_connections(id,scope_id,label,chat_id,ciphertext,enabled) VALUES (%s,%s,'Synthetic','12345',%s,false)",
            rows,
        )

    def create():
        try:
            return store.create(*who, body())["enabled"]
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert results.count(True) == 1 and results.count("connection_limit") == 1
    assert len(store.list(*who)) == 100


def test_management_readiness_requires_both_credential_migrations(accounts, dedicated):
    restricted = Accounts(dedicated("management"))
    assert restricted.ready()
    for name in ("0011_provider_connections.sql", "0012_telegram_connections.sql"):
        with connection(accounts.dsn) as c:
            c.execute("UPDATE schema_migrations SET name=%s WHERE name=%s", ("held-" + name, name))
        assert not restricted.ready()
        with connection(accounts.dsn) as c:
            c.execute("UPDATE schema_migrations SET name=%s WHERE name=%s", (name, "held-" + name))
        assert restricted.ready()
