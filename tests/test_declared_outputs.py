"""Declared post-call values with real persistence and synthetic model/tool results."""

import asyncio
import copy
import json
import uuid

import pytest
from cryptography.fernet import Fernet
from openai import AsyncOpenAI
from agents import Runner
from agents.testing import ScriptedModel, ModelStep, assistant_message
from alojan_agent.store import call_uuid
from psycopg.types.json import Jsonb

from alojan.auth import AuthError, connection
from alojan.action_grants import ActionGrants
from alojan.calls import Calls
from alojan.http_connections import HTTPConnections
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan_agent.action_delivery import ActionDelivery
from alojan_agent.backend import Backend
from alojan_agent.models import PostCallAnalysis
from alojan_agent.records import CallRecords, CallSummaries
from alojan_contracts.configuration import AgentDraft, EnginePreset, canonical_digest
from alojan_contracts.http_actions import HTTPAction
from alojan_contracts.outputs import (
    OutputDefinition,
    finalized_outputs,
    extraction_model,
    validate_tools,
)
from alojan_contracts.runtime import compile_agent
from alojan_contracts.routing import validated_release
from alojan_contracts.secrets import SecretBox
from test_agent_drafts import content
from test_agent_releases import qualify, prepare_assets
from test_action_grants import consent
from test_http_actions import config, source, HTTPTransport, Transport, URL
from test_scoped_call_records import ended, summary
from test_provider_connections import owner
import test_mcp_tools as selection
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
configured = selection.configured


def definition(name="product", kind="string", **changes):
    return (
        dict(name=name, type=kind, source="conversation", description="Explicit product name")
        | changes
    )


def test_closed_definitions_types_unknowns_and_bounds():
    for changes in [
        dict(name="model_dump"),
        dict(name="x.y"),
        dict(type="object"),
        dict(source="tool"),
        dict(tool_alias="mcp_search"),
        dict(description="\r\n"),
    ]:
        with pytest.raises(ValueError):
            OutputDefinition(**definition(**changes))
    for kind, invalid in [
        ("number", True),
        ("number", float("inf")),
        ("number", 10**13),
        ("number", 10**1000),
        ("boolean", 1),
        ("string", {}),
        ("string", "a" * 513),
        ("string_array", ["a"] * 9),
        ("number_array", [1, True]),
    ]:
        with pytest.raises(ValueError):
            OutputDefinition(**definition(kind=kind)).validate_value(invalid)
    definitions = [
        OutputDefinition(**definition()),
        OutputDefinition(**definition("amount", "number")),
    ]
    assert finalized_outputs(definitions, {"product": None, "amount": False}, {}) == {
        "outputs": {"product": None, "amount": None},
        "output_status": {"product": "missing", "amount": "failed"},
    }
    assert set(
        finalized_outputs(definitions, {"product": "x", "amount": 3, "unselected": "secret"}, {})[
            "output_status"
        ].values()
    ) == {"failed"}
    model = extraction_model(definitions)
    assert model.model_validate({"product": None, "amount": 3}).amount == 3
    with pytest.raises(ValueError):
        model.model_validate({"product": "x", "amount": True})
    with pytest.raises(AuthError):
        validate_draft(content() | {"outputs": [definition(), definition()]})


def test_mapping_requires_declared_source_status_and_body_only():
    ref = str(uuid.uuid4())
    action = config(
        ref, body={"product": source("outputs.product"), "status": source("output_status.product")}
    )
    with pytest.raises(AuthError):
        validate_draft(content() | {"post_call_actions": [action]})
    validate_draft(content() | {"outputs": [definition()], "post_call_actions": [action]})
    with pytest.raises(ValueError):
        HTTPAction(**config(ref, body={"product": source("outputs.product")}))
    with pytest.raises(ValueError):
        HTTPAction(**(action | {"query": {"private": source("outputs.product")}}))
    with pytest.raises(ValueError):
        OutputDefinition(
            **definition(source="tool", tool_alias="mcp_search", path="items.0.password")
        )


def test_tool_projection_schema_is_exact_and_nullable_types_are_checked():
    d = OutputDefinition(**definition(source="tool", tool_alias="mcp_search", path="answer"))
    tool = {"alias": "mcp_search", "capability": "read", "tool": selection.TOOL}
    validate_tools([d], [tool])
    for changed in [[], [tool | {"capability": "write"}], [tool | {"alias": "mcp_other"}]]:
        with pytest.raises(ValueError):
            validate_tools([d], changed)
    with pytest.raises(ValueError):
        validate_tools([d.model_copy(update={"type": "number"})], [tool])
    values = finalized_outputs(
        [d], None, {"mcp_search": {"answer": "Approved field", "hidden": "not selected"}}
    )
    assert values["outputs"] == {"product": "Approved field"}
    assert "hidden" not in json.dumps(values)


