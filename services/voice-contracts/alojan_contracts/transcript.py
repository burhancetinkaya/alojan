"""Versioned opt-in transcript export policy; text data only, never executable context."""

POLICY = "bounded_text.v1"
DISCLOSURE = (
    "Bu görüşmenin yazılı dökümü, görüşme sonunda bağlı hizmet sağlayıcılarla paylaşılabilir."
)
MAX_ROWS = 100
MAX_BYTES = 8192
VISIBLE = """is_final AND (speaker='caller' OR
    (speaker='assistant' AND audio_sent_end_ms>audio_sent_start_ms))"""
STATUSES = {"complete", "truncated", "empty", "omitted_size_limit"}


def bounded_transcript(rows):
    """Rows are chronological (speaker, bounded text, database text was clipped)."""
    parts, size = [], 0
    truncated = len(rows) > MAX_ROWS
    for speaker, text, clipped in rows[:MAX_ROWS]:
        if speaker not in ("caller", "assistant") or not isinstance(text, str):
            raise ValueError("Invalid transcript row")
        text = "".join(c for c in text if c.isprintable() or c in "\n\t")
        label = "Arayan" if speaker == "caller" else "Asistan"
        line = ("\n" if parts else "") + label + ": " + text
        encoded = line.encode()
        if clipped or size + len(encoded) > MAX_BYTES:
            parts.append(encoded[: MAX_BYTES - size].decode("utf-8", errors="ignore"))
            truncated = True
            break
        parts.append(line)
        size += len(encoded)
    return {
        "text": "".join(parts) or None,
        "status": "truncated" if truncated else "complete" if parts else "empty",
    }


def validate_projection(payload):
    text, status = payload.get("transcript.text"), payload.get("transcript.status")
    if status not in STATUSES:
        raise ValueError("Invalid transcript status")
    if status in ("empty", "omitted_size_limit"):
        if text is not None:
            raise ValueError("Unexpected transcript text")
    elif (
        not isinstance(text, str)
        or not text
        or len(text.encode()) > MAX_BYTES
        or any(not c.isprintable() and c not in "\n\t" for c in text)
    ):
        raise ValueError("Invalid transcript text")
