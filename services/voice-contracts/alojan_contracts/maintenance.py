"""Operator-only inference fencing on existing private gRPC worker listeners."""

import asyncio
from contextlib import aclosing
import inspect
import os
from pathlib import Path
import secrets
import stat

import grpc
from grpc_health.v1 import health_pb2

MAINTENANCE = "voice.v1.Maintenance"
CLEANUP = frozenset(
    {
        "/voice.v1.GenerationControl/CancelGeneration",
        "/voice.v1.GenerationControl/ReleaseCall",
        "/voice.v1.Agent/CancelCallSetup",
        "/voice.v1.Agent/EndCall",
        "/voice.v1.Agent/ReportPlayback",
    }
)


class WorkerMaintenance(grpc.aio.ServerInterceptor):
    def __init__(self, service, state_file):
        self.service = service
        self.state_file = Path(state_file)
        self.closed = True
        self.active_rpcs = 0
        self.instance = secrets.token_hex(8)
        self.task = None

    @classmethod
    def from_environment(cls, service):
        path = os.environ.get("ALOJAN_WORKER_ADMISSION_FILE")
        return cls(service, path) if path else None

    @property
    def quiescent(self):
        service = self.service
        inference = getattr(service, "inference", None)
        return (
            self.closed
            and not self.active_rpcs
            and not service.leases
            and not service.active
            and not getattr(service, "summary_active", False)
            and not getattr(service, "initializations", {})
            and not getattr(service, "turn_tasks", {})
            and not getattr(service, "cleanup_failed", False)
            and getattr(service.backend, "quiescence_confirmed", True)
            and all(call.ended for call in getattr(service, "calls", {}).values())
            # A cancelled asyncio future cannot attest that its native thread has exited.
            and (
                inference is None
                or (
                    inference.done() and not inference.cancelled() and inference.exception() is None
                )
            )
        )

    def read_closed(self):
        try:
            fd = os.open(self.state_file, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            try:
                return not (stat.S_ISREG(os.fstat(fd).st_mode) and os.read(fd, 16) == b"open\n")
            finally:
                os.close(fd)
        except OSError:
            return True

    async def run(self):
        previous = None
        try:
            while True:
                self.closed = self.read_closed()
                mode = "open" if not self.closed else "quiescent" if self.quiescent else "draining"
                if mode != previous:
                    print(
                        f"event=worker_maintenance instance={self.instance} mode={mode}", flush=True
                    )
                    previous = mode
                await asyncio.sleep(0.25)
        finally:
            self.closed = True

    def start(self):
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        self.closed = True
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def intercept_service(self, continuation, details):
        handler = await continuation(details)
        if handler is None:
            return None
        if details.method == "/grpc.health.v1.Health/Check":

            async def check(request, context):
                if request.service == MAINTENANCE:
                    # Compute now; a cached health flag can outlive in-flight cleanup or resume.
                    return health_pb2.HealthCheckResponse(
                        status=(
                            health_pb2.HealthCheckResponse.SERVING
                            if self.quiescent
                            else health_pb2.HealthCheckResponse.NOT_SERVING
                        )
                    )
                return await handler.unary_unary(request, context)

            return grpc.unary_unary_rpc_method_handler(
                check,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        if details.method.startswith("/grpc.health.v1.Health/"):
            return handler

        async def enter(context):
            if self.closed and details.method not in CLEANUP:
                await context.abort(grpc.StatusCode.UNAVAILABLE, "worker maintenance")
            self.active_rpcs += 1

        for name in ("unary_unary", "unary_stream", "stream_unary", "stream_stream"):
            method = getattr(handler, name)
            if method is None:
                continue
            if inspect.isasyncgenfunction(method):

                async def wrapped(request, context):
                    await enter(context)
                    try:
                        async with aclosing(method(request, context)) as stream:
                            async for response in stream:
                                yield response
                    finally:
                        self.active_rpcs -= 1
            else:

                async def wrapped(request, context):
                    await enter(context)
                    try:
                        return await method(request, context)
                    finally:
                        self.active_rpcs -= 1

            return getattr(grpc, name + "_rpc_method_handler")(
                wrapped,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
