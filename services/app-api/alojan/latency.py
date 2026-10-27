"""Bounded, content-free gateway timing import and workspace distributions."""

import argparse
from collections import Counter
import json
import math
import os
import re
import statistics
import sys
import uuid

from psycopg import sql
from psycopg.rows import dict_row

from alojan.auth import AuthError, connection
from alojan.calls import identifier
from alojan.roles import dedicated_role
from alojan_contracts.routing import node_identifier

FIELDS = (
    "endpoint_silence_audio_ms",
    "asr_finalize_ms",
    "agent_first_phrase_ms",
    "tts_first_chunk_ms",
    "pcm_to_output_ms",
    "endpoint_to_audio_ms",
    "vad_end_to_audio_estimate_ms",
)
CALL_LIMIT = 200
SAMPLE_LIMIT = 5000


def parse(line):
    if not line.startswith("event=turn_latency "):
        return None
    if len(line) > 4096:
        raise ValueError("oversized timing")
    pairs = [item.split("=", 1) for item in line.split()]
    if any(len(item) != 2 for item in pairs) or len(dict(pairs)) != len(pairs):
        raise ValueError("invalid timing")
    record = dict(pairs)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", record.get("call_trace", "")) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,142}", record.get("generation", "")
    ):
        raise ValueError("invalid timing identity")
    if record.get("status") not in {"completed", "failed", "cancelled", "interrupted"}:
        raise ValueError("invalid timing status")
    error = int(record["error"])
    if not 0 <= error <= 1000 or not record.get("kind"):
        raise ValueError("invalid timing outcome")
    values = []
    for name in FIELDS:
        value = int(record[name])
        if not -1 <= value <= 600000:
            raise ValueError("invalid timing duration")
        values.append(None if value == -1 else value)
    # Same stable identity as call initialization; never use caller identity for ownership.
    return (
        uuid.uuid5(uuid.NAMESPACE_URL, "alojan:call:" + record["call_trace"]),
        record["generation"],
        record["status"],
        "response" if record["kind"] == "response" else "recovery",
        error,
        *values,
    )


def ingest(dsn, node, lines):
    node = node_identifier(node)
    counts = Counter(imported=0, duplicate_or_unowned=0, malformed=0, lines=0)
    with connection(dsn) as conn:
        # Serialize overlap/replay and enforce a per-call ceiling without live call locks.
        conn.execute("SELECT pg_advisory_xact_lock(714219)")
        for line in lines:
            counts["lines"] += 1
            if counts["lines"] > 10000:
                raise ValueError("timing batch exceeds 10000 lines")
            try:
                record = parse(line)
            except (ValueError, KeyError):
                counts["malformed"] += 1
                continue
            if record is None:
                continue
            call, generation, status, kind, error, *values = record
            result = conn.execute(
                sql.SQL("""INSERT INTO call_latency(scope_id,call_id,release_id,generation,status,kind,error_code,{})
                SELECT s.scope_id,s.call_id,s.release_id,%s,%s,%s,%s,{}
                FROM call_route_snapshots s WHERE s.call_id=%s AND s.node_id=%s
                AND (SELECT count(*) FROM call_latency WHERE call_id=s.call_id)<1000
                ON CONFLICT DO NOTHING""").format(
                    sql.SQL(",").join(map(sql.Identifier, FIELDS)),
                    sql.SQL(",").join(sql.Placeholder() for _ in FIELDS),
                ),
                (generation, status, kind, error, *values, call, node),
            )
            counts["imported" if result.rowcount else "duplicate_or_unowned"] += 1
    return dict(counts)


