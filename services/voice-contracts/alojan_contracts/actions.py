"""Versioned consent review data; no network, credentials or execution authority."""

import uuid
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, TypeAdapter
from alojan_contracts.configuration import TelegramAction, canonical_digest
from alojan_contracts.http_actions import ReviewedHTTPAction
from alojan_contracts.outputs import selected_outputs, output_tools


class ReviewedAction(TelegramAction):
    connection_label: str = Field(min_length=1, max_length=80)
    chat_id: str = Field(pattern=r"^-?[1-9][0-9]{0,15}$")

    @field_validator("chat_id")
    @classmethod
    def bounded_chat(cls, value):
        if abs(int(value)) > 4503599627370495:
            raise ValueError("Invalid chat ID")
        return value


class ActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1, 2, 3, 4, 5, 6] = 1
    scope_id: str
    profile_id: str
    actions: list[ReviewedAction | ReviewedHTTPAction] = Field(min_length=1, max_length=4)

    @field_validator("scope_id", "profile_id")
    @classmethod
    def identities(cls, value):
        return str(uuid.UUID(value))

    @model_validator(mode="after")
    def version(self):
        if any(
            isinstance(a, ReviewedHTTPAction) for a in self.actions
        ) and self.schema_version not in (2, 3, 4, 5, 6):
            raise ValueError("HTTP actions require review v2")
        if any(
            isinstance(a, ReviewedHTTPAction) and a.outputs for a in self.actions
        ) and self.schema_version not in (3, 4, 5, 6):
            raise ValueError("Declared outputs require review v3")
        if any(a.condition != "answered" for a in self.actions) and self.schema_version not in (
            4,
            5,
            6,
        ):
            raise ValueError("Conditional actions require review v4")
        if any(
            getattr(a, "transcript_policy", None) for a in self.actions
        ) and self.schema_version not in (5, 6):
            raise ValueError("Transcript sharing requires review v5")
        if (
            any(a.condition in ("no_answer", "interrupted") for a in self.actions)
            and self.schema_version != 6
        ):
            raise ValueError("Lifecycle actions require review v6")
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode()) > 16384:
            raise ValueError("Action review size limit")
        return self

    def digest(self):
        return canonical_digest(self.model_dump())

    def check_draft(self, draft):
        selected = [
            a.model_dump(
                exclude={
                    "chat_id",
                    "connection_label",
                    "endpoint",
                    "auth_type",
                    "outputs",
                    "output_tools",
                }
            )
            for a in self.actions
        ]
        for action in self.actions:
            if isinstance(action, ReviewedHTTPAction):
                definitions = selected_outputs(draft.outputs, action.fields)
                if action.outputs != definitions or action.output_tools != output_tools(
                    definitions, draft.mcp_tools
                ):
                    raise ValueError("Output definitions or tools differ from consent")
        if selected != [a.model_dump() for a in draft.post_call_actions]:
            raise ValueError("Action grant differs from draft")


class ActionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    review: ActionReview

    @field_validator("id")
    @classmethod
    def identity(cls, value):
        return str(uuid.UUID(value))


def reviewed_action(value):
    return TypeAdapter(ReviewedAction | ReviewedHTTPAction).validate_python(value)
