"""Transport validation shared by voice services; no model or network dependency."""

import math
import re
import struct
from dataclasses import dataclass

MAX_MESSAGE_BYTES = 16 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def generation_key(message):
    if not all(IDENTIFIER.fullmatch(value) for value in (message.call_id, message.generation_id)):
        raise ValueError("invalid call or generation identifier")
    return message.call_id, message.generation_id


@dataclass
class AudioStreamValidator:
    """One mono PCM stream, monotonically numbered from zero, at most 20 ms/frame."""

    identity: tuple | None = None
    sequence: int = 0

    def accept(self, frame):
        key = generation_key(frame)
        if frame.channels != 1 or frame.sample_rate_hz not in (8000, 16000, 24000, 48000):
            raise ValueError("unsupported sample rate or channel count")
        width = {"pcm_s16le": 2, "pcm_f32le": 4}.get(frame.format)
        if width is None:
            raise ValueError("unsupported PCM format")
        if not frame.audio or len(frame.audio) % width:
            raise ValueError("empty or misaligned PCM")
        if len(frame.audio) > frame.sample_rate_hz // 50 * width:
            raise ValueError("PCM frame exceeds 20 ms")
        if frame.format == "pcm_f32le" and any(
            not math.isfinite(value) or abs(value) > 1
            for (value,) in struct.iter_unpack("<f", frame.audio)
        ):
            raise ValueError("float PCM must be finite and normalized")
        identity = (*key, frame.sample_rate_hz, frame.format)
        if self.identity is not None and identity != self.identity:
            raise ValueError("stream identity or format changed")
        if frame.sequence != self.sequence or frame.captured_at_unix_ms < 0:
            raise ValueError("invalid sequence or capture timestamp")
        self.identity = identity
        self.sequence += 1
        return key