def grant_ingest(dsn, role, node):
    node = node_identifier(node)
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table, permissions in (
            ("call_route_snapshots", "SELECT(scope_id,call_id,release_id,node_id)"),
            ("call_latency", "SELECT(call_id), INSERT"),
        ):
            conn.execute(
                sql.SQL("GRANT {} ON {} TO {}").format(
                    sql.SQL(permissions), sql.Identifier(schema, table), target
                )
            )
        for table, command, predicate in (
            ("call_route_snapshots", "SELECT", sql.SQL("node_id={}").format(sql.Literal(node))),
            ("call_latency", "SELECT", sql.SQL("true")),
            (
                "call_latency",
                "INSERT",
                sql.SQL(
                    "EXISTS(SELECT 1 FROM {} s WHERE "
                    "(s.scope_id,s.call_id,s.release_id)=(call_latency.scope_id,call_latency.call_id,call_latency.release_id) "
                    "AND s.node_id={})"
                ).format(sql.Identifier(schema, "call_route_snapshots"), sql.Literal(node)),
            ),
        ):
            name = sql.Identifier("latency_" + command.lower() + "_" + str(oid))
            relation = sql.Identifier(schema, table)
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(name, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR {} TO {} {} ({})").format(
                    name,
                    relation,
                    sql.SQL(command),
                    target,
                    sql.SQL("WITH CHECK" if command == "INSERT" else "USING"),
                    predicate,
                )
            )


class Latency:
    def __init__(self, accounts):
        self.accounts = accounts

    def get(self, token, scope, *, agent=None, call=None):
        agent = identifier(agent, "invalid_call_filter")
        call = identifier(call, "invalid_call_filter")
        with self.accounts.workspace(token, scope) as (conn, _):
            where, args = "scope_id=%s", [scope]
            for value, column, table in (
                (agent, "profile_id", "assistant_profiles"),
                (call, "call_id", "call_route_snapshots"),
            ):
                if value is None:
                    continue
                key = "id" if table == "assistant_profiles" else "call_id"
                if not conn.execute(
                    f"SELECT 1 FROM {table} WHERE scope_id=%s AND {key}=%s", (scope, value)
                ).fetchone():
                    raise AuthError("not_found", 404)
                where += f" AND {column}=%s"
                args.append(value)
            # Indexed recent-call window bounds both SQL work and response aggregation.
            routes = conn.execute(
                "SELECT call_id,created_at FROM call_route_snapshots WHERE "
                + where
                + " ORDER BY created_at DESC,call_id DESC LIMIT %s",
                [*args, CALL_LIMIT + 1],
            ).fetchall()
            with conn.cursor(row_factory=dict_row) as c:
                rows = c.execute(
                    """SELECT t.* FROM unnest(%s::uuid[]) WITH ORDINALITY r(id,position)
                    CROSS JOIN LATERAL (SELECT status,kind,error_code,imported_at,"""
                    + ",".join(FIELDS)
                    + """ FROM call_latency WHERE call_id=r.id
                    ORDER BY generation LIMIT 1000) t ORDER BY r.position LIMIT %s""",
                    ([r[0] for r in routes[:CALL_LIMIT]], SAMPLE_LIMIT + 1),
                ).fetchall()
        truncated = len(rows) > SAMPLE_LIMIT
        rows = rows[:SAMPLE_LIMIT]
        eligible = [
            r
            for r in rows
            if r["status"] == "completed" and r["kind"] == "response" and r["error_code"] == 0
        ]
        metrics = {}
        for name in FIELDS:
            samples = sorted(r[name] for r in eligible if r[name] is not None)
            metrics[name] = dict(
                samples=len(samples),
                missing=len(eligible) - len(samples),
                p50_ms=statistics.median(samples) if samples else None,
                p95_ms=samples[math.ceil(0.95 * len(samples)) - 1] if samples else None,
                max_ms=max(samples) if samples else None,
            )
        return dict(
            calls_considered=min(len(routes), CALL_LIMIT),
            call_limit=CALL_LIMIT,
            has_older_calls=len(routes) > CALL_LIMIT,
            sample_limit=SAMPLE_LIMIT,
            truncated=truncated,
            observed_turns=len(rows),
            eligible_turns=len(eligible),
            excluded_turns=len(rows) - len(eligible),
            status_counts=dict(Counter(r["status"] for r in rows)),
            latest_import_at=max((r["imported_at"] for r in rows), default=None).isoformat()
            if rows
            else None,
            metrics=metrics,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(ingest(os.environ["ALOJAN_DATABASE_URL"], args.node, sys.stdin)))
    except Exception:
        raise SystemExit("Timing import failed; inspect private configuration") from None


if __name__ == "__main__":
    main()
