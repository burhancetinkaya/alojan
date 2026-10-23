"""Loopback-only ASR worker; reports ready only after pinned CUDA warm-up."""

import argparse
import asyncio
import signal

from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from .model import PIN, WhisperBackend
from .service import RecognitionService, create_server


async def serve(port):
    backend = WhisperBackend()
    service = RecognitionService(backend)
    server = create_server(service)
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
    print(
        f"event=asr_ready device=cuda compute_type=float16 revision={PIN['revision']}", flush=True
    )
    try:
        await stopping.wait()
    finally:
        await readiness.enter_graceful_shutdown()
        for state in service.generations.values():
            state.cancelled.set()
        await server.stop(2)
        service.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15071)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        asyncio.run(serve(args.port))
    except Exception as error:
        # Model/transport exceptions may contain paths or data; keep startup output bounded.
        print(f"event=asr_startup_failed kind={type(error).__name__}", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
