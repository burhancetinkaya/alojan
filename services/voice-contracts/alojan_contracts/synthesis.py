"""Immutable voice capability identity shared by release compilation and TTS workers."""

from dataclasses import asdict, dataclass, fields
import re

EMA_MODEL = "canberkkkkkk/ema-lightning"
EMA_VOICE = "ema-default"


@dataclass(frozen=True)
class SynthesisProfile:
    model: str
    model_revision: str
    voice: str
    schema_version: int = 1
    sample_rate_hz: int = 8000
    channels: int = 1
    format: str = "pcm_s16le"

    def __post_init__(self):
        if (
            self.schema_version != 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}/[A-Za-z0-9_.-]{1,64}", self.model)
            or not re.fullmatch(r"[0-9a-f]{40}", self.model_revision)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.voice)
            or (self.sample_rate_hz, self.channels, self.format) != (8000, 1, "pcm_s16le")
        ):
            raise ValueError("Unsupported synthesis configuration")

    @classmethod
    def from_proto(cls, value):
        return cls(**{field.name: getattr(value, field.name) for field in fields(cls)})

    def to_proto(self):
        # The independent management image compiles profiles without RPC bindings.
        from voice.v1 import voice_pb2 as pb

        return pb.SynthesisConfiguration(**asdict(self))
