"""Exact MCP grant snapshots shared by publication and immutable consumers."""

import json
import re
import uuid

from jsonschema.exceptions import SchemaError, ValidationError

from alojan_contracts.configuration import MCPToolConfig, canonical_digest
from alojan_contracts.mcp import endpoint
from alojan_contracts.mcp_tools import schema_binding, runtime_schema


def authorization(value, draft):
    try:
        return _authorization(value, draft)
    except (TypeError, KeyError, AttributeError, OverflowError) as error:
        raise ValueError("Invalid MCP authorization") from error


def _authorization(value, draft):
    if not isinstance(value, dict) or value.keys() != {"id", "review"}:
        raise ValueError("MCP authorization required")
    if str(uuid.UUID(value["id"])) != value["id"]:
        raise ValueError("Invalid MCP grant identity")
    review = value["review"]
    if (
        not isinstance(review, dict)
        or review.keys() != {"schema_version", "scope_id", "profile_id", "tools"}
        or type(review["schema_version"]) is not int
        or review["schema_version"] not in (1, 2, 3)
    ):
        raise ValueError("Invalid MCP review")
    for key in ("scope_id", "profile_id"):
        if str(uuid.UUID(review[key])) != review[key]:
            raise ValueError("Invalid MCP review identity")
    if not isinstance(review["tools"], list) or len(review["tools"]) != len(draft.mcp_tools):
        raise ValueError("MCP selection mismatch")
    version = 1
    for selection, item in zip(draft.mcp_tools, review["tools"], strict=True):
        keys = set(MCPToolConfig.model_fields)
        extra = (
            {"schema_policy", "input_schema", "output_schema"}
            if isinstance(item, dict) and "schema_policy" in item
            else set()
        )
        version = max(
            version, 3 if item.get("schema_policy") == "bounded.v2" else 2 if extra else 1
        )
        if not isinstance(item, dict) or item.keys() != keys | extra | {
            "endpoint",
            "capability",
            "tool",
            "runtime_schema",
        }:
            raise ValueError("Invalid MCP tool binding")
        if {k: item[k] for k in keys} != selection.model_dump() or item["capability"] != "read":
            raise ValueError("MCP configuration changed")
        endpoint(item["endpoint"])
        tool = item["tool"]
        if (
            not isinstance(tool, dict)
            or tool.keys() - {"outputSchema"}
            != {
                "name",
                "description",
                "inputSchema",
                "read_only_hint",
                "review_status",
                "digest",
            }
            or tool["review_status"] != "unreviewed"
        ):
            raise ValueError("Invalid MCP tool snapshot")
        if canonical_digest({k: v for k, v in tool.items() if k != "digest"}) != tool["digest"]:
            raise ValueError("MCP tool digest mismatch")
        if (
            not isinstance(tool["name"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", tool["name"])
            or not isinstance(tool["description"], str)
            or len(tool["description"]) > 4096
            or type(tool["read_only_hint"]) is not bool
        ):
            raise ValueError("Invalid MCP tool metadata")
        try:
            schemas = schema_binding(tool)
            if schemas != {k: item[k] for k in extra}:
                raise ValueError("MCP qualified schema mismatch")
            if (
                runtime_schema(
                    schemas.get("input_schema", tool["inputSchema"]),
                    selection.fixed_arguments,
                    nullable=bool(schemas),
                    formats=schemas.get("schema_policy") == "bounded.v2",
                )
                != item["runtime_schema"]
            ):
                raise ValueError("MCP runtime schema mismatch")
        except (SchemaError, ValidationError) as error:
            raise ValueError("Unsupported MCP schema") from error
    if review["schema_version"] != version:
        raise ValueError("MCP review capability version mismatch")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if not draft.mcp_tools or len(raw.encode()) > 65536:
        raise ValueError("MCP release tool budget")
    return raw
