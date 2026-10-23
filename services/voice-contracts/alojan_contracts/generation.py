"""Shared bounded generation identity and cancellation semantics for speech workers."""

import asyncio
from dataclasses import dataclass, field

import grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc
from .audio import generation_key


@dataclass
class Generation:
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    started: bool = False


class GenerationControl(rpc.GenerationControlServicer):
    def __init__(self):
        self.generations = {}

    async def state(self, request, context):
        try:
            key = generation_key(request)
        except ValueError as error:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        if key not in self.generations:
            # shortcut: no call-release RPC yet; fail closed until lifecycle cleanup is specified.
            if len(self.generations) >= 4096:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "generation capacity")
            self.generations[key] = Generation()
        return self.generations[key]

    async def CancelGeneration(self, request, context):
        state = await self.state(request, context)
        state.cancelled.set()
        return pb.CancelReply(cancelled=True)

    async def wait(self, operation, state, context, timeout=None):
        """Race reads, writes and shielded inference against explicit invalidation."""
        task = asyncio.ensure_future(operation)
        cancelled = asyncio.create_task(state.cancelled.wait())
        try:
            if state.cancelled.is_set():
                await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
            done, _ = await asyncio.wait(
                (task, cancelled), timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if state.cancelled.is_set():
                await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
            if task not in done:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "slow consumer")
            return await task
        finally:
            task.cancel()
            cancelled.cancel()
            await asyncio.gather(task, cancelled, return_exceptions=True)
