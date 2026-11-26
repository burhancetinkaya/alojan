"""Workspace-scoped submission and history of one-way announcements."""

import hashlib
import json
import re
import uuid

from psycopg.rows import dict_row
from pydantic import ValidationError

from alojan.auth import AuthError
from alojan.calls import PAGE_SIZE, identifier
from alojan.deliveries import metadata
from alojan_contracts.configuration import OutboundSettings


ELIGIBLE = """FROM phone_numbers n
    JOIN number_bindings b ON (b.scope_id,b.number_id,b.id)=(n.scope_id,n.id,n.active_binding_id)
    JOIN agent_publications p ON (p.scope_id,p.profile_id,p.release_id)=(b.scope_id,b.profile_id,b.release_id)
    JOIN agent_releases r ON (r.scope_id,r.profile_id,r.id)=(b.scope_id,b.profile_id,b.release_id)
    WHERE n.scope_id=%s AND n.enabled AND n.status='verified'
    AND r.manifest->'content'->'outbound'->'enabled'='true'::jsonb"""
TIMERS = {"ring_timeout_seconds", "post_playback_seconds"}
HISTORY = """o.id,o.profile_id AS agent_id,r.manifest->'content'->>'agent_name' AS agent_name,
    o.status,o.queued_at,o.answered_at,o.ended_at,o.failure_code"""
FROM_HISTORY = """FROM outbound_calls o JOIN agent_releases r
    ON (r.scope_id,r.profile_id,r.id)=(o.scope_id,o.profile_id,o.release_id) WHERE o.scope_id=%s"""


# Turkish national numbering plan. Exclude non-geographic ranges, including
# 392 (Northern Cyprus), paging and personal numbers that share a mobile prefix.
GEOGRAPHIC = re.compile(
    r"(?:2(?:1[26]|[28][2468]|[3-5][268]|[67][246])"
    r"|3(?:[13][28]|[24-6][2468]|[78][02468])"
    r"|4(?:[16][246]|[23578][2468]|4[26]))[0-9]{7}"
)
MOBILE = re.compile(
    r"5(?:[03-5][0-9]|1[06]|24|6[24]|7[245]|9[46])[0-9]{7}"
    r"|5(?:61(?:011|61[0-9])|82[2-5][0-9]{2})[0-9]{4}"
)


def destination(value):
    if not isinstance(value, str) or len(value) > 32:
        raise AuthError("invalid_destination", 400)
    compact = re.sub(r"[ ()-]", "", value)
    match = re.fullmatch(r"(?:\+90|0090|0)?([2345][0-9]{9})", compact)
    if not match or not (GEOGRAPHIC.fullmatch(match[1]) or MOBILE.fullmatch(match[1])):
        raise AuthError("invalid_destination", 400)
    return "+90" + match[1]


