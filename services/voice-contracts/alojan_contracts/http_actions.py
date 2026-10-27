"""Typed HTTP action data and rendering; no network or executable templates."""

import json
import re
import uuid
from typing import Literal
from alojan_contracts.action_conditions import ActionCondition
from urllib.parse import urlencode

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    model_serializer,
)
from alojan_contracts.action_fields import OutputField
from alojan_contracts.outputs import OutputPath, OutputDefinition, selected_outputs
from alojan_contracts.transcript import validate_projection


class SourceValue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["source"] = "source"
    source: OutputField | OutputPath | Literal["transcript.text", "transcript.status"]
    on_missing: Literal["null", "omit", "fail"]


class LiteralValue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["literal"]
    value: str | int | float | bool | None

    @field_validator("value")
    @classmethod
    def bounded(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 2048 or (
            isinstance(value, str) and any(ord(c) < 32 for c in value)
        ):
            raise ValueError("HTTP literal limit")
        return value


class HTTPAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    alias: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    adapter: Literal["http_request.v1"]
    connection_id: str
    event: Literal["call.finalized.v1"] = "call.finalized.v1"
    condition: ActionCondition = "answered"
    transcript_policy: Literal["bounded_text.v1"] | None = None
    method: Literal["POST", "PUT", "PATCH"]
    headers: dict[str, str] = Field(default_factory=dict, max_length=4)
    body: dict[str, SourceValue | LiteralValue] = Field(min_length=1, max_length=16)
    query: dict[str, SourceValue | LiteralValue] = Field(default_factory=dict, max_length=8)

    @model_serializer(mode="wrap")
    def serialize(self, handler):
        data = handler(self)
        if self.transcript_policy is None:
            data.pop("transcript_policy", None)
        return data

    @field_validator("connection_id")
    @classmethod
    def identity(cls, value):
        return str(uuid.UUID(value))

    @field_validator("headers")
    @classmethod
    def safe_headers(cls, values):
        # Business labels only. Authentication, routing and idempotency remain platform-owned.
        for name, value in values.items():
            if (
                not re.fullmatch(r"X-Data-[A-Za-z0-9-]{1,40}", name)
                or not 1 <= len(value) <= 256
                or any(not 32 <= ord(c) <= 126 for c in value)
            ):
                raise ValueError("Unsupported HTTP header")
        if len({k.lower() for k in values}) != len(values):
            raise ValueError("Duplicate HTTP header")
        return values

    @field_validator("body", "query")
    @classmethod
    def safe_keys(cls, values):
        if any(not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,39}", k) for k in values):
            raise ValueError("Invalid HTTP field name")
        return values

    @property
    def fields(self):
        return sorted(
            {
                v.source
                for v in [*self.body.values(), *self.query.values()]
                if isinstance(v, SourceValue)
            }
        )

    @model_validator(mode="after")
    def bounded_mapping(self):
        if self.transcript_policy and self.condition == "no_answer":
            raise ValueError("Unanswered calls cannot have disclosed transcript sharing")
        fields = self.fields
        transcript_fields = {f for f in fields if f.startswith("transcript.")}
        if transcript_fields != (
            {"transcript.text", "transcript.status"} if self.transcript_policy else set()
        ):
            raise ValueError("Transcript sharing requires explicit policy, text and status")
        if any(
            v.kind == "source" and v.source.startswith("transcript.") for v in self.query.values()
        ):
            raise ValueError("Transcript belongs in the JSON body, not URL logs")
        for number in ("called_number", "caller_number"):
            if number in fields and number + "_source" not in fields:
                raise ValueError("Number provenance must be included")
        if any(f.startswith("summary.") for f in fields) and "summary_status" not in fields:
            raise ValueError("Summary status must be included")
        for field in fields:
            if (
                field.startswith("outputs.")
                and "output_status." + field.split(".")[1] not in fields
            ):
                raise ValueError("Declared output status must be included")
        if any(v.kind == "source" and v.source.startswith("outputs.") for v in self.query.values()):
            raise ValueError("Declared outputs belong in the JSON body, not URL logs")
        if len(self.model_dump_json().encode()) > 4096:
            raise ValueError("HTTP action configuration limit")
        return self


class ReviewedHTTPAction(HTTPAction):
    outputs: list[OutputDefinition] = Field(default_factory=list, max_length=8)
    output_tools: dict[str, dict] = Field(default_factory=dict, max_length=8)

    @model_serializer(mode="wrap")
    def serialize(self, handler):
        data = handler(self)
        if self.transcript_policy is None:
            data.pop("transcript_policy", None)
        for field in ("outputs", "output_tools"):
            if not getattr(self, field):
                data.pop(field, None)
        return data

    @model_validator(mode="after")
    def declared(self):
        if selected_outputs(self.outputs, self.fields) != self.outputs:
            raise ValueError("Unexpected output definition")
        if set(self.output_tools) != {d.tool_alias for d in self.outputs if d.source == "tool"}:
            raise ValueError("Output tool binding mismatch")
        return self

    connection_label: str = Field(min_length=1, max_length=80)
    endpoint: str
    auth_type: Literal["none", "bearer"]

    @field_validator("endpoint")
    @classmethod
    def target(cls, value):
        from alojan_contracts.mcp import endpoint

        return endpoint(value)


def request_data(action, payload):
    action = ReviewedHTTPAction.model_validate(action)
    if set(payload) != set(action.fields):
        raise ValueError("HTTP projection mismatch")
    if action.transcript_policy:
        validate_projection(payload)
    result = {}
    for group in ("body", "query"):
        mapped = {}
        for key, mapping in getattr(action, group).items():
            if isinstance(mapping, LiteralValue):
                value = mapping.value
            else:
                value = payload[mapping.source]
                if value is None:
                    if mapping.on_missing == "omit":
                        continue
                    if mapping.on_missing == "fail":
                        raise ValueError("Required HTTP output is missing")
                else:
                    if mapping.source.startswith("outputs."):
                        definition = next(
                            d for d in action.outputs if d.name == mapping.source.split(".")[1]
                        )
                        definition.validate_value(value)
                        mapped[key] = value
                        continue
                    if mapping.source.startswith("output_status.") and value not in {
                        "done",
                        "missing",
                        "failed",
                        "unavailable",
                    }:
                        raise ValueError("Invalid output status")
                    expected = (
                        int
                        if mapping.source == "duration_ms"
                        else bool
                        if mapping.source == "last_note.confirmed"
                        else str
                    )
                    if type(value) is not expected:
                        raise ValueError("HTTP output type mismatch")
            mapped[key] = value
        result[group] = mapped
    body = json.dumps(result["body"], ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    query = urlencode(
        {
            k: json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            for k, v in result["query"].items()
        }
    )
    if len(body.encode()) > 65536 or len(query.encode()) > 4096:
        raise ValueError("HTTP request size limit")
    return {
        "method": action.method,
        "url": action.endpoint + ("?" + query if query else ""),
        "headers": action.headers,
        "body": body,
    }


def synthetic_preview(action):
    payload = {
        field: 12000
        if field == "duration_ms"
        else False
        if field == "last_note.confirmed"
        else "done"
        if field == "summary_status"
        else "00000000-0000-4000-8000-000000000001"
        if field == "call_id"
        else "Örnek veri"
        for field in action.fields
    }
    if action.transcript_policy:
        payload.update(
            {"transcript.text": "Arayan: Örnek görüşme metni.", "transcript.status": "complete"}
        )
    for d in action.outputs:
        if "outputs." + d.name in payload:
            sample = {"string": "Örnek veri", "number": 12.5, "boolean": False}[
                d.type.removesuffix("_array")
            ]
            payload["outputs." + d.name] = [sample] if d.type.endswith("_array") else sample
        if "output_status." + d.name in payload:
            payload["output_status." + d.name] = "done"
    request = request_data(action, payload)
    return request | {"body": json.loads(request["body"]), "synthetic": True}
