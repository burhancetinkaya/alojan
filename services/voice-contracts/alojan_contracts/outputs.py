"""Declared post-call data, never executable instructions or arbitrary lookup paths."""

import json
import math
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

NAME = r"[a-z][a-z0-9_]{0,31}"
OutputPath = Annotated[str, Field(pattern=rf"^(outputs|output_status)\.{NAME}$")]


class OutputDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=rf"^{NAME}$")
    type: Literal["string", "number", "boolean", "string_array", "number_array", "boolean_array"]
    source: Literal["conversation", "tool"]
    description: str = Field(min_length=1, max_length=160)
    tool_alias: str | None = None
    path: str | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.name in dir(BaseModel) or self.name.startswith("model_"):
            raise ValueError("Reserved output name")
        if not self.description.strip() or not self.description.isprintable():
            raise ValueError("Invalid output description")
        if self.source == "conversation":
            if self.tool_alias is not None or self.path is not None:
                raise ValueError("Conversation output cannot read tools")
        elif (
            not isinstance(self.tool_alias, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", self.tool_alias)
            or not isinstance(self.path, str)
            or not re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]{0,39}(\.[A-Za-z][A-Za-z0-9_]{0,39}){0,3}", self.path
            )
        ):
            raise ValueError("A fixed tool alias and object property path are required")
        return self

    def validate_value(self, value):
        if value is None:
            return None
        kind = self.type.removesuffix("_array")
        values = value if self.type.endswith("_array") else [value]
        if self.type.endswith("_array") and (type(value) is not list or len(value) > 8):
            raise ValueError("Output array limit")
        for item in values:
            if kind == "string":
                valid = (
                    type(item) is str
                    and len(item) <= 512
                    and all(c.isprintable() or c in "\n\t" for c in item)
                )
            elif kind == "number":
                valid = type(item) in (int, float) and abs(item) <= 1e12 and math.isfinite(item)
            else:
                valid = type(item) is bool
            if not valid:
                raise ValueError("Output type or value limit")
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 1024:
            raise ValueError("Output byte limit")
        return value


def selected_outputs(definitions, fields):
    names = {f.split(".")[1] for f in fields if f.startswith(("outputs.", "output_status."))}
    selected = [d for d in definitions if d.name in names]
    if names != {d.name for d in selected}:
        raise ValueError("Undeclared output source")
    return selected


def output_tools(definitions, tools):
    aliases = {d.tool_alias for d in definitions if d.source == "tool"}
    return {t.alias: t.model_dump() for t in tools if t.alias in aliases}


def validate_tools(definitions, tools):
    bindings = {t["alias"]: t for t in tools}
    for definition in definitions:
        if definition.source != "tool":
            continue
        binding = bindings.get(definition.tool_alias)
        if binding is None or binding.get("capability") != "read":
            raise ValueError("Output requires an approved selected read tool")
        schema = binding.get("output_schema", binding["tool"].get("outputSchema"))
        if schema is None:
            raise ValueError("Tool has no declared output properties")
        for part in definition.path.split("."):
            if schema.get("type") != "object" or part not in schema.get("properties", {}):
                raise ValueError("Output property is not declared by the tool")
            schema = schema["properties"][part]
        expected = definition.type.removesuffix("_array")
        if definition.type.endswith("_array"):
            if schema.get("type") != "array":
                raise ValueError("Tool output type differs")
            schema = schema.get("items", {})
        kinds = schema.get("type")
        kinds = set(kinds) if isinstance(kinds, list) else {kinds}
        if (
            not kinds
            or not kinds
            <= ({"number", "integer", "null"} if expected == "number" else {expected, "null"})
            or kinds == {"null"}
        ):
            raise ValueError("Tool output type differs")


def extraction_model(definitions):
    fields = {}
    for d in definitions:
        if d.source != "conversation":
            continue
        scalar = {"string": str, "number": float, "boolean": bool}[d.type.removesuffix("_array")]
        value_type = list[scalar] if d.type.endswith("_array") else scalar
        fields[d.name] = (value_type | None, Field(..., description=d.description))
    return create_model(
        "DeclaredConversationOutputs", __config__=ConfigDict(extra="forbid", strict=True), **fields
    )


def finalized_outputs(definitions, extracted, tool_results):
    values, statuses = {}, {}
    expected = {d.name for d in definitions if d.source == "conversation"}
    extraction_valid = isinstance(extracted, dict) and set(extracted) == expected
    for d in definitions:
        if d.source == "conversation":
            value = extracted[d.name] if extraction_valid else None
            status = "done" if extraction_valid else "failed"
        else:
            value = tool_results.get(d.tool_alias)
            status = "done" if d.tool_alias in tool_results else "unavailable"
            for part in d.path.split("."):
                value = value.get(part) if isinstance(value, dict) else None
        try:
            value = d.validate_value(value)
            if value is None and status == "done":
                status = "missing"
        except (ValueError, TypeError, OverflowError):
            value, status = None, "failed"
        values[d.name], statuses[d.name] = value, status
    return {"outputs": values, "output_status": statuses}
