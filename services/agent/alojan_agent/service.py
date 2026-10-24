"""Bounded, generation-scoped agent streaming and audio receipt accounting."""

import asyncio
import hashlib
import json
import re
import time
import unicodedata

import grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc
from alojan_contracts.audio import generation_key
from alojan_contracts.generation import GenerationControl

from .models import Call, acknowledges_note, normalize, offers_more_help
from .phrases import phrase_end
from .timing import TurnTiming


RECOVERY_PROMPTS = {
    "silence_reminder": "Buradayım, sizi dinliyorum.",
    "clarification": "Son söylediğinizi net anlayamadım, tekrar eder misiniz?",
    "silence_timeout": (
        "Sesinizi alamıyorum. Dilerseniz daha sonra tekrar arayabilirsiniz. Hoşça kalın."
    ),
}


async def recovery_stream(event):
    yield RECOVERY_PROMPTS[event]


class AgentService(GenerationControl, rpc.AgentServicer):
    def __init__(self, backend, store):
        super().__init__()
        self.backend, self.store = backend, store
        self.calls = {}
        self.active = 0

    async def RunTurn(self, request, context):
        if context.time_remaining() is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "deadline required")
        state = await self.state(request, context)
        text = request.final_user_text.strip()
        try:
            if len(text.encode()) > 4096 or len(request.context_json) > 1024:
                raise ValueError()
            if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in text):
                raise ValueError()
            metadata = json.loads(request.context_json or "{}")
            if not isinstance(metadata, dict) or set(metadata) - {"caller_number", "input_event"}:
                raise ValueError()
            event = metadata.get("input_event")
            if "input_event" in metadata:
                if not isinstance(event, str) or event not in RECOVERY_PROMPTS or text:
                    raise ValueError()
            elif not text:
                raise ValueError()
            number = metadata.get("caller_number")
            if number is not None and not re.fullmatch(r"\+[1-9][0-9]{7,14}", number):
                raise ValueError()
        except (ValueError, TypeError):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid turn input")
        if state.cancelled.is_set():
            await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
        if state.started:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, "generation used")
        call = self.calls.get(request.call_id)
        if call is None:
            if len(self.calls) >= 128:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "call capacity")
            call = self.calls[request.call_id] = Call(caller_number=number)
        if call.ended or call.active or call.turns >= 16 or self.active >= 2:
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "call unavailable")
        if event == "silence_reminder" and call.silence_reminded:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "reminder already used")
        if event == "silence_reminder":
            call.silence_reminded = True
        state.started = call.active = True
        call.turns += 1
        call.generation_turns[request.generation_id] = call.turns
        self.active += 1
        call.finish = event == "silence_timeout"
        call.response_ack_version = 0 if event else None
        if not event:
            call.last_user = text
            call.add_message("user", text)
        stream = None
        pending_delta = None
        started = time.monotonic()
        call.timing = timing = TurnTiming()
        first_phrase_ms = -1
        first_content_ms = -1
        outcome = "failed"
        try:
            await self.store.start(request.call_id, call.caller_number)
            if not event:
                await self.store.utterance(request.call_id, request.generation_id, "caller", text)
            timing.db_ready_ms = timing.elapsed()

            async def save_note(note, version):
                if state.cancelled.is_set() or call.ended:
                    raise asyncio.CancelledError()
                return await self.store.note(request.call_id, note, version)

            stream = recovery_stream(event) if event else self.backend.stream(call, save_note)
            buffer = ""
            total = 0
            index = 0
            content_phrases = 0
            async with asyncio.timeout(min(20, context.time_remaining())):
                while True:
                    try:
                        pending_delta = asyncio.create_task(
                            self.wait(anext(stream), state, context)
                        )
                        delta = await pending_delta
                        pending_delta = None
                    except StopAsyncIteration:
                        break
                    if not isinstance(delta, str) or not delta:
                        raise ValueError("invalid text delta")
                    total += len(delta.encode())
                    if total > 4096:
                        raise ValueError("text limit")
                    buffer += delta
                    while True:
                        end = phrase_end(buffer)
                        if end is None:
                            break
                        phrase, buffer = buffer[:end].strip(), buffer[end:]
                        if phrase:
                            await self.emit(request, call, state, context, index, phrase)
                            if content_phrases == 0:
                                first_content_ms = round((time.monotonic() - started) * 1000)
                            content_phrases += 1
                            if index == 0:
                                first_phrase_ms = round((time.monotonic() - started) * 1000)
                            index += 1
                if buffer.strip():
                    await self.emit(request, call, state, context, index, buffer.strip())
                    if content_phrases == 0:
                        first_content_ms = round((time.monotonic() - started) * 1000)
                    content_phrases += 1
                    if index == 0:
                        first_phrase_ms = round((time.monotonic() - started) * 1000)
                    index += 1
                if not content_phrases:
                    raise ValueError("empty response")
                await self.wait(
                    context.write(
                        pb.AgentEvent(
                            call_id=request.call_id,
                            generation_id=request.generation_id,
                            type="end",
                            detail_json=json.dumps({"finish_call": call.finish}),
                        )
                    ),
                    state,
                    context,
                    2,
                )
                if call.response_ack_version:
                    # Bind semantic intent to the complete emitted response and durable version.
                    call.note_ack_groups[request.generation_id] = (
                        call.response_ack_version,
                        index,
                    )
                    call.acknowledge_playback(request.generation_id)
                outcome = "completed"
        except asyncio.TimeoutError:
            outcome = "timed_out"
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "agent turn failed")
        except ValueError:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "agent turn failed")
        except grpc.RpcError:
            raise
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception as error:
            print(f"event=agent_failed kind={type(error).__name__}", flush=True)
            await context.abort(grpc.StatusCode.UNAVAILABLE, "agent unavailable")
        finally:
            try:
                if pending_delta is not None:
                    pending_delta.cancel()
                    await asyncio.gather(pending_delta, return_exceptions=True)
                if stream is not None:
                    await stream.aclose()
            finally:
                if outcome == "failed" and state.cancelled.is_set():
                    outcome = "cancelled"
                state.cancelled.set()
                call.active = False
                self.active -= 1
                print(
                    "event=agent_turn "
                    f"call_key={hashlib.sha256(request.call_id.encode()).hexdigest()[:12]} "
                    f"generation={request.generation_id} status={outcome} "
                    f"first_phrase_ms={first_phrase_ms} "
                    f"first_content_ms={first_content_ms} "
                    f"elapsed_ms={round((time.monotonic() - started) * 1000)} "
                    f"finish={int(call.finish)}",
                    flush=True,
                )
                print(
                    "event=agent_latency data="
                    + json.dumps(
                        {
                            "call_key": hashlib.sha256(request.call_id.encode()).hexdigest()[:12],
                            "generation": request.generation_id,
                            "status": outcome,
                            "kind": event or "response",
                            "routing": getattr(self.backend, "routing", "test"),
                            "first_phrase_ms": first_content_ms,
                            "elapsed_ms": round((time.monotonic() - started) * 1000),
                            **timing.snapshot(),
                        },
                        separators=(",", ":"),
                    ),
                    flush=True,
                )

    async def emit(self, request, call, state, context, index, phrase, kind="response"):
        if index >= 16 or len(phrase.encode()) > 1024:
            raise ValueError("phrase limit")
        call.phrases[(request.generation_id, index)] = phrase
        call.phrase_note_versions[(request.generation_id, index)] = (
            call.version if call.note_id and call.response_ack_version is None else 0
        )
        await self.wait(
            context.write(
                pb.AgentEvent(
                    call_id=request.call_id,
                    generation_id=request.generation_id,
                    type="text_delta",
                    text=phrase,
                    detail_json=json.dumps({"phrase_index": index, "kind": kind}),
                )
            ),
            state,
            context,
            5,
        )

    async def ReportPlayback(self, request, context):
        try:
            generation_key(request)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid identity")
        call = self.calls.get(request.call_id)
        key = (request.generation_id, request.phrase_index)
        if call is None or key not in call.phrases or request.sent_audio_ms > 30000:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "unknown playback")
        receipt = (request.sent_audio_ms, request.completed)
        if key in call.receipts:
            if call.receipts[key] != receipt:
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, "receipt conflict")
            return pb.AgentAck(accepted=True)
        if request.completed and not request.sent_audio_ms:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "empty completed playback")
        phrase = call.phrases[key] if request.completed else ""
        await self.store.utterance(
            request.call_id,
            request.generation_id + "-p" + str(request.phrase_index),
            "assistant",
            phrase,
            request.sent_audio_ms,
        )
        call.receipts[key] = receipt
        call.acknowledge_playback(request.generation_id)
        if phrase:
            call.add_message("assistant", phrase)
            if offers_more_help(phrase):
                call.further_help_offered = True
            if acknowledges_note(phrase):
                # A late receipt acknowledges its emitted version, never a newer correction.
                call.acknowledged_note_version = max(
                    call.acknowledged_note_version, call.phrase_note_versions.get(key, 0)
                )
            delivered = " ".join(
                p
                for k, p in call.phrases.items()
                if k[0] == request.generation_id and call.receipts.get(k, (0, False))[1]
            )
            if (
                call.note
                and not call.note.confirmed
                and call.generation_turns.get(request.generation_id) == call.turns
                and normalize(call.note.message) in normalize(delivered)
                and normalize(delivered).endswith("doğru mu")
            ):
                call.offered_version = call.version
                call.offered_turn = call.turns + 1
        return pb.AgentAck(accepted=True)

    async def EndCall(self, request, context):
        try:
            generation_key(pb.CancelRequest(call_id=request.call_id, generation_id="end"))
            if request.reason not in {"completed", "disconnected", "failed"}:
                raise ValueError()
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid call end")
        call = self.calls.get(request.call_id)
        if call:
            call.ended = True
            for (cid, _), state in self.generations.items():
                if cid == request.call_id:
                    state.cancelled.set()
        await self.store.start(request.call_id, None)
        await self.store.end(request.call_id, request.reason)
        return pb.AgentAck(accepted=True)

    async def summaries(self):
        while True:
            try:
                job = await self.store.pending()
                if job:
                    data = await self.store.summary_input(job[0])
                    try:
                        async with asyncio.timeout(20):
                            summary = await self.backend.summarize(data)
                        # A model cannot upgrade unconfirmed caller content to confirmed facts.
                        confirmed = bool(data["last_note"] and data["last_note"][1])
                        summary.confirmation_status = "confirmed" if confirmed else "unconfirmed"
                        await self.store.summary_result(job[0], summary)
                    except Exception:
                        await self.store.summary_result(job[0])
            except Exception:
                # No exception payloads: providers/DB may include private text or credentials.
                print("event=summary_worker_unavailable", flush=True)
            await asyncio.sleep(1)


def create_server(service):
    server = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", 16384),
            ("grpc.max_send_message_length", 16384),
        ],
        maximum_concurrent_rpcs=16,
    )
    rpc.add_AgentServicer_to_server(service, server)
    rpc.add_GenerationControlServicer_to_server(service, server)
    return server
