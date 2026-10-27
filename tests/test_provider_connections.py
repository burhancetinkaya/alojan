"""Scoped credential storage, client isolation and revocation; no external API calls."""

import asyncio
from dataclasses import replace
import json
import time
import uuid

from cryptography.fernet import Fernet
import httpx
import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import create_app, COOKIE
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.connections import Connections
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_contracts.configuration import AgentDraft
from alojan_contracts.secrets import SecretBox
from alojan_agent.backend import Backend
from alojan_agent.credentials import ProviderClients
from test_agent_runtime import configured
from test_agent_drafts import content
from test_native_auth import register, ORIGIN
from test_agent_releases import qualify, prepare_assets
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated


def secret(n=1):
    return f"synthetic-provider-private-token-{n}"


def body(n=1):
    return dict(provider="openrouter", label=f"Synthetic {n}", api_key=secret(n))


def owner(accounts, name="first.owner"):
    token = register(accounts, name)
    return token, accounts.session(token)["workspaces"][0]["id"]


def test_envelopes_bind_identity_and_never_accept_tampering():
    box = SecretBox(Fernet.generate_key())
    scope, reference = str(uuid.uuid4()), str(uuid.uuid4())
    encrypted = box.seal(scope, reference, secret())
    assert secret().encode() not in encrypted
    assert box.open(scope, reference, encrypted) == secret()
    for s, r, value in (
        (str(uuid.uuid4()), reference, encrypted),
        (scope, str(uuid.uuid4()), encrypted),
        (scope, reference, encrypted[:-10]),
    ):
        with pytest.raises(ValueError, match="unavailable"):
            box.open(s, r, value)
    with pytest.raises(ValueError):
        SecretBox(Fernet.generate_key()).open(scope, reference, encrypted)


def test_write_only_api_owner_authorization_and_scoped_draft_reference(accounts, dedicated):
    one, two = owner(accounts), owner(accounts, "second.owner")
    restricted = Accounts(dedicated("management"))
    box = SecretBox(Fernet.generate_key())
    app = create_app(restricted, ORIGIN, secrets=box)
    with TestClient(app, base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, one[0])
        url = f"/v1/workspaces/{one[1]}/provider-connections"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(one[0])}
        assert client.post(url, json=body()).status_code == 403
        result = client.post(url, json=body(), headers=headers)
        assert result.status_code == 201, result.text
        reference = result.json()["id"]
        assert "api_key" not in result.text and secret() not in result.text
        listed = client.get(url)
        assert listed.status_code == 200 and "ciphertext" not in listed.text
        assert secret() not in listed.text
        assert client.get(f"/v1/workspaces/{two[1]}/provider-connections").status_code == 404
        Profiles(restricted).create(*one, content() | {"model_connection": reference})
        with pytest.raises(AuthError, match="provider_connection_unavailable"):
            Profiles(restricted).create(*two, content() | {"model_connection": reference})
        with connection(accounts.dsn) as c:
            c.execute("UPDATE workspace_memberships SET role='editor' WHERE scope_id=%s", (one[1],))
        assert client.post(url, json=body(2), headers=headers).status_code == 403
        assert (
            client.post(url + f"/{reference}/revoke", json={}, headers=headers).status_code == 403
        )
        with connection(accounts.dsn) as c:
            c.execute("UPDATE workspace_memberships SET role='owner' WHERE scope_id=%s", (one[1],))
        assert (
            client.post(url + f"/{reference}/revoke", json={}, headers=headers).status_code == 200
        )
        with pytest.raises(AuthError, match="provider_connection_unavailable"):
            Profiles(restricted).create(*one, content() | {"model_connection": reference})
    with connection(accounts.dsn) as c:
        ciphertext = bytes(c.execute("SELECT ciphertext FROM provider_connections").fetchone()[0])
        assert box.open(one[1], reference, ciphertext) == secret()
        assert secret() not in str(c.execute("SELECT * FROM management_audit").fetchall())
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE provider_connections SET enabled=true")
    for purpose in ("management", "routing", "records", "summaries", "readiness"):
        with (
            connection(dedicated(purpose)) as c,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            c.execute("SELECT ciphertext FROM provider_connections")
    with connection(dedicated("credentials")) as c:
        assert c.execute("SELECT count(*) FROM provider_connections").fetchone() == (0,)
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (one[1],))
        assert c.execute("SELECT count(*) FROM provider_connections").fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM users")


