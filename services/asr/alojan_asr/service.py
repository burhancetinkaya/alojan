"""Bounded recognition over voice.v1; model inference never runs on the event loop."""

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor

import grpc
from alojan_contracts.audio import IDENTIFIER, MAX_MESSAGE_BYTES, AudioStreamValidator
from alojan_contracts.generation import GenerationControl
from alojan_contracts.vocabulary import compile_replacements
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc


class RecognitionService(GenerationControl, rpc.RecognitionServicer):
    def __init__(self, backend, *, require_agent_release=False):
        self.backend = backend
        super().__init__()
        self.active = False
        self.inference = None
        self.inference_call_id = None
        self.require_agent_release = require_agent_release
        self.configurations = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr")

    async def ConfigureCall(self, request, context):
        if (
            context.time_remaining() is None
            or not IDENTIFIER.fullmatch(request.call_id)
            or not request.call_id.startswith("managed-")
            or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", request.release_id)
            or not re.fullmatch(r"[0-9a-f]{64}", request.manifest_digest)
            or request.configuration.schema_version != 1
        ):
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "invalid recognition configuration"
            )
        await self.require_lease(request.call_id, context)
        aliases = dict(request.configuration.replacements)
        try:
            compiled = compile_replacements(json.dumps(aliases, ensure_ascii=False))
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid recognition vocabulary")
        identity = (request.release_id, request.manifest_digest, tuple(sorted(aliases.items())))
        existing = self.configurations.get(request.call_id)
        if existing:
            if existing[0] != identity:
                await context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION, "recognition release pinned"
                )
            return pb.AgentAck(accepted=True)
        if any(
            key[0] == request.call_id and state.started for key, state in self.generations.items()
        ):
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "recognition already started")
        self.configurations[request.call_id] = (identity, compiled)
        return pb.AgentAck(accepted=True)

    def release_call(self, call_id):
        super().release_call(call_id)
        self.configurations.pop(call_id, None)

    async def decode(self, audio, sample_format, state, context, call_id, configuration):
        self.inference_call_id = call_id
        args = (bytes(audio), sample_format)
        if configuration is not None:
            args += (configuration[1],)
        self.inference = asyncio.get_running_loop().run_in_executor(
            self.executor, self.backend.transcribe, *args
        )
        # Observe exceptions even if the RPC ends before the native decoder returns.
        self.inference.add_done_callback(
            lambda future: None if future.cancelled() else future.exception()
        )
        try:
            # Native CTranslate2 decoding is not preemptible. Retain its admission slot
            # until it returns; cancellation drops its output and never queues another decode.
            result = await self.wait(asyncio.shield(self.inference), state, context)
        except grpc.aio.AbortError:
            raise
        except Exception:
            await context.abort(grpc.StatusCode.INTERNAL, "recognition failed")
        try:
            valid = isinstance(result, str) and len(result.encode("utf-8")) <= 8192
        except UnicodeError:
            valid = False
        if not valid:
            await context.abort(grpc.StatusCode.INTERNAL, "invalid recognition output")
        return result

    async def StreamRecognize(self, request_iterator, context):
        if context.time_remaining() is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "deadline required")
        validator = AudioStreamValidator()
        state = None
        audio = bytearray()
        samples = 0
        next_partial = 16000
        text = ""
        decoded_samples = 0
        claimed = False
        configuration = None
        try:
            while True:
                try:
                    frame = (
                        await self.wait(anext(request_iterator), state, context)
                        if state
                        else await anext(request_iterator)
                    )
                except StopAsyncIteration:
                    break
                try:
                    validator.accept(frame)
                    if frame.sample_rate_hz != 16000:
                        raise ValueError("recognition requires 16 kHz PCM")
                except ValueError as error:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
                if state is None:
                    state = await self.state(frame, context)
                    configuration = self.configurations.get(frame.call_id)
                    if self.require_agent_release and configuration is None:
                        await context.abort(
                            grpc.StatusCode.FAILED_PRECONDITION, "agent release required"
                        )
                    if state.cancelled.is_set():
                        await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
                    if state.started:
                        await context.abort(
                            grpc.StatusCode.ALREADY_EXISTS, "generation already used"
                        )
                    draining = self.inference is not None and not self.inference.done()
                    if self.active or (draining and self.inference_call_id != frame.call_id):
                        await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "recognition busy")
                    state.started = True
                    self.active = claimed = True
                    if draining:
                        # A cancelled monitor may still be inside non-preemptible CUDA decode.
                        # Reserve one successor for this call; never queue a second native job.
                        await self.wait(
                            asyncio.gather(asyncio.shield(self.inference), return_exceptions=True),
                            state,
                            context,
                            timeout=1.5,
                        )
                width = 2 if frame.format == "pcm_s16le" else 4
                samples += len(frame.audio) // width
                if samples > 30 * 16000:
                    await context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED, "turn exceeds 30 seconds"
                    )
                audio.extend(frame.audio)
                # Spend the next periodic decode at most 400 ms early, never add a
                # decode per hint. Repeated hints cannot accelerate the one-second budget.
                hinted = frame.partial_hint and samples >= next_partial - 6400
                if samples >= next_partial or hinted:
                    text = await self.decode(
                        audio, frame.format, state, context, frame.call_id, configuration
                    )
                    decoded_samples = samples
                    next_partial = max(next_partial, samples) + 16000
                    await self.wait(
                        context.write(
                            pb.RecognitionEvent(
                                call_id=frame.call_id,
                                generation_id=frame.generation_id,
                                text=text,
                                processed_audio_ms=samples // 16,
                            )
                        ),
                        state,
                        context,
                        timeout=1.0,
                    )
            if state is None:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "empty audio stream")
            if samples != decoded_samples:
                text = await self.decode(
                    audio, frame.format, state, context, frame.call_id, configuration
                )
            await self.wait(
                context.write(
                    pb.RecognitionEvent(
                        call_id=frame.call_id,
                        generation_id=frame.generation_id,
                        text=text,
                        is_final=True,
                        processed_audio_ms=samples // 16,
                    )
                ),
                state,
                context,
                timeout=1.0,
            )
        finally:
            if claimed:
                self.active = False
            audio.clear()

    def close(self):
        self.close_leases()
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
    rpc.add_RecognitionServicer_to_server(service, server)
    rpc.add_GenerationControlServicer_to_server(service, server)
    return server
