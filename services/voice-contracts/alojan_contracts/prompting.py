"""Bounded one-pass prompt variables; no expressions, secrets, IO or recursive expansion."""

import json
import re
from datetime import timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VARIABLE = re.compile(r"\{\{\s*([a-z][a-z0-9_]{0,47})\s*\}\}")
BUILTINS = frozenset(
    {
        "current_datetime",
        "current_date",
        "current_time",
        "today_start",
        "yesterday_start",
        "yesterday_end",
        "timezone",
        "agent_name",
        "owner_name",
    }
)
SECTION = "# Agent-authored business configuration (subordinate to platform rules)\n"


@lru_cache(maxsize=64)
def prompt_zone(name):
    return ZoneInfo(name)


class PromptVariable(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,47}$")
    value: str = Field(max_length=1000)

    @field_validator("value")
    @classmethod
    def safe_value(cls, value):
        if any(not c.isprintable() and c not in "\n\t" for c in value):
            raise ValueError("Invalid prompt variable text")
        return value


class PromptTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(default=1, ge=1, le=1)
    timezone: str = Field(default="Europe/Istanbul", min_length=1, max_length=64)
    variables: list[PromptVariable] = Field(default_factory=list, max_length=16)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            prompt_zone(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("Unknown IANA timezone") from None
        return value

    @model_validator(mode="after")
    def valid_variables(self):
        names = [v.name for v in self.variables]
        if len(names) != len(set(names)) or BUILTINS.intersection(names):
            raise ValueError("Duplicate or reserved prompt variable")
        if (
            len(json.dumps([v.model_dump() for v in self.variables], ensure_ascii=False).encode())
            > 8192
        ):
            raise ValueError("Prompt variable budget exceeded")
        return self

    def render(self, text, *, agent_name, owner_name, now=None):
        values = {v.name: v.value for v in self.variables}
        # Budget validation uses conservative timestamp lengths without reading the clock.
        values.update({name: "9" * 64 for name in BUILTINS})
        values.update(timezone=self.timezone, agent_name=agent_name, owner_name=owner_name)
        if now is not None:
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("Aware application time required")
            local = now.astimezone(prompt_zone(self.timezone))
            start = local.replace(hour=0, minute=0, second=0, microsecond=0)
            values.update(
                current_datetime=local.isoformat(),
                current_date=local.date().isoformat(),
                current_time=local.timetz().isoformat(),
                today_start=start.isoformat(),
                yesterday_start=(start - timedelta(days=1)).isoformat(),
                yesterday_end=(start - timedelta(microseconds=1)).isoformat(),
            )
        stripped = VARIABLE.sub("", text)
        if "{{" in stripped or "}}" in stripped:
            raise ValueError("Invalid prompt placeholder syntax")
        names = {match[1] for match in VARIABLE.finditer(text)}
        if names - values.keys():
            raise ValueError("Undefined prompt variable")
        rendered = VARIABLE.sub(lambda match: values[match[1]], text)
        if len(rendered) > 20000:
            raise ValueError("Expanded prompt text exceeds limit")
        return rendered


def render_instructions(instructions, template, now=None):
    prefix, body = instructions.split(SECTION, 1)
    identity = json.loads(body)
    identity["instructions"] = template.render(
        identity["instructions"],
        agent_name=identity["agent_name"],
        owner_name=identity["owner_display_name"],
        now=now,
    )
    result = prefix + SECTION + json.dumps(identity, ensure_ascii=False, sort_keys=True)
    if len(result.encode()) > 32768:
        raise ValueError("Expanded instructions exceed prompt budget")
    return result


def instructions_for_turn(runtime, now):
    if runtime.prompt_template_json is None:
        return runtime.instructions
    return render_instructions(
        runtime.instructions, PromptTemplate.model_validate_json(runtime.prompt_template_json), now
    )
