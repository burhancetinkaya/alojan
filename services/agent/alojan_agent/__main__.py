"""Loopback-only agent with durable post-call work, never credential/transcript logs."""

import argparse
import asyncio
import os
import signal

from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from .backend import Backend
from .service import AgentService, create_server
from .store import Store


async def serve(port):
    backend = Backend()
    store = Store(os.environ["ALOJAN_DATABASE_URL"])
    await store.run(lambda c: c.execute("SELECT call_id FROM summary_jobs LIMIT 0"))
    service = AgentService(backend, store)
    server = create_server(service)
    readiness = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(readiness, server)
    if not server.add_insecure_port(f"127.0.0.1:{port}"):
        raise RuntimeError("agent bind failed")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)
    await readiness.set("voice.v1.Agent", health_pb2.HealthCheckResponse.SERVING)
    await server.start()
    summaries = asyncio.create_task(service.summaries())
    print("event=agent_ready provider=openrouter api_access=separate_acceptance", flush=True)
    try:
        await stopping.wait()
    finally:
        await readiness.enter_graceful_shutdown()
        for state in service.generations.values():
            state.cancelled.set()
        await server.stop(2)
        summaries.cancel()
        await asyncio.gather(summaries, return_exceptions=True)
        await backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15073)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        asyncio.run(serve(args.port))
    except Exception as error:
        print(f"event=agent_startup_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
