"""Scoped delivery outcomes and explicit owner-reviewed retries; no network or delivery-state writes."""

import re
import uuid

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from alojan.auth import AuthError, audit
from alojan.action_grants import live_grant
from alojan.telegram_connections import action_connections
from alojan_contracts.actions import reviewed_action
from alojan_contracts.configuration import canonical_digest
from alojan_contracts.delivery import render

STATES = {"pending", "leased", "sending", "sent", "failed", "paused", "delivery_unknown"}
RETRYABLE = {"failed", "paused", "delivery_unknown"}
COLUMNS = """j.id,j.scope_id,j.profile_id,j.call_id,j.release_id,j.grant_id,j.connection_id,
    j.alias,j.status,j.attempts,j.retry_generation,j.failure_code,j.remote_message_id,j.http_status,
    j.created_at,j.updated_at,j.next_attempt_at"""


def metadata(row):
    return {
        key: (
            str(value)
            if isinstance(value, uuid.UUID)
            else value.isoformat()
            if hasattr(value, "isoformat")
            else value
        )
        for key, value in row.items()
        if key not in {"action", "payload"}
    }


def load(conn, scope, profile, identifier, *, lock=False):
    with conn.cursor(row_factory=dict_row) as c:
        row = c.execute(
            "SELECT " + COLUMNS + ",j.action,j.payload FROM action_jobs j "
            "WHERE j.scope_id=%s AND j.profile_id=%s AND j.id=%s" + (" FOR UPDATE" if lock else ""),
            (scope, profile, identifier),
        ).fetchone()
    if not row:
        raise AuthError("not_found", 404)
    return row


def pending(conn, row):
    return (
        conn.execute(
            "SELECT 1 FROM action_retry_requests WHERE scope_id=%s AND job_id=%s AND generation=%s",
            (row["scope_id"], row["id"], row["retry_generation"] + 1),
        ).fetchone()
        is not None
    )


def check_authority(conn, row):
    action = reviewed_action(row["action"])
    targets = action_connections(conn, row["scope_id"], [action])
    grant = live_grant(conn, row["scope_id"], row["profile_id"], reference=row["grant_id"])
    if (
        action not in grant.review.actions
        or action.alias != row["alias"]
        or action.connection_id != str(row["connection_id"])
        or any(getattr(action, k) != v for k, v in targets[action.connection_id].items())
    ):
        raise AuthError("invalid_action_intent", 409)


def review_data(row):
    try:
        message = render(row["action"], row["payload"])
    except ValueError:
        raise AuthError("invalid_action_intent", 409) from None
    return dict(
        schema_version=1,
        job=metadata(row),
        action=row["action"],
        payload_digest=canonical_digest(row["payload"]),
        message_text=message,
        duplicate_warning="duplicate_delivery_possible",
    )


def blocked(conn, row):
    if row["status"] not in RETRYABLE:
        return "delivery_not_retryable"
    if pending(conn, row):
        return "retry_already_requested"
    if row["retry_generation"] >= 3:
        return "manual_retry_limit"
    try:
        check_authority(conn, row)
    except AuthError as error:
        return error.code
    except ValueError:
        return "invalid_action_intent"
    return None


