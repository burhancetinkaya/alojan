"""Private node-local preload and expiring readiness; never inference or media IO.

Trusted management publications and explicit deployment targets supply release IDs.
This coordinator does not publish agents, bind numbers, create audio assets or
qualify provider API quality.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import re
import time
import uuid

import psycopg
from grpc_health.v1 import health_pb2, health_pb2_grpc
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc

from alojan_contracts.routing import node_identifier, validated_release
from .prepared import release_key


class ReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    scope_id: str
    release_id: str
    manifest_digest: str
    manifest_json: str
    consumer_id: str


class ReadinessRepository:
    def __init__(self, dsn, node_id):
        self.dsn, self.node_id = dsn, node_identifier(node_id)

    @asynccontextmanager
    async def connection(self, scope=None):
        scope = str(uuid.UUID(str(scope))) if scope is not None else ""
        async with asyncio.timeout(1):
            async with await psycopg.AsyncConnection.connect(self.dsn, connect_timeout=1) as c:
                await c.execute("SET LOCAL statement_timeout=500")
                await c.execute("SET LOCAL lock_timeout=100")
                await c.execute("SET LOCAL transaction_timeout=700")
                await c.execute("SELECT set_config('alojan.scope_id',%s,true)", (scope,))
                yield c

    async def desired(self, limit):
        async with self.connection() as c:
            rows = await (
                await c.execute(
                    """WITH wanted AS (
                    SELECT b.scope_id,b.release_id,0 AS priority FROM phone_numbers n
                    JOIN number_bindings b ON (b.scope_id,b.id)=(n.scope_id,n.active_binding_id)
                    WHERE n.enabled AND n.status='verified' AND b.node_id=%s
                    UNION ALL
                    SELECT scope_id,release_id,1 FROM agent_publications WHERE node_id=%s)
                SELECT w.scope_id,w.release_id FROM wanted w
                JOIN recipient_scopes s ON s.id=w.scope_id AND s.enabled
                GROUP BY w.scope_id,w.release_id
                ORDER BY min(w.priority),w.scope_id,w.release_id LIMIT %s""",
                    (self.node_id, self.node_id, limit),
                )
            ).fetchall()
            return [(str(scope), str(release)) for scope, release in rows]

    async def claim(self, scope, release):
        scope, release = str(uuid.UUID(str(scope))), str(uuid.UUID(str(release)))
        async with self.connection(scope) as c:
            row = await (
                await c.execute(
                    """SELECT r.profile_id,r.manifest,r.manifest_digest FROM agent_releases r
                JOIN recipient_scopes s ON s.id=r.scope_id AND s.enabled
                JOIN model_catalog_status m ON m.model_id=r.manifest->'model'->>'id'
                  AND m.model_revision=(r.manifest->'model'->>'revision')::integer AND m.enabled
                WHERE r.scope_id=%s AND r.id=%s""",
                    (scope, release),
                )
            ).fetchone()
            if row is None:
                raise ReadinessError("release_unavailable")
            manifest = validated_release(row[1], row[2])
            consumer = str(uuid.uuid4())
            await c.execute(
                """INSERT INTO release_readiness(scope_id,profile_id,release_id,node_id,
                manifest_digest,consumer_id,ready,acknowledged_at,valid_until)
                VALUES (%s,%s,%s,%s,%s,%s,false,now(),now()+interval '10 seconds')
                ON CONFLICT (scope_id,release_id,node_id) DO UPDATE SET
                consumer_id=excluded.consumer_id,ready=false,acknowledged_at=excluded.acknowledged_at,
                valid_until=excluded.valid_until,checked_at=now()""",
                (scope, row[0], release, self.node_id, row[2], consumer),
            )
            return Candidate(scope, release, row[2], manifest, consumer)

    async def renew(self, candidate):
        async with self.connection(candidate.scope_id) as c:
            row = await c.execute(
                """UPDATE release_readiness d SET ready=true,acknowledged_at=now(),
                valid_until=now()+interval '10 seconds',checked_at=now()
                FROM agent_releases r, recipient_scopes s, model_catalog_status m
                WHERE d.scope_id=%s AND d.release_id=%s AND d.node_id=%s
                AND d.manifest_digest=%s AND d.consumer_id=%s
                AND (r.scope_id,r.id)=(d.scope_id,d.release_id)
                AND s.id=d.scope_id AND s.enabled
                AND m.model_id=r.manifest->'model'->>'id'
                AND m.model_revision=(r.manifest->'model'->>'revision')::integer AND m.enabled""",
                (
                    candidate.scope_id,
                    candidate.release_id,
                    self.node_id,
                    candidate.manifest_digest,
                    candidate.consumer_id,
                ),
            )
            return row.rowcount == 1

    async def withdraw(self, candidate):
        async with self.connection(candidate.scope_id) as c:
            await c.execute(
                """UPDATE release_readiness SET ready=false,checked_at=now()
                WHERE scope_id=%s AND release_id=%s AND node_id=%s AND consumer_id=%s""",
                (candidate.scope_id, candidate.release_id, self.node_id, candidate.consumer_id),
            )

    async def retire(self, candidate):
        async with self.connection(candidate.scope_id) as c:
            # Binding takes a shared receipt lock. Fence new bindings before checking whether
            # one committed since discovery; never evict a newly bound release from a stale scan.
            await c.execute(
                """SELECT 1 FROM release_readiness WHERE scope_id=%s AND release_id=%s
                AND node_id=%s AND consumer_id=%s FOR UPDATE""",
                (candidate.scope_id, candidate.release_id, self.node_id, candidate.consumer_id),
            )
            bound = await (
                await c.execute(
                    """SELECT 1 FROM phone_numbers n JOIN number_bindings b
                ON (b.scope_id,b.id)=(n.scope_id,n.active_binding_id)
                WHERE n.scope_id=%s AND n.enabled AND n.status='verified'
                AND b.release_id=%s AND b.node_id=%s LIMIT 1""",
                    (candidate.scope_id, candidate.release_id, self.node_id),
                )
            ).fetchone()
            if bound:
                return False
            await c.execute(
                """UPDATE release_readiness SET ready=false,checked_at=now()
                WHERE scope_id=%s AND release_id=%s AND node_id=%s AND consumer_id=%s""",
                (candidate.scope_id, candidate.release_id, self.node_id, candidate.consumer_id),
            )
            return True


class ReleaseReadiness:
    def __init__(self, service, repository, asr_channel, tts_channel):
        if (
            service.router is None
            or service.prepared is None
            or service.readiness is not None
            or service.router.node_id != repository.node_id
        ):
            raise ValueError("Matching routed service and exclusive readiness owner required")
        self.service, self.repository = service, repository
        self.asr, self.tts = asr_channel, tts_channel
        self.targets = {}
        self.expires = {}
        self.lock = asyncio.Lock()
        self.activation_lock = asyncio.Lock()
        self.closed = False
        service.readiness = self

    def accepts(self, route):
        key = release_key(route.scope_id, route.release_id, route.manifest_digest)
        return (
            not self.closed
            and route.node_id == self.repository.node_id
            and self.expires.get(key, 0) > time.monotonic()
            and key in self.service.prepared.entries
            and not self.service.prepared.closed
        )

    async def check_dependencies(self):
        async def health(channel, name):
            result = await health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest(service=name), timeout=0.5
            )
            if result.status != health_pb2.HealthCheckResponse.SERVING:
                raise ReadinessError("voice_dependency_unavailable")

        async def storage():
            async with await psycopg.AsyncConnection.connect(
                self.service.store.dsn, connect_timeout=1
            ) as c:
                await c.execute("SET LOCAL statement_timeout=500")
                await c.execute("SELECT id FROM calls LIMIT 0")
                row = await (
                    await c.execute("""SELECT
                    has_table_privilege(current_user,'utterances','INSERT'),
                    has_table_privilege(current_user,'notes','INSERT'),
                    has_table_privilege(current_user,'summary_jobs','INSERT')""")
                ).fetchone()
                if not all(row):
                    raise ReadinessError("record_writer_unavailable")

        async with asyncio.TaskGroup() as group:
            group.create_task(health(self.asr, "voice.v1.Recognition"))
            group.create_task(health(self.tts, "voice.v1.Synthesis"))
            group.create_task(storage())

    async def probe(self, channel, configuration, method):
        control = rpc.GenerationControlStub(channel)
        cid, token = "managed-preflight-" + uuid.uuid4().hex, None
        try:
            opened = await control.OpenCall(pb.CallLeaseRequest(call_id=cid), timeout=0.5)
            token = opened.lease
            if not re.fullmatch(r"[0-9a-f]{32}", token):
                raise ReadinessError("invalid_probe_lease")
            configuration.call_id = cid
            reply = await method(configuration, timeout=0.5, metadata=(("x-alojan-lease", token),))
            if not reply.accepted:
                raise ReadinessError("voice_configuration_rejected")
        finally:
            if token:
                # Lost replies remain unready; known leases are released even on cancellation.
                cleanup = asyncio.ensure_future(
                    control.ReleaseCall(pb.CallLeaseRequest(call_id=cid, lease=token), timeout=0.5)
                )
                try:
                    reply = await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    raise
                if not reply.accepted:
                    raise ReadinessError("probe_cleanup_unconfirmed")

    async def activate(self, scope, release):
        if self.closed or self.activation_lock.locked():
            raise ReadinessError("readiness_busy_or_closed")
        scope, release = str(uuid.UUID(str(scope))), str(uuid.UUID(str(release)))
        for key, (candidate, _) in list(self.targets.items()):
            if key[:2] == (scope, release):
                await self.refresh()
                if key not in self.targets:
                    raise ReadinessError("readiness_superseded")
                return candidate
        # A cold release must not hold up existing releases' two-second renewals.
        async with self.activation_lock:
            if len(self.targets) >= self.service.prepared.max_entries:
                raise ReadinessError("readiness_capacity")
            candidate = None
            pack = None
            key = None
            try:
                async with asyncio.timeout(5):
                    candidate = await self.repository.claim(scope, release)
                    key = release_key(scope, release, candidate.manifest_digest)
                    await self.service.prepared.preload(
                        candidate.scope_id,
                        candidate.release_id,
                        candidate.manifest_json,
                        candidate.manifest_digest,
                    )
                    pack = self.service.prepared.pin(candidate)
                    await self.probe(
                        self.asr,
                        pb.RecognitionCallConfiguration(
                            release_id=candidate.release_id,
                            manifest_digest=candidate.manifest_digest,
                            configuration=pb.RecognitionConfiguration(
                                schema_version=1, replacements=dict(pack.runtime.asr_replacements)
                            ),
                        ),
                        rpc.RecognitionStub(self.asr).ConfigureCall,
                    )
                    await self.probe(
                        self.tts,
                        pb.SynthesisCallConfiguration(
                            release_id=candidate.release_id,
                            manifest_digest=candidate.manifest_digest,
                            configuration=pack.runtime.synthesis.to_proto(),
                        ),
                        rpc.SynthesisStub(self.tts).ConfigureCall,
                    )
                    start = time.monotonic()
                    await self.check_dependencies()
                    if hasattr(self.service.backend, "prepare_runtime"):
                        await self.service.backend.prepare_runtime(pack.runtime)
                    self.service.backend.check_runtime(pack.runtime)
                    if self.closed or not await self.repository.renew(candidate):
                        raise ReadinessError("readiness_superseded")
                    self.targets[key] = candidate, pack
                    self.expires[key] = start + 2
                    return candidate
            except BaseException:
                if pack:
                    self.service.prepared.unpin(pack)
                if candidate:
                    try:
                        await self.repository.withdraw(candidate)
                    except Exception:
                        pass  # Local admission is closed; the database receipt expires in 10s.
                raise

    async def discover(self, seeds=()):
        desired = await self.repository.desired(self.service.prepared.max_entries)
        wanted = list(dict.fromkeys([*desired, *seeds]))
        active = {(r.scope_id, r.release_id) for r in self.service.routes.values()}
        # Retain admission/credentials for in-flight calls until their leases are released.
        async with self.lock:
            for key, (candidate, pack) in list(self.targets.items()):
                if key[:2] not in wanted and key[:2] not in active:
                    if not await self.repository.retire(candidate):
                        continue
                    if any(
                        (r.scope_id, r.release_id) == key[:2] for r in self.service.routes.values()
                    ):
                        continue
                    self.expires.pop(key, None)
                    self.targets.pop(key)
                    self.service.prepared.unpin(pack)
        credentials = getattr(self.service.backend, "credentials", None)
        if credentials is not None:
            await credentials.retain([pack.runtime for _, pack in self.targets.values()])
        for scope, release in wanted:
            if self.closed:
                return
            if any(key[:2] == (scope, release) for key in self.targets):
                continue
            try:
                await self.activate(scope, release)
            except Exception:
                # Bad credentials/assets/grants belong to this release, never the whole node.
                print("event=release_activation_unavailable", flush=True)

    async def watch_publications(self, stopping, seeds=()):
        while not stopping.is_set() and not self.closed:
            try:
                await self.discover(seeds)
            except Exception:
                print("event=release_discovery_unavailable", flush=True)
            try:
                await asyncio.wait_for(stopping.wait(), timeout=2)
            except TimeoutError:
                pass

    async def refresh(self):
        if self.closed or self.lock.locked():
            raise ReadinessError("readiness_busy_or_closed")
        async with self.lock:
            if not self.targets:
                return
            start = time.monotonic()
            failure = None
            try:
                async with asyncio.timeout(1.5):
                    await self.check_dependencies()
                    for key, (candidate, pack) in list(self.targets.items()):
                        if (
                            self.service.prepared.closed
                            or self.service.prepared.entries.get(key) is not pack
                        ):
                            raise ReadinessError("prepared_release_unavailable")
                        try:
                            if hasattr(self.service.backend, "prepare_runtime"):
                                await self.service.backend.prepare_runtime(pack.runtime)
                            self.service.backend.check_runtime(pack.runtime)
                            if not await self.repository.renew(candidate):
                                self.expires.pop(key, None)
                                self.targets.pop(key)
                                self.service.prepared.unpin(pack)
                            else:
                                self.expires[key] = start + 2
                        except Exception as error:
                            # A revoked agent capability must not disable unrelated releases.
                            self.expires.pop(key, None)
                            failure = failure or error
            except BaseException:
                self.expires.clear()
                raise
            if failure is not None:
                raise failure

    async def run(self, stopping):
        try:
            while not stopping.is_set() and not self.closed:
                try:
                    await self.refresh()
                except Exception:
                    print("event=release_readiness_unavailable", flush=True)
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=0.5)
                except TimeoutError:
                    pass
        finally:
            await self.close()

    async def close(self):
        self.closed = True
        self.expires.clear()
        async with self.activation_lock, self.lock:
            for candidate, pack in self.targets.values():
                self.service.prepared.unpin(pack)
                try:
                    await self.repository.withdraw(candidate)
                except Exception:
                    pass
            self.targets.clear()
