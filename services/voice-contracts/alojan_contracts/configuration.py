"""Versioned business configuration shared by authoring and voice consumers."""

import hashlib
import json
import string
import uuid
from typing import Literal
from alojan_contracts.action_conditions import ActionCondition

from alojan_contracts.vocabulary import validate_replacements
from alojan_contracts.outputs import OutputDefinition, selected_outputs
from alojan_contracts.action_fields import OutputField
from alojan_contracts.http_actions import HTTPAction
from alojan_contracts.prompting import PromptTemplate
from alojan_contracts.experience import ResponseExperience

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    model_serializer,
)


# Shared Turkish sentence boundaries; protocol policy, not owner-editable text.
SPEECH_ABBREVIATIONS = frozenset({"dr", "prof", "doç", "av", "sn", "no", "vb", "vs", "örn"})


class ToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tool: Literal["take_note"]
    alias: str = Field(default="take_note", pattern=r"^[a-z][a-z0-9_]{0,39}$")
    guidance: str = Field(
        default="Save a concrete caller request before acknowledging it.", max_length=1000
    )

    @field_validator("alias")
    @classmethod
    def reserved_alias(cls, value):
        if value in {"respond", "finish_call"}:
            raise ValueError("Core speech tools cannot be replaced")
        return value

    @field_validator("guidance")
    @classmethod
    def printable_guidance(cls, value):
        if any(not c.isprintable() and c not in "\n\t" for c in value):
            raise ValueError("Invalid guidance characters")
        return value


class MCPToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    connection_id: str
    review_id: str
    alias: str = Field(pattern=r"^mcp_[a-z][a-z0-9_]{0,35}$")
    fixed_arguments: dict = Field(default_factory=dict, max_length=32)
    guidance: str = Field(default="", max_length=1000)

    @field_validator("connection_id", "review_id")
    @classmethod
    def identity(cls, value):
        return str(uuid.UUID(value))

    @field_validator("guidance")
    @classmethod
    def printable_guidance(cls, value):
        return ToolConfig.printable_guidance(value)

    @field_validator("fixed_arguments")
    @classmethod
    def bounded_arguments(cls, value):
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 8:
                raise ValueError("MCP argument depth")
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    raise ValueError("MCP argument keys must be strings")
                pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if len(raw) > 8192 or b"\\u0000" in raw:
            raise ValueError("MCP fixed argument limit")
        return value


class TelegramAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    alias: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    adapter: Literal["telegram.send_message.v1"] = "telegram.send_message.v1"
    connection_id: str
    event: Literal["call.finalized.v1"] = "call.finalized.v1"
    condition: ActionCondition = "answered"
    on_missing: Literal["null"] = "null"
    fields: list[OutputField] = Field(min_length=1, max_length=23)

    @field_validator("connection_id")
    @classmethod
    def connection_identity(cls, value):
        return str(uuid.UUID(value))

    @field_validator("fields")
    @classmethod
    def distinct_fields(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate output field")
        for number in ("called_number", "caller_number"):
            if number in value and number + "_source" not in value:
                raise ValueError("Number provenance must be included")
        if any(field.startswith("summary.") for field in value) and "summary_status" not in value:
            raise ValueError("Summary status must be included")
        return value


class AgentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    agent_name: str = Field(min_length=1, max_length=100)
    owner_display_name: str = Field(min_length=1, max_length=100)
    owner_address: str = Field(min_length=1, max_length=120)
    owner_dative: str = Field(min_length=1, max_length=120)
    owner_genitive: str = Field(min_length=1, max_length=120)
    # The existing live instructions exceed 18k characters; the compiled 32 KiB cap still applies.
    instructions: str = Field(min_length=1, max_length=20000)
    prompt_template: PromptTemplate | None = None
    response_experience: ResponseExperience | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    role_description: str = Field(default="Personal AI assistant.", min_length=1, max_length=2000)
    tone_description: str = Field(
        default="Warm, respectful and concise.", min_length=1, max_length=2000
    )
    business_context: str = Field(default="", max_length=6000)
    # Mandatory AI identity is prepended by the compiler, outside editable wording.
    greeting_text: str = Field(
        default="Size nasıl yardımcı olabilirim?", min_length=1, max_length=400
    )
    availability_text: str = Field(
        default="Şu anda görüşmeye bağlayamıyorum.", min_length=1, max_length=400
    )
    unavailable_text: str = Field(
        default="Şu anda mesaj alamıyorum. Lütfen daha sonra tekrar arayın. Hoşça kalın.",
        min_length=1,
        max_length=400,
    )
    offer_further_help: bool = True
    further_help_text: str = Field(
        default="Başka yardımcı olabileceğim bir konu var mı?", min_length=1, max_length=400
    )
    clarification_text: str = Field(
        default="Son söylediğinizi net anlayamadım, tekrar eder misiniz?",
        min_length=1,
        max_length=400,
    )
    silence_reminder_text: str = Field(
        default="Buradayım, sizi dinliyorum.", min_length=1, max_length=400
    )
    silence_timeout_text: str = Field(
        default="Sesinizi alamıyorum. Dilerseniz daha sonra tekrar arayabilirsiniz. Hoşça kalın.",
        min_length=1,
        max_length=400,
    )
    farewell_text: str = Field(default="Rica ederim, iyi günler.", min_length=1, max_length=400)
    explicit_stop_text: str = Field(default="Hoşça kalın.", min_length=1, max_length=400)
    note_ack_template: str = Field(
        default="Talebinizi {owner_dative} iletmek üzere not aldım.", min_length=1, max_length=400
    )
    callback_unknown_template: str = Field(
        default="{owner_genitive} dönüş zamanı hakkında kesin bir bilgim yok.",
        min_length=1,
        max_length=400,
    )
    summary_role_template: str = Field(
        default="Write a concise Turkish handover for {owner_address}.",
        min_length=1,
        max_length=2000,
    )
    model: Literal["gpt-oss-120b-cerebras"] = "gpt-oss-120b-cerebras"
    model_connection: str | None = None
    voice: Literal["ema-default"] = "ema-default"
    language: Literal["tr"] = "tr"
    post_call_actions: list[TelegramAction | HTTPAction] = Field(default_factory=list, max_length=4)
    vocabulary: list[str] = Field(default_factory=list, max_length=100)
    asr_replacements: dict[str, str] = Field(default_factory=dict, max_length=8)
    tools: list[ToolConfig] = Field(
        default_factory=lambda: [ToolConfig(tool="take_note")], max_length=1
    )

    outputs: list[OutputDefinition] = Field(default_factory=list, max_length=8)

    mcp_tools: list[MCPToolConfig] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def distinct_tool_aliases(self):
        if self.prompt_template is not None:
            self.prompt_template.render(
                self.instructions, agent_name=self.agent_name, owner_name=self.owner_display_name
            )
        aliases = [t.alias for t in (*self.tools, *self.mcp_tools)]
        if len(set(aliases)) != len(aliases):
            raise ValueError("Duplicate tool alias")
        if len({d.name for d in self.outputs}) != len(self.outputs):
            raise ValueError("Duplicate output name")
        if any(
            d.source == "tool" and d.tool_alias not in {t.alias for t in self.mcp_tools}
            for d in self.outputs
        ):
            raise ValueError("Output tool is not selected")
        for action in self.post_call_actions:
            selected_outputs(self.outputs, action.fields)
        return self

    @field_validator("model_connection")
    @classmethod
    def connection_id(cls, value):
        return str(uuid.UUID(value)) if value is not None else None

    @model_serializer(mode="wrap")
    def serialize(self, handler):
        data = handler(self)
        # Preserve historical manifest/draft digests when no connection was selected.
        if self.prompt_template is None:
            data.pop("prompt_template", None)
        if self.model_connection is None:
            data.pop("model_connection", None)
        if not self.post_call_actions:
            data.pop("post_call_actions", None)
        if not self.mcp_tools:
            data.pop("mcp_tools", None)
        if not self.outputs:
            data.pop("outputs", None)
        return data

    @field_validator("post_call_actions")
    @classmethod
    def distinct_actions(cls, value):
        if len({item.alias for item in value}) != len(value):
            raise ValueError("Duplicate action alias")
        return value

    @field_validator("*")
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str):
            if not value.strip() and value != "":
                raise ValueError("Whitespace-only fields are invalid")
            if any(not c.isprintable() and c not in "\n\t" for c in value):
                raise ValueError("Control characters are invalid")
        return value

    @field_validator(
        "agent_name", "owner_display_name", "owner_address", "owner_dative", "owner_genitive"
    )
    @classmethod
    def identity(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError("Names must be printable and trimmed")
        return value

    @field_validator("vocabulary")
    @classmethod
    def terms(cls, values):
        if len(set(values)) != len(values) or any(
            not 1 <= len(value) <= 100 or value != value.strip() or not value.isprintable()
            for value in values
        ):
            raise ValueError("Vocabulary must contain distinct bounded terms")
        return values

    @field_validator("asr_replacements")
    @classmethod
    def spelling_aliases(cls, value):
        return validate_replacements(value)

    @model_validator(mode="after")
    def templates(self):
        for field in ("note_ack_template", "callback_unknown_template", "summary_role_template"):
            rendered = self.render(getattr(self, field))
            if len(rendered) > (2000 if field == "summary_role_template" else 400):
                raise ValueError("Expanded template exceeds its speech limit")
        if len(self.greeting()) > 1000:
            raise ValueError("Greeting exceeds its supported asset limit")
        return self

    def render(self, template):
        names = {
            key: getattr(self, key)
            for key in (
                "agent_name",
                "owner_display_name",
                "owner_address",
                "owner_dative",
                "owner_genitive",
            )
        }
        for _, name, spec, conversion in string.Formatter().parse(template):
            if name is not None and (name not in names or spec or conversion):
                raise ValueError("Only declared identity placeholders are supported")
        return template.format_map(names)

    def greeting(self):
        from alojan_contracts.transcript import DISCLOSURE

        disclosure = (
            DISCLOSURE + " "
            if any(getattr(a, "transcript_policy", None) for a in self.post_call_actions)
            else ""
        )
        return f"Merhaba, ben {self.agent_name}. {self.owner_genitive} yapay zekâ asistanıyım. {disclosure}{self.greeting_text}"

    def digest(self):
        return hashlib.sha256(
            json.dumps(
                self.model_dump(),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def speech_texts(self):
        texts = {"greeting": self.greeting(), "unavailable": self.unavailable_text}
        if self.response_experience and self.response_experience.enabled:
            texts["waiting"] = self.response_experience.text()
        return texts


class NativeCalibration(BaseModel):
    """Versioned operator calibration; v1 defaults preserve historical engine behavior."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    partial_hint: bool = False
    vad_percent: int = Field(default=50, ge=20, le=90)
    candidate_ms: int = Field(default=250, ge=100, le=500)
    yes_no_ms: int = Field(default=350, ge=350, le=1000)
    open_ms: int = Field(default=500, ge=500, le=1500)
    uncertain_ms: int = Field(default=1200, ge=1200, le=2000)
    incomplete_ms: int = Field(default=2200, ge=2200, le=5000)
    silence_reminder_ms: int = Field(default=7000, ge=3000, le=15000, multiple_of=20)
    interrupt_vad_percent: int = Field(default=50, ge=20, le=90)
    interrupt_min_voice_ms: int = Field(default=192, ge=160, le=320, multiple_of=32)
    interrupt_sustained_voice_ms: int = Field(default=640, ge=320, le=1280, multiple_of=32)
    interrupt_max_quiet_ms: int = Field(default=800, ge=400, le=1200, multiple_of=20)
    interrupt_sustained_quiet_ms: int = Field(default=160, ge=80, le=320, multiple_of=20)

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if not (
            self.candidate_ms
            <= self.yes_no_ms
            <= self.open_ms
            <= self.uncertain_ms
            < self.incomplete_ms
            and self.interrupt_min_voice_ms < self.interrupt_sustained_voice_ms
        ):
            raise ValueError("Invalid native calibration threshold ordering")
        return self


# Never retune this compatibility value: historical releases keep their v1 meaning.
LEGACY_NATIVE_CALIBRATION = NativeCalibration()


class OutputBudget(BaseModel):
    """Operator-selected speech limits within fixed v1 transport ceilings."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    phrase_max_chars: int = Field(default=240, ge=40, le=240)
    phrase_max_bytes: int = Field(default=1024, ge=160, le=1024)
    max_phrases: int = Field(default=16, ge=1, le=16)
    turn_max_bytes: int = Field(default=4096, ge=1024, le=4096)

    @model_validator(mode="after")
    def compatible_limits(self):
        # A Unicode scalar may require four UTF-8 bytes; never split encoded text.
        if not 4 * self.phrase_max_chars <= self.phrase_max_bytes <= self.turn_max_bytes:
            raise ValueError("Phrase characters/bytes must fit the turn budget")
        return self

    def accepts(self, text):
        from alojan_contracts.phrases import phrase_end

        if len(text.encode()) > self.turn_max_bytes:
            return False
        count = 0
        while text:
            end = phrase_end(text, self.phrase_max_chars)
            if end is None:
                end = len(text)
            phrase, text = text[:end].strip(), text[end:]
            if phrase:
                count += 1
                if count > self.max_phrases or len(phrase.encode()) > self.phrase_max_bytes:
                    return False
        return True


# Frozen historical v1 behavior. Never retune these compatibility defaults.
LEGACY_OUTPUT_BUDGET = OutputBudget()


class EnginePreset(BaseModel):
    """Operator-owned v1 limits, bounded by the current Python/native contracts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    model: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    base_url: Literal["https://openrouter.ai/api/v1"] = "https://openrouter.ai/api/v1"
    provider: Literal["cerebras"] = "cerebras"
    reasoning: Literal["low", "medium", "high"] = "medium"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    routing: Literal["default", "latency", "sticky", "latency-sticky"] = "default"
    llm_timeout_seconds: int = Field(default=15, ge=1, le=20)
    llm_max_retries: int = Field(default=0, ge=0, le=2)
    model_steps_per_turn: int = Field(default=5, ge=1, le=5)
    max_call_turns: int = Field(default=16, ge=1, le=16)
    history_max_bytes: int = Field(default=12000, ge=1024, le=12000)
    summary_input_max_bytes: int = Field(default=12000, ge=1024, le=12000)
    reply_max_chars: int = Field(default=400, ge=1, le=400)
    reply_max_questions: int = Field(default=1, ge=0, le=1)
    reply_max_sentences: int = Field(default=2, ge=1, le=5)
    turn_timeout_seconds: int = Field(default=20, ge=1, le=20)
    max_call_seconds: int = Field(default=120, ge=10, le=300)
    answer_delay_ms: int = Field(default=3000, ge=0, le=5000)
    closing_delay_ms: int = Field(default=3000, ge=0, le=5000)
    media_drain_ms: int = Field(default=150, ge=0, le=1000)
    greeting_pad_ms: int = Field(default=400, ge=0, le=1000, multiple_of=20)
    asset_max_duration_ms: int = Field(default=30000, ge=1000, le=30000, multiple_of=20)
    asset_sample_rate_hz: Literal[8000] = 8000
    voice_model_revision: Literal["e7c96f2fc0ba843cd0f86e02786655bb56f50df8"] = (
        "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"
    )
    allow_fallbacks: Literal[False] = False
    provider_store: Literal[False] = False
    tracing_enabled: Literal[False] = False
    raw_recording_enabled: Literal[False] = False
    parallel_tool_calls: Literal[False] = False
    # Omission preserves historical canonical JSON/digests, including summary replay.
    calibration: NativeCalibration | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    output: OutputBudget | None = Field(default=None, exclude_if=lambda value: value is None)

    @property
    def output_budget(self):
        return self.output if self.output is not None else LEGACY_OUTPUT_BUDGET

    @property
    def native_calibration(self):
        return self.calibration if self.calibration is not None else LEGACY_NATIVE_CALIBRATION

    @model_validator(mode="after")
    def deadlines(self):
        if self.llm_timeout_seconds > self.turn_timeout_seconds:
            raise ValueError("Model deadline must fit the turn deadline")
        return self

    def gateway_configuration(self):
        # Management compilation must not depend on the generated RPC environment.
        from voice.v1 import voice_pb2 as pb

        return pb.GatewayConfiguration(
            schema_version=1,
            max_call_seconds=self.max_call_seconds,
            answer_delay_ms=self.answer_delay_ms,
            closing_delay_ms=self.closing_delay_ms,
            media_drain_ms=self.media_drain_ms,
            max_call_turns=self.max_call_turns,
            turn_timeout_seconds=self.turn_timeout_seconds,
            calibration=pb.NativeCalibration(**self.native_calibration.model_dump()),
            output=pb.OutputBudget(**self.output_budget.model_dump()),
        )


def canonical_digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