class Deliveries:
    def __init__(self, accounts):
        self.accounts = accounts

    def list(self, token, scope, profile, *, status=None, after=None):
        if status is not None and status not in STATES:
            raise AuthError("invalid_delivery_filter", 400)
        try:
            after = uuid.UUID(after) if after is not None else None
        except (ValueError, TypeError, AttributeError):
            raise AuthError("invalid_delivery_cursor", 400) from None
        with self.accounts.workspace(token, scope) as (conn, _):
            if not conn.execute(
                "SELECT 1 FROM assistant_profiles WHERE scope_id=%s AND id=%s", (scope, profile)
            ).fetchone():
                raise AuthError("not_found", 404)
            boundary = (None, None)
            if after is not None:
                boundary = conn.execute(
                    "SELECT created_at,id FROM action_jobs WHERE scope_id=%s AND profile_id=%s AND id=%s",
                    (scope, profile, after),
                ).fetchone()
                if boundary is None:
                    raise AuthError("invalid_delivery_cursor", 400)
            with conn.cursor(row_factory=dict_row) as c:
                rows = c.execute(
                    "SELECT "
                    + COLUMNS
                    + """ ,(r.id IS NOT NULL) AS retry_queued
                    FROM action_jobs j LEFT JOIN action_retry_requests r
                        ON (r.scope_id,r.job_id,r.generation)=(j.scope_id,j.id,j.retry_generation+1)
                    WHERE j.scope_id=%s AND j.profile_id=%s AND (%s::text IS NULL OR j.status=%s)
                    AND (%s::timestamptz IS NULL OR (j.created_at,j.id)<(%s,%s))
                    ORDER BY j.created_at DESC,j.id DESC LIMIT 51""",
                    (scope, profile, status, status, boundary[0], *boundary),
                ).fetchall()
        return {
            "deliveries": [metadata(r) for r in rows[:50]],
            "next_cursor": str(rows[49]["id"]) if len(rows) > 50 else None,
        }

    def get(self, token, scope, profile, identifier):
        with self.accounts.workspace(token, scope) as (conn, _):
            # Lock gives a consistent current state plus the bounded retry history.
            row = load(conn, scope, profile, identifier, lock=True)
            queued = pending(conn, row)
            requests = conn.execute(
                """SELECT id,generation,created_at,review#>>'{job,status}',
                (review#>>'{job,attempts}')::integer FROM action_retry_requests
                WHERE scope_id=%s AND job_id=%s ORDER BY generation""",
                (scope, identifier),
            ).fetchall()
        return metadata(row) | {
            "retry_queued": queued,
            "retries": [
                dict(
                    id=str(r[0]),
                    generation=r[1],
                    requested_at=r[2].isoformat(),
                    previous_status=r[3],
                    previous_attempts=r[4],
                )
                for r in requests
            ],
        }

    def review(self, token, scope, profile, identifier):
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, _):
            row = load(conn, scope, profile, identifier, lock=True)
            review = review_data(row)
            reason = blocked(conn, row)
        return dict(
            review=review,
            review_digest=canonical_digest(review),
            can_retry=reason is None,
            blocked_reason=reason,
            warning="Önce hedef sistemdeki sonucu kontrol edin. Önceki istek ulaşmış olabilir; yeniden deneme aynı işlemi iki kez gerçekleştirebilir."
            if row["action"]["adapter"] == "http_request.v1"
            else "Önce Telegram hedefini kontrol edin. Önceki mesaj ulaşmış olabilir; yeniden deneme aynı mesajı iki kez gönderebilir.",
        )

    def retry(self, token, scope, profile, identifier, body):
        if (
            body.keys() != {"request_id", "review_digest", "accept_duplicate_risk"}
            or body["accept_duplicate_risk"] is not True
            or not isinstance(body["review_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", body["review_digest"])
        ):
            raise AuthError("explicit_retry_consent_required", 400)
        try:
            request_id = uuid.UUID(body["request_id"])
        except (ValueError, TypeError, AttributeError):
            raise AuthError("invalid_retry_request", 400) from None
        with self.accounts.workspace(token, scope, roles=("owner",)) as (conn, user):
            row = load(conn, scope, profile, identifier, lock=True)
            existing = conn.execute(
                """SELECT job_id,review_digest,requested_by,generation FROM action_retry_requests
                WHERE scope_id=%s AND profile_id=%s AND id=%s""",
                (scope, profile, request_id),
            ).fetchone()
            if existing:
                if (str(existing[0]), existing[1], str(existing[2])) != (
                    str(identifier),
                    body["review_digest"],
                    str(user["id"]),
                ):
                    raise AuthError("retry_request_conflict", 409)
                generation = existing[3]
            else:
                reason = blocked(conn, row)
                if reason:
                    raise AuthError(reason, 409)
                review = review_data(row)
                if canonical_digest(review) != body["review_digest"]:
                    raise AuthError("stale_retry_review", 409)
                generation = row["retry_generation"] + 1
                inserted = conn.execute(
                    """INSERT INTO action_retry_requests
                    (id,scope_id,profile_id,job_id,generation,requested_by,review,review_digest)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
                    (
                        request_id,
                        scope,
                        profile,
                        identifier,
                        generation,
                        user["id"],
                        Jsonb(review),
                        body["review_digest"],
                    ),
                ).fetchone()
                if not inserted:
                    raise AuthError("retry_request_conflict", 409)
                audit(conn, user["id"], "delivery.retry_requested", scope=scope, target=request_id)
        return dict(
            id=str(request_id), job_id=str(identifier), generation=generation, status="accepted"
        )
