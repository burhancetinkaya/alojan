"""One admitted synthesis, bounded PCM frames, and cancellation across worker threads."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import threading
import unicodedata

import grpc
from alojan_contracts.audio import IDENTIFIER, MAX_MESSAGE_BYTES
from alojan_contracts.generation import GenerationControl
from alojan_contracts.synthesis import SynthesisProfile
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

RATE = 8000
FRAME_BYTES = 320


class InvalidText(ValueError):
    """The pinned frontend produced no speakable text or exceeded its expansion limit."""


class SynthesisService(GenerationControl, rpc.SynthesisServicer):
    def __init__(self, backend, *, require_agent_release=False):
        super().__init__()
        self.backend = backend
        profile = getattr(backend, "synthesis_profile", None)
        if profile is not None and not isinstance(profile, SynthesisProfile):
            raise ValueError("Invalid loaded synthesis profile")
        self.loaded_profile = profile
        self.require_agent_release = require_agent_release
        self.configurations = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tts")
        self.inference = None
        self.active = False
        self.stop = threading.Event()
        self.queue_peak = 0

    async def ConfigureCall(self, request, context):
        if (
            context.time_remaining() is None
            or not IDENTIFIER.fullmatch(request.call_id)
            or not request.call_id.startswith("managed-")
            or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", request.release_id)
            or not re.fullmatch(r"[0-9a-f]{64}", request.manifest_digest)
        ):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid synthesis configuration")
        await self.require_lease(request.call_id, context)
        try:
            profile = SynthesisProfile.from_proto(request.configuration)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid synthesis profile")
        if self.loaded_profile is None or profile != self.loaded_profile:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "synthesis worker mismatch")
        identity = (request.release_id, request.manifest_digest, profile)
        existing = self.configurations.get(request.call_id)
        if existing:
            if existing != identity:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "synthesis release pinned")
            return pb.AgentAck(accepted=True)
        if any(
            key[0] == request.call_id and state.started for key, state in self.generations.items()
        ):
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "synthesis already started")
        self.configurations[request.call_id] = identity
        return pb.AgentAck(accepted=True)

    def release_call(self, call_id):
        super().release_call(call_id)
        self.configurations.pop(call_id, None)

    def produce(self, text, queue, loop, stop):
        async def enqueue(item):
            await queue.put(item)
            self.queue_peak = max(self.queue_peak, queue.qsize())

        def put(item):
            pending = asyncio.run_coroutine_threadsafe(enqueue(item), loop)
            try:
                while not stop.is_set():
                    try:
                        pending.result(timeout=0.05)
                        return True
                    except FutureTimeout:
                        pass
                return False
            finally:
                pending.cancel()

        stream = None
        tail = bytearray()
        total = 0
        status = None
        try:
            stream = self.backend.stream(text)
            while not stop.is_set():
                try:
                    chunk = next(stream)
                except StopIteration:
                    break
                if (
                    not isinstance(chunk, bytes)
                    or not chunk
                    or len(chunk) % 2
                    or len(chunk) > 80000
                ):
                    raise ValueError("invalid model PCM")
                total += len(chunk)
                if total > 30 * RATE * 2:
                    status = grpc.StatusCode.RESOURCE_EXHAUSTED
                    break
                tail.extend(chunk)
                offset = 0
                while offset + FRAME_BYTES <= len(tail):
                    if not put(bytes(tail[offset : offset + FRAME_BYTES])):
                        return
                    offset += FRAME_BYTES
                del tail[:offset]
            if not stop.is_set() and status is None:
                if not total:
                    raise ValueError("empty model audio")
                if tail:
                    put(bytes(tail).ljust(FRAME_BYTES, b"\0"))
        except InvalidText:
            status = grpc.StatusCode.INVALID_ARGUMENT
        except Exception:
            status = grpc.StatusCode.INTERNAL
        finally:
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                self.cleanup_failed = True
                status = grpc.StatusCode.INTERNAL
            tail.clear()
            if not stop.is_set():
                put(status)

    async def StreamSynthesize(self, request, context):
        if context.time_remaining() is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "deadline required")
        text = request.text.strip()
        if (
            not text
            or len(text) > 512
            or not any(ch.isalnum() for ch in text)
            or any(unicodedata.category(ch).startswith("C") and ch not in "\n\t" for ch in text)
        ):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid synthesis text")
        state = await self.state(request, context)
        if (
            self.require_agent_release or request.call_id.startswith("managed-")
        ) and request.call_id not in self.configurations:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "synthesis not configured")
        if state.cancelled.is_set():
            await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
        if state.started:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, "generation already used")
        if self.active or (self.inference is not None and not self.inference.done()):
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "synthesis busy")
        state.started = self.active = True
        self.stop = stop = threading.Event()
        queue = asyncio.Queue(maxsize=8)
        loop = asyncio.get_running_loop()
        self.inference = loop.run_in_executor(self.executor, self.produce, text, queue, loop, stop)
        self.inference.add_done_callback(
            lambda future: None if future.cancelled() else future.exception()
        )
        sequence = 0
        try:
            while True:
                self.queue_peak = max(self.queue_peak, queue.qsize())
                audio = await self.wait(queue.get(), state, context)
                if audio is None:
                    await self.wait(asyncio.shield(self.inference), state, context)
                    break
                if isinstance(audio, grpc.StatusCode):
                    await context.abort(audio, "synthesis failed or exceeded limits")
                await self.wait(
                    context.write(
                        pb.AudioFrame(
                            call_id=request.call_id,
                            generation_id=request.generation_id,
                            sequence=sequence,
                            sample_rate_hz=RATE,
                            channels=1,
                            format="pcm_s16le",
                            audio=audio,
                        )
                    ),
                    state,
                    context,
                    timeout=0.2,
                )
                sequence += 1
        finally:
            stop.set()
            self.active = False
            while not queue.empty():
                queue.get_nowait()

    def close(self):
        self.close_leases()
        self.stop.set()
        for state in self.generations.values():
            state.cancelled.set()
        self.executor.shutdown(wait=False, cancel_futures=True)


def create_server(service, *, maintenance=None):
    service.maintenance = maintenance
    server = grpc.aio.server(
        interceptors=[maintenance] if maintenance is not None else [],
        options=[
            ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
            ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
        ],
        maximum_concurrent_rpcs=16,
    )
    rpc.add_SynthesisServicer_to_server(service, server)
    rpc.add_GenerationControlServicer_to_server(service, server)
    return server
