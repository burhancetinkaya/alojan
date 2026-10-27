"""One fenced OAuth refresh outside calls; uncertain rotation requires reconnect."""

import asyncio
import uuid

from alojan_contracts.mcp_oauth import exchange
from alojan_agent.mcp_discovery_worker import connection


def claim(dsn):
    with connection(dsn) as conn:
        conn.execute("""UPDATE mcp_oauth_credentials SET status='reauth_required',claim_token=NULL,lease_until=NULL
            WHERE connection_id IN (SELECT connection_id FROM mcp_oauth_credentials
                WHERE status='refreshing' AND lease_until<=now() FOR UPDATE SKIP LOCKED LIMIT 100)""")
        row = conn.execute("""SELECT connection_id,scope_id FROM mcp_oauth_credentials
            WHERE status='active' AND refresh_after<=now() ORDER BY refresh_after,connection_id
            FOR UPDATE SKIP LOCKED LIMIT 1""").fetchone()
        if row is None:
            return None
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(row[1]),))
        eligible = conn.execute(
            """SELECT 1 FROM mcp_connections c
            JOIN mcp_oauth_credentials o ON (o.scope_id,o.connection_id)=(c.scope_id,c.id)
            JOIN users u ON u.id=o.authorized_by AND u.enabled
            JOIN recipient_scopes s ON s.id=c.scope_id AND s.enabled
            JOIN workspace_memberships m ON m.scope_id=c.scope_id AND m.user_id=u.id AND m.role='owner'
            WHERE c.scope_id=%s AND c.id=%s AND c.enabled AND c.auth_type='oauth'""",
            (row[1], row[0]),
        ).fetchone()
        if not eligible:
            conn.execute(
                "UPDATE mcp_oauth_credentials SET status='reauth_required' WHERE connection_id=%s",
                (row[0],),
            )
            return None
        lease = uuid.uuid4()
        data = conn.execute(
            """UPDATE mcp_oauth_credentials SET status='refreshing',claim_token=%s,lease_until=now()+interval '30 seconds'
            WHERE connection_id=%s RETURNING connection_id,scope_id,provider,refresh_ciphertext,claim_token""",
            (lease, row[0]),
        ).fetchone()
        return data


def complete(dsn, job, result, box):
    reference, scope, _, _, lease = job
    with connection(dsn) as conn:
        conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
        # Share-lock the connection so revocation wins before a new token becomes eligible.
        enabled = conn.execute(
            """SELECT c.enabled AND s.enabled AND u.enabled AND EXISTS(
                SELECT 1 FROM workspace_memberships m WHERE m.scope_id=c.scope_id
                AND m.user_id=u.id AND m.role='owner')
            FROM mcp_connections c JOIN mcp_oauth_credentials o ON (o.scope_id,o.connection_id)=(c.scope_id,c.id)
            JOIN recipient_scopes s ON s.id=c.scope_id JOIN users u ON u.id=o.authorized_by
            WHERE c.scope_id=%s AND c.id=%s FOR SHARE OF c""",
            (scope, reference),
        ).fetchone()
        if result is None or not enabled or not enabled[0]:
            conn.execute(
                """UPDATE mcp_oauth_credentials SET status='reauth_required',claim_token=NULL,lease_until=NULL
                WHERE scope_id=%s AND connection_id=%s AND status='refreshing' AND claim_token=%s""",
                (scope, reference, lease),
            )
            return
        access, refresh, lifetime = result
        conn.execute(
            """UPDATE mcp_oauth_credentials SET status='active',generation=generation+1,
            access_ciphertext=%s,refresh_ciphertext=%s,expires_at=now()+%s*interval '1 second',
            refresh_after=now()+%s*interval '1 second',claim_token=NULL,lease_until=NULL
            WHERE scope_id=%s AND connection_id=%s AND status='refreshing' AND claim_token=%s AND lease_until>now()""",
            (
                box.seal(scope, reference, access, purpose="mcp-oauth-access"),
                box.seal(scope, reference, refresh, purpose="mcp-oauth-refresh"),
                lifetime - 10,
                max(1, lifetime - 70),
                scope,
                reference,
                lease,
            ),
        )


async def process_one(dsn, box, registry, *, exchange_tokens=exchange):
    job = await asyncio.to_thread(claim, dsn)
    if job is None:
        return False
    result = None
    try:
        if registry.get(job[2]["id"]) != job[2] or job[3] is None:
            raise ValueError("OAuth reconnect required")
        refresh = box.open(job[1], job[0], bytes(job[3]), purpose="mcp-oauth-refresh")
        async with asyncio.timeout(8):
            result = await exchange_tokens(job[2], refresh=refresh)
    except Exception:
        # Rotating credentials may have been consumed even if their response was lost.
        pass
    await asyncio.to_thread(complete, dsn, job, result, box)
    return True
