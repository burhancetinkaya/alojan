"""Bounded, literal call search and filter-bound cursors; no model-generated SQL."""

import base64
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from alojan.auth import AuthError

FILTERS = {
    "from_time",
    "to_time",
    "caller",
    "called",
    "status",
    "summary_status",
    "query",
    "search_in",
}
SUMMARY_TEXT = "concat_ws(' ', f.payload->'summary'->>'caller_name', f.payload->'summary'->>'subject', f.payload->'summary'->>'message', f.payload->'summary'->>'reason')"


def filters(values):
    if any(
        k not in FILTERS or not isinstance(v, str) or not v or len(v) > 200
        for k, v in values.items()
    ):
        raise AuthError("invalid_call_filter", 400)
    if bool(values.get("from_time")) != bool(values.get("to_time")):
        raise AuthError("call_time_range_required", 400)
    clauses, arguments = [], []
    if "from_time" in values:
        try:
            start, end = (
                datetime.fromisoformat(values[k].replace("Z", "+00:00"))
                for k in ("from_time", "to_time")
            )
            if (
                start.tzinfo is None
                or end.tzinfo is None
                or not timedelta(0) < end - start <= timedelta(days=90)
            ):
                raise ValueError()
        except ValueError:
            raise AuthError("invalid_call_time_range", 400) from None
        clauses += ["s.created_at >= %s", "s.created_at < %s"]
        arguments += [start.astimezone(timezone.utc), end.astimezone(timezone.utc)]
    for key, column in (("caller", "c.from_number_e164"), ("called", "s.called_e164")):
        if key in values:
            number = re.sub(r"[ ()-]", "", values[key])
            if not re.fullmatch(r"\+[1-9][0-9]{6,14}", number):
                raise AuthError("invalid_call_filter", 400)
            clauses.append(column + "=%s")
            arguments.append(number)
    for key, column in (
        ("status", "c.status"),
        ("summary_status", "COALESCE(f.summary_status,j.status,'not_requested')"),
    ):
        if key in values:
            if not re.fullmatch(r"[a-z_]{1,40}", values[key]):
                raise AuthError("invalid_call_filter", 400)
            clauses.append(column + "=%s")
            arguments.append(values[key])
    if values.get("search_in", "summary") not in {"summary", "transcript"} or (
        "search_in" in values and "query" not in values
    ):
        raise AuthError("invalid_call_filter", 400)
    if "query" in values:
        if len(values["query"].strip()) < 2 or "from_time" not in values:
            raise AuthError("bounded_call_search_required", 400)
        literal = (
            "%"
            + values["query"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        if values.get("search_in") == "transcript":
            clauses.append(
                "EXISTS (SELECT 1 FROM utterances u WHERE u.call_id=s.call_id AND u.is_final AND (u.speaker='caller' OR (u.speaker='assistant' AND u.audio_sent_end_ms>u.audio_sent_start_ms)) AND u.text ILIKE %s)"
            )
        else:
            clauses.append(SUMMARY_TEXT + " ILIKE %s")
        arguments.append(literal)
    return "".join(" AND " + clause for clause in clauses), arguments


def fingerprint(scope, agent, values):
    return hashlib.sha256(
        json.dumps([str(scope), str(agent), values], sort_keys=True).encode()
    ).hexdigest()


def decode_cursor(value, expected, *, filtered):
    if value is None:
        return None
    try:
        if not isinstance(value, str) or len(value) > 400:
            raise ValueError()
        if not filtered:
            return uuid.UUID(value)
        data = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if (
            not isinstance(data, dict)
            or data.keys() != {"id", "filter"}
            or data["filter"] != expected
            or not isinstance(data["id"], str)
        ):
            raise ValueError()
        return uuid.UUID(data["id"])
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise AuthError("invalid_call_cursor", 400) from None


def encode_cursor(identifier, digest, *, filtered):
    if not filtered:
        return str(identifier)
    return (
        base64.urlsafe_b64encode(json.dumps({"id": str(identifier), "filter": digest}).encode())
        .decode()
        .rstrip("=")
    )
