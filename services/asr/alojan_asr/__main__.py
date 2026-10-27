"""Loopback-only ASR worker; reports ready only after pinned CUDA warm-up."""

import argparse
import asyncio
import os
import signal

from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from alojan_contracts.maintenance import WorkerMaintenance

from .model import WhisperBackend
from .service import RecognitionService, create_server


def create_backend(name, replacements):
    if name == "whisper":
        return WhisperBackend(replacements=replacements)
    if name == "nemotron":
        from .nemotron import NemotronBackend

        return NemotronBackend(replacements=replacements)
    raise ValueError("ALOJAN_ASR_BACKEND must be whisper or nemotron")


async def serve(port, require_agent_release=False):
    name = os.environ.get("ALOJAN_ASR_BACKEND", "whisper")
    backend = create_backend(name, os.environ.get("ALOJAN_ASR_REPLACEMENTS", "{}"))
    service = RecognitionService(backend, require_agent_release=require_agent_release)
    admission = WorkerMaintenance.from_environment(service)
    server = create_server(service, maintenance=admission)
    readiness = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(readiness, server)
    if not server.add_insecure_port(f"127.0.0.1:{port}"):
        service.close()
        raise RuntimeError("ASR loopback bind failed")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)
    await readiness.set("voice.v1.Recognition", health_pb2.HealthCheckResponse.SERVING)
    await server.start()
    if admission:
        admission.start()
    print(
        f"event=asr_ready device=cuda backend={name} revision={backend.pin['revision']} "
        f"vocabulary_entries={len(backend.replacements)}",
        flush=True,
    )
    try:
        await stopping.wait()
    finally:
        if admission:
            await admission.stop()
        await readiness.enter_graceful_shutdown()
        for state in service.generations.values():
            state.cancelled.set()
        await server.stop(2)
        service.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15071)
    parser.add_argument("--require-agent-release", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        asyncio.run(serve(args.port, args.require_agent_release))
    except Exception as error:
        # Model/transport exceptions may contain paths or data; keep startup output bounded.
        print(f"event=asr_startup_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
