"""Pinned call records and leased finalization; private runtime APIs, never tenant input."""

import asyncio
import json
import math
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import psycopg
from psycopg.types.json import Jsonb

from alojan_contracts.runtime import compile_release
from .models import Note, Summary, PostCallAnalysis
from alojan_contracts.outputs import OutputDefinition, finalized_outputs
from alojan_contracts.action_conditions import matches
from alojan_contracts.transcript import POLICY, VISIBLE, MAX_ROWS, bounded_transcript
from .action_events import enqueue
from .store import Store, call_uuid


NO_ANSWER_JOB = """INSERT INTO summary_jobs(call_id,scope_id,release_id)
    SELECT s.call_id,s.scope_id,s.release_id FROM call_route_snapshots s
    JOIN agent_releases r ON (r.scope_id,r.id)=(s.scope_id,s.release_id)
    WHERE s.call_id=%s AND r.manifest->>'schema_version' IN ('7','8','9','10')
    AND r.manifest->'content'->'post_call_actions' @> '[{"condition":"no_answer"}]'::jsonb
    ON CONFLICT DO NOTHING"""


def validated_summary(summary):
    result = Summary.model_validate(summary.model_dump())
    if len(result.model_dump_json().encode()) > 24000:
        raise ValueError("summary exceeds output budget")
    return result


def summary_retry_delay(value):
    if value is None:
        return 60
    try:
        delay = float(value)
        if delay < 0:
            return None
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            delay = (date - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    if not math.isfinite(delay) or delay > 300:
        return None
    return max(60, math.ceil(delay))


@contextmanager
def transaction(dsn, scope=None):
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        conn.execute("SET LOCAL statement_timeout=3000")
        conn.execute("SET LOCAL lock_timeout=1000")
        conn.execute("SET LOCAL transaction_timeout=5000")
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (scope or "",))
        yield conn