class OutboundCalls:
    def __init__(self, accounts):
        self.accounts = accounts

    def agents(self, token, scope):
        with (
            self.accounts.workspace(token, scope) as (conn, _),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            rows = cur.execute(
                """SELECT b.profile_id AS agent_id,n.e164 AS caller,r.manifest->'content'->>'agent_name' AS name,
                r.manifest->'content'->>'voice' AS voice,r.manifest->'content'->'outbound' AS settings """
                + ELIGIBLE
                + " ORDER BY name,n.e164",
                (scope,),
            ).fetchall()
            return {"agents": [metadata(row) for row in rows]}

    def submit(self, token, scope, body, key):
        try:
            operation = uuid.UUID(key or "")
        except ValueError:
            raise AuthError("operation_key_required", 428) from None
        if not {"agent_id", "to", "text"} <= body.keys() or body.keys() - (
            {"agent_id", "to", "text", "caller"} | TIMERS
        ):
            raise AuthError("invalid_fields", 400)
        agent = identifier(body["agent_id"], "invalid_fields")
        to = destination(body["to"])
        text = body["text"]
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 2000
            or any(not ch.isprintable() and ch not in "\n\t" for ch in text)
        ):
            raise AuthError("invalid_announcement", 400)
        caller = body.get("caller")
        if caller is not None and (
            not isinstance(caller, str) or not re.fullmatch(r"\+90850[0-9]{7}", caller)
        ):
            raise AuthError("invalid_fields", 400)
        overrides = {k: body[k] for k in TIMERS if k in body}
        try:
            OutboundSettings(**overrides)
        except ValidationError:
            raise AuthError("invalid_outbound_timing", 400) from None
        digest = hashlib.sha256(
            json.dumps(body | {"to": to}, sort_keys=True, ensure_ascii=False).encode()
        ).digest()
        with self.accounts.workspace(token, scope, roles=("owner", "editor")) as (conn, user):
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{scope}:{operation}",)
            )
            previous = conn.execute(
                """SELECT id,request_digest FROM outbound_calls WHERE scope_id=%s AND operation_key=%s
                UNION ALL SELECT id,request_digest FROM outbound_receipts WHERE scope_id=%s AND operation_key=%s""",
                (scope, operation, scope, operation),
            ).fetchone()
            if previous:
                if bytes(previous[1]) != digest:
                    raise AuthError("operation_key_conflict", 409)
                return {"id": str(previous[0]), "status": "queued"}
            rows = conn.execute(
                "SELECT n.id,b.id,b.release_id,b.node_id,n.e164,r.manifest->'content'->'outbound' "
                + ELIGIBLE
                + " AND b.profile_id=%s"
                + (" AND n.e164=%s" if caller else "")
                + " LIMIT 2 FOR SHARE OF n",
                (scope, agent, caller) if caller else (scope, agent),
            ).fetchall()
            if len(rows) != 1:
                raise AuthError("outbound_line_unavailable", 409)
            number, binding, release, node, line, settings = rows[0]
            policy = OutboundSettings(**(settings | overrides))
            call = uuid.uuid4()
            conn.execute(
                """INSERT INTO outbound_calls(id,scope_id,requested_by,operation_key,request_digest,
                number_id,binding_id,profile_id,release_id,node_id,caller_e164,destination,message,
                ring_timeout_seconds,post_playback_seconds) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    call,
                    scope,
                    user["id"],
                    operation,
                    digest,
                    number,
                    binding,
                    agent,
                    release,
                    node,
                    line,
                    to,
                    text,
                    policy.ring_timeout_seconds,
                    policy.post_playback_seconds,
                ),
            )
            return {"id": str(call), "status": "queued"}

    def history(self, token, scope, call=None, after=None):
        with (
            self.accounts.workspace(token, scope) as (conn, _),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            if call:
                row = cur.execute(
                    "SELECT "
                    + HISTORY
                    + ",o.destination,o.message,o.caller_e164,o.release_id,o.ring_timeout_seconds,o.post_playback_seconds "
                    + FROM_HISTORY
                    + " AND o.id=%s",
                    (scope, call),
                ).fetchone()
                if not row:
                    raise AuthError("not_found", 404)
                return metadata(row)
            args = [scope]
            where = ""
            if after:
                boundary = conn.execute(
                    "SELECT queued_at,id FROM outbound_calls WHERE scope_id=%s AND id=%s",
                    (scope, identifier(after, "invalid_call_filter")),
                ).fetchone()
                if not boundary:
                    raise AuthError("invalid_call_filter", 400)
                where = " AND (o.queued_at,o.id)<(%s,%s)"
                args.extend(boundary)
            rows = cur.execute(
                "SELECT "
                + HISTORY
                + ",'***' || right(o.destination,4) AS destination "
                + FROM_HISTORY
                + where
                + " ORDER BY o.queued_at DESC,o.id DESC LIMIT %s",
                [*args, PAGE_SIZE + 1],
            ).fetchall()
            return {
                "calls": [metadata(r) for r in rows[:PAGE_SIZE]],
                "next_cursor": str(rows[PAGE_SIZE - 1]["id"]) if len(rows) > PAGE_SIZE else None,
            }
