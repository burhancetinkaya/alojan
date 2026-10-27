"""Content identities and bounded WAV verification for prepared voice packs."""

import hashlib
import io
import struct
import wave
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from alojan_contracts.configuration import canonical_digest


class VoiceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    samples: int = Field(gt=0, le=240000, multiple_of=160)


class VoiceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    model: Literal["canberkkkkkk/ema-lightning"] = "canberkkkkkk/ema-lightning"
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    speech_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_rate_hz: Literal[8000] = 8000
    greeting_pad_ms: int = Field(ge=0, le=1000, multiple_of=20)
    greeting: VoiceFile
    unavailable: VoiceFile
    waiting: VoiceFile | None = Field(default=None, exclude_if=lambda value: value is None)


def speech_identity(draft, preset):
    return canonical_digest(
        {
            "schema_version": 1,
            "texts": draft.speech_texts(),
            "voice": draft.voice,
            "model_revision": preset.voice_model_revision,
            "sample_rate_hz": preset.asset_sample_rate_hz,
            "greeting_pad_ms": preset.greeting_pad_ms,
        }
    )


def validate_manifest(value, draft, preset):
    manifest = VoiceManifest.model_validate(value)
    if (
        manifest.speech_digest != speech_identity(draft, preset)
        or manifest.model_revision != preset.voice_model_revision
        or manifest.greeting_pad_ms != preset.greeting_pad_ms
    ):
        raise ValueError("Voice pack does not match this preparation")
    for name, text in draft.speech_texts().items():
        file = getattr(manifest, name)
        if file is None:
            raise ValueError("Required speech asset missing")
        if file.text_sha256 != hashlib.sha256(text.encode()).hexdigest():
            raise ValueError("Speech text mismatch")
        if file.samples * 1000 > preset.asset_max_duration_ms * manifest.sample_rate_hz:
            raise ValueError("Speech asset exceeds preset duration")
        if name == "waiting" and file.samples > 5 * 8000:
            raise ValueError("Waiting speech must fit five seconds")
    if manifest.waiting is not None and "waiting" not in draft.speech_texts():
        raise ValueError("Unexpected waiting speech asset")
    minimum_samples_ms = (
        manifest.greeting.samples * 1000 + (preset.closing_delay_ms + preset.media_drain_ms) * 8000
    )
    if minimum_samples_ms >= preset.max_call_seconds * 1000 * 8000:
        raise ValueError("Greeting and closing leave no time for conversation")
    return manifest


def validate_wav(data, expected, *, leading_silence_ms=0):
    if len(data) > 500000 or hashlib.sha256(data).hexdigest() != expected.sha256:
        raise ValueError("Speech file digest or size mismatch")
    if (
        len(data) < 12
        or data[:4] != b"RIFF"
        or data[8:12] != b"WAVE"
        or int.from_bytes(data[4:8], "little") + 8 != len(data)
    ):
        raise ValueError("Incomplete WAV container")
    offset = 12
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("Incomplete WAV chunk")
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        offset += 8 + size + size % 2
        if offset > len(data):
            raise ValueError("Truncated WAV chunk")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                1,
                2,
                8000,
                "NONE",
            ) or wav.getnframes() != expected.samples:
                raise ValueError("Speech file must be complete mono PCM16 at 8 kHz")
            pcm = wav.readframes(expected.samples)
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid speech WAV") from exc
    if len(pcm) != expected.samples * 2:
        raise ValueError("Truncated speech WAV")
    pad_bytes = leading_silence_ms * 8 * 2
    if any(pcm[:pad_bytes]):
        raise ValueError("Greeting pad must be silent")
    count = (len(pcm) - pad_bytes) // 2
    energy = sum(v[0] * v[0] for v in struct.iter_unpack("<h", memoryview(pcm)[pad_bytes:]))
    if count <= 0 or energy / count < (0.001 * 32768) ** 2:
        raise ValueError("Silent speech file")
    return pcm
