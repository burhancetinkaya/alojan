"""Existing PostgreSQL schema; no notifications or raw audio writes."""

import asyncio
import json
import uuid

import psycopg
from psycopg.types.json import Jsonb
from alojan_contracts.runtime import compile_release


def call_uuid(call_id):
    return uuid.uuid5(uuid.NAMESPACE_URL, "alojan:call:" + call_id)


class Store:
    def __init__(self, dsn):
        self.dsn = dsn

    def for_route(self, route):
        from .records import CallRecords

        return CallRecords(self.dsn, route)

    def transaction(self, operation):
        with psycopg.connect(self.dsn, connect_timeout=3) as conn:
            conn.execute("SET LOCAL statement_timeout=3000")
            return operation(conn)

    async def run(self, operation):
        return await asyncio.to_thread(self.transaction, operation)

    async def start(self, call_id, number):
        await self.run(
            lambda c: c.execute(
                "INSERT INTO calls(id,sip_call_id,direction,status,from_number_e164,from_number_source) "
                "VALUES(%s,%s,'inbound','active',%s,%s) ON CONFLICT(id) DO NOTHING",
                (call_uuid(call_id), call_id, number, "gateway_hint" if number else "unknown"),
            )
        )

    async def utterance(self, call_id, generation, speaker, text, sent_ms=None):
        await self.run(
            lambda c: c.execute(
                "INSERT INTO utterances(id,call_id,speaker,text,is_final,source_generation_id,"
                "audio_sent_start_ms,audio_sent_end_ms) VALUES(%s,%s,%s,%s,true,%s,%s,%s) "
                "ON CONFLICT(call_id,source_generation_id,speaker) DO NOTHING",
                (
                    uuid.uuid4(),
                    call_uuid(call_id),
                    speaker,
                    text,
                    generation,
                    0 if sent_ms is not None else None,
                    sent_ms,
                ),
            )
        )

    async def note(self, call_id, note, version):
        note_id = uuid.uuid5(call_uuid(call_id), "note:" + str(version))

        def save(c):
            status = c.execute(
                "SELECT status FROM calls WHERE id=%s FOR UPDATE", (call_uuid(call_id),)
            ).fetchone()
            if status != ("active",):
                raise ValueError("call no longer accepts notes")
            saved = c.execute(
                "INSERT INTO notes(id,call_id,note_version,text,confirmed) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(call_id,note_version) DO UPDATE "
                "SET confirmed=EXCLUDED.confirmed WHERE notes.text=EXCLUDED.text RETURNING id",
                (
                    note_id,
                    call_uuid(call_id),
                    version,
                    note.model_dump_json(exclude={"confirmed"}),
                    note.confirmed,
                ),
            ).fetchone()
            if saved is None:
                raise ValueError("note version conflict")

        await self.run(save)
        return str(note_id)

    async def end(self, call_id, reason):
        def save(c):
            c.execute(
                "UPDATE calls SET status='ended',ended_at=COALESCE(ended_at,now()),"
                "hangup_reason=COALESCE(hangup_reason,%s) WHERE id=%s",
                (reason, call_uuid(call_id)),
            )
            c.execute(
                "INSERT INTO summary_jobs(call_id) VALUES(%s) ON CONFLICT DO NOTHING",
                (call_uuid(call_id),),
            )

        await self.run(save)

    async def pending(self):
        return await self.run(
            lambda c: c.execute(
                "SELECT call_id FROM summary_jobs WHERE status='pending' AND scope_id IS NULL ORDER BY call_id LIMIT 1"
            ).fetchone()
        )

    async def reconcile_stale(self, age_seconds):
        """Recover missing end events after the deployment's hard call limit plus margin."""
        if not 300 <= age_seconds <= 86400:
            raise ValueError("reconciliation age must be 300..86400 seconds")

        def recover(c):
            # Setup never became an answered conversation; do not create post-call work.
            abandoned = c.execute(
                "WITH stale AS (SELECT id FROM calls WHERE status='initializing' AND ended_at IS NULL "
                "AND started_at < now()-make_interval(secs=>%s) "
                "AND NOT EXISTS (SELECT 1 FROM call_route_snapshots s WHERE s.call_id=calls.id) "
                "ORDER BY started_at LIMIT 100 FOR UPDATE SKIP LOCKED) "
                "UPDATE calls SET status='ended',ended_at=now(),duration_ms=NULL,"
                "hangup_reason='failed',failure_code='abandoned_initialization' "
                "WHERE id IN (SELECT id FROM stale) RETURNING id",
                (age_seconds,),
            ).fetchall()
            # Recovery time is not a measured hangup time; leave duration unknown.
            rows = c.execute(
                "WITH stale AS (SELECT id FROM calls WHERE status='active' AND ended_at IS NULL "
                "AND started_at < now()-make_interval(secs=>%s) "
                "AND NOT EXISTS (SELECT 1 FROM call_route_snapshots s WHERE s.call_id=calls.id) "
                "ORDER BY started_at LIMIT 100 FOR UPDATE SKIP LOCKED) "
                "UPDATE calls SET status='ended',ended_at=now(),duration_ms=NULL,"
                "hangup_reason='failed',failure_code='missing_end_event' "
                "WHERE id IN (SELECT id FROM stale) RETURNING id",
                (age_seconds,),
            ).fetchall()
            for (cid,) in rows:
                c.execute(
                    "INSERT INTO summary_jobs(call_id) VALUES(%s) ON CONFLICT DO NOTHING", (cid,)
                )
                c.execute(
                    "INSERT INTO call_events(id,call_id,event_type,metadata_jsonb) "
                    "VALUES(%s,%s,'call_reconciled',%s)",
                    (uuid.uuid4(), cid, Jsonb({"reason": "missing_end_event"})),
                )
            return len(rows) + len(abandoned)

        return await self.run(recover)

    async def summary_input(self, cid):
        def load(c):
            runtime = None
            if c.execute("SELECT to_regclass('call_route_snapshots')").fetchone()[0]:
                # Fail if RLS would hide a route and accidentally select legacy identity.
                # The current legacy worker is privileged; a scoped worker role is a rollout gate.
                c.execute("SET LOCAL row_security=off")
                snapshot = c.execute(
                    "SELECT scope_id,release_id,manifest_digest FROM call_route_snapshots WHERE call_id=%s",
                    (cid,),
                ).fetchone()
                c.execute("SET LOCAL row_security=on")
                if snapshot:
                    scope, release, digest = snapshot
                    c.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
                    row = c.execute(
                        "SELECT manifest FROM agent_releases WHERE scope_id=%s AND id=%s",
                        (scope, release),
                    ).fetchone()
                    if not row:
                        raise ValueError("Pinned summary release unavailable")
                    runtime = compile_release(json.dumps(row[0]), digest)
            return self.read_summary(c, cid, runtime)

        return await self.run(load)

    @staticmethod
    def read_summary(c, cid, runtime):
        byte_limit = runtime.engine.summary_input_max_bytes if runtime else 12000
        rows = c.execute(
            "SELECT speaker,text FROM utterances WHERE call_id=%s "
            "ORDER BY created_at DESC,id DESC LIMIT 100",
            (cid,),
        ).fetchall()
        # Preserve the most recent corrections and bound the post-call model input.
        recent = []
        size = 0
        for speaker, text in rows:
            if size + len(text.encode()) > byte_limit:
                break
            recent.append((speaker, text))
            size += len(text.encode())
        note = c.execute(
            "SELECT text,confirmed FROM notes WHERE call_id=%s ORDER BY note_version DESC LIMIT 1",
            (cid,),
        ).fetchone()
        return {"utterances": list(reversed(recent)), "last_note": note, "runtime": runtime}

    async def summary_result(self, cid, summary=None):
        def save(c):
            row = c.execute("SELECT scope_id FROM summary_jobs WHERE call_id=%s", (cid,)).fetchone()
            if row and row[0] is not None:
                raise ValueError("routed summary requires a scoped claim")
            if summary is not None:
                self.write_summary(c, cid, summary)
            c.execute(
                "UPDATE summary_jobs SET status=%s,attempts=attempts+1,failure_code=%s "
                "WHERE call_id=%s",
                ("done" if summary else "failed", None if summary else "summary_failed", cid),
            )

        await self.run(save)

    @staticmethod
    def write_summary(c, cid, summary):
        c.execute(
            "INSERT INTO call_summaries(call_id,caller_name,subject,summary,urgency,"
            "requested_action,confirmation_status,json_schema_version,detail_jsonb) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s) ON CONFLICT(call_id) DO UPDATE SET "
            "detail_jsonb=EXCLUDED.detail_jsonb,summary=EXCLUDED.summary,"
            "caller_name=EXCLUDED.caller_name,subject=EXCLUDED.subject,"
            "urgency=EXCLUDED.urgency,requested_action=EXCLUDED.requested_action,"
            "confirmation_status=EXCLUDED.confirmation_status",
            (
                cid,
                summary.caller_name,
                summary.subject,
                summary.summary,
                summary.urgency,
                summary.requested_action,
                summary.confirmation_status,
                Jsonb(summary.model_dump()),
            ),
        )