@pytest.fixture
def release(configured, accounts, dedicated, tmp_path):
    scoped, author, original = configured
    qualify(accounts)
    box = SecretBox(Fernet.generate_key())
    ref = HTTPConnections(scoped, box).create(
        *author[:2], dict(label="Output sink", endpoint=URL, auth_type="none", token=None)
    )["id"]
    defs = [
        definition(),
        definition("quantity", "number"),
        definition("tags", "string_array"),
        definition("lookup", source="tool", tool_alias="mcp_search", path="answer"),
    ]
    body = {}
    for d in defs:
        body[d["name"]] = source("outputs." + d["name"])
        body[d["name"] + "_status"] = source("output_status." + d["name"], "fail")
    draft = original | {"outputs": defs, "post_call_actions": [config(ref, body=body, query={})]}
    Profiles(scoped).update(*author, draft, 1)
    selection.consent(scoped, author)
    consent(scoped, author)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    release_id = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
    routing.bound(accounts, (*author, release_id))
    route = routing.initialize(accounts, "declared-output-call")
    asyncio.run(ended(CallRecords(dedicated("records"), route)))
    with connection(accounts.dsn) as c:
        for ordinal, output, offset in [
            (1, "older", -3),
            (2, "latest before close", -1),
            (3, "late result", 1),
        ]:
            c.execute(
                """INSERT INTO mcp_tool_executions(id,scope_id,call_id,release_id,ordinal,turn,alias,status,output,completed_at)
                SELECT %s,%s,id,%s,%s,1,'mcp_search','succeeded',%s,ended_at+%s*interval '1 second' FROM calls WHERE id=%s""",
                (
                    uuid.uuid4(),
                    author[1],
                    release_id,
                    ordinal,
                    Jsonb({"answer": output}),
                    offset,
                    call_uuid(route.call_id),
                ),
            )
    return (
        scoped,
        author,
        draft,
        route,
        CallSummaries(dedicated("summaries")),
        ActionDelivery(dedicated("actions"), box),
    )


def test_pinned_extraction_tool_snapshot_event_http_and_call_detail(release, accounts):
    scoped, author, draft, route, summaries, worker = release
    changed = copy.deepcopy(draft)
    changed["outputs"][0]["description"] = "Different future field meaning"
    Profiles(scoped).update(*author, changed, 2)
    with connection(accounts.dsn) as c:
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (route.release_id,)
        ).fetchone()[0]
    assert manifest["schema_version"] == 4
    assert manifest["action_grant"]["review"]["schema_version"] == 3
    assert validated_release(manifest, canonical_digest(manifest))
    tampered = copy.deepcopy(manifest)
    tampered["content"]["outputs"][0]["description"] = "Substitute meaning"
    with pytest.raises(ValueError):
        validated_release(tampered, canonical_digest(tampered))

    class Model:
        async def summarize(self, data, *, runtime):
            assert json.loads(runtime.outputs_json)[0]["description"] == "Explicit product name"
            assert "tool_results" not in data
            return PostCallAnalysis(
                summary=summary(),
                outputs={
                    "product": "<script>untrusted</script>",
                    "quantity": 2.5,
                    "tags": ["a", "b"],
                },
            )

    assert asyncio.run(summaries.process_one(Model()))
    assert not asyncio.run(summaries.process_one(Model()))
    detail = Calls(scoped).get(*author[:2], str(call_uuid(route.call_id)))
    assert detail["outputs"] == {
        "product": "<script>untrusted</script>",
        "quantity": 2.5,
        "tags": ["a", "b"],
        "lookup": "latest before close",
    }
    assert set(detail["output_status"].values()) == {"done"}
    stranger = owner(accounts, "foreign-output")
    with pytest.raises(AuthError):
        Calls(scoped).get(*stranger, str(call_uuid(route.call_id)))
    http = HTTPTransport()
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert json.loads(http.calls[0][1]["body"])["tags"] == ["a", "b"]
    with connection(accounts.dsn) as c:
        event = c.execute(
            "SELECT payload FROM call_finalizations WHERE call_id=%s", (call_uuid(route.call_id),)
        ).fetchone()[0]
        assert event["schema_version"] == 2
        assert "late result" not in json.dumps(event)


def test_failed_extraction_preserves_summary_and_independent_tool_output(release):
    scoped, author, _, route, summaries, worker = release

    class Model:
        async def summarize(self, data, *, runtime):
            return PostCallAnalysis(
                summary=summary(), outputs={"product": None, "quantity": True, "tags": ["x"] * 9}
            )

    asyncio.run(summaries.process_one(Model()))
    data = Calls(scoped).get(*author[:2], str(call_uuid(route.call_id)))
    assert data["summary_status"] == "done"
    assert data["output_status"] == {
        "product": "missing",
        "quantity": "failed",
        "tags": "failed",
        "lookup": "done",
    }
    http = HTTPTransport()
    asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert json.loads(http.calls[0][1]["body"])["quantity"] is None


