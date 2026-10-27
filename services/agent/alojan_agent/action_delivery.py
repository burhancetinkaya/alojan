"""Private scoped delivery claims, live authority checks and fenced completion."""

import asyncio
from dataclasses import dataclass, field
import time
import uuid

from psycopg.rows import dict_row

from alojan_contracts.actions import ActionReview, reviewed_action
from alojan_contracts.delivery import render
from alojan_contracts.http_actions import ReviewedHTTPAction, request_data
from alojan_contracts.configuration import canonical_digest
from .records import transaction
from .telegram_delivery import Result


@dataclass(frozen=True)
class Claim:
    id: uuid.UUID
    scope_id: str
    token: uuid.UUID
    endpoint: str | None = None


@dataclass(frozen=True)
class Dispatch:
    token: str = field(repr=False)
    chat_id: str = field(repr=False)
    text: str = field(repr=False)
    authorized_at: float


@dataclass(frozen=True)
class HTTPDispatch:
    token: str | None = field(repr=False)
    request: dict = field(repr=False)
    authorized_at: float


class ActionDelivery:
    def __init__(self, dsn, secrets):
        self.dsn, self.secrets = dsn, secrets

    async def claim(self):
        def take():
            with transaction(self.dsn) as c:
                c.row_factory = dict_row
                # Bounded crash recovery: only pre-send leases can become pending again.
                c.execute("""WITH expired AS (
                    SELECT id FROM action_jobs WHERE status IN ('leased','sending')
                    AND lease_until<clock_timestamp() ORDER BY lease_until,id
                    LIMIT 32 FOR UPDATE SKIP LOCKED)
                    UPDATE action_jobs j SET status=CASE WHEN status='sending' THEN 'delivery_unknown'
                        WHEN attempts=5 THEN 'failed' ELSE 'pending' END,
                    failure_code=CASE WHEN status='sending' THEN 'send_uncertain'
                        WHEN attempts=5 THEN 'attempts_exhausted' ELSE NULL END,
                    claim_token=NULL,lease_until=NULL,updated_at=now()
                    FROM expired WHERE j.id=expired.id""")
                # The partial index bounds polling to unconsumed approvals, not delivery history.
                c.execute("""WITH requested AS (
                    SELECT j.id,r.id AS request_id,r.generation FROM action_retry_requests r
                    JOIN action_jobs j
                        ON (r.scope_id,r.job_id,r.generation)=(j.scope_id,j.id,j.retry_generation+1)
                    WHERE r.consumed_at IS NULL AND j.status IN ('failed','paused','delivery_unknown')
                    ORDER BY r.created_at,r.id LIMIT 32 FOR UPDATE OF j,r SKIP LOCKED),
                    reopened AS (UPDATE action_jobs j SET status='pending',attempts=0,failure_code=NULL,
                        retry_generation=r.generation,next_attempt_at=now(),updated_at=now()
                    FROM requested r WHERE j.id=r.id RETURNING j.id)
                    UPDATE action_retry_requests r SET consumed_at=now()
                    FROM requested q JOIN reopened j ON j.id=q.id WHERE r.id=q.request_id""")
                gate = c.execute("""SELECT 1 FROM action_dispatch_clock WHERE provider='telegram'
                    AND next_dispatch_at<=clock_timestamp() FOR UPDATE SKIP LOCKED""").fetchone()
                if not gate:
                    return None
                scope = c.execute("""SELECT s.scope_id FROM action_dispatch_scopes s
                    WHERE s.next_dispatch_at<=clock_timestamp() AND EXISTS(
                    SELECT 1 FROM action_jobs j WHERE j.scope_id=s.scope_id AND j.status='pending'
                    AND j.next_attempt_at<=clock_timestamp())
                    ORDER BY s.last_claim_at,s.scope_id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
                if not scope:
                    return None
                row = c.execute(
                    """SELECT id,action FROM action_jobs WHERE scope_id=%s AND status='pending'
                    AND next_attempt_at<=clock_timestamp() ORDER BY created_at,id
                    LIMIT 1 FOR UPDATE SKIP LOCKED""",
                    (scope["scope_id"],),
                ).fetchone()
                if not row:
                    return None
                token = uuid.uuid4()
                c.execute(
                    """UPDATE action_jobs SET status='leased',claim_token=%s,
                    lease_until=now()+interval '30 seconds',attempts=attempts+1,updated_at=now()
                    WHERE id=%s""",
                    (token, row["id"]),
                )
                c.execute(
                    """UPDATE action_dispatch_scopes SET last_claim_at=clock_timestamp(),
                    next_dispatch_at=clock_timestamp()+interval '1 second' WHERE scope_id=%s""",
                    (scope["scope_id"],),
                )
                c.execute("""UPDATE action_dispatch_clock SET
                    next_dispatch_at=clock_timestamp()+interval '50 milliseconds' WHERE provider='telegram' """)
                return Claim(
                    row["id"],
                    str(scope["scope_id"]),
                    token,
                    row["action"].get("endpoint")
                    if row["action"].get("adapter") == "http_request.v1"
                    else None,
                )

        return await asyncio.to_thread(take)

    @staticmethod
    def checked(c, job, status):
        row = c.execute(
            """SELECT * FROM action_jobs WHERE id=%s AND scope_id=%s
            AND status=%s AND claim_token=%s AND lease_until>clock_timestamp() FOR UPDATE""",
            (job.id, job.scope_id, status, job.token),
        ).fetchone()
        if not row:
            raise ValueError("action claim expired or replaced")
        return row

    async def begin(self, job):
        def prepare():
            with transaction(self.dsn, job.scope_id) as c:
                c.row_factory = dict_row
                row = self.checked(c, job, "leased")
                is_http = row["action"].get("adapter") == "http_request.v1"
                target_table = "http_connections" if is_http else "telegram_connections"
                target_fields = "t.endpoint,t.auth_type" if is_http else "t.chat_id"
                live = c.execute(
                    f"""SELECT g.review,g.review_digest,{target_fields},t.label,t.ciphertext
                    FROM action_grants g
                    JOIN users u ON u.id=g.granted_by AND u.enabled
                    JOIN workspace_memberships m ON m.user_id=g.granted_by AND m.scope_id=g.scope_id
                        AND m.role='owner'
                    JOIN recipient_scopes s ON s.id=g.scope_id AND s.enabled
                    JOIN {target_table} t ON t.scope_id=g.scope_id AND t.id=%s AND t.enabled
                    WHERE g.scope_id=%s AND g.profile_id=%s AND g.id=%s AND g.enabled""",
                    (row["connection_id"], job.scope_id, row["profile_id"], row["grant_id"]),
                ).fetchone()
                retry = None
                if row["retry_generation"]:
                    retry = c.execute(
                        """SELECT r.review,r.review_digest FROM action_retry_requests r
                        JOIN users u ON u.id=r.requested_by AND u.enabled
                        JOIN workspace_memberships m ON m.user_id=r.requested_by AND m.scope_id=r.scope_id AND m.role='owner'
                        WHERE r.scope_id=%s AND r.job_id=%s AND r.generation=%s AND r.consumed_at IS NOT NULL""",
                        (job.scope_id, job.id, row["retry_generation"]),
                    ).fetchone()
                    if not retry:
                        live = None
                if not live:
                    self.complete(c, job, Result("paused", "authority_revoked"))
                    return None
                try:
                    action = reviewed_action(row["action"])
                    review = ActionReview.model_validate(live["review"])
                    if (
                        review.digest() != live["review_digest"]
                        or review.scope_id != job.scope_id
                        or review.profile_id != str(row["profile_id"])
                        or action not in review.actions
                        or action.alias != row["alias"]
                        or action.connection_id != str(row["connection_id"])
                        or action.connection_label != live["label"]
                        or (
                            is_http
                            and (action.endpoint, action.auth_type)
                            != (live["endpoint"], live["auth_type"])
                        )
                        or (not is_http and action.chat_id != live["chat_id"])
                    ):
                        raise ValueError("action intent mismatch")
                    text = render(action, row["payload"])
                    if retry and (
                        canonical_digest(retry["review"]) != retry["review_digest"]
                        or retry["review"]["action"] != row["action"]
                        or retry["review"]["message_text"] != text
                        or retry["review"]["payload_digest"] != canonical_digest(row["payload"])
                    ):
                        raise ValueError("retry review differs from original intent")
                except (ValueError, KeyError, TypeError):
                    self.complete(c, job, Result("failed", "invalid_intent"))
                    return None
                try:
                    token = (
                        self.secrets.open(
                            job.scope_id,
                            row["connection_id"],
                            live["ciphertext"],
                            purpose="http" if is_http else "telegram",
                        )
                        if not is_http or live["auth_type"] == "bearer"
                        else None
                    )
                except ValueError:
                    self.complete(c, job, Result("failed", "credential_unavailable"))
                    return None
                c.execute(
                    "UPDATE action_jobs SET status='sending',updated_at=now() WHERE id=%s",
                    (job.id,),
                )
                if isinstance(action, ReviewedHTTPAction):
                    return HTTPDispatch(
                        token, request_data(action, row["payload"]), time.monotonic()
                    )
                return Dispatch(token, action.chat_id, text, time.monotonic())

        return await asyncio.to_thread(prepare)

    @staticmethod
    def complete(c, job, result):
        row = c.execute("SELECT attempts FROM action_jobs WHERE id=%s", (job.id,)).fetchone()
        status, code = result.status, result.code
        if status == "pending" and row["attempts"] >= 5:
            status, code = "failed", "attempts_exhausted"
        delay = max(result.retry_after, min(300, 2 ** row["attempts"]))
        c.execute(
            """UPDATE action_jobs SET status=%s,failure_code=%s,remote_message_id=%s,http_status=%s,
            claim_token=NULL,lease_until=NULL,next_attempt_at=now()+%s*interval '1 second',
            updated_at=now() WHERE id=%s""",
            (status, code, result.message_id, result.http_status, delay, job.id),
        )
        if result.code == "rate_limited":
            # Conservative aggregate cooldown also covers duplicate bot references in other scopes.
            c.execute(
                """UPDATE action_dispatch_clock SET next_dispatch_at=
                greatest(next_dispatch_at,clock_timestamp()+%s*interval '1 second')
                WHERE provider='telegram' """,
                (result.retry_after,),
            )

    async def finish(self, job, result, *, phase="sending"):
        def save():
            with transaction(self.dsn, job.scope_id) as c:
                c.row_factory = dict_row
                self.checked(c, job, phase)
                self.complete(c, job, result)

        await asyncio.to_thread(save)

    async def process_one(self, transport, *, http_transport=None):
        job = await self.claim()
        if job is None:
            return False
        # Resolve before authorization: no network await separates the live check from dispatch setup.
        try:
            if job.endpoint is not None:
                from .http_delivery import Webhook

                http_transport = http_transport or Webhook()
                address = await http_transport.resolve(job.endpoint)
            else:
                address = await transport.resolve()
        except Exception:
            await self.finish(job, Result("pending", "connect_failed"), phase="leased")
            return True
        dispatch = await self.begin(job)
        if dispatch is None:
            return True
        if time.monotonic() - dispatch.authorized_at > 2:
            await self.finish(job, Result("pending", "connect_failed"))
            return True
        try:
            if isinstance(dispatch, HTTPDispatch):
                result = await http_transport.send(
                    address, dispatch.token, dispatch.request, job.id
                )
            else:
                result = await transport.send(
                    address, dispatch.token, dispatch.chat_id, dispatch.text
                )
        except asyncio.CancelledError:
            # If persistence also fails, the expired sending lease becomes unknown on next startup.
            await asyncio.shield(self.finish(job, Result("delivery_unknown", "send_uncertain")))
            raise
        except Exception:
            result = Result("delivery_unknown", "send_uncertain")
        await self.finish(job, result)
        return True