def test_publication_and_rollback_recheck_revocation_and_historical_digest(accounts, tmp_path):
    qualify(accounts)
    token, scope = owner(accounts)
    connections = Connections(accounts, SecretBox(Fernet.generate_key()))
    reference = connections.create(token, scope, body())["id"]
    author = (
        token,
        scope,
        Profiles(accounts).create(token, scope, content() | {"model_connection": reference})["id"],
    )
    prep, _, _ = prepare_assets(accounts, author, tmp_path)
    release = Releases(accounts).publish(*author, prep["id"], 0)["id"]
    connections.revoke(token, scope, reference)
    with pytest.raises(AuthError, match="provider_connection_unavailable"):
        Releases(accounts).rollback(*author, release, 1)
    with connection(accounts.dsn) as c:
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
        assert manifest["content"]["model_connection"] == reference
        assert secret() not in json.dumps(manifest)
    legacy = AgentDraft.model_validate(content())
    assert "model_connection" not in legacy.model_dump()


def test_clients_keep_workspace_keys_isolated_and_fail_closed_without_turn_io(
    accounts, dedicated, monkeypatch
):
    box = SecretBox(Fernet.generate_key())
    one, two = owner(accounts), owner(accounts, "second.owner")
    connections = Connections(accounts, box)
    refs = [connections.create(*o, body(i))["id"] for i, o in enumerate((one, two), 1)]
    runtimes = [
        replace(configured(), scope_id=o[1], model_connection=ref)
        for o, ref in zip((one, two), refs)
    ]

    async def run():
        clients = ProviderClients(dedicated("credentials"), box)
        backend = Backend(credentials=clients)
        try:
            for runtime in runtimes:
                await backend.prepare_runtime(runtime)
            # Refresh must not briefly invalidate a still-fresh key while its IO is pending.
            original_connect = psycopg.AsyncConnection.connect
            entered, proceed = asyncio.Event(), asyncio.Event()

            async def delayed(*args, **kwargs):
                entered.set()
                await proceed.wait()
                return await original_connect(*args, **kwargs)

            with monkeypatch.context() as patch:
                patch.setattr(psycopg.AsyncConnection, "connect", staticmethod(delayed))
                refreshing = asyncio.create_task(backend.prepare_runtime(runtimes[0]))
                await asyncio.wait_for(entered.wait(), 1)
                backend.check_runtime(runtimes[0])
                proceed.set()
                await refreshing
            seen = []

            async def handler(request):
                seen.append(request.headers["authorization"])
                return httpx.Response(200, json={"object": "list", "data": []})

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
                # SDK requests verify actual per-client Authorization, without provider traffic.
                for runtime in runtimes:
                    client = clients.get(runtime).with_options(http_client=transport)
                    await client.models.list()
            assert seen == ["Bearer " + secret(1), "Bearer " + secret(2)]
            clients.dsn = "invalid: no IO permitted while selecting a model"
            backend.model_for(runtimes[0])
            with pytest.raises(ValueError):
                backend.model_for(replace(runtimes[0], scope_id=two[1]))
            with pytest.raises(ValueError):
                backend.model_for(configured())
            clients.expires[clients.key(runtimes[0])] = time.monotonic() - 1
            with pytest.raises(ValueError, match="expired"):
                backend.model_for(runtimes[0])
            clients.dsn = dedicated("credentials")
            await backend.prepare_runtime(runtimes[0])
            connections.revoke(*one, refs[0])
            with pytest.raises(ValueError, match="unavailable"):
                await backend.prepare_runtime(runtimes[0])
            with pytest.raises(ValueError, match="expired"):
                backend.model_for(runtimes[0])
            await backend.prepare_runtime(runtimes[1])
            backend.check_runtime(runtimes[1])
        finally:
            await backend.close()
        assert clients.closed and not clients.clients

    asyncio.run(run())
