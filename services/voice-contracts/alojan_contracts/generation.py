"""Shared bounded generation identity and cancellation semantics for speech workers."""

import asyncio
import secrets
from dataclasses import dataclass, field

import grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc
from .audio import IDENTIFIER, generation_key


@dataclass
class Generation:
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    started: bool = False


class GenerationControl(rpc.GenerationControlServicer):
    def __init__(self):
        self.generations = {}
        self.leases = {}
        self.cleanup_failed = False

    async def OpenCall(self, request, context):
        if (
            not IDENTIFIER.fullmatch(request.call_id)
            or not request.call_id.startswith("managed-")
            or request.lease
        ):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid managed call")
        if request.call_id in self.leases:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, "call already open")
        if len(self.leases) >= 128:
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "call lease capacity")
        token = secrets.token_hex(16)
        # The current gateway hard limit is 120s. Expiry also bounds a lost release RPC.
        timer = asyncio.get_running_loop().call_later(300, self.release_call, request.call_id)
        self.leases[request.call_id] = (token, timer)
        return pb.CallLeaseReply(lease=token)

    async def require_lease(self, call_id, context):
        tokens = [value for key, value in context.invocation_metadata() if key == "x-alojan-lease"]
        if call_id.startswith("managed-") or tokens:
            lease = self.leases.get(call_id)
            if not lease or tokens != [lease[0]]:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "call lease closed")

    def release_call(self, call_id):
        lease = self.leases.pop(call_id, None)
        if lease:
            lease[1].cancel()
            for key in [key for key in self.generations if key[0] == call_id]:
                self.generations.pop(key).cancelled.set()

    async def ReleaseCall(self, request, context):
        if (
            not IDENTIFIER.fullmatch(request.call_id)
            or not request.call_id.startswith("managed-")
            or not request.lease
            or len(request.lease) > 64
        ):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid call release")
        lease = self.leases.get(request.call_id)
        if lease:
            if request.lease != lease[0]:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "call lease mismatch")
            self.release_call(request.call_id)
        return pb.AgentAck(accepted=True)

    def close_leases(self):
        for call_id in list(self.leases):
            self.release_call(call_id)

    async def state(self, request, context):
        try:
            key = generation_key(request)
        except ValueError as error:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        await self.require_lease(key[0], context)
        if key not in self.generations:
            # Legacy callers retain fail-closed tombstones; managed calls release them explicitly.
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
            pending = not task.done()
            task.cancel()
            cancelled.cancel()
            result, _ = await asyncio.gather(task, cancelled, return_exceptions=True)
            if (
                (pending or state.cancelled.is_set())
                and isinstance(result, BaseException)
                and not isinstance(result, asyncio.CancelledError)
            ):
                self.cleanup_failed = True
