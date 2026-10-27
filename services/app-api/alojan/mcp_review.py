"""Private operator CLI: review exact read-only tool semantics, never remote annotations."""

import argparse
import os
import uuid

from psycopg.types.json import Jsonb

from alojan.auth import connection
from alojan.mcp_tools import current_tools, validate_tool


def approve(dsn, scope, reference, digest, *, reviewer, evidence):
    if any(
        not isinstance(v, str) or not v.strip() or not v.isprintable() or len(v) > limit
        for v, limit in ((reviewer, 100), (evidence, 1000))
    ):
        raise ValueError("Bounded reviewer and evidence required")
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
        # Coordinate operator approvals and explicit discovery requests.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,20))", (str(scope),))
        _, discovery, tools = current_tools(conn, scope, reference)
        tool = next((t for t in tools if t["digest"] == digest), None)
        if tool is None:
            raise ValueError("Exact current tool digest required")
        validate_tool(tool)
        existing = conn.execute(
            "SELECT id FROM mcp_tool_reviews WHERE scope_id=%s AND connection_id=%s AND tool_digest=%s AND enabled",
            (scope, reference, digest),
        ).fetchone()
        if existing:
            return str(existing[0])
        if (
            conn.execute(
                "SELECT count(*) FROM mcp_tool_reviews WHERE scope_id=%s", (scope,)
            ).fetchone()[0]
            >= 1000
        ):
            raise ValueError("MCP review limit")
        identity = uuid.uuid4()
        conn.execute(
            """INSERT INTO mcp_tool_reviews(id,scope_id,connection_id,discovery_id,
            tool_name,tool_digest,tool,capability,reviewed_by,evidence)
            VALUES(%s,%s,%s,%s,%s,%s,%s,'read',%s,%s)""",
            (
                identity,
                scope,
                reference,
                discovery,
                tool["name"],
                digest,
                Jsonb(tool),
                reviewer,
                evidence,
            ),
        )
        return str(identity)


def revoke(dsn, scope, review):
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
        if not conn.execute(
            "UPDATE mcp_tool_reviews SET enabled=false WHERE scope_id=%s AND id=%s RETURNING id",
            (scope, review),
        ).fetchone():
            raise ValueError("MCP review not found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True, type=uuid.UUID)
    commands = parser.add_subparsers(dest="command", required=True)
    allow = commands.add_parser("approve-read")
    allow.add_argument("--connection", required=True, type=uuid.UUID)
    allow.add_argument("--tool-digest", required=True)
    allow.add_argument("--reviewer", required=True)
    allow.add_argument("--evidence", required=True)
    deny = commands.add_parser("revoke")
    deny.add_argument("--review", required=True, type=uuid.UUID)
    args = parser.parse_args()
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    if args.command == "revoke":
        revoke(dsn, args.scope, args.review)
        print("MCP review revoked")
    else:
        print(
            approve(
                dsn,
                args.scope,
                args.connection,
                args.tool_digest,
                reviewer=args.reviewer,
                evidence=args.evidence,
            )
        )


if __name__ == "__main__":
    main()