class CallRecords:
    def __init__(self, dsn, route):
        self.dsn, self.route = dsn, route

    def _run(self, call_id, operation):
        if call_id != self.route.call_id:
            raise ValueError("call ownership mismatch")
        r = self.route
        with transaction(self.dsn, r.scope_id) as c:
            row = c.execute(
                """SELECT c.status,c.answered_at,c.from_number_e164,c.started_at FROM calls c
                JOIN call_route_snapshots s ON s.call_id=c.id
                WHERE c.id=%s AND c.sip_call_id=%s AND
                (s.scope_id,s.number_id,s.binding_id,s.profile_id,s.release_id,s.node_id,s.manifest_digest)
                =(%s,%s,%s,%s,%s,%s,%s) FOR UPDATE OF c""",
                (
                    call_uuid(call_id),
                    call_id,
                    r.scope_id,
                    r.number_id,
                    r.binding_id,
                    r.profile_id,
                    r.release_id,
                    r.node_id,
                    r.manifest_digest,
                ),
            ).fetchone()
            if not row:
                raise ValueError("call ownership mismatch")
            return operation(c, row)

    async def run(self, call_id, operation):
        return await asyncio.to_thread(self._run, call_id, operation)

    @staticmethod
    def active(row):
        if row[0] != "active" or row[1] is None:
            raise ValueError("call is not answered and active")

    @staticmethod
    def observed_time(value, row):
        if type(value) is not int or value <= 0:
            raise ValueError("invalid lifecycle timestamp")
        try:
            observed = datetime.fromtimestamp(value / 1000, UTC)
        except (ValueError, OverflowError, OSError):
            raise ValueError("invalid lifecycle timestamp") from None
        # Native and DB clocks are qualified together; allow at most five seconds skew.
        if (
            not row[3] - timedelta(seconds=5)
            <= observed
            <= datetime.now(UTC) + timedelta(seconds=5)
        ):
            raise ValueError("invalid lifecycle timestamp")
        return observed

    def save_answer(self, c, call_id, row, observed_ms=None):
        observed = self.observed_time(observed_ms, row) if observed_ms is not None else None
        if row[0] == "active" and row[1] is not None:
            if observed is not None and observed != row[1]:
                raise ValueError("answer timestamp conflict")
            return row[1]
        if row[0] != "initializing":
            raise ValueError("call cannot be answered")
        return c.execute(
            "UPDATE calls SET status='active',answered_at=COALESCE(%s,now()) WHERE id=%s RETURNING answered_at",
            (observed, call_uuid(call_id)),
        ).fetchone()[0]

    async def answered(self, call_id, observed_ms=None):
        await self.run(call_id, lambda c, row: self.save_answer(c, call_id, row, observed_ms))

    async def start(self, call_id, number):
        def check(c, row):
            self.active(row)
            if number is not None and number != row[2]:
                raise ValueError("caller metadata conflict")

        await self.run(call_id, check)

    async def utterance(self, call_id, generation, speaker, text, sent_ms=None):
        if (
            not isinstance(generation, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,142}", generation)
            or speaker not in {"caller", "assistant"}
            or not isinstance(text, str)
            or len(text.encode()) > 4096
            or (speaker == "caller" and (not text or sent_ms is not None))
            or (
                speaker == "assistant"
                and (
                    type(sent_ms) is not int or not 0 <= sent_ms <= 30000 or (text and not sent_ms)
                )
            )
        ):
            raise ValueError("invalid utterance")

        def save(c, row):
            self.active(row)
            saved = c.execute(
                """INSERT INTO utterances(id,call_id,speaker,text,is_final,source_generation_id,
                audio_sent_start_ms,audio_sent_end_ms) VALUES(%s,%s,%s,%s,true,%s,%s,%s)
                ON CONFLICT(call_id,source_generation_id,speaker) DO UPDATE SET text=utterances.text
                WHERE utterances.text=EXCLUDED.text AND
                utterances.audio_sent_end_ms IS NOT DISTINCT FROM EXCLUDED.audio_sent_end_ms RETURNING id""",
                (
                    uuid.uuid4(),
                    call_uuid(call_id),
                    speaker,
                    text,
                    generation,
                    0 if sent_ms is not None else None,
                    sent_ms,
                ),
            ).fetchone()
            if not saved:
                raise ValueError("utterance conflict")

        await self.run(call_id, save)

    async def note(self, call_id, note, version):
        note = Note.model_validate(note.model_dump())
        if type(version) is not int or not 1 <= version <= 2147483647:
            raise ValueError("invalid note version")
        note_id = uuid.uuid5(call_uuid(call_id), "note:" + str(version))

        def save(c, row):
            self.active(row)
            saved = c.execute(
                """INSERT INTO notes(id,call_id,note_version,text,confirmed) VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT(call_id,note_version) DO UPDATE SET confirmed=EXCLUDED.confirmed
                WHERE notes.text=EXCLUDED.text RETURNING id""",
                (
                    note_id,
                    call_uuid(call_id),
                    version,
                    note.model_dump_json(exclude={"confirmed"}),
                    note.confirmed,
                ),
            ).fetchone()
            if not saved:
                raise ValueError("note version conflict")

        await self.run(call_id, save)
        return str(note_id)

    def enqueue(self, c, call_id):
        c.execute(
            "INSERT INTO summary_jobs(call_id,scope_id,release_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (call_uuid(call_id), self.route.scope_id, self.route.release_id),
        )

    async def end(self, call_id, reason, *, answered_ms=None, ended_ms=None):
        if reason not in {"completed", "disconnected", "failed"}:
            raise ValueError("invalid call outcome")

        def save(c, row):
            if row[0] == "ended":
                return
            ended = self.observed_time(ended_ms, row) if ended_ms is not None else datetime.now(UTC)
            answered = row[1]
            if answered_ms:
                answered = self.save_answer(c, call_id, row, answered_ms)
            if answered is not None and ended < answered:
                raise ValueError("end precedes answer")
            if row[0] not in {"active", "initializing"}:
                raise ValueError("call cannot be ended")
            c.execute(
                """UPDATE calls SET status='ended',ended_at=%s,hangup_reason=%s,duration_ms=%s WHERE id=%s""",
                (
                    ended,
                    reason,
                    (ended - answered) // timedelta(milliseconds=1) if answered else None,
                    call_uuid(call_id),
                ),
            )
            if answered is not None:
                self.enqueue(c, call_id)
            else:
                c.execute(NO_ANSWER_JOB, (call_uuid(call_id),))

        await self.run(call_id, save)

    async def reconcile(self, age_seconds):
        if not 300 <= age_seconds <= 86400:
            raise ValueError("reconciliation age must be 300..86400 seconds")

        def recover(c, row):
            if row[0] not in {"active", "initializing"} or row[3] >= datetime.now(UTC) - timedelta(
                seconds=age_seconds
            ):
                return 0
            failure = "missing_end_event" if row[1] is not None else "abandoned_initialization"
            c.execute(
                """UPDATE calls SET status='ended',ended_at=now(),duration_ms=NULL,
                hangup_reason='failed',failure_code=%s WHERE id=%s""",
                (failure, call_uuid(self.route.call_id)),
            )
            if row[1] is not None:
                self.enqueue(c, self.route.call_id)
            else:
                c.execute(NO_ANSWER_JOB, (call_uuid(self.route.call_id),))
            c.execute(
                """INSERT INTO call_events(id,call_id,event_type,metadata_jsonb)
                VALUES(%s,%s,'call_reconciled',%s)""",
                (uuid.uuid4(), call_uuid(self.route.call_id), Jsonb({"reason": failure})),
            )
            return 1

        return await self.run(self.route.call_id, recover)


