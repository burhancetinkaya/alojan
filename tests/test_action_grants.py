"""Explicit scoped action consent, immutable publication and runtime acceptance."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import uuid

from cryptography.fernet import Fernet
import psycopg
from psycopg.types.json import Jsonb
import pytest
from starlette.testclient import TestClient

from alojan.api import create_app, COOKIE
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.action_grants import ActionGrants
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.telegram_connections import TelegramConnections
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.routing import validated_release
from alojan_contracts.runtime import compile_release
from alojan_contracts.secrets import SecretBox
from alojan_agent.prepared import PreparedReleases
from test_agent_drafts import content
from test_agent_releases import qualify, prepare_assets
from test_provider_connections import owner
from test_telegram_connections import body
from test_native_auth import ORIGIN
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated


def action(reference, **changes):
    return (
        dict(
            alias="handover",
            connection_id=reference,
            fields=["agent_name", "summary_status", "summary.subject"],
        )
        | changes
    )


def setup(accounts, who=None):
    who = who or owner(accounts)
    reference = TelegramConnections(accounts, SecretBox(Fernet.generate_key())).create(
        *who, body()
    )["id"]
    config = content() | {"post_call_actions": [action(reference)]}
    agent = Profiles(accounts).create(*who, config)["id"]
    return (*who, agent), config, reference


def consent(accounts, author):
    grants = ActionGrants(accounts)
    review = grants.review(*author)
    return grants.authorize(*author, {k: review[k] for k in ("draft_version", "review_digest")})


def test_action_schema_rejects_undeclared_data_and_preserves_old_digests():
    reference = str(uuid.uuid4())
    old = validate_draft(content())
    assert old.model_dump() == validate_draft(content() | {"post_call_actions": []}).model_dump()
    assert "post_call_actions" not in old.model_dump()
    for change in (
        {"fields": ["transcript"]},
        {"fields": ["secrets.bot_token"]},
        {"fields": []},
        {"fields": ["call_id", "call_id"]},
        {"fields": ["caller_number"]},
        {"fields": ["summary.subject"]},
        {"adapter": "http_request.v1"},
        {"event": "model.requested"},
        {"condition": "any"},
        {"on_missing": "guess"},
        {"connection_id": "bad"},
        {"url": "https://example.test"},
        {"grant": True},
    ):
        with pytest.raises(AuthError, match="invalid_agent_configuration"):
            validate_draft(content() | {"post_call_actions": [action(reference, **change)]})
    for actions in ([action(reference)] * 2, [action(reference, alias=f"a{i}") for i in range(5)]):
        with pytest.raises(AuthError):
            validate_draft(content() | {"post_call_actions": actions})


def test_scoped_api_requires_exact_review_owner_and_csrf(accounts, dedicated):
    author, config, reference = setup(accounts)
    foreign, _, foreign_ref = setup(accounts, owner(accounts, "other.owner"))
    restricted = Accounts(dedicated("management"))
    with TestClient(create_app(restricted, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, author[0])
        base = f"/v1/workspaces/{author[1]}/agents/{author[2]}"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(author[0])}
        preview = client.get(base + "/action-review")
        assert preview.status_code == 200, preview.text
        review = preview.json()
        target = review["review"]["actions"][0]
        assert target["chat_id"] == body()["chat_id"] and target["connection_id"] == reference
        assert target["fields"] == config["post_call_actions"][0]["fields"]
        assert review["delivery_available"] and body()["bot_token"] not in preview.text
        request = {k: review[k] for k in ("draft_version", "review_digest")}
        assert client.post(base + "/action-grants", json=request).status_code == 403
        for role in ("viewer", "editor"):
            with connection(accounts.dsn) as c:
                c.execute(
                    "UPDATE workspace_memberships SET role=%s WHERE scope_id=%s", (role, author[1])
                )
            assert client.get(base + "/action-review").status_code == 200
            assert (
                client.post(base + "/action-grants", json=request, headers=headers).status_code
                == 403
            )
        with connection(accounts.dsn) as c:
            c.execute(
                "UPDATE workspace_memberships SET role='owner' WHERE scope_id=%s", (author[1],)
            )
        assert (
            client.post(
                base + "/action-grants", json=request | {"draft_version": True}, headers=headers
            ).status_code
            == 400
        )
        assert (
            client.post(
                base + "/action-grants", json=request | {"review_digest": "0" * 64}, headers=headers
            ).status_code
            == 409
        )
        response = client.post(base + "/action-grants", json=request, headers=headers)
        assert response.status_code == 201, response.text
        grant = response.json()["id"]
        assert client.get(base + "/action-grants").json()["grants"][0]["id"] == grant
        other_agent = Profiles(restricted).create(*author[:2], config)["id"]
        with pytest.raises(AuthError, match="stale_action_review"):
            ActionGrants(restricted).authorize(*author[:2], other_agent, request)
        assert (
            client.get(f"/v1/workspaces/{foreign[1]}/agents/{foreign[2]}/action-review").status_code
            == 404
        )
        with pytest.raises(AuthError, match="telegram_connection_unavailable"):
            Profiles(restricted).update(
                *author, config | {"post_call_actions": [action(foreign_ref)]}, 1
            )
        Profiles(restricted).update(*author, config | {"instructions": "Changed instructions"}, 1)
        assert (
            client.post(base + "/action-grants", json=request, headers=headers).status_code == 412
        )
        for _ in range(2):
            assert (
                client.post(
                    base + f"/action-grants/{grant}/revoke", json={}, headers=headers
                ).status_code
                == 200
            )
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        assert body()["bot_token"] not in str(
            c.execute("SELECT * FROM management_audit").fetchall()
        )


def test_publication_pins_authority_and_rollback_cannot_resurrect_revocation(
    accounts, dedicated, tmp_path
):
    qualify(accounts)
    author, config, reference = setup(accounts)
    restricted = Accounts(dedicated("management"))
    releases = Releases(restricted)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    with pytest.raises(AuthError, match="action_grant_required"):
        releases.publish(*author, preparation["id"], 0)
    with connection(accounts.dsn) as c:
        assert c.execute("SELECT count(*) FROM agent_releases").fetchone() == (0,)
        assert c.execute("SELECT count(*) FROM assistant_profile_revisions").fetchone() == (0,)
    first_grant = consent(restricted, author)
    first = releases.publish(*author, preparation["id"], 0)
    assert first["deployment_status"] == "requires_delivery_worker"
    with connection(accounts.dsn) as c:
        original = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (first["id"],)
        ).fetchone()[0]
    assert original["schema_version"] == 2
    assert original["action_grant"]["id"] == first_grant["id"]
    assert original["action_grant"]["review"]["profile_id"] == author[2]
    assert body()["bot_token"] not in json.dumps(original)
    changed = config | {"post_call_actions": [action(reference, fields=["call_id"])]}
    Profiles(restricted).update(*author, changed, 1)
    newer, _, _ = prepare_assets(accounts, author, tmp_path, 2)
    with pytest.raises(AuthError, match="action_grant_required"):
        releases.publish(*author, newer["id"], 1)
    # Current drafts do not retarget a historical release or require its new fields.
    second = releases.rollback(*author, first["id"], 1)
    with connection(accounts.dsn) as c:
        assert (
            c.execute(
                "SELECT manifest FROM agent_releases WHERE id=%s", (second["id"],)
            ).fetchone()[0]
            == original
        )
    ActionGrants(restricted).revoke(*author, first_grant["id"])
    with pytest.raises(AuthError, match="action_grant_required"):
        releases.rollback(*author, first["id"], 2)
    Profiles(restricted).update(*author, config, 2)
    replacement = consent(restricted, author)
    assert replacement["id"] != first_grant["id"]
    with pytest.raises(AuthError, match="action_grant_required"):
        releases.rollback(*author, first["id"], 2)
    newest, _, _ = prepare_assets(accounts, author, tmp_path, 3)
    third = releases.publish(*author, newest["id"], 2)
    with connection(accounts.dsn) as c:
        assert (
            str(
                c.execute(
                    "SELECT action_grant_id FROM agent_releases WHERE id=%s", (third["id"],)
                ).fetchone()[0]
            )
            == replacement["id"]
        )
    TelegramConnections(restricted).revoke(*author[:2], reference)
    with pytest.raises(AuthError, match="telegram_connection_unavailable"):
        releases.rollback(*author, third["id"], 3)


def test_reviewed_action_release_compiles_and_preloads_only_for_its_workspace(accounts, tmp_path):
    qualify(accounts)
    author, _, _ = setup(accounts)
    consent(accounts, author)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    release = Releases(accounts).publish(*author, preparation["id"], 0)
    with connection(accounts.dsn) as c:
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release["id"],)
        ).fetchone()[0]
    encoded = validated_release(manifest, release["digest"])
    assert compile_release(encoded, release["digest"], scope_id=author[1]).scope_id == author[1]
    for scope in (None, str(uuid.uuid4())):
        with pytest.raises(ValueError, match="exact workspace"):
            compile_release(encoded, release["digest"], scope_id=scope)

    async def load():
        cache = PreparedReleases(tmp_path / "store")
        entry = await cache.preload(author[1], release["id"], encoded, release["digest"])
        assert entry.runtime.scope_id == author[1]
        assert entry.greeting_pcm and entry.unavailable_pcm
        await cache.close()

    asyncio.run(load())
    tampered = copy.deepcopy(manifest)
    tampered["action_grant"]["review"]["actions"][0]["fields"] = ["call_id"]
    with pytest.raises(ValueError, match="differs"):
        validated_release(tampered, canonical_digest(tampered))
    for altered in (
        manifest | {"schema_version": 1},
        {k: v for k, v in manifest.items() if k != "action_grant"},
    ):
        with pytest.raises(ValueError):
            validated_release(altered, canonical_digest(altered))


def test_grants_are_idempotent_immutable_and_invisible_to_other_workspaces(accounts, dedicated):
    author, config, _ = setup(accounts)
    restricted = Accounts(dedicated("management"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        grants = list(pool.map(lambda _: consent(restricted, author), range(2)))
    assert grants[0]["id"] == grants[1]["id"]
    reference = grants[0]["id"]
    with connection(accounts.dsn) as c:
        assert c.execute(
            "SELECT count(*) FROM management_audit WHERE event='action.authorized'"
        ).fetchone() == (1,)
        review = c.execute("SELECT review FROM action_grants WHERE id=%s", (reference,)).fetchone()[
            0
        ]
    with connection(restricted.dsn) as c:
        assert c.execute("SELECT count(*) FROM action_grants").fetchone() == (0,)
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (author[1],))
        assert c.execute("SELECT count(*) FROM action_grants").fetchone() == (1,)
    for assignment in (
        "review_digest=repeat('0',64)",
        "granted_by=gen_random_uuid()",
        "review='{}'::jsonb",
    ):
        with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
            c.execute(f"UPDATE action_grants SET {assignment} WHERE id=%s", (reference,))
    foreign, _, _ = setup(accounts, owner(accounts, "foreign.owner"))
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.ForeignKeyViolation):
        c.execute(
            "INSERT INTO action_grants(id,scope_id,profile_id,review,review_digest,granted_by) SELECT %s,%s,%s,%s,%s,granted_by FROM action_grants WHERE id=%s",
            (
                uuid.uuid4(),
                author[1],
                foreign[2],
                Jsonb(review | {"profile_id": foreign[2]}),
                "1" * 64,
                reference,
            ),
        )
    for purpose in ("routing", "records", "summaries", "readiness", "credentials"):
        with (
            connection(dedicated(purpose)) as c,
            pytest.raises(psycopg.errors.InsufficientPrivilege),
        ):
            c.execute("UPDATE action_grants SET enabled=false")
    ActionGrants(restricted).revoke(*author, reference)
    with connection(accounts.dsn) as c, pytest.raises(psycopg.errors.CheckViolation):
        c.execute("UPDATE action_grants SET enabled=true WHERE id=%s", (reference,))


@pytest.mark.parametrize("state", ["disabled", "demoted"])
def test_grant_issuer_must_remain_an_enabled_owner(accounts, dedicated, tmp_path, state):
    qualify(accounts)
    author, _, _ = setup(accounts)
    consent(accounts, author)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    other = owner(accounts, "replacement.owner")
    with connection(accounts.dsn) as c:
        issuer = c.execute(
            "SELECT user_id FROM workspace_memberships WHERE scope_id=%s", (author[1],)
        ).fetchone()[0]
        c.execute(
            "INSERT INTO workspace_memberships(scope_id,user_id,role) SELECT %s,user_id,'owner' FROM workspace_memberships WHERE scope_id=%s",
            (author[1], other[1]),
        )
        if state == "disabled":
            c.execute("UPDATE users SET enabled=false WHERE id=%s", (issuer,))
        else:
            c.execute(
                "UPDATE workspace_memberships SET role='editor' WHERE scope_id=%s AND user_id=%s",
                (author[1], issuer),
            )
    with pytest.raises(AuthError, match="action_grant_required"):
        Releases(Accounts(dedicated("management"))).publish(
            other[0], author[1], author[2], preparation["id"], 0
        )


def test_revoked_grants_count_toward_limit_and_readiness_requires_schema(accounts, dedicated):
    author, _, _ = setup(accounts)
    grant = consent(accounts, author)
    restricted = Accounts(dedicated("management"))
    ActionGrants(restricted).revoke(*author, grant["id"])
    with connection(accounts.dsn) as c:
        c.execute(
            """INSERT INTO action_grants(id,scope_id,profile_id,review,review_digest,granted_by,enabled)
            SELECT gen_random_uuid(),scope_id,profile_id,review,review_digest,granted_by,false
            FROM action_grants CROSS JOIN generate_series(1,999) WHERE id=%s""",
            (grant["id"],),
        )
    with pytest.raises(AuthError, match="action_grant_limit"):
        consent(restricted, author)
    assert len(ActionGrants(restricted).list(*author)) == 1000
    assert restricted.ready()
    with connection(accounts.dsn) as c:
        c.execute(
            "UPDATE schema_migrations SET name='held-0013' WHERE name='0013_action_grants.sql'"
        )
    assert not restricted.ready()
