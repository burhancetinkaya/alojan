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

from .models import Call, acknowledges_note, normalize
from .prepared import PreloadError
from .legacy import LEGACY_RUNTIME
from .phrases import phrase_end
from .timing import TurnTiming
from .routing import RoutingError
from .experience import ResponseLifecycle


RECOVERY_PROMPTS = {
    key: getattr(LEGACY_RUNTIME.speech, key)
    for key in ("silence_reminder", "clarification", "silence_timeout")
}


async def recovery_stream(event, runtime=None):
    yield getattr((runtime or LEGACY_RUNTIME).speech, event)


class AgentService(GenerationControl, rpc.AgentServicer):
    def __init__(self, backend, store, *, router=None, prepared=None):
        super().__init__()
        self.backend, self.store = backend, store
        self.calls = {}
        self.active = 0
        self.summary_active = False
        self.maintenance = None
        self.turn_tasks = {}
        self.router = router
        self.prepared = prepared
        self.readiness = None
        self.prepared_calls = {}
        self.routes = {}
        self.initializations = {}
        # Only the attached node coordinator may grant admission; legacy startup has none.
        self.answer_permits = set()
        self.answered_calls = set()
        self.lifecycle_locks = {}

    def release_call(self, call_id):
        super().release_call(call_id)
        pending = self.initializations.pop(call_id, None)
        if pending:
            pending.cancel()
        self.routes.pop(call_id, None)
        self.answer_permits.discard(call_id)
        self.answered_calls.discard(call_id)
        self.lifecycle_locks.pop(call_id, None)
        pack = self.prepared_calls.pop(call_id, None)
        if pack is not None:
            self.prepared.unpin(pack)
        call = self.calls.pop(call_id, None)
        if call:
            call.ended = True

    async def setup_boundary(self, request, context):
        if self.router is None:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "routing not enabled")
        if context.time_remaining() is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "deadline required")
        try:
            generation_key(pb.CancelRequest(call_id=request.call_id, generation_id="setup"))
            if not request.call_id.startswith("managed-"):
                raise ValueError()
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid managed call")
        await self.require_lease(request.call_id, context)

    async def InitializeCall(self, request, context):
        await self.setup_boundary(request, context)
        cid = request.call_id
        if cid in self.initializations:
            await context.abort(grpc.StatusCode.ABORTED, "initialization in progress")
        lease = self.leases[cid][0]
        task = asyncio.create_task(
            self.router.initialize(
                cid, request.called_e164, request.called_source, request.caller_e164 or None
            )
        )
        self.initializations[cid] = task
        try:
            async with asyncio.timeout(min(1.8, context.time_remaining())):
                route = await task
            await self.require_lease(cid, context)
            if self.leases[cid][0] != lease:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "call lease changed")
            if self.prepared is None:
                raise PreloadError("release_not_preloaded")
            if cid not in self.calls:
                pack = self.prepared.pin(route)
                self.prepared_calls[cid] = pack
                self.calls[cid] = Call(
                    runtime=pack.runtime, route=route, caller_number=request.caller_e164 or None
                )
            self.routes[cid] = route
            ready = self.readiness is not None and self.readiness.accepts(route)
            if ready:
                self.answer_permits.add(cid)
            return pb.CallInitializationReply(
                release_id=route.release_id,
                manifest_digest=route.manifest_digest,
                ready_for_answer=ready,
                gateway=self.calls[cid].runtime.engine.gateway_configuration(),
                synthesis=self.calls[cid].runtime.synthesis.to_proto(),
                recognition=pb.RecognitionConfiguration(
                    schema_version=1,
                    replacements=dict(self.calls[cid].runtime.asr_replacements),
                ),
            )
        except RoutingError as error:
            code = grpc.StatusCode.FAILED_PRECONDITION
            if error.code.startswith("invalid_"):
                code = grpc.StatusCode.INVALID_ARGUMENT
            elif error.code == "routing_temporarily_unavailable":
                code = grpc.StatusCode.UNAVAILABLE
            await context.abort(code, error.code)
        except TimeoutError:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "initialization timed out")
        except asyncio.CancelledError:
            if context.cancelled():
                raise
            await context.abort(grpc.StatusCode.CANCELLED, "initialization cancelled")
        except (grpc.RpcError, grpc.aio.AbortError):
            raise
        except PreloadError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "release not preloaded")
        except ValueError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "unsupported agent runtime")
        except Exception:
            await context.abort(grpc.StatusCode.UNAVAILABLE, "initialization unavailable")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if self.initializations.get(cid) is task:
                self.initializations.pop(cid)

    async def GetPreparedAudio(self, request, context):
        await self.setup_boundary(request, context)
        pack = self.prepared_calls.get(request.call_id)
        call = self.calls.get(request.call_id)
        if (
            pack is None
            or call is None
            or call.ended
            or request.call_id in self.initializations
            or (request.release_id, request.manifest_digest) != pack.key[1:]
        ):
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "prepared audio unavailable")
        # Immutable prevalidated bytes only: no disk, model, DB or mutable current binding.
        return pb.PreparedAudioReply(
            call_id=request.call_id,
            release_id=pack.key[1],
            manifest_digest=pack.key[2],
            greeting_pcm=pack.greeting_pcm,
            unavailable_pcm=pack.unavailable_pcm,
            greeting_pad_ms=pack.runtime.engine.greeting_pad_ms,
            waiting_pcm=pack.waiting_pcm,
            waiting_text=pack.runtime.waiting_text or "",
        )

    async def CancelCallSetup(self, request, context):
        await self.setup_boundary(request, context)
        async with self.lifecycle_locks.setdefault(request.call_id, asyncio.Lock()):
            await self.require_lease(request.call_id, context)
            return await self.cancel_setup(request, context)

    async def cancel_setup(self, request, context):
        pending = self.initializations.get(request.call_id)
        if pending:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        try:
            async with asyncio.timeout(min(1.8, context.time_remaining())):
                await self.router.cancel_unanswered(request.call_id)
        except RoutingError as error:
            code = (
                grpc.StatusCode.FAILED_PRECONDITION
                if error.code == "call_already_answered"
                else grpc.StatusCode.UNAVAILABLE
            )
            await context.abort(code, "setup cancellation unavailable")
        except TimeoutError:
            await context.abort(grpc.StatusCode.UNAVAILABLE, "setup cancellation unavailable")
        self.answer_permits.discard(request.call_id)
        self.answered_calls.discard(request.call_id)
        self.routes.pop(request.call_id, None)
        pack = self.prepared_calls.pop(request.call_id, None)
        if pack is not None:
            self.prepared.unpin(pack)
        call = self.calls.pop(request.call_id, None)
        if call:
            call.ended = True
        return pb.AgentAck(accepted=True)

    def call_store(self, call_id):
        if self.router is None:
            return self.store
        route = self.routes.get(call_id)
        if route is None:
            raise ValueError("call route unavailable")
        return self.store.for_route(route)

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
        if self.router is not None:
            if (
                call is None
                or call.runtime is None
                or call.ended
                or request.call_id not in self.answer_permits
                or request.call_id not in self.answered_calls
                or request.call_id not in self.routes
                or request.call_id not in self.prepared_calls
            ):
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "routed call not active")
            if number is not None and number != call.caller_number:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "caller metadata conflict")
        if call is None:
            if len(self.calls) >= 128:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "call capacity")
            call = self.calls[request.call_id] = Call(caller_number=number)
        engine = (call.runtime or LEGACY_RUNTIME).engine
        output = engine.output_budget
        if call.ended or call.active or call.turns >= engine.max_call_turns or self.active >= 2:
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "call unavailable")
        if event == "silence_reminder" and call.silence_reminded:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "reminder already used")
        if event == "silence_reminder":
            call.silence_reminded = True
        state.started = call.active = True
        self.turn_tasks[request.call_id] = asyncio.current_task()
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
        waiting_text = call.runtime.waiting_text if call.runtime and not event else None
        lifecycle = ResponseLifecycle(call.turns) if waiting_text else None
        call.response_lifecycle = lifecycle
        first_phrase_ms = -1
        first_content_ms = -1
        outcome = "failed"
        try:
            await self.call_store(request.call_id).start(request.call_id, call.caller_number)
            if not event:
                await self.call_store(request.call_id).utterance(
                    request.call_id, request.generation_id, "caller", text
                )
            timing.db_ready_ms = timing.elapsed()

            async def save_note(note, version):
                if state.cancelled.is_set() or call.ended:
                    raise asyncio.CancelledError()
                operation = ("note", version)
                if lifecycle:
                    lifecycle.dispatch(operation, call.turns)
                try:
                    return await self.call_store(request.call_id).note(
                        request.call_id, note, version
                    )
                finally:
                    if lifecycle:
                        lifecycle.settle(operation)

            stream = (
                recovery_stream(event, call.runtime)
                if event
                else self.backend.stream(call, save_note)
            )
            buffer = ""
            total = 0
            index = 0
            content_phrases = 0
            async with asyncio.timeout(min(engine.turn_timeout_seconds, context.time_remaining())):
                while True:
                    try:
                        pending_delta = asyncio.create_task(
                            self.wait(anext(stream), state, context)
                        )
                        if lifecycle:
                            while not pending_delta.done():
                                await asyncio.wait({pending_delta}, timeout=0.05)
                                # A completed response or cancellation wins the same-tick race.
                                if pending_delta.done() or state.cancelled.is_set():
                                    break
                                if lifecycle.claim_waiting():
                                    await self.emit(
                                        request,
                                        call,
                                        state,
                                        context,
                                        index,
                                        waiting_text,
                                        kind="waiting",
                                    )
                                    if index == 0:
                                        first_phrase_ms = timing.elapsed()
                                    index += 1
                        delta = await pending_delta
                        pending_delta = None
                    except StopAsyncIteration:
                        break
                    if not isinstance(delta, str) or not delta:
                        raise ValueError("invalid text delta")
                    if lifecycle:
                        lifecycle.final_ready = True
                    total += len(delta.encode())
                    if total > output.turn_max_bytes:
                        raise ValueError("text limit")
                    buffer += delta
                    while True:
                        end = phrase_end(buffer, output.phrase_max_chars)
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
        except (grpc.RpcError, grpc.aio.AbortError):
            raise
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception as error:
            print(f"event=agent_failed kind={type(error).__name__}", flush=True)
            await context.abort(grpc.StatusCode.UNAVAILABLE, "agent unavailable")
        finally:
            if lifecycle:
                lifecycle.closed = True
            try:
                if pending_delta is not None:
                    pending_delta.cancel()
                    await asyncio.gather(pending_delta, return_exceptions=True)
                if stream is not None:
                    await stream.aclose()
            except BaseException:
                self.cleanup_failed = True
                raise
            finally:
                if outcome == "failed" and state.cancelled.is_set():
                    outcome = "cancelled"
                state.cancelled.set()
                call.active = False
                self.active -= 1
                if self.turn_tasks.get(request.call_id) is asyncio.current_task():
                    self.turn_tasks.pop(request.call_id, None)
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
        output = (call.runtime or LEGACY_RUNTIME).engine.output_budget
        content_index = index - int(call.phrase_kinds.get((request.generation_id, 0)) == "waiting")
        if (
            (kind == "waiting" and index != 0)
            or (kind != "waiting" and content_index >= output.max_phrases)
            or len(phrase) > output.phrase_max_chars
            or len(phrase.encode()) > output.phrase_max_bytes
        ):
            raise ValueError("phrase limit")
        call.phrases[(request.generation_id, index)] = phrase
        call.phrase_kinds[(request.generation_id, index)] = kind
        call.phrase_note_versions[(request.generation_id, index)] = (
            call.version
            if kind != "waiting" and call.note_id and call.response_ack_version is None
            else 0
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
        await self.require_lease(request.call_id, context)
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
        waiting = call.phrase_kinds.get(key) == "waiting"
        await self.call_store(request.call_id).utterance(
            request.call_id,
            request.generation_id + ("-w" if waiting else "-p") + str(request.phrase_index),
            "assistant",
            phrase,
            request.sent_audio_ms,
        )
        call.receipts[key] = receipt
        call.acknowledge_playback(request.generation_id)
        if phrase and not waiting:
            call.add_message("assistant", phrase)
            if acknowledges_note(phrase):
                # A late receipt acknowledges its emitted version, never a newer correction.
                call.acknowledged_note_version = max(
                    call.acknowledged_note_version, call.phrase_note_versions.get(key, 0)
                )
            delivered = " ".join(
                p
                for k, p in call.phrases.items()
                if k[0] == request.generation_id
                and call.receipts.get(k, (0, False))[1]
                and call.phrase_kinds.get(k) != "waiting"
            )
            if call.is_help_invitation(delivered):
                call.further_help_offered = True
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

    def lifecycle_route(self, request):
        route = self.routes.get(request.call_id)
        call = self.calls.get(request.call_id)
        if (
            route is None
            or call is None
            or request.call_id not in self.answer_permits
            or (request.release_id, request.manifest_digest)
            != (route.release_id, route.manifest_digest)
        ):
            raise ValueError("call lifecycle unavailable")
        return call

    async def ReportCallAnswered(self, request, context):
        await self.setup_boundary(request, context)
        async with self.lifecycle_locks.setdefault(request.call_id, asyncio.Lock()):
            await self.require_lease(request.call_id, context)
            try:
                call = self.lifecycle_route(request)
                if call.ended:
                    raise ValueError("call ended")
                async with asyncio.timeout(min(1.8, context.time_remaining())):
                    await self.call_store(request.call_id).answered(
                        request.call_id, request.answered_at_unix_ms
                    )
                await self.require_lease(request.call_id, context)
                if self.calls.get(request.call_id) is not call or call.ended:
                    raise ValueError("call released during answer")
                self.answered_calls.add(request.call_id)
            except ValueError:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "answer not accepted")
            except Exception:
                await context.abort(grpc.StatusCode.UNAVAILABLE, "answer persistence unavailable")
        return pb.AgentAck(accepted=True)

    async def reconcile_stale(self, age_seconds):
        if self.router is None:
            return await self.store.reconcile_stale(age_seconds)
        count = 0
        for route in await self.router.stale_routes(age_seconds):
            count += await self.store.for_route(route).reconcile(age_seconds)
        return count

    async def EndCall(self, request, context):
        try:
            generation_key(pb.CancelRequest(call_id=request.call_id, generation_id="end"))
            if request.reason not in {"completed", "disconnected", "failed"}:
                raise ValueError()
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "invalid call end")
        await self.require_lease(request.call_id, context)
        if self.router is not None:
            await self.setup_boundary(request, context)
            async with self.lifecycle_locks.setdefault(request.call_id, asyncio.Lock()):
                await self.require_lease(request.call_id, context)
                if request.call_id not in self.answer_permits:
                    return await self.cancel_setup(
                        pb.CallSetupCancellation(call_id=request.call_id), context
                    )
                try:
                    call = self.lifecycle_route(request)
                    call.ended = True
                    self.answered_calls.discard(request.call_id)
                    for (cid, _), state in self.generations.items():
                        if cid == request.call_id:
                            state.cancelled.set()
                    async with asyncio.timeout(min(1.8, context.time_remaining())):
                        task = self.turn_tasks.get(request.call_id)
                        if task is not None:
                            await asyncio.gather(asyncio.shield(task), return_exceptions=True)
                        await self.call_store(request.call_id).end(
                            request.call_id,
                            request.reason,
                            answered_ms=request.answered_at_unix_ms,
                            ended_ms=request.ended_at_unix_ms,
                        )
                except ValueError:
                    await context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION, "call end not accepted"
                    )
                except Exception:
                    await context.abort(
                        grpc.StatusCode.UNAVAILABLE, "call end persistence unavailable"
                    )
            return pb.AgentAck(accepted=True)
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
            if self.maintenance is not None and self.maintenance.closed:
                await asyncio.sleep(0.25)
                continue
            self.summary_active = True
            try:
                job = await self.store.pending()
                if job:
                    data = await self.store.summary_input(job[0])
                    try:
                        runtime = data.get("runtime") or LEGACY_RUNTIME
                        async with asyncio.timeout(runtime.engine.turn_timeout_seconds):
                            summary = (
                                await self.backend.summarize(data, runtime=data["runtime"])
                                if data.get("runtime")
                                else await self.backend.summarize(data)
                            )
                        # A model cannot upgrade unconfirmed caller content to confirmed facts.
                        confirmed = bool(data["last_note"] and data["last_note"][1])
                        summary.confirmation_status = "confirmed" if confirmed else "unconfirmed"
                        await self.store.summary_result(job[0], summary)
                    except Exception:
                        await self.store.summary_result(job[0])
            except Exception:
                # No exception payloads: providers/DB may include private text or credentials.
                print("event=summary_worker_unavailable", flush=True)
            finally:
                self.summary_active = False
            await asyncio.sleep(1)


def create_server(service, *, reuse_port=True, maintenance=None):
    service.maintenance = maintenance
    server = grpc.aio.server(
        interceptors=[maintenance] if maintenance is not None else [],
        options=[
            ("grpc.so_reuseport", int(reuse_port)),
            ("grpc.max_receive_message_length", 16384),
            # Two 30-second clips plus an optional five-second waiting clip and metadata.
            ("grpc.max_send_message_length", 1100000),
        ],
        maximum_concurrent_rpcs=16,
    )
    rpc.add_AgentServicer_to_server(service, server)
    rpc.add_GenerationControlServicer_to_server(service, server)
    return server
