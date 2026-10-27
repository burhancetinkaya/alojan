import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import create_app
from alojan.auth import AuthError, connection
from alojan.profiles import Profiles, validate_draft
import test_native_auth
from test_native_auth import ORIGIN, PASSWORD, register

accounts = test_native_auth.accounts
database = test_native_auth.database


def content(agent="Example Assistant", owner="Example Owner"):
    return {
        "agent_name": agent,
        "owner_display_name": owner,
        "owner_address": owner,
        "owner_dative": owner,
        "owner_genitive": owner,
        "instructions": "Collect messages for the represented person.",
    }


def test_existing_live_instructions_survive_profile_storage_and_compilation(accounts):
    from alojan_agent.legacy import INSTRUCTIONS
    from alojan_contracts.configuration import EnginePreset
    from alojan_contracts.runtime import compile_agent

    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    profiles = Profiles(accounts)
    body = content("Kübra", "Burhan") | {"instructions": INSTRUCTIONS}
    created = profiles.create(token, scope, body)
    stored = profiles.get(token, scope, created["id"])["content"]
    assert len(INSTRUCTIONS) > 6000 and stored["instructions"] == INSTRUCTIONS
    runtime = compile_agent(validate_draft(stored), EnginePreset())
    assert json.dumps(INSTRUCTIONS, ensure_ascii=False) in runtime.instructions
    assert len(runtime.instructions.encode()) <= 32768


def test_long_business_instructions_do_not_expand_compiled_prompt_budget():
    from alojan_contracts.configuration import EnginePreset
    from alojan_contracts.runtime import compile_agent

    assert len(validate_draft(content() | {"instructions": "x" * 20000}).instructions) == 20000
    with pytest.raises(AuthError, match="invalid_agent_configuration"):
        validate_draft(content() | {"instructions": "x" * 20001})
    draft = validate_draft(content() | {"instructions": "ç" * 16000})
    with pytest.raises(ValueError, match="bounded prompt budget"):
        compile_agent(draft, EnginePreset())


def test_business_fields_and_template_expansion_are_bounded():
    draft = validate_draft(content())
    assert "yapay zekâ" in draft.greeting()
    assert "Example Assistant" in draft.greeting()
    assert "Example Owner" in draft.render(draft.note_ack_template)
    assert "Burhan" not in draft.greeting() and "Kübra" not in draft.greeting()
    assert draft.digest() == validate_draft(draft.model_dump()).digest()
    assert draft.digest() != validate_draft(content(agent="Changed Assistant")).digest()
    invalid = [
        {"temperature": 1},
        {"max_call_seconds": 999},
        {"voice": "unapproved"},
        {"owner_display_name": " space "},
        {"agent_name": "\ud800"},
        {"instructions": "   "},
        {"vocabulary": ["word", "word"]},
        {"asr_replacements": {"Example Product": "1234 Number"}},
        {"asr_replacements": {"Evet": "Example Brand"}},
        {
            "asr_replacements": {
                "Example Product": "Example Brand",
                "EXAMPLE PRODUCT": "Other Brand",
            }
        },
        {"note_ack_template": "{owner_address.__class__}"},
        {"note_ack_template": "{owner_address!r}"},
        {"note_ack_template": "{owner_address:100000000}"},
        {"tools": [{"tool": "shell"}]},
        {"tools": [{"tool": "take_note", "alias": "respond"}]},
        {"tools": [{"tool": "take_note", "guidance": "\ud800"}]},
    ]
    for change in invalid:
        with pytest.raises(AuthError, match="invalid_agent_configuration"):
            validate_draft({**content(), **change})
    assert validate_draft({**content(), "tools": []}).tools == []


def test_registered_owner_can_create_edit_and_preview_only_own_agents(accounts):
    one, two = register(accounts), register(accounts, "other.owner")
    scope1 = accounts.session(one)["workspaces"][0]["id"]
    scope2 = accounts.session(two)["workspaces"][0]["id"]
    profiles = Profiles(accounts)
    agent1 = profiles.create(one, scope1, content())
    agent2 = profiles.create(two, scope2, content("Second Assistant", "Second Owner"))
    assert [p["id"] for p in profiles.list(one, scope1)] == [agent1["id"]]
    with pytest.raises(AuthError, match="not_found"):
        profiles.get(one, scope1, agent2["id"])
    with pytest.raises(AuthError, match="not_found"):
        profiles.create(one, scope2, content())
    with pytest.raises(AuthError, match="not_found"):
        profiles.update(one, scope1, agent2["id"], content(), 1)
    updated = profiles.update(one, scope1, agent1["id"], content("New Assistant"), 1)
    assert updated["version"] == 2
    assert profiles.preview(one, scope1, agent1["id"])["greeting"].startswith(
        "Merhaba, ben New Assistant."
    )
    assert not profiles.preview(one, scope1, agent1["id"])["can_receive_calls"]
    assert profiles.get(two, scope2, agent2["id"])["version"] == 1


