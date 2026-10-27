"""Explicit loopback managed-node launcher; never enables numbers or sends notifications."""

import argparse
import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import uuid

import grpc
import psycopg
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from alojan_contracts.maintenance import WorkerMaintenance
from alojan_contracts.routing import node_identifier
from alojan_contracts.secrets import SecretBox
from .credentials import ProviderClients
from .__main__ import reconcile
from .backend import Backend
from .prepared import PreparedReleases
from .readiness import ReadinessRepository, ReleaseReadiness, ReadinessError
from .routing import CallRouter
from .service import AgentService, create_server
from .store import Store


@dataclass(frozen=True)
class Deployment:
    node_id: str
    asset_root: Path
    agent_port: int
    asr_port: int
    tts_port: int
    targets: tuple[tuple[str, str], ...]

    @classmethod
    def load(cls, path):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate deployment key")
                result[key] = value
            return result

        with Path(path).open("rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise ValueError("deployment file too large")
        data = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(data, dict) or set(data) != {
            "schema_version",
            "node_id",
            "asset_root",
            "agent_port",
            "asr_port",
            "tts_port",
            "targets",
        }:
            raise ValueError("invalid deployment fields")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("unsupported deployment version")
        node = node_identifier(data["node_id"])
        root = Path(data["asset_root"])
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("absolute installed asset directory required")
        ports = [data[key] for key in ("agent_port", "asr_port", "tts_port")]
        if any(type(p) is not int or not 1024 <= p <= 65535 for p in ports) or len(set(ports)) != 3:
            raise ValueError("distinct nonprivileged loopback ports required")
        targets = data["targets"]
        if not isinstance(targets, list) or len(targets) > 16:
            raise ValueError("at most sixteen explicit release targets allowed")
        selected = []
        for target in targets:
            if not isinstance(target, dict) or set(target) != {"scope_id", "release_id"}:
                raise ValueError("invalid release target")
            if any(not isinstance(value, str) for value in target.values()):
                raise ValueError("release identifiers must be strings")
            selected.append(tuple(str(uuid.UUID(target[k])) for k in ("scope_id", "release_id")))
        if len(set(selected)) != len(selected):
            raise ValueError("duplicate release target")
        return cls(node, root, *ports, tuple(selected))


async def serve(deployment, stopping):
    shadow = os.getenv("ALOJAN_JEV_SHADOW", "1")
    if shadow not in {"0", "1"}:
        raise ValueError("invalid decision shadow mode")
    # Separate role credentials are mandatory; never fall back to the legacy database URL.
    records, routing, readiness = (
        os.environ[name]
        for name in (
            "ALOJAN_RECORDS_DATABASE_URL",
            "ALOJAN_ROUTING_DATABASE_URL",
            "ALOJAN_READINESS_DATABASE_URL",
        )
    )
    async with AsyncExitStack() as resources:
        decisions = None
        if shadow == "1":
            from .decisions import Decisions

            decisions = Decisions()
            resources.push_async_callback(decisions.close)
        mcp = None
        if os.getenv("ALOJAN_MCP_DATABASE_URL"):
            from .mcp_runtime import MCPExecutor

            mcp = MCPExecutor(
                os.environ["ALOJAN_MCP_DATABASE_URL"],
                SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"]),
            )
            resources.push_async_callback(mcp.close)
        backend = Backend(
            decisions=decisions,
            mcp=mcp,
            credentials=ProviderClients(
                os.environ["ALOJAN_CREDENTIALS_DATABASE_URL"],
                SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"]),
            ),
        )
        resources.push_async_callback(backend.close)
        cache = PreparedReleases(deployment.asset_root)
        resources.push_async_callback(cache.close)
        asr = await resources.enter_async_context(
            grpc.aio.insecure_channel(f"127.0.0.1:{deployment.asr_port}")
        )
        tts = await resources.enter_async_context(
            grpc.aio.insecure_channel(f"127.0.0.1:{deployment.tts_port}")
        )
        service = AgentService(
            backend, Store(records), router=CallRouter(routing, deployment.node_id), prepared=cache
        )
        coordinator = ReleaseReadiness(
            service, ReadinessRepository(readiness, deployment.node_id), asr, tts
        )
        admission = WorkerMaintenance.from_environment(service)
        server = create_server(service, reuse_port=False, maintenance=admission)
        status = health.aio.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(status, server)
        worker = None
        discovery = None
        maintenance = None
        try:
            # Reserve exclusively before claiming receipts; overlapping listeners cannot split calls.
            if not server.add_insecure_port(f"127.0.0.1:{deployment.agent_port}"):
                raise RuntimeError("managed agent bind failed")
            async with asyncio.timeout(1):
                async with await psycopg.AsyncConnection.connect(routing, connect_timeout=1) as c:
                    await c.execute("SET LOCAL statement_timeout=500")
                    await c.execute("SELECT id FROM calls LIMIT 0")
                    await c.execute("SELECT call_id FROM call_route_snapshots LIMIT 0")
                    row = await (
                        await c.execute("""SELECT
                        has_table_privilege(current_user,'calls','INSERT'),
                        has_table_privilege(current_user,'call_route_snapshots','INSERT'),
                        has_table_privilege(current_user,'phone_numbers','SELECT'),
                        has_column_privilege(current_user,'calls','status','UPDATE')""")
                    ).fetchone()
                    if not all(row):
                        raise ReadinessError("routing_writer_unavailable")
            await coordinator.check_dependencies()
            await coordinator.discover(deployment.targets)
            try:
                await coordinator.refresh()
            except Exception:
                print("event=release_readiness_unavailable", flush=True)
            await status.set("voice.v1.Agent", health_pb2.HealthCheckResponse.SERVING)
            await server.start()
            if admission:
                admission.start()
            worker = asyncio.create_task(coordinator.run(stopping))
            discovery = asyncio.create_task(
                coordinator.watch_publications(stopping, deployment.targets)
            )
            # Above every qualified preset's 300-second hard limit, with cleanup margin.
            maintenance = asyncio.create_task(reconcile(service, 600))
            print("event=managed_agent_ready api_access=separate_acceptance", flush=True)
            await stopping.wait()
        finally:
            # Close local admission synchronously before any shutdown IO or task cancellation.
            stopping.set()
            if admission:
                await admission.stop()
            coordinator.closed = True
            coordinator.expires.clear()
            await status.enter_graceful_shutdown()
            if discovery:
                discovery.cancel()
                await asyncio.gather(discovery, return_exceptions=True)
            if worker:
                # Let its bounded refresh/withdraw finish; cancelling midway can unpin twice.
                await asyncio.gather(worker, return_exceptions=True)
            if maintenance:
                maintenance.cancel()
                await asyncio.gather(maintenance, return_exceptions=True)
            await coordinator.close()
            for state in service.generations.values():
                state.cancelled.set()
            await server.stop(2)
            pending = list(service.turn_tasks.values()) + list(service.initializations.values())
            service.close_leases()
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


async def run(deployment):
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    worker = asyncio.create_task(serve(deployment, stopping))

    def stop():
        if not stopping.is_set():
            stopping.set()
            # Cancel once, before waking serve; never interrupt cleanup with a second cancellation.
            worker.cancel()

    for sig in signals:
        loop.add_signal_handler(sig, stop)
    try:
        await worker
    except asyncio.CancelledError:
        if not stopping.is_set():
            raise
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        for sig in signals:
            loop.remove_signal_handler(sig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(run(Deployment.load(args.config)))
    except Exception as error:
        print(f"event=managed_agent_startup_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
