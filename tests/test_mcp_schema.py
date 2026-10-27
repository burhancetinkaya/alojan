"""Bounded remote schema qualification; synthetic network, real scoped PostgreSQL."""

import asyncio
import copy
import json

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from alojan.auth import Accounts
from alojan.mcp_tools import MCPTools
from alojan.profiles import Profiles
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.mcp import manifest
from alojan_contracts.mcp_tools import qualified_schema, runtime_schema, schema_binding
from alojan_contracts.outputs import OutputDefinition, validate_tools
from alojan_contracts.routing import validated_release
import test_mcp_tools as selection
import test_mcp_runtime as runtime

accounts, database, dedicated = runtime.accounts, runtime.database, runtime.dedicated
released, call = runtime.released, runtime.call
TOOL = {
    "name": "list_banks",
    "description": "Synthetic paginated read lookup with optional query",
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
            "limit": {"type": "integer", "default": 100},
            "offset": {"type": "integer", "default": 0},
        },
    },
    "outputSchema": {
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
        "x-fastmcp-wrap-result": True,
    },
    "annotations": {"readOnlyHint": True},
}


@pytest.fixture
def configured(accounts, dedicated):
    who = selection.owner(accounts)
    ref = selection.discovered(accounts, who, TOOL)
    review = selection.operator_review(accounts, who[1], ref, TOOL)
    restricted = Accounts(dedicated("management"))
    draft = selection.content() | {
        "mcp_tools": [
            {
                "connection_id": ref,
                "review_id": review,
                "alias": "mcp_banks",
                "fixed_arguments": {"limit": 1, "offset": 0},
            }
        ]
    }
    profile = Profiles(restricted).create(*who, draft)["id"]
    return restricted, (*who, profile), draft


def test_qualification_narrows_remote_language_and_preserves_legacy_bytes():
    original = copy.deepcopy(TOOL)
    binding = schema_binding(manifest([TOOL])["tools"][0])
    assert TOOL == original
    assert schema_binding(manifest([selection.TOOL])["tools"][0]) == {}
    effective = binding["input_schema"]
    assert binding["schema_policy"] == "bounded.v1"
    assert effective["properties"]["query"] == {"type": ["string", "null"], "maxLength": 4096}
    assert effective["properties"]["limit"] == {"type": "integer"}
    exposed = runtime_schema(effective, {"limit": 1, "offset": 0}, nullable=True)
    for value in ({}, {"query": None}, {"query": ""}, {"query": "x" * 4096}):
        Draft202012Validator(exposed).validate(value)
        Draft202012Validator(TOOL["inputSchema"]).validate(value | {"limit": 1, "offset": 0})
    for value in ({"limit": 99}, {"query": 7}, {"query": "x" * 4097}, {"secret": "x"}):
        with pytest.raises(ValidationError):
            Draft202012Validator(exposed).validate(value)
    assert "default" not in json.dumps(binding)
    assert binding["output_schema"]["additionalProperties"] is False
    assert binding["output_schema"]["properties"]["result"]["maxLength"] == 4096
    for value in ({"result": "x" * 4097}, {"result": "ok", "extra": 1}, {}):
        with pytest.raises(ValidationError):
            Draft202012Validator(binding["output_schema"]).validate(value)


@pytest.mark.parametrize(
    "child",
    [
        {"type": "string", "pattern": "(a+)+$"},
        {"$ref": "https://example.test/schema"},
        {"oneOf": [{"type": "string"}, {"type": "null"}]},
        {"anyOf": [{"type": "string"}, {"type": "number"}]},
        {"anyOf": [{"type": "null"}, {"type": "null"}]},
        {"anyOf": [False, {"type": "null"}]},
        {"anyOf": [{"type": "object"}, {"type": "null"}]},
        {"anyOf": [{"type": "string"}, {"type": "null"}], "enum": ["x"]},
        {"type": "object", "properties": {}, "additionalProperties": True},
        {"type": "object"},
        {"type": "string", "minLength": 4097},
        {"type": "array", "minItems": 101, "items": {"type": "integer"}},
        {"type": "string", "x-execute": "untrusted"},
    ],
)
def test_unsupported_constraints_cannot_be_discarded(child):
    with pytest.raises((ValueError, SchemaError)):
        qualified_schema({"type": "object", "properties": {"value": child}})


def test_qualified_bounds_intersect_and_nullable_enum_preserves_null():
    def qualify(child):
        return qualified_schema({"type": "object", "properties": {"value": child}})["properties"][
            "value"
        ]

    assert qualify({"type": "string", "maxLength": 12})["maxLength"] == 12
    assert qualify({"type": "string", "maxLength": 9000})["maxLength"] == 4096
    assert qualify({"type": "array", "items": {"type": "integer"}})["maxItems"] == 100
    child = qualify({"anyOf": [{"type": "null"}, {"type": "string", "enum": ["yes"]}]})
    for value in (None, "yes"):
        Draft202012Validator(child).validate(value)
    with pytest.raises(ValidationError):
        Draft202012Validator(child).validate("no")
    nested = {"type": "string"}
    for _ in range(8):
        nested = {"type": "object", "properties": {"value": nested}}
    with pytest.raises(ValueError, match="depth"):
        qualified_schema(nested)


