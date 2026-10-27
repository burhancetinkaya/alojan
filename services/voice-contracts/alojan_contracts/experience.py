"""Release-bound waiting speech; engine timing is not a user tuning surface."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponseExperience(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    enabled: bool = False
    style: Literal["concise", "natural"] = "concise"
    waiting_text: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("waiting_text")
    @classmethod
    def safe_waiting_text(cls, value):
        if value is not None and (
            not value.strip()
            or value != value.strip()
            or not all(c.isprintable() for c in value)
            or any(c in value for c in "{}<>?\n")
        ):
            raise ValueError("Waiting text must be one plain statement")
        return value

    def text(self):
        if not self.enabled:
            return None
        return self.waiting_text or (
            "Biraz bekleteceğim, kontrol ediyorum."
            if self.style == "concise"
            else "Sizi kısa bir süre bekleteceğim, kontrol ediyorum."
        )
