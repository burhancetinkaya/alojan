"""Reviewed MCP schema subset and fixed/runtime argument ownership."""

from datetime import datetime
import copy
import json
import re

from jsonschema import Draft202012Validator, FormatChecker

from alojan_contracts.configuration import MCPToolConfig


FORMATS = FormatChecker(formats=["uuid"])


@FORMATS.checks("date-time", raises=ValueError)
def timestamp(value):
    # A bounded RFC3339 subset: explicit timezone and ordinary seconds, no leap seconds.
    if not isinstance(value, str):
        return True
    return (
        bool(
            re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
                value,
            )
        )
        and datetime.fromisoformat(value.upper()).tzinfo is not None
    )


def schema_validator(schema):
    return Draft202012Validator(schema, format_checker=FORMATS)


def reviewed_schema(schema, *, nullable=False, formats=False):
    # shortcut: closed, nonrecursive schemas only; expand after bounded evaluator qualification.
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("MCP object schema required")
    if len(json.dumps(schema, allow_nan=False).encode()) > 16384:
        raise ValueError("MCP schema limit")
    Draft202012Validator.check_schema(schema)
    pending = [(schema, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 6 or not isinstance(item, dict):
            raise ValueError("MCP schema depth")
        kind = item.get("type")
        if isinstance(kind, list):
            if (
                not nullable
                or len(kind) != 2
                or kind[1] != "null"
                or kind[0] not in ("string", "integer", "number", "boolean")
            ):
                raise ValueError("MCP nullable scalar required")
            kind = kind[0]
        allowed = {"type", "title", "description"}
        if kind in {"string", "integer", "number", "boolean", "null"}:
            allowed.add("enum")
        if kind == "object":
            allowed |= {"properties", "required", "additionalProperties"}
            props = item.get("properties", {})
            if item.get("additionalProperties") is not False or len(props) > 32:
                raise ValueError("MCP closed object required")
            if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", k) for k in props):
                raise ValueError("MCP property name")
            if not set(item.get("required", [])) <= props.keys():
                raise ValueError("MCP required property missing")
            pending.extend((v, depth + 1) for v in props.values())
        elif kind == "array":
            allowed |= {"items", "minItems", "maxItems"}
            if not 0 <= item.get("maxItems", 101) <= 100 or "items" not in item:
                raise ValueError("MCP bounded array required")
            pending.append((item["items"], depth + 1))
        elif kind == "string":
            allowed |= {"minLength", "maxLength"}
            if formats and "format" in item:
                if item["format"] not in ("uuid", "date-time"):
                    raise ValueError("MCP string format unsupported")
                allowed.add("format")
            if not 0 <= item.get("maxLength", 4097) <= 4096:
                raise ValueError("MCP bounded string required")
        elif kind in {"integer", "number"}:
            allowed |= {"minimum", "maximum"}
        elif kind not in {"boolean", "null"}:
            raise ValueError("MCP schema type unsupported")
        if item.keys() - allowed:
            raise ValueError("MCP schema keyword unsupported")
    return schema


def qualified_schema(schema, *, output=False, formats=False):
    """Narrow common remote schemas to a deterministic bounded subset; never apply defaults."""
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("MCP object schema required")
    if len(json.dumps(schema, allow_nan=False).encode()) > 16384:
        raise ValueError("MCP schema limit")
    Draft202012Validator.check_schema(schema)
    result = copy.deepcopy(schema)
    if output and result.get("x-fastmcp-wrap-result") is True:
        del result["x-fastmcp-wrap-result"]
    pending = [(result, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 6 or not isinstance(item, dict):
            raise ValueError("MCP schema depth")
        item.pop("default", None)
        if "anyOf" in item:
            branches = item["anyOf"]
            if (
                item.keys() - {"anyOf", "title", "description"}
                or len(branches) != 2
                or branches.count({"type": "null"}) != 1
            ):
                raise ValueError("MCP nullable scalar required")
            scalar = next(b for b in branches if b != {"type": "null"})
            if not isinstance(scalar, dict) or scalar.get("type") not in (
                "string",
                "integer",
                "number",
                "boolean",
            ):
                raise ValueError("MCP nullable scalar required")
            del item["anyOf"]
            item.update(scalar)
            item.pop("default", None)
            item["type"] = [scalar["type"], "null"]
            if "enum" in item and None not in item["enum"]:
                item["enum"] = [*item["enum"], None]
        kind = item.get("type")
        if isinstance(kind, list):
            if len(kind) != 2 or "null" not in kind:
                raise ValueError("MCP nullable scalar required")
            kind = next(k for k in kind if k != "null")
            item["type"] = [kind, "null"]
        if kind == "object":
            if "properties" not in item:
                raise ValueError("MCP closed object requires explicit properties")
            item.setdefault("additionalProperties", False)
            pending.extend((v, depth + 1) for v in item["properties"].values())
        elif kind == "array":
            item["maxItems"] = min(item.get("maxItems", 100), 100)
            if item.get("minItems", 0) > item["maxItems"]:
                raise ValueError("MCP array minimum exceeds limit")
            pending.append((item.get("items"), depth + 1))
        elif kind == "string":
            item["maxLength"] = min(item.get("maxLength", 4096), 4096)
            if item.get("minLength", 0) > item["maxLength"]:
                raise ValueError("MCP string minimum exceeds limit")
    return reviewed_schema(result, nullable=True, formats=formats)


def schema_binding(tool):
    """Preserve existing grants; formats and schema-less JSON require a v3 grant."""
    try:
        reviewed_schema(tool.get("inputSchema"))
        reviewed_schema(tool.get("outputSchema"))
        return {}
    except ValueError:
        pass
    try:
        return {
            "schema_policy": "bounded.v1",
            "input_schema": qualified_schema(tool.get("inputSchema")),
            "output_schema": qualified_schema(tool.get("outputSchema"), output=True),
        }
    except ValueError:
        return {
            "schema_policy": "bounded.v2",
            "input_schema": qualified_schema(tool.get("inputSchema"), formats=True),
            "output_schema": (
                qualified_schema(tool["outputSchema"], output=True, formats=True)
                if "outputSchema" in tool
                else None
            ),
        }


def runtime_schema(schema, fixed, *, nullable=False, formats=False):
    reviewed_schema(schema, nullable=nullable, formats=formats)
    props = schema.get("properties", {})
    if fixed.keys() - props.keys():
        raise ValueError("MCP fixed property undeclared")
    partial = copy.deepcopy(schema)
    partial["required"] = [key for key in schema.get("required", []) if key in fixed]
    schema_validator(partial).validate(fixed)
    result = copy.deepcopy(schema)
    result["properties"] = {key: value for key, value in props.items() if key not in fixed}
    result["required"] = [key for key in schema.get("required", []) if key not in fixed]
    return result


def invocation_arguments(schema, fixed, supplied):
    """Reject overrides before composing and validating the full request."""
    if not isinstance(supplied, dict) or fixed.keys() & supplied.keys():
        raise ValueError("MCP fixed argument override")
    MCPToolConfig.bounded_arguments(supplied)
    schema_validator(runtime_schema(schema, fixed)).validate(supplied)
    result = fixed | supplied
    MCPToolConfig.bounded_arguments(result)
    schema_validator(schema).validate(result)
    return result