def test_summary_failure_does_not_invent_outputs_or_discard_tool_result(release):
    scoped, author, _, route, summaries, _ = release

    class Model:
        async def summarize(self, data, *, runtime):
            raise ValueError("synthetic failure")

    asyncio.run(summaries.process_one(Model()))
    data = Calls(scoped).get(*author[:2], str(call_uuid(route.call_id)))
    assert data["summary_status"] == "failed" and data["outputs"]["lookup"] == "latest before close"
    assert data["output_status"]["product"] == "failed"


def test_output_schema_changes_invalidate_consent_and_tool_type_is_validated(release):
    scoped, author, draft, _, _, _ = release
    old = ActionGrants(scoped).review(*author)
    changed = copy.deepcopy(draft)
    changed["outputs"][0]["type"] = "boolean"
    Profiles(scoped).update(*author, changed, 2)
    new = ActionGrants(scoped).review(*author)
    assert old["review_digest"] != new["review_digest"]
    with pytest.raises(AuthError):
        ActionGrants(scoped).authorize(
            *author, {"draft_version": 3, "review_digest": old["review_digest"]}
        )
    changed["outputs"][-1]["type"] = "number"
    with pytest.raises(AuthError, match="invalid_output_configuration"):
        Profiles(scoped).update(*author, changed, 3)


def test_summary_sdk_uses_one_structured_request_and_no_tools(monkeypatch):
    draft = AgentDraft(
        **(content() | {"outputs": [definition(), definition("tags", "string_array")]})
    )
    runtime = compile_agent(draft, EnginePreset())
    seen = []

    original_run = Runner.run

    async def run(agent, records, **kwargs):
        seen.append((agent, records, kwargs))
        return await original_run(agent, records, **kwargs)

    monkeypatch.setattr("alojan_agent.backend.Runner.run", run)
    scripted = ScriptedModel(
        [
            ModelStep(
                output=[
                    assistant_message(
                        json.dumps(
                            {
                                "summary": summary().model_dump(),
                                "outputs": {"product": "Product A", "tags": ["x"]},
                            }
                        )
                    )
                ]
            )
        ]
    )
    backend = Backend(model=scripted, client=AsyncOpenAI(api_key="synthetic-unused-key"))
    result = asyncio.run(
        backend.summarize(
            {"utterances": [("caller", "Synthetic product request")], "last_note": None},
            runtime=runtime,
        )
    )
    assert isinstance(result, PostCallAnalysis) and result.outputs["product"] == "Product A"
    agent, records, kwargs = seen[0]
    assert len(seen) == 1 and not agent.tools and kwargs["max_turns"] == 1
    assert "untrusted" in agent.instructions and "never guess" in agent.instructions
    schema = agent.output_type.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["DeclaredConversationOutputs"]["required"] == ["product", "tags"]
    asyncio.run(backend.close())


def test_projection_does_not_broaden_worker_privileges(release, accounts, dedicated):
    import psycopg

    _, author, _, _, _, _ = release
    with connection(dedicated("summaries")) as c:
        assert c.execute("SELECT count(*) FROM mcp_tool_executions").fetchone()[0] == 0
        c.execute("SELECT set_config('alojan.scope_id',%s,true)", (author[1],))
        assert c.execute("SELECT count(output) FROM mcp_tool_executions").fetchone()[0] == 3
    for role in ("management", "records", "actions"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection(dedicated(role)) as c:
            c.execute("SELECT output FROM mcp_tool_executions")
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        connection(dedicated("summaries")) as c,
    ):
        c.execute("UPDATE mcp_tool_executions SET output='{}'")


def test_selected_tool_configuration_is_part_of_output_consent(release):
    scoped, author, draft, _, _, _ = release
    old = ActionGrants(scoped).review(*author)
    changed = copy.deepcopy(draft)
    changed["mcp_tools"][0]["fixed_arguments"]["project"] = 8
    Profiles(scoped).update(*author, changed, 2)
    new = ActionGrants(scoped).review(*author)
    assert old["review_digest"] != new["review_digest"]
    assert new["review"]["actions"][0]["output_tools"]["mcp_search"]["fixed_arguments"] == {
        "project": 8
    }


def test_readonly_sql_example_matches_declared_contract(accounts):
    from pathlib import Path

    with connection(accounts.dsn) as c:
        example = c.execute(Path("infra/examples/declared-outputs.sql").read_text()).fetchone()[0]
    defs = [OutputDefinition.model_validate(d) for d in example["outputs"]]
    assert defs[0].type == "string_array"
    a = config(str(uuid.uuid4()), body=example["body_mapping_example"])
    validate_draft(content() | {"outputs": example["outputs"], "post_call_actions": [a]})