@dataclass(frozen=True)
class SummaryClaim:
    call_id: uuid.UUID
    scope_id: str
    release_id: str
    token: uuid.UUID


class CallSummaries:
    def __init__(self, dsn):
        self.dsn = dsn

    async def claim(self):
        def take():
            with transaction(self.dsn) as c:
                row = c.execute("""SELECT call_id,scope_id,release_id FROM summary_jobs
                    WHERE scope_id IS NOT NULL AND (status='pending' OR
                    (status='processing' AND lease_until<clock_timestamp()))
                    ORDER BY call_id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
                if not row:
                    return None
                token = uuid.uuid4()
                c.execute(
                    """UPDATE summary_jobs SET status='processing',claim_token=%s,
                    lease_until=now()+interval '60 seconds',attempts=attempts+1 WHERE call_id=%s""",
                    (token, row[0]),
                )
                return SummaryClaim(row[0], str(row[1]), str(row[2]), token)

        return await asyncio.to_thread(take)

    def _check(self, c, job):
        if not c.execute(
            """SELECT 1 FROM summary_jobs WHERE call_id=%s AND scope_id=%s AND release_id=%s
            AND status='processing' AND claim_token=%s AND lease_until>clock_timestamp() FOR UPDATE""",
            (job.call_id, job.scope_id, job.release_id, job.token),
        ).fetchone():
            raise ValueError("summary claim expired or replaced")

    def _input(self, c, job):
        self._check(c, job)
        row = c.execute(
            """SELECT r.manifest,s.manifest_digest,c.status,c.answered_at,
            s.called_e164,s.called_source,c.from_number_e164,c.from_number_source,
            c.started_at,c.ended_at,c.duration_ms,c.hangup_reason,s.profile_id
            FROM call_route_snapshots s JOIN agent_releases r ON (r.scope_id,r.id)=(s.scope_id,s.release_id)
            JOIN calls c ON c.id=s.call_id WHERE s.call_id=%s AND s.scope_id=%s AND s.release_id=%s""",
            (job.call_id, job.scope_id, job.release_id),
        ).fetchone()
        if not row or row[2] != "ended" or row[9] is None:
            raise ValueError("finalization requires an ended call")
        runtime = compile_release(json.dumps(row[0]), row[1], scope_id=job.scope_id)
        unanswered = row[3] is None
        if unanswered and not any(
            a.get("condition") == "no_answer"
            for a in row[0]["content"].get("post_call_actions", [])
        ):
            raise ValueError("Unanswered finalization requires explicit intent")
        data = (
            {"runtime": runtime, "last_note": None, "utterances": []}
            if unanswered
            else Store.read_summary(c, job.call_id, runtime)
        )
        data["post_call_actions"] = row[0]["content"].get("post_call_actions", [])
        data["event"] = {
            "schema_version": 1,
            "call_id": str(job.call_id),
            "scope_id": job.scope_id,
            "release_id": job.release_id,
            "profile_id": str(row[12]),
            "agent_name": runtime.name,
            "owner_name": row[0]["content"]["owner_display_name"],
            "called_number": row[4],
            "called_number_source": row[5],
            "caller_number": row[6],
            "caller_number_source": row[7],
            "started_at": row[8].isoformat(),
            "answered_at": row[3].isoformat() if row[3] else None,
            "ended_at": row[9].isoformat() if row[9] else None,
            "duration_ms": row[10],
            "outcome": row[11],
            "last_note": (
                {**json.loads(data["last_note"][0]), "confirmed": data["last_note"][1]}
                if data["last_note"]
                else None
            ),
        }
        return data

    async def input(self, job):
        def load():
            with transaction(self.dsn, job.scope_id) as c:
                return self._input(c, job)

        return await asyncio.to_thread(load)

    async def finish(self, job, summary=None, *, outputs=None):
        if summary is not None:
            summary = validated_summary(summary)

        def save():
            with transaction(self.dsn, job.scope_id) as c:
                data = self._input(c, job)
                unanswered = data["event"]["answered_at"] is None
                if unanswered and (summary is not None or outputs is not None):
                    raise ValueError("Unanswered calls cannot have a summary or extracted outputs")
                if summary is not None:
                    summary.confirmation_status = (
                        "confirmed" if data["last_note"] and data["last_note"][1] else "unconfirmed"
                    )
                    Store.write_summary(c, job.call_id, summary)
                status = (
                    "not_requested" if unanswered else "done" if summary is not None else "failed"
                )
                event = {
                    **data["event"],
                    "summary_status": status,
                    "summary": summary.model_dump() if summary else None,
                }
                definitions = [
                    OutputDefinition.model_validate(d)
                    for d in json.loads(data["runtime"].outputs_json or "[]")
                ]
                if definitions:
                    aliases = sorted({d.tool_alias for d in definitions if d.source == "tool"})
                    results = {}
                    if aliases and not unanswered:
                        rows = c.execute(
                            """SELECT DISTINCT ON (alias) alias,output FROM mcp_tool_executions
                            WHERE scope_id=%s AND call_id=%s AND release_id=%s AND alias=ANY(%s)
                            AND status='succeeded' AND completed_at<=%s::timestamptz
                            ORDER BY alias,ordinal DESC LIMIT 8""",
                            (
                                job.scope_id,
                                job.call_id,
                                job.release_id,
                                aliases,
                                data["event"]["ended_at"],
                            ),
                        ).fetchall()
                        results = dict(rows)
                    event.update(
                        schema_version=2, **finalized_outputs(definitions, outputs, results)
                    )
                if unanswered:
                    event["schema_version"] = 4
                    if definitions:
                        event.update(
                            outputs={d.name: None for d in definitions},
                            output_status={d.name: "unavailable" for d in definitions},
                        )
                if any(
                    a.get("transcript_policy") == POLICY
                    and matches(a.get("condition", "answered"), event)
                    for a in data["post_call_actions"]
                ):
                    rows = c.execute(
                        "SELECT speaker,left(text,8192),length(text)>8192 FROM utterances "
                        "WHERE call_id=%s AND " + VISIBLE + " ORDER BY created_at,id LIMIT %s",
                        (job.call_id, MAX_ROWS + 1),
                    ).fetchall()
                    event.update(schema_version=3, transcript=bounded_transcript(rows))
                    # Preserve the existing final-event JSONB cap, even with escaped model text.
                    if len(json.dumps(event, ensure_ascii=False).encode()) > 60000:
                        event["transcript"] = {"text": None, "status": "omitted_size_limit"}
                c.execute(
                    """INSERT INTO call_finalizations(call_id,scope_id,release_id,summary_status,payload)
                    VALUES(%s,%s,%s,%s,%s)""",
                    (
                        job.call_id,
                        job.scope_id,
                        job.release_id,
                        status,
                        Jsonb(event),
                    ),
                )
                enqueue(c, job, event)
                c.execute(
                    """UPDATE summary_jobs SET status=%s,failure_code=%s,claim_token=NULL,lease_until=NULL
                    WHERE call_id=%s""",
                    (status, "summary_failed" if status == "failed" else None, job.call_id),
                )

        await asyncio.to_thread(save)

    async def process_one(self, backend):
        from openai import RateLimitError

        job = await self.claim()
        if job is None:
            return False
        # Infrastructure/input errors retain the lease for retry; model failure is an explicit result.
        data = await self.input(job)
        if data["event"]["answered_at"] is None:
            await self.finish(job)
            return True
        prepare = getattr(
            backend, "prepare_summary_runtime", getattr(backend, "prepare_runtime", None)
        )
        if prepare is not None:
            try:
                await prepare(data["runtime"])
            except ValueError:
                # Revoked/missing credentials are an explicit unavailable summary, never fallback.
                await self.finish(job)
                return True
        outputs = None
        try:
            async with asyncio.timeout(data["runtime"].engine.turn_timeout_seconds):
                summary = await backend.summarize(data, runtime=data["runtime"])
                if isinstance(summary, PostCallAnalysis):
                    outputs, summary = summary.outputs, summary.summary
                summary = validated_summary(summary)
        except RateLimitError as error:
            if await self.defer_rate_limit(job, error.response.headers.get("retry-after")):
                return True
            summary, outputs = None, None
        except Exception:
            summary, outputs = None, None
        await self.finish(job, summary, outputs=outputs)
        return True

    async def defer_rate_limit(self, job, retry_after):
        delay = summary_retry_delay(retry_after)
        if delay is None:
            return False

        def defer():
            with transaction(self.dsn) as c:
                self._check(c, job)
                attempts = c.execute(
                    "SELECT attempts FROM summary_jobs WHERE call_id=%s", (job.call_id,)
                ).fetchone()[0]
                if attempts >= 3:
                    return False
                # Reuse the fenced lease as cooldown; other jobs continue without sleeping.
                c.execute(
                    """UPDATE summary_jobs SET lease_until=clock_timestamp()+%s*interval '1 second',
                    failure_code='provider_rate_limited' WHERE call_id=%s""",
                    (delay, job.call_id),
                )
                return True

        return await asyncio.to_thread(defer)
