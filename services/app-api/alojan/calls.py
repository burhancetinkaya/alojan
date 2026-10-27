"""Bounded read-only call history, authorized by immutable routing ownership."""

import json
import uuid

from psycopg.rows import dict_row

from alojan.call_search import filters, fingerprint, decode_cursor, encode_cursor
from alojan.auth import AuthError
from alojan.deliveries import metadata

PAGE_SIZE = 50
TRANSCRIPT_VISIBLE = """is_final AND (speaker='caller' OR
    (speaker='assistant' AND audio_sent_end_ms>audio_sent_start_ms))"""
COLUMNS = """s.call_id AS id,s.profile_id,s.release_id,s.called_e164 AS called_number,
    s.created_at,c.status,c.started_at,c.answered_at,c.ended_at,c.duration_ms,
    c.hangup_reason,c.failure_code,
    r.manifest->'content'->>'agent_name' AS agent_name,
    r.manifest->'content'->>'owner_display_name' AS owner_name,r.revision,
    COALESCE(f.summary_status,j.status,'not_requested') AS summary_status"""
JOINS = """FROM call_route_snapshots s JOIN calls c ON c.id=s.call_id
    JOIN agent_releases r ON (r.scope_id,r.id)=(s.scope_id,s.release_id)
    LEFT JOIN call_finalizations f ON (f.scope_id,f.call_id)=(s.scope_id,s.call_id)
    LEFT JOIN summary_jobs j ON j.call_id=s.call_id"""


def identifier(value, code):
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except (ValueError, TypeError, AttributeError):
        raise AuthError(code, 400) from None


class Calls:
    def __init__(self, accounts):
        self.accounts = accounts

    def transcript(self, token, scope, call, *, after=None):
        after = identifier(after, "invalid_transcript_cursor")
        with self.accounts.workspace(token, scope) as (conn, _):
            if not conn.execute(
                "SELECT 1 FROM call_route_snapshots WHERE scope_id=%s AND call_id=%s",
                (scope, call),
            ).fetchone():
                raise AuthError("not_found", 404)
            where, args = "call_id=%s AND " + TRANSCRIPT_VISIBLE, [call]
            if after is not None:
                boundary = conn.execute(
                    "SELECT created_at,id FROM utterances WHERE " + where + " AND id=%s",
                    [*args, after],
                ).fetchone()
                if not boundary:
                    raise AuthError("invalid_transcript_cursor", 400)
                where += " AND (created_at,id)>(%s,%s)"
                args.extend(boundary)
            with conn.cursor(row_factory=dict_row) as c:
                rows = c.execute(
                    "SELECT id,speaker,text,created_at,audio_sent_start_ms,audio_sent_end_ms, "
                    "CASE WHEN speaker='assistant' AND source_generation_id ~ '-w[0-9]+$' "
                    "THEN 'waiting' ELSE 'response' END AS kind "
                    "FROM utterances WHERE " + where + " ORDER BY created_at,id LIMIT %s",
                    [*args, PAGE_SIZE + 1],
                ).fetchall()
            return dict(
                utterances=[metadata(r) for r in rows[:PAGE_SIZE]],
                next_cursor=str(rows[PAGE_SIZE - 1]["id"]) if len(rows) > PAGE_SIZE else None,
            )

    def list(self, token, scope, *, agent=None, after=None, **search):
        agent = identifier(agent, "invalid_call_filter")
        extra, extra_args = filters(search)
        digest = fingerprint(scope, agent, search)
        after = decode_cursor(after, digest, filtered=bool(search))
        if search.get("search_in") == "transcript":
            from alojan.personal_tokens import BearerCredential

            if isinstance(token, BearerCredential):
                token = BearerCredential(
                    token.value, token.scope, token.required | {"transcripts:read"}
                )
        with self.accounts.workspace(token, scope) as (conn, _):
            where, args = "s.scope_id=%s", [scope]
            if agent is not None:
                if not conn.execute(
                    "SELECT 1 FROM assistant_profiles WHERE scope_id=%s AND id=%s", (scope, agent)
                ).fetchone():
                    raise AuthError("not_found", 404)
                where += " AND s.profile_id=%s"
                args.append(agent)
            where += extra
            args.extend(extra_args)
            if after is not None:
                boundary = conn.execute(
                    "SELECT s.created_at,s.call_id "
                    + JOINS
                    + " WHERE "
                    + where
                    + " AND s.call_id=%s",
                    [*args, after],
                ).fetchone()
                if not boundary:
                    raise AuthError("invalid_call_cursor", 400)
                where += " AND (s.created_at,s.call_id)<(%s,%s)"
                args.extend(boundary)
            with conn.cursor(row_factory=dict_row) as c:
                rows = c.execute(
                    "SELECT "
                    + COLUMNS
                    + " "
                    + JOINS
                    + " WHERE "
                    + where
                    + " ORDER BY s.created_at DESC,s.call_id DESC LIMIT %s",
                    [*args, PAGE_SIZE + 1],
                ).fetchall()
            return dict(
                calls=[metadata(r) for r in rows[:PAGE_SIZE]],
                next_cursor=encode_cursor(rows[PAGE_SIZE - 1]["id"], digest, filtered=bool(search))
                if len(rows) > PAGE_SIZE
                else None,
                search_source=search.get("search_in", "summary") if "query" in search else None,
            )

    def get(self, token, scope, call):
        with self.accounts.workspace(token, scope) as (conn, _):
            # One statement gives a consistent snapshot without locking live call rows.
            with conn.cursor(row_factory=dict_row) as c:
                row = c.execute(
                    "SELECT "
                    + COLUMNS
                    + """,c.from_number_e164 AS caller_number,
                    c.from_number_source AS caller_number_source,f.payload->'summary' AS summary,
                    f.payload->'outputs' AS outputs, f.payload->'output_status' AS output_status,
                    n.text AS note_text,n.confirmed AS note_confirmed,n.note_version,
                    COALESCE((SELECT jsonb_agg(jsonb_build_object(
                        'id',a.id,'alias',a.alias,'status',a.status,'attempts',a.attempts,
                        'failure_code',a.failure_code,'updated_at',a.updated_at,
                        'retry_queued',EXISTS(SELECT 1 FROM action_retry_requests q
                            WHERE q.scope_id=a.scope_id AND q.job_id=a.id
                            AND q.generation=a.retry_generation+1)) ORDER BY a.created_at,a.id)
                        FROM action_jobs a WHERE a.scope_id=s.scope_id AND a.call_id=s.call_id),
                        '[]'::jsonb) AS deliveries """
                    + JOINS
                    + """
                    LEFT JOIN LATERAL (SELECT text,confirmed,note_version FROM notes
                        WHERE call_id=s.call_id ORDER BY note_version DESC LIMIT 1) n ON true
                    WHERE s.scope_id=%s AND s.call_id=%s""",
                    (scope, call),
                ).fetchone()
            if not row:
                raise AuthError("not_found", 404)
            text = row.pop("note_text")
            confirmed, version = row.pop("note_confirmed"), row.pop("note_version")
            row["note"] = None
            if text is not None:
                note = json.loads(text)
                row["note"] = {
                    key: note.get(key)
                    for key in ("caller_name", "caller_number", "subject", "message")
                }
                row["note"].update(confirmed=confirmed, version=version)
            return metadata(row)
