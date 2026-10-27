"""Closed post-call conditions evaluated from durable finalization metadata only."""

from typing import Literal

ActionCondition = Literal["answered", "summary_ready", "summary_failed", "no_answer", "interrupted"]
LIFECYCLE_CONDITIONS = ("no_answer", "interrupted")


def matches(condition, event):
    if condition not in ("answered", "summary_ready", "summary_failed", *LIFECYCLE_CONDITIONS):
        raise ValueError("Unsupported action condition")
    status = event.get("summary_status")
    if status not in ("done", "failed", "not_requested"):
        raise ValueError("Action condition requires a finalized summary status")
    if not event.get("ended_at"):
        return False
    answered = bool(event.get("answered_at"))
    if condition == "no_answer":
        return not answered and status == "not_requested"
    if not answered or status == "not_requested":
        return False
    if condition == "interrupted":
        return event.get("outcome") in ("disconnected", "failed")
    return condition == "answered" or status == (
        "done" if condition == "summary_ready" else "failed"
    )
