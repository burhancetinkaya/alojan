"""Reviewed MCP authoring/grants against restricted Linux DB roles; no network."""

import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from jsonschema.exceptions import SchemaError, ValidationError
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.mcp_connections import MCPConnections
from alojan.mcp_grants import MCPGrants, live_grant, review_tools
from alojan.mcp_review import approve, revoke
from alojan.mcp_roles import grant_discovery
from alojan.mcp_tools import MCPTools
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.roles import grant_management
from alojan_agent.mcp_discovery_worker import claim, complete
from alojan_contracts.configuration import EnginePreset, MCPToolConfig
from alojan_contracts.mcp import manifest
from alojan_contracts.mcp_tools import invocation_arguments, reviewed_schema, runtime_schema
from alojan_contracts.runtime import compile_agent
from test_agent_drafts import content
from test_agent_releases import qualify
from test_mcp_discovery import URL
from test_native_auth import ORIGIN
from test_provider_connections import owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
SCHEMA = {
    "type": "object",
    "properties": {
        "project": {"type": "integer", "minimum": 1},
        "query": {"type": "string", "maxLength": 100},
    },
    "required": ["project", "query"],
    "additionalProperties": False,
}
TOOL = {
    "name": "search",
    "description": "Synthetic read lookup",
    "inputSchema": SCHEMA,
    "outputSchema": {
        "type": "object",
        "properties": {"answer": {"type": "string", "maxLength": 100}},
        "required": ["answer"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}


def discovered(accounts, who, tool=TOOL):
    store = MCPConnections(accounts)
    ref = store.create(*who, dict(label="Synthetic", endpoint=URL, auth_type="none", token=None))[
        "id"
    ]
    rediscover(accounts, who, ref, [tool])
    return ref


def rediscover(accounts, who, ref, tools):
    MCPConnections(accounts).discover(*who, ref, request=True)
    complete(accounts.dsn, claim(accounts.dsn), manifest(tools), None)


def operator_review(accounts, scope, ref, tool=TOOL):
    return approve(
        accounts.dsn,
        scope,
        ref,
        manifest([tool])["tools"][0]["digest"],
        reviewer="synthetic-operator",
        evidence="Synthetic read implementation inspected",
    )


@pytest.fixture
def configured(accounts, dedicated):
    who = owner(accounts)
    ref = discovered(accounts, who)
    review = operator_review(accounts, who[1], ref)
    config = dict(
        connection_id=ref, review_id=review, alias="mcp_search", fixed_arguments={"project": 7}
    )
    restricted = Accounts(dedicated("management"))
    draft = content() | {"mcp_tools": [config]}
    profile = Profiles(restricted).create(*who, draft)["id"]
    return restricted, (*who, profile), draft


def consent(accounts, author):
    result = MCPGrants(accounts).review(*author)
    body = {k: result[k] for k in ("draft_version", "review_digest")}
    return MCPGrants(accounts).authorize(*author, body)


def current_grant(accounts, author, draft, reference=None):
    with accounts.workspace(*author[:2]) as (conn, _):
        review = review_tools(conn, author[1], author[2], validate_draft(draft))
        return live_grant(conn, author[1], author[2], review, reference=reference)


def test_fixed_values_removed_and_cannot_be_overridden_or_injected():
    exposed = runtime_schema(SCHEMA, {"project": 7})
    assert exposed["properties"] == {"query": SCHEMA["properties"]["query"]}
    assert exposed["required"] == ["query"] and exposed["additionalProperties"] is False
    assert SCHEMA["required"] == ["project", "query"]
    assert invocation_arguments(SCHEMA, {"project": 7}, {"query": "status"}) == {
        "project": 7,
        "query": "status",
    }
    for args in (
        {"project": 8, "query": "status"},
        {"query": "q", "token": "x"},
        {},
        {"query": "x" * 101},
        {"query": 9},
    ):
        with pytest.raises((ValueError, ValidationError)):
            invocation_arguments(SCHEMA, {"project": 7}, args)
    for fixed in ({"project": 0}, {"project": True}, {"project": "7"}, {"secret": "x"}):
        with pytest.raises((ValueError, ValidationError)):
            runtime_schema(SCHEMA, fixed)


@pytest.mark.parametrize(
    "schema",
    [
        SCHEMA | {"additionalProperties": True},
        SCHEMA | {"$ref": "#/x"},
        SCHEMA | {"allOf": []},
        SCHEMA | {"required": ["unknown"]},
        SCHEMA | {"properties": {"query": {"type": "string"}}},
        SCHEMA
        | {"properties": {"query": {"type": "string", "maxLength": 100, "pattern": "(a+)+$"}}},
        SCHEMA | {"properties": {"query": {"type": "array", "items": {"type": "integer"}}}},
    ],
)
def test_unbounded_recursive_or_executable_schema_features_rejected(schema):
    with pytest.raises((ValueError, SchemaError)):
        reviewed_schema(schema)


def test_root_constraints_cannot_disappear_when_fixed_parameters_are_removed():
    with pytest.raises(ValueError):
        runtime_schema(SCHEMA | {"enum": [{"project": 7, "query": "only"}]}, {"project": 7})


def test_nested_schema_and_argument_bounds():
    nested = {
        "type": "object",
        "properties": {"items": {"type": "array", "maxItems": 2, "items": SCHEMA}},
        "additionalProperties": False,
    }
    assert invocation_arguments(nested, {}, {"items": [{"project": 1, "query": "x"}]})
    with pytest.raises(ValidationError):
        invocation_arguments(nested, {}, {"items": [{"project": 1, "query": "x"}] * 3})
    for fixed in ({"value": "x" * 8193}, {"value": float("nan")}, {"value": "\x00"}):
        with pytest.raises(ValueError):
            MCPToolConfig.bounded_arguments(fixed)
    deep = {}
    for _ in range(10):
        deep = {"v": deep}
    with pytest.raises(ValueError):
        MCPToolConfig.bounded_arguments(deep)


def test_old_digests_and_aliases_are_preserved():
    old = validate_draft(content())
    assert "mcp_tools" not in old.model_dump()
    assert old.digest() == validate_draft(content() | {"mcp_tools": []}).digest()
    config = dict(connection_id=str(uuid.uuid4()), review_id=str(uuid.uuid4()), alias="mcp_search")
    for changes in ({"alias": "respond"}, {"review_id": "x"}, {"approved": True}):
        with pytest.raises(AuthError):
            validate_draft(content() | {"mcp_tools": [config | changes]})
    for configs in ([config, config], [config | {"alias": f"mcp_t{i}"} for i in range(9)]):
        with pytest.raises(AuthError):
            validate_draft(content() | {"mcp_tools": configs})
    with pytest.raises(AuthError):
        validate_draft(
            content()
            | {"tools": [{"tool": "take_note", "alias": "mcp_search"}], "mcp_tools": [config]}
        )


def test_unreviewed_annotation_is_not_capability_or_owner_consent(accounts, dedicated):
    who = owner(accounts)
    ref = discovered(accounts, who)
    restricted = Accounts(dedicated("management"))
    catalog = MCPTools(restricted).list(*who, ref)
    assert catalog["tools"][0]["review_id"] is None and not catalog["execution_available"]
    with pytest.raises(AuthError, match="mcp_tool_review_required"):
        Profiles(restricted).create(
            *who,
            content()
            | {
                "mcp_tools": [
                    dict(connection_id=ref, review_id=str(uuid.uuid4()), alias="mcp_search")
                ]
            },
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        operator_review(restricted, who[1], ref)
    review = operator_review(accounts, who[1], ref)
    assert operator_review(accounts, who[1], ref) == review
    assert MCPTools(restricted).list(*who, ref)["tools"][0]["review_id"] == review


def test_scoped_http_review_consent_and_revoke(configured, accounts):
    restricted, author, draft = configured
    stranger = owner(accounts, "other.mcp.owner")
    with TestClient(create_app(restricted, ORIGIN), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, author[0])
        base = f"/v1/workspaces/{author[1]}/agents/{author[2]}"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(author[0])}
        catalog = client.get(
            f"/v1/workspaces/{author[1]}/mcp-connections/{draft['mcp_tools'][0]['connection_id']}/tools"
        )
        assert catalog.status_code == 200
        assert catalog.json()["tools"][0]["review_id"] == draft["mcp_tools"][0]["review_id"]
        response = client.get(base + "/mcp-review")
        assert response.status_code == 200, response.text
        review = response.json()
        assert not review["execution_available"]
        selected = review["review"]["tools"][0]
        assert selected["fixed_arguments"] == {"project": 7} and selected["endpoint"] == URL
        assert "project" not in selected["runtime_schema"]["properties"]
        body = {k: review[k] for k in ("draft_version", "review_digest")}
        assert client.post(base + "/mcp-grants", json=body).status_code == 403
        for role in ("editor", "viewer"):
            with connection(accounts.dsn) as conn:
                conn.execute(
                    "UPDATE workspace_memberships SET role=%s WHERE scope_id=%s", (role, author[1])
                )
            assert client.get(base + "/mcp-review").status_code == 200
            assert client.post(base + "/mcp-grants", json=body, headers=headers).status_code == 403
        with connection(accounts.dsn) as conn:
            conn.execute(
                "UPDATE workspace_memberships SET role='owner' WHERE scope_id=%s", (author[1],)
            )
        assert (
            client.post(
                base + "/mcp-grants", json=body | {"draft_version": True}, headers=headers
            ).status_code
            == 400
        )
        assert (
            client.post(
                base + "/mcp-grants", json=body | {"review_digest": "0" * 64}, headers=headers
            ).status_code
            == 409
        )
        result = client.post(base + "/mcp-grants", json=body, headers=headers)
        assert result.status_code == 201, result.text
        grant = result.json()["id"]
        assert current_grant(restricted, author, draft)["id"] == grant
        assert client.get(base + "/mcp-grants").json()["grants"][0]["id"] == grant
        assert client.get(base + "/mcp-review?extra=1").status_code == 400
        client.cookies.set(COOKIE, stranger[0])
        assert client.get(base + "/mcp-review").status_code == 404
        client.cookies.set(COOKIE, author[0])
        for _ in range(2):
            assert (
                client.post(
                    base + f"/mcp-grants/{grant}/revoke", json={}, headers=headers
                ).status_code
                == 200
            )
        with pytest.raises(AuthError, match="mcp_grant_required"):
            current_grant(restricted, author, draft, grant)
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM agent_releases").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)


def test_grants_pin_parameters_agent_and_review_not_just_tool_name(configured, accounts):
    restricted, author, draft = configured
    old = MCPGrants(restricted).review(*author)
    granted = consent(restricted, author)
    changed = copy.deepcopy(draft)
    changed["mcp_tools"][0]["fixed_arguments"]["project"] = 8
    Profiles(restricted).update(*author, changed, 1)
    with pytest.raises(AuthError, match="stale_version"):
        MCPGrants(restricted).authorize(
            *author, {k: old[k] for k in ("draft_version", "review_digest")}
        )
    with pytest.raises(AuthError, match="mcp_grant_required"):
        current_grant(restricted, author, changed)
    assert current_grant(restricted, author, draft)["id"] == granted["id"]
    other = Profiles(restricted).create(*author[:2], draft)["id"]
    with pytest.raises(AuthError, match="mcp_grant_required"):
        current_grant(restricted, (*author[:2], other), draft)
    # Grant issuer must still be an enabled owner, even when another owner is active.
    with connection(accounts.dsn) as conn:
        conn.execute(
            "UPDATE workspace_memberships SET role='editor' WHERE scope_id=%s", (author[1],)
        )
    with pytest.raises(AuthError, match="mcp_grant_required"):
        current_grant(restricted, author, draft)


def test_parallel_authorization_is_idempotent_and_immutable(configured, accounts):
    restricted, author, draft = configured
    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(lambda _: consent(restricted, author)["id"], range(2)))
    assert refs[0] == refs[1]
    for table, reference in (
        ("mcp_tool_grants", refs[0]),
        ("mcp_tool_reviews", draft["mcp_tools"][0]["review_id"]),
    ):
        with connection(accounts.dsn) as conn, pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(f"UPDATE {table} SET id=%s WHERE id=%s", (uuid.uuid4(), reference))
        with connection(accounts.dsn) as conn:
            conn.execute(f"UPDATE {table} SET enabled=false WHERE id=%s", (reference,))
        with connection(accounts.dsn) as conn, pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(f"UPDATE {table} SET enabled=true WHERE id=%s", (reference,))


def test_drift_rediscovery_and_operator_revocation_never_expand_selection(configured, accounts):
    restricted, author, draft = configured
    consent(restricted, author)
    config = draft["mcp_tools"][0]
    ref = config["connection_id"]
    rediscover(accounts, author[:2], ref, [TOOL, TOOL | {"name": "other"}])
    assert len(current_grant(restricted, author, draft)["review"]["tools"]) == 1
    rediscover(accounts, author[:2], ref, [TOOL | {"description": "Changed semantics"}])
    with pytest.raises(AuthError, match="mcp_tool_changed"):
        MCPGrants(restricted).review(*author)
    assert MCPTools(restricted).list(*author[:2], ref)["tools"][0]["review_id"] is None
    rediscover(accounts, author[:2], ref, [TOOL])
    revoke(accounts.dsn, author[1], config["review_id"])
    with pytest.raises(AuthError, match="mcp_tool_review_required"):
        current_grant(restricted, author, draft)
    new_review = operator_review(accounts, author[1], ref)
    assert new_review != config["review_id"]
    changed = copy.deepcopy(draft)
    changed["mcp_tools"][0]["review_id"] = new_review
    with pytest.raises(AuthError, match="mcp_grant_required"):
        current_grant(restricted, author, changed)


def test_connection_revocation_and_cross_workspace_selection(configured, accounts):
    restricted, author, draft = configured
    foreign = owner(accounts, "other.mcp.owner")
    with pytest.raises(AuthError, match="mcp_connection_unavailable"):
        Profiles(restricted).create(*foreign, draft)
    with connection(restricted.dsn) as conn:
        assert conn.execute("SELECT id FROM mcp_tool_reviews").fetchall() == []
        assert conn.execute("SELECT id FROM mcp_tool_grants").fetchall() == []
    MCPConnections(restricted).revoke(*author[:2], draft["mcp_tools"][0]["connection_id"])
    with pytest.raises(AuthError, match="mcp_connection_unavailable"):
        MCPGrants(restricted).review(*author)


def test_pending_discovery_blocks_preparation_and_compilation_requires_grant(configured, accounts):
    restricted, author, draft = configured
    qualify(accounts)
    with pytest.raises(ValueError, match="MCP authorization required"):
        compile_agent(validate_draft(draft), EnginePreset())
    with pytest.raises(AuthError, match="mcp_grant_required"):
        Releases(restricted).prepare(*author, 1)
    consent(restricted, author)
    Releases(restricted).prepare(*author, 1)
    MCPConnections(restricted).discover(
        *author[:2], draft["mcp_tools"][0]["connection_id"], request=True
    )
    with pytest.raises(AuthError, match="mcp_discovery_required"):
        Releases(restricted).prepare(*author, 1)
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM agent_preparations").fetchone() == (1,)


@pytest.mark.parametrize(
    "purpose,table,privilege",
    [
        ("management", "mcp_tool_reviews", "INSERT(tool)"),
        ("management", "mcp_tool_executions", "INSERT(id)"),
        ("management", "mcp_tool_executions", "UPDATE(output)"),
        ("management", "mcp_tool_reviews", "UPDATE(enabled)"),
        ("mcp", "mcp_tool_reviews", "INSERT(tool)"),
        ("mcp", "mcp_tool_grants", "INSERT(review)"),
    ],
)
def test_service_roles_cannot_be_reprovisioned_with_forged_permissions(
    accounts, dedicated, purpose, table, privilege
):
    dsn = dedicated(purpose)
    with connection(dsn) as conn:
        role = conn.execute("SELECT current_user").fetchone()[0]
    with connection(accounts.dsn) as conn:
        conn.execute(
            psycopg.sql.SQL("GRANT {} ON {} TO {}").format(
                psycopg.sql.SQL(privilege),
                psycopg.sql.Identifier(table),
                psycopg.sql.Identifier(role),
            )
        )
    with pytest.raises(ValueError):
        (grant_management if purpose == "management" else grant_discovery)(accounts.dsn, role)


def test_discovery_worker_cannot_review_or_authorize(accounts, dedicated):
    dsn = dedicated("mcp")
    for table in ("mcp_tool_reviews", "mcp_tool_grants"):
        with connection(dsn) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(f"INSERT INTO {table}(id) VALUES(%s)", (uuid.uuid4(),))


def test_operator_requires_current_digest_and_supported_output_schema(accounts):
    who = owner(accounts)
    ref = discovered(accounts, who)
    with pytest.raises(ValueError, match="Exact current tool digest"):
        approve(accounts.dsn, who[1], ref, "0" * 64, reviewer="operator", evidence="Inspected")
    unsupported = TOOL | {"outputSchema": {"type": "object"}}
    rediscover(accounts, who, ref, [unsupported])
    with pytest.raises(ValueError, match="closed object"):
        operator_review(accounts, who[1], ref, unsupported)
    # A false hint cannot deny an independently reviewed implementation either.
    explicit = TOOL | {"annotations": {"readOnlyHint": False}}
    rediscover(accounts, who, ref, [explicit])
    assert operator_review(accounts, who[1], ref, explicit)


def test_invalid_fixed_configuration_never_saves_or_leaks_values(configured):
    restricted, author, draft = configured
    invalid = copy.deepcopy(draft)
    invalid["mcp_tools"][0]["fixed_arguments"] = {"project": "sensitive-invalid-value"}
    with pytest.raises(AuthError, match="unsupported_mcp_configuration") as error:
        Profiles(restricted).update(*author, invalid, 1)
    assert "sensitive-invalid-value" not in str(error.value)
    saved = Profiles(restricted).get(*author)
    assert saved["version"] == 1 and saved["content"]["mcp_tools"][0]["fixed_arguments"] == {
        "project": 7
    }


def test_revoked_grant_needs_new_consent_and_wrong_agent_cannot_revoke(configured):
    restricted, author, draft = configured
    first = consent(restricted, author)
    other = Profiles(restricted).create(*author[:2], draft)["id"]
    with pytest.raises(AuthError, match="not_found"):
        MCPGrants(restricted).revoke(*author[:2], other, first["id"])
    MCPGrants(restricted).revoke(*author, first["id"])
    second = consent(restricted, author)
    assert first["id"] != second["id"]
    with pytest.raises(AuthError, match="mcp_grant_required"):
        current_grant(restricted, author, draft, first["id"])
    assert current_grant(restricted, author, draft)["id"] == second["id"]


def test_permission_sql_example_is_repeatable_and_does_not_change_consent(configured):
    restricted, author, draft = configured
    grant = consent(restricted, author)
    script = (Path(__file__).parents[1] / "infra/examples/mcp_tool_permissions.sql").read_text()
    script = script.replace(":'workspace_id'", "'" + author[1] + "'")
    for _ in range(2):
        with connection(restricted.dsn) as conn:
            cursor = conn.execute(script)
            while cursor.nextset():
                pass
        assert current_grant(restricted, author, draft)["id"] == grant["id"]
