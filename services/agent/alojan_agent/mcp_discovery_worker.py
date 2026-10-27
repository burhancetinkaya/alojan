"""Independent bounded MCP discovery consumer. Never executes tools or reads calls."""

import argparse
import asyncio
import logging
import os
import uuid

import psycopg
from psycopg.types.json import Jsonb
from psycopg.conninfo import conninfo_to_dict

from alojan_contracts.mcp import endpoint
from alojan_contracts.secrets import SecretBox
from alojan_agent.mcp_discovery import discover


def connection(dsn):
    options = (
        conninfo_to_dict(dsn).get("options", "") + " -c statement_timeout=5000 -c lock_timeout=3000"
    )
    return psycopg.connect(dsn, connect_timeout=3, options=options)


def claim(dsn):
    with connection(dsn) as conn:
        conn.execute("""UPDATE mcp_discovery_jobs SET status='failed',failure_code='lease_expired',
            lease_until=NULL,completed_at=now() WHERE status='running' AND lease_until<now()""")
        row = conn.execute("""SELECT id,scope_id,connection_id FROM mcp_discovery_jobs
            WHERE status='queued' ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
        if not row:
            return None
        token = uuid.uuid4()
        conn.execute(
            """UPDATE mcp_discovery_jobs SET status='running',claim_token=%s,
            lease_until=now()+interval '30 seconds' WHERE id=%s""",
            (token, row[0]),
        )
        return (*row, token)


def load(dsn, job):
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(job[1]),))
        return conn.execute(
            """SELECT endpoint,auth_type,ciphertext FROM mcp_connections c
            WHERE c.scope_id=%s AND c.id=%s AND c.enabled
            AND EXISTS(SELECT 1 FROM recipient_scopes s WHERE s.id=c.scope_id AND s.enabled)
            AND EXISTS(SELECT 1 FROM workspace_memberships m JOIN users u ON u.id=m.user_id
                WHERE m.scope_id=c.scope_id AND m.role='owner' AND u.enabled)""",
            (job[1], job[2]),
        ).fetchone()


def complete(dsn, job, snapshot, failure):
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(job[1]),))
        # Serialize completion with revocation; a revoked discovery cannot become ready.
        enabled = conn.execute(
            "SELECT enabled FROM mcp_connections WHERE scope_id=%s AND id=%s FOR SHARE",
            (job[1], job[2]),
        ).fetchone()
        if not enabled or not enabled[0]:
            snapshot, failure = None, "connection_revoked"
        conn.execute(
            """UPDATE mcp_discovery_jobs SET status=%s,manifest=%s,failure_code=%s,
            lease_until=NULL,completed_at=now() WHERE id=%s AND scope_id=%s
            AND status='running' AND claim_token=%s AND lease_until>now()""",
            (
                "failed" if failure else "ready",
                Jsonb(snapshot) if snapshot is not None else None,
                failure,
                job[0],
                job[1],
                job[3],
            ),
        )


def oauth_token(dsn, box, job):
    from alojan_contracts.mcp_oauth_tokens import ACCESS_SQL

    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(job[1]),))
        row = conn.execute(ACCESS_SQL, (job[1], [job[2]])).fetchone()
        if row is None:
            raise ValueError("OAuth credentials unavailable")
        return box.open(job[1], job[2], bytes(row[1]), purpose="mcp-oauth-access")


async def process_one(dsn, secrets, *, discover_tools=discover):
    job = await asyncio.to_thread(claim, dsn)
    if job is None:
        return False
    snapshot, failure = None, None
    try:
        row = await asyncio.to_thread(load, dsn, job)
        if row is None:
            failure = "connection_revoked"
        else:
            endpoint(row[0])
            token = (
                secrets.open(job[1], job[2], bytes(row[2]), purpose="mcp")
                if row[1] == "bearer"
                else None
            )
            if row[1] == "oauth":
                token = await asyncio.to_thread(oauth_token, dsn, secrets, job)
            async with asyncio.timeout(18):
                snapshot = await discover_tools(row[0], token)
    except Exception:
        # Remote errors can contain credentials, URLs or server content. Persist only a fixed code.
        failure = "discovery_failed"
    await asyncio.to_thread(complete, dsn, job, snapshot, failure)
    return True


async def main():
    from alojan_contracts.mcp_oauth import providers
    from alojan_agent.mcp_oauth_refresh import process_one as refresh_one

    registry = providers(os.environ.get("ALOJAN_MCP_OAUTH_PROVIDERS_FILE"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    # SDK/HTTP logs may contain untrusted response bodies; this process logs fixed outcomes only.
    for name in ("mcp", "httpx2", "httpcore2"):
        logger = logging.getLogger(name)
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
    secrets = SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"])
    while True:
        try:
            refreshed = (
                await refresh_one(os.environ["ALOJAN_DATABASE_URL"], secrets, registry)
                if registry
                else False
            )
            worked = await process_one(os.environ["ALOJAN_DATABASE_URL"], secrets) or refreshed
        except psycopg.Error:
            logging.error("mcp_discovery_database_unavailable")
            if args.once:
                raise SystemExit(1) from None
            worked = False
        if args.once:
            return
        await asyncio.sleep(0.25 if worked else 2)


if __name__ == "__main__":
    asyncio.run(main())