def test_concurrent_draft_changes_require_latest_version(accounts):
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    profiles = Profiles(accounts)
    agent = profiles.create(token, scope, content())

    def update(name):
        try:
            return profiles.update(token, scope, agent["id"], content(name), 1)["version"]
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["First edit", "Second edit"]))
    assert sorted(map(str, results)) == ["2", "stale_version"]


def test_viewer_cannot_create_or_edit(accounts):
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    profiles = Profiles(accounts)
    agent = profiles.create(token, scope, content())
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE workspace_memberships SET role='viewer'")
    assert profiles.get(token, scope, agent["id"])["id"] == agent["id"]
    with pytest.raises(AuthError, match="forbidden"):
        profiles.create(token, scope, content())
    with pytest.raises(AuthError, match="forbidden"):
        profiles.update(token, scope, agent["id"], content(), 1)


def test_rls_under_non_owner_role_and_transaction_context_reset(accounts):
    tokens = [register(accounts, name) for name in ("first.owner", "other.owner")]
    scopes = [accounts.session(token)["workspaces"][0]["id"] for token in tokens]
    profiles = Profiles(accounts)
    for token, scope in zip(tokens, scopes):
        profiles.create(token, scope, content())
    role = psycopg.sql.Identifier("test_agp_" + uuid.uuid4().hex)
    with connection(accounts.dsn) as conn:
        schema = psycopg.sql.Identifier(conn.execute("SELECT current_schema()").fetchone()[0])
        conn.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
        conn.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, role))
        conn.execute(psycopg.sql.SQL("GRANT SELECT, UPDATE ON agent_drafts TO {}").format(role))
    try:
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("SET LOCAL ROLE {}").format(role))
            assert conn.execute("SELECT count(*) FROM agent_drafts").fetchone()[0] == 0
            conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (scopes[0],))
            assert conn.execute("SELECT count(*) FROM agent_drafts").fetchone()[0] == 1
            assert (
                conn.execute(
                    "UPDATE agent_drafts SET version=2 WHERE scope_id=%s", (scopes[1],)
                ).rowcount
                == 0
            )
            with conn.transaction():
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute("UPDATE agent_drafts SET scope_id=%s", (scopes[1],))
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("SET LOCAL ROLE {}").format(role))
            assert conn.execute("SELECT count(*) FROM agent_drafts").fetchone()[0] == 0
    finally:
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("DROP OWNED BY {}").format(role))
            conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(role))


def test_http_agent_authoring_schema_and_version_contract(accounts):
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        response = client.post(
            "/v1/auth/register",
            json={
                "login": "web.author",
                "password": PASSWORD,
                "display_name": "Synthetic Author",
            },
            headers={"Origin": ORIGIN},
        )
        assert response.status_code == 201
        scope = response.json()["workspaces"][0]["id"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}
        url = f"/v1/workspaces/{scope}/agents"
        response = client.post(url, json=content(), headers=headers)
        assert response.status_code == 201
        assert response.headers["etag"] == '"1"'
        agent = response.json()["id"]
        assert client.put(f"{url}/{agent}", json=content(), headers=headers).status_code == 428
        response = client.put(
            f"{url}/{agent}", json=content("Renamed"), headers={**headers, "If-Match": '"1"'}
        )
        assert response.status_code == 200 and response.headers["etag"] == '"2"'
        assert (
            client.put(
                f"{url}/{agent}", json=content(), headers={**headers, "If-Match": '"1"'}
            ).status_code
            == 412
        )
        assert client.get(url).json()["agents"][0]["name"] == "Renamed"
        assert (
            "Renamed"
            in client.post(f"{url}/{agent}/preview", json={}, headers=headers).json()["greeting"]
        )
        schema = client.get(f"/v1/workspaces/{scope}/agent-schema").json()
        assert "instructions" in schema["properties"] and "temperature" not in schema["properties"]