def test_qualified_catalog_and_grant_pin_exact_effective_schemas(released):
    restricted, author, draft, _, _, manifest_value = released
    config = draft["mcp_tools"][0]
    catalog = MCPTools(restricted).list(*author[:2], config["connection_id"])["tools"][0]
    review = manifest_value["mcp_grant"]["review"]
    bound = review["tools"][0]
    assert manifest_value["schema_version"] == 8 and review["schema_version"] == 2
    assert catalog["input_schema"] == bound["input_schema"]
    assert catalog["tool"] == bound["tool"]
    assert catalog["output_schema"] == bound["output_schema"]
    validate_tools(
        [
            OutputDefinition(
                name="answer",
                description="Synthetic result",
                type="string",
                source="tool",
                tool_alias="mcp_banks",
                path="result",
            )
        ],
        [bound],
    )
    damages = [manifest_value | {"mcp_grant": value} for value in (None, [], "invalid")]
    for field in ("input_schema", "output_schema", "schema_policy"):
        changed = copy.deepcopy(manifest_value)
        del changed["mcp_grant"]["review"]["tools"][0][field]
        damages.append(changed)
    changed = copy.deepcopy(manifest_value)
    changed["mcp_grant"]["review"]["tools"][0]["output_schema"]["properties"]["result"][
        "maxLength"
    ] = 9000
    damages.append(changed)
    changed = copy.deepcopy(manifest_value)
    changed["mcp_grant"]["review"]["schema_version"] = 1
    damages.append(changed)
    damages.append(manifest_value | {"schema_version": 3})
    for changed in damages:
        with pytest.raises(ValueError):
            validated_release(changed, canonical_digest(changed))


@pytest.mark.parametrize("supplied", [{}, {"query": None}, {"query": "synthetic"}])
def test_executor_validates_qualified_schema_without_inserting_defaults(
    call, accounts, dedicated, supplied
):
    seen = []

    async def peer(url, token, name, arguments):
        seen.append(arguments)
        return {"result": '{"banks":[]}'}

    async def run():
        executor = runtime.execution(dedicated, peer)
        try:
            await executor.prepare(call.runtime)
            assert not json.loads(await executor.execute(call, 1, "mcp_banks", '{"limit":99}'))[
                "ok"
            ]
            assert not seen
            response = json.loads(
                await executor.execute(call, 1, "mcp_banks", json.dumps(supplied))
            )
            assert response == {"ok": True, "result": {"result": '{"banks":[]}'}}
            assert seen == [{"limit": 1, "offset": 0} | supplied]
        finally:
            await executor.close()

    asyncio.run(run())
    assert runtime.rows(accounts) == [("succeeded", None, {"result": '{"banks":[]}'})]


@pytest.mark.parametrize("result", [{"result": "x" * 4097}, {"result": "ok", "extra": "bad"}])
def test_executor_rejects_result_that_only_raw_remote_schema_allows(
    call, accounts, dedicated, result
):
    async def peer(*_args):
        return result

    async def run():
        executor = runtime.execution(dedicated, peer)
        try:
            await executor.prepare(call.runtime)
            assert not json.loads(await executor.execute(call, 1, "mcp_banks", "{}"))["ok"]
        finally:
            await executor.close()

    asyncio.run(run())
    assert runtime.rows(accounts) == [("failed", "invalid_result", None)]


@pytest.mark.parametrize("cancel", [False, True])
def test_qualified_release_preserves_unanswered_action_queue(
    configured, accounts, dedicated, tmp_path, cancel
):
    from alojan.auth import connection
    from alojan.releases import Releases
    from alojan_agent.records import CallRecords
    from test_action_grants import setup, consent as action_consent
    from test_agent_releases import prepare_assets, qualify
    import test_number_routing as routing

    scoped, author, draft = configured
    _, actions, _ = setup(accounts, who=author[:2])
    actions["post_call_actions"][0]["condition"] = "no_answer"
    draft = draft | {"post_call_actions": actions["post_call_actions"]}
    Profiles(scoped).update(*author, draft, 1)
    action_consent(scoped, author)
    selection.consent(scoped, author)
    qualify(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    release = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
    routing.bound(accounts, (*author, release))
    route = routing.initialize(accounts, "qualified-unanswered-call")

    async def end():
        if cancel:
            assert await routing.CallRouter(dedicated("routing"), routing.NODE).cancel_unanswered(
                route.call_id
            )
        else:
            await CallRecords(dedicated("records"), route).end(route.call_id, "disconnected")

    asyncio.run(end())
    with connection(accounts.dsn) as conn:
        assert conn.execute(
            "SELECT manifest->>'schema_version' FROM agent_releases WHERE id=%s", (release,)
        ).fetchone() == ("8",)
        assert conn.execute("SELECT status FROM summary_jobs").fetchall() == [("pending",)]
        assert conn.execute("SELECT count(*) FROM mcp_tool_executions").fetchone() == (0,)
