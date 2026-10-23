"""Validated local data; caller and model output never grant permissions."""

from dataclasses import dataclass, field
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    caller_name: str | None = Field(default=None, max_length=100)
    caller_number: str | None = Field(default=None, max_length=32)
    subject: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=1500)
    confirmed: bool = False


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    caller_name: str | None
    caller_number: str | None
    subject: str = Field(max_length=160)
    summary: str = Field(max_length=3000)
    requested_action: str = Field(max_length=1000)
    urgency: Literal["low", "medium", "high"]
    promised_action: Literal["none"]
    confirmation_status: Literal["confirmed", "unconfirmed", "partial"]
    unresolved_questions: list[str] = Field(max_length=10)
    confidence: float = Field(ge=0, le=1)
    privacy_flags: list[str] = Field(max_length=10)


def normalize(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.casefold()).split())


@dataclass
class Call:
    messages: list[dict] = field(default_factory=list)
    note: Note | None = None
    version: int = 0
    note_id: str | None = None
    offered_version: int = 0
    offered_turn: int = 0
    last_user: str = ""
    finish: bool = False
    active: bool = False
    ended: bool = False
    phrases: dict = field(default_factory=dict)
    receipts: dict = field(default_factory=dict)
    generation_turns: dict = field(default_factory=dict)
    turns: int = 0
    caller_number: str | None = None

    def take_note(self, note):
        if note.confirmed:
            if (
                not self.note
                or self.offered_version != self.version
                or self.offered_turn != self.turns
                or normalize(self.last_user)
                not in {"evet", "evet doğru", "doğru", "onaylıyorum", "aynen"}
                or self.note.model_copy(update={"confirmed": True}) != note
            ):
                raise ValueError("confirmation requires a delivered readback and unchanged note")
        elif self.note != note:
            self.version += 1
        self.note = note
        return self.version

    def add_message(self, role, text):
        self.messages.append({"role": role, "content": text})
        # UTF-8 bytes upper-bound text token count; preserve recent complete utterances.
        while sum(len(x["content"].encode()) for x in self.messages) > 12000:
            self.messages.pop(0)
