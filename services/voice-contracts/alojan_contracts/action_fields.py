"""Approved scalar post-call fields; no transcript, secrets or arbitrary paths."""

from typing import Literal

OutputField = Literal[
    "call_id",
    "agent_name",
    "owner_name",
    "called_number",
    "called_number_source",
    "caller_number",
    "caller_number_source",
    "started_at",
    "answered_at",
    "ended_at",
    "duration_ms",
    "outcome",
    "summary_status",
    "summary.caller_name",
    "summary.subject",
    "summary.summary",
    "summary.requested_action",
    "summary.urgency",
    "summary.confirmation_status",
    "last_note.caller_name",
    "last_note.subject",
    "last_note.message",
    "last_note.confirmed",
]
