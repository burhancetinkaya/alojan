"""Semantic acknowledgement must be backed by storage and complete, versioned playback."""

import asyncio
import json

import grpc
import pytest
from agents.testing import ModelStep, ScriptedModel, function_call
from openai import AsyncOpenAI
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc

from alojan_agent.backend import Backend, FAREWELL
from alojan_agent.models import Call, Note, acknowledges_note
from alojan_agent.service import AgentService, create_server
from test_agent import MemoryStore, collect, request


def speech(text, acknowledgement, call_id="speech"):
    return ModelStep(
        output=[
            function_call(
                "respond",
                {"text": text, "acknowledges_saved_note": acknowledgement},
                call_id=call_id,
            )
        ]
    )


@pytest.mark.parametrize("delivery", ["complete", "partial", "late"])
def test_natural_acknowledgement_binds_to_complete_response_and_saved_version(delivery):
    async def run():
        note = Note(subject="Rapor", message="Rapor perşembe gelecek.")
        natural = "Değişikliği de ekledim."
        assert not acknowledges_note(natural)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[function_call("take_note", note.model_dump(), call_id="save")]
                    ),
                    speech(natural, True),
                    ModelStep(
                        output=[
                            function_call(
                                "finish_call",
                                {
                                    "reason": "caller_finished",
                                    "confirmed_message": None,
                                    "closing_text": "Değişikliği de ekledim, iyi günler.",
                                    "acknowledges_saved_note": True,
                                },
                                call_id="close",
                            )
                        ]
                    ),
                ]
            ),
        )
        service = AgentService(backend, MemoryStore())
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = rpc.AgentStub(channel)
                events = await collect(stub, request(text="Rapor perşembe gelecek."))
                assert len(events) == 3
                call = service.calls["one"]
                if delivery == "late":
                    call.take_note(note.model_copy(update={"message": "Rapor cuma gelecek."}))
                    call.note_id = await service.store.note("one", call.note, call.version)
                for index in range(2):
                    report = pb.PlaybackReport(
                        call_id="one",
                        generation_id="turn-1",
                        phrase_index=index,
                        sent_audio_ms=500,
                        completed=not (delivery == "partial" and index == 1),
                    )
                    await stub.ReportPlayback(report, timeout=2)
                    await stub.ReportPlayback(report, timeout=2)
                    if index == 0:
                        assert call.acknowledged_note_version == 0
                assert call.acknowledged_note_version == (0 if delivery == "partial" else 1)
                assert not call.note.confirmed
                if delivery == "late":
                    assert call.version == 2
                if delivery == "complete":
                    closing = await collect(
                        stub, request(gen="turn-2", text="Hepsi bu, iyi günler.")
                    )
                    assert " ".join(e.text for e in closing[:-1]) == FAREWELL
                    assert json.loads(closing[-1].detail_json)["finish_call"]
                    assert len(service.store.notes) == 1
        finally:
            await server.stop(0)
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("saved", [False, True])
def test_question_is_not_acknowledgement_and_intent_cannot_authorize_storage(saved):
    async def run():
        call = Call(last_user="Bir sorum var.")
        call.add_message("user", call.last_user)
        if saved:
            call.take_note(Note(subject="Hesap", message="Hesabıma giremiyorum."))
            call.note_id = "durable"
        steps = [] if saved else [speech("İsteğinizi de ekledim.", True, "invalid-ack")]
        steps.append(speech("Hangi uygulamada sorun yaşıyorsunuz?", False))
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=ScriptedModel(steps)
        )

        async def save(*args):
            raise AssertionError("unexpected save")

        try:
            replies = [s async for s in backend.stream(call, save)]
            assert replies == ["Hangi uygulamada sorun yaşıyorsunuz?"]
            assert call.response_ack_version == 0
            assert call.acknowledged_note_version == 0
        finally:
            await backend.close()

    asyncio.run(run())


def test_cancelled_response_cannot_leave_acknowledgement_for_next_turn():
    async def run():
        blocked = asyncio.Event()

        class Interrupted:
            async def stream(self, call, save):
                call.response_ack_version = call.version
                yield "Değişikliği de ekledim. "
                blocked.set()
                await asyncio.Event().wait()

        service = AgentService(Interrupted(), MemoryStore())
        call = service.calls["one"] = Call()
        call.take_note(Note(subject="Talep", message="Rapor gönderilsin."))
        call.note_id = "durable"
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = rpc.AgentStub(channel)
                stream = stub.RunTurn(request(), timeout=2)
                assert (await stream.read()).type == "text_delta"
                await asyncio.wait_for(blocked.wait(), 1)
                stream.cancel()
                for _ in range(100):
                    if not call.active:
                        break
                    await asyncio.sleep(0.01)
                assert not call.active and not call.note_ack_groups
                await stub.ReportPlayback(
                    pb.PlaybackReport(
                        call_id="one",
                        generation_id="turn-1",
                        phrase_index=0,
                        sent_audio_ms=500,
                        completed=True,
                    ),
                    timeout=2,
                )
                assert call.acknowledged_note_version == 0
                await collect(
                    stub,
                    request(gen="turn-2", text="", context='{"input_event":"silence_reminder"}'),
                )
                assert call.response_ack_version == 0 and not call.note_ack_groups
        finally:
            await server.stop(0)

    asyncio.run(run())


def test_receipt_before_response_seals_waits_for_remaining_audio():
    async def run():
        release = asyncio.Event()

        class SplitResponse:
            async def stream(self, call, save):
                call.response_ack_version = call.version
                yield "Değişikliği de ekledim. "
                await release.wait()
                yield "Başka yardımcı olabileceğim bir konu var mı?"

        service = AgentService(SplitResponse(), MemoryStore())
        call = service.calls["one"] = Call()
        call.take_note(Note(subject="Talep", message="Rapor gönderilsin."))
        call.note_id = "durable"
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = rpc.AgentStub(channel)
                stream = stub.RunTurn(request(), timeout=2)
                assert (await stream.read()).type == "text_delta"
                await stub.ReportPlayback(
                    pb.PlaybackReport(
                        call_id="one",
                        generation_id="turn-1",
                        phrase_index=0,
                        sent_audio_ms=500,
                        completed=True,
                    ),
                    timeout=2,
                )
                assert not call.note_ack_groups and call.acknowledged_note_version == 0
                release.set()
                assert (await stream.read()).type == "text_delta"
                assert (await stream.read()).type == "end"
                assert await stream.read() is grpc.aio.EOF
                assert call.acknowledged_note_version == 0
                await stub.ReportPlayback(
                    pb.PlaybackReport(
                        call_id="one",
                        generation_id="turn-1",
                        phrase_index=1,
                        sent_audio_ms=500,
                        completed=True,
                    ),
                    timeout=2,
                )
                assert call.acknowledged_note_version == 1
        finally:
            await server.stop(0)

    asyncio.run(run())
