"""Pure bounded output projection/rendering shared by owner review and delivery."""

import json
from alojan_contracts.actions import reviewed_action
from alojan_contracts.http_actions import ReviewedHTTPAction, request_data


def project(action, event):
    result = {}
    for path in action.fields:
        value = event
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if (
            value is not None
            and type(value) not in (str, int, bool)
            and not path.startswith("outputs.")
        ):
            raise ValueError("non-scalar action output")
        result[path] = value
    return result


LABELS = {
    "call_id": "Çağrı",
    "agent_name": "Asistan",
    "owner_name": "Numara sahibi",
    "called_number": "Aranan numara",
    "called_number_source": "Aranan numara kaynağı",
    "caller_number": "Arayan numara",
    "caller_number_source": "Arayan numara kaynağı",
    "started_at": "Başlangıç",
    "answered_at": "Yanıtlanma",
    "ended_at": "Bitiş",
    "duration_ms": "Süre (ms)",
    "outcome": "Sonuç",
    "summary_status": "Özet durumu",
    "summary.caller_name": "Arayan adı",
    "summary.subject": "Konu",
    "summary.summary": "Özet",
    "summary.requested_action": "İstenen işlem",
    "summary.urgency": "Aciliyet",
    "summary.confirmation_status": "Özet onayı",
    "last_note.caller_name": "Not: arayan adı",
    "last_note.subject": "Not: konu",
    "last_note.message": "Not: mesaj",
    "last_note.confirmed": "Not onayı",
}


def clipped(value, units):
    encoded = value.encode("utf-16-le")
    if len(encoded) <= units * 2:
        return value
    return encoded[: (units - 1) * 2].decode("utf-16-le", errors="ignore") + "…"


def render(action, payload):
    """One plain-text message, no parse mode, expressions, implicit fields or multipart replay."""
    action = reviewed_action(action)
    if isinstance(action, ReviewedHTTPAction):
        return json.dumps(request_data(action, payload), ensure_ascii=False, sort_keys=True)
    if set(payload) != set(action.fields):
        raise ValueError("action projection mismatch")
    labels = [LABELS[path] for path in action.fields]
    overhead = sum(len(label.encode("utf-16-le")) // 2 + 3 for label in labels)
    budget = (4000 - overhead) // len(labels)
    lines = []
    for path, label in zip(action.fields, labels, strict=True):
        value = payload[path]
        if (
            value is not None
            and type(value) not in (str, int, bool)
            and not path.startswith("outputs.")
        ):
            raise ValueError("non-scalar action output")
        text = "null" if value is None else str(value)
        # Keep caller text as data, and eliminate control characters/bidi display overrides.
        text = "".join(
            c
            if c in "\n\t"
            or (
                ord(c) >= 32
                and ord(c) != 127
                and not 0x202A <= ord(c) <= 0x202E
                and not 0x2066 <= ord(c) <= 0x2069
            )
            else " "
            for c in text
        )
        lines.append(f"{label}: {clipped(text, budget)}")
    return "\n".join(lines)
