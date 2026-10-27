"""Private asynchronous admission repository; never called from a media callback.

The gateway must authenticate the carrier peer and select its configured DID field
before this boundary. There is intentionally no management HTTP admission endpoint.
"""

import asyncio
import re

import psycopg

from alojan_contracts.routing import PinnedRoute, canonical_did, node_identifier, validated_release
from alojan_agent.store import call_uuid
from alojan_agent.records import NO_ANSWER_JOB


class RoutingError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class CallRouter:
    def __init__(self, dsn, node_id):
        self.dsn = dsn
        self.node_id = node_identifier(node_id)

    async def initialize(self, call_id, did, source, caller_number=None):
        if not isinstance(call_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id):
            raise RoutingError("invalid_call_identity")
        try:
            canonical_did(did)
        except ValueError:
            raise RoutingError("invalid_called_number") from None
        if source not in ("request_uri", "to") or (
            caller_number is not None
            and (
                not isinstance(caller_number, str)
                or not re.fullmatch(r"\+[1-9][0-9]{7,14}", caller_number)
            )
        ):
            raise RoutingError("invalid_identity_metadata")
        try:
            async with asyncio.timeout(1.8):
                async with await psycopg.AsyncConnection.connect(
                    self.dsn, connect_timeout=1
                ) as conn:
                    await conn.execute("SET LOCAL statement_timeout=700")
                    await conn.execute("SET LOCAL lock_timeout=200")
                    await conn.execute("SET LOCAL transaction_timeout=1000")
                    return await self._initialize(conn, call_id, did, source, caller_number)
        except (TimeoutError, psycopg.Error):
            raise RoutingError("routing_temporarily_unavailable") from None

    async def _initialize(self, conn, call_id, did, source, caller_number):
        cid = call_uuid(call_id)
        # Retries for the same opaque call serialize before choosing a route.
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,714208))", (str(cid),))
        old = await (
            await conn.execute(
                """SELECT s.scope_id,s.number_id,s.binding_id,s.profile_id,s.release_id,s.node_id,
            s.manifest_digest,s.called_e164,s.called_source,c.from_number_e164,c.ended_at
            FROM call_route_snapshots s JOIN calls c ON c.id=s.call_id WHERE s.call_id=%s""",
                (cid,),
            )
        ).fetchone()
        if old:
            if old[5] != self.node_id or (old[7], old[8], old[9]) != (did, source, caller_number):
                raise RoutingError("conflicting_initialization")
            if old[10] is not None:
                raise RoutingError("call_already_ended")
            await conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(old[0]),))
            return await self._snapshot(conn, call_id, old[:7])
        previous = await (
            await conn.execute("SELECT ended_at FROM calls WHERE id=%s", (cid,))
        ).fetchone()
        if previous:
            raise RoutingError("call_already_ended" if previous[0] else "unscoped_call_conflict")
        directory = await (
            await conn.execute(
                "SELECT scope_id FROM phone_numbers WHERE e164=%s AND status='verified' AND enabled",
                (did,),
            )
        ).fetchone()
        if not directory:
            raise RoutingError("number_not_routed")
        await conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(directory[0]),))
        number = await (
            await conn.execute(
                """SELECT scope_id,id,active_binding_id FROM phone_numbers
            WHERE e164=%s AND scope_id=%s AND status='verified' AND enabled FOR SHARE""",
                (did, directory[0]),
            )
        ).fetchone()
        if not number:
            raise RoutingError("number_not_routed")
        scope, number_id, binding = number
        await conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))
        if not await (
            await conn.execute(
                "SELECT 1 FROM recipient_scopes WHERE id=%s AND enabled FOR SHARE",
                (scope,),
            )
        ).fetchone():
            raise RoutingError("workspace_disabled")
        row = await (
            await conn.execute(
                """SELECT b.profile_id,b.release_id,b.node_id,r.manifest_digest,r.manifest
            FROM number_bindings b JOIN agent_releases r
            ON (r.scope_id,r.profile_id,r.id)=(b.scope_id,b.profile_id,b.release_id)
            WHERE b.scope_id=%s AND b.number_id=%s AND b.id=%s""",
                (scope, number_id, binding),
            )
        ).fetchone()
        if not row or row[2] != self.node_id:
            raise RoutingError("release_unavailable_on_node")
        profile, release, node, digest, manifest = row
        try:
            manifest_json = validated_release(manifest, digest)
        except ValueError:
            raise RoutingError("invalid_release") from None
        model = manifest["model"]
        if not await (
            await conn.execute(
                """SELECT 1 FROM model_catalog_status WHERE model_id=%s AND model_revision=%s
            AND enabled FOR SHARE""",
                (model["id"], model["revision"]),
            )
        ).fetchone():
            raise RoutingError("model_not_qualified")
        if not await (
            await conn.execute(
                """SELECT 1 FROM release_readiness WHERE scope_id=%s AND release_id=%s
            AND node_id=%s AND manifest_digest=%s AND ready
            AND acknowledged_at <= clock_timestamp() AND valid_until > clock_timestamp()
            FOR SHARE""",
                (scope, release, node, digest),
            )
        ).fetchone():
            raise RoutingError("release_unavailable_on_node")
        inserted = await (
            await conn.execute(
                """INSERT INTO calls(id,sip_call_id,direction,status,from_number_e164,from_number_source,to_number_e164)
            VALUES (%s,%s,'inbound','initializing',%s,%s,%s) ON CONFLICT (id) DO NOTHING RETURNING id""",
                (cid, call_id, caller_number, "gateway_hint" if caller_number else "unknown", did),
            )
        ).fetchone()
        if not inserted:
            raise RoutingError("unscoped_call_conflict")
        await conn.execute(
            """INSERT INTO call_route_snapshots(call_id,scope_id,number_id,binding_id,profile_id,
            release_id,node_id,called_e164,called_source,manifest_digest)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (cid, scope, number_id, binding, profile, release, node, did, source, digest),
        )
        return PinnedRoute(
            call_id,
            str(scope),
            str(number_id),
            str(binding),
            str(profile),
            str(release),
            node,
            digest,
            manifest_json,
        )

    async def _snapshot(self, conn, call_id, fields):
        scope, number, binding, profile, release, node, digest = fields
        row = await (
            await conn.execute(
                "SELECT manifest FROM agent_releases WHERE scope_id=%s AND profile_id=%s AND id=%s",
                (scope, profile, release),
            )
        ).fetchone()
        try:
            if not row:
                raise ValueError("Missing pinned release")
            manifest_json = validated_release(row[0], digest)
        except ValueError:
            raise RoutingError("invalid_pinned_release") from None
        return PinnedRoute(
            call_id,
            str(scope),
            str(number),
            str(binding),
            str(profile),
            str(release),
            node,
            digest,
            manifest_json,
        )

    async def stale_routes(self, age_seconds):
        if not 300 <= age_seconds <= 86400:
            raise ValueError("reconciliation age must be 300..86400 seconds")
        async with await psycopg.AsyncConnection.connect(self.dsn, connect_timeout=1) as c:
            await c.execute("SET LOCAL statement_timeout=700")
            await c.execute("SET LOCAL transaction_timeout=3000")
            rows = await (
                await c.execute(
                    """SELECT c.sip_call_id,s.scope_id,s.number_id,s.binding_id,
                s.profile_id,s.release_id,s.node_id,s.manifest_digest FROM call_route_snapshots s
                JOIN calls c ON c.id=s.call_id WHERE s.node_id=%s AND c.status IN ('initializing','active')
                AND c.started_at<now()-make_interval(secs=>%s) ORDER BY c.started_at LIMIT 16""",
                    (self.node_id, age_seconds),
                )
            ).fetchall()
            routes = []
            for row in rows:
                await c.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(row[1]),))
                routes.append(await self._snapshot(c, row[0], row[1:]))
            return routes

    async def cancel_unanswered(self, call_id):
        """Fence late setup; queue only explicit pinned no-answer intent after a scoped cancellation."""
        if not isinstance(call_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id):
            raise RoutingError("invalid_call_identity")
        try:
            async with asyncio.timeout(1.8):
                async with await psycopg.AsyncConnection.connect(
                    self.dsn, connect_timeout=1
                ) as conn:
                    await conn.execute("SET LOCAL statement_timeout=700")
                    await conn.execute("SET LOCAL lock_timeout=200")
                    await conn.execute("SET LOCAL transaction_timeout=1000")
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s,714208))",
                        (str(call_uuid(call_id)),),
                    )
                    row = await (
                        await conn.execute(
                            "SELECT scope_id FROM call_route_snapshots WHERE call_id=%s AND node_id=%s",
                            (call_uuid(call_id), self.node_id),
                        )
                    ).fetchone()
                    if not row:
                        cancelled = await conn.execute(
                            """INSERT INTO calls(id,sip_call_id,direction,status,ended_at,hangup_reason)
                            VALUES (%s,%s,'inbound','ended',now(),'cancelled_before_initialization')
                            ON CONFLICT (id) DO NOTHING""",
                            (call_uuid(call_id), call_id),
                        )
                        return cancelled.rowcount == 1
                    await conn.execute(
                        "SELECT set_config('alojan.scope_id',%s,true)", (str(row[0]),)
                    )
                    state = await (
                        await conn.execute(
                            "SELECT status FROM calls WHERE id=%s FOR UPDATE", (call_uuid(call_id),)
                        )
                    ).fetchone()
                    if state == ("active",):
                        raise RoutingError("call_already_answered")
                    result = await conn.execute(
                        """UPDATE calls SET status='ended',ended_at=now(),hangup_reason='cancelled_before_answer'
                        WHERE id=%s AND status='initializing' AND ended_at IS NULL""",
                        (call_uuid(call_id),),
                    )
                    if result.rowcount == 1:
                        await conn.execute(NO_ANSWER_JOB, (call_uuid(call_id),))
                    return result.rowcount == 1
        except (TimeoutError, psycopg.Error):
            raise RoutingError("routing_temporarily_unavailable") from None
