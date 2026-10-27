"""Waiting is optional progress, never a final answer or note acknowledgement."""

import asyncio
from dataclasses import replace
import json

import grpc
import pytest

from alojan_agent.experience import ResponseLifecycle
from alojan_agent.legacy import LEGACY_RUNTIME
from alojan_agent.models import Call, Note
from alojan_agent.service import AgentService, create_server
from alojan_contracts.configuration import AgentDraft, EnginePreset
from alojan_contracts.assets import speech_identity, validate_manifest
from alojan_contracts.experience import ResponseExperience
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc
from test_agent import MemoryStore, request, collect
from test_agent_releases import pack


def test_lifecycle_is_once_per_turn_and_ignores_stale_operations():
    now = [0.0]
    state = ResponseLifecycle(2, clock=lambda: now[0])
    state.dispatch("stale", 1)
    now[0] = 2
    assert not state.due()
    state.dispatch("one", 2)
    assert not state.due()
    now[0] += 0.31
    assert state.claim_waiting()
    state.settle("stale")
    assert state.operation == "one"
    state.settle("one")
    state.dispatch("two", 2)
    now[0] += 3
    assert not state.claim_waiting()
    state.closed = True
    state.dispatch("late", 2)
    assert state.operation == "two"


@pytest.mark.parametrize("mode", ["fast", "slow", "off", "cancel"])
def test_real_grpc_waiting_preserves_final_response_receipts_and_cancellation(mode):
    async def run():
        class Backend:
            async def stream(self, call, save):
                state = call.response_lifecycle
                if state:
                    state.dispatch("operation", call.turns)
                    # Advance only the test clock origin; production thresholds stay fixed.
                    state.started -= 2
                    state.operation_started -= 1
                if mode in {"slow", "cancel"}:
                    await asyncio.sleep(0.15 if mode == "slow" else 10)
                if state:
                    state.settle("operation")
                call.response_ack_version = 1
                yield "İstenen kayıt sayısı üç."

        runtime = replace(
            LEGACY_RUNTIME, waiting_text=None if mode == "off" else "Kontrol ediyorum."
        )
        service = AgentService(Backend(), MemoryStore())
        call = service.calls["one"] = Call(runtime=runtime)
        call.note = Note(subject="Synthetic", message="Synthetic")
        call.note_id, call.version = "note", 1
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = rpc.AgentStub(channel)
                if mode == "cancel":
                    stream = stub.RunTurn(request(), timeout=2)
                    first = await stream.read()
                    assert json.loads(first.detail_json)["kind"] == "waiting"
                    await rpc.GenerationControlStub(channel).CancelGeneration(
                        pb.CancelRequest(call_id="one", generation_id="turn-1"), timeout=1
                    )
                    with pytest.raises(grpc.aio.AioRpcError):
                        await stream.read()
                    return
                events = await collect(stub, request())
                phrases = [e for e in events if e.type == "text_delta"]
                assert len(phrases) == (2 if mode == "slow" else 1)
                assert phrases[-1].text == "İstenen kayıt sayısı üç."
                assert not json.loads(events[-1].detail_json)["finish_call"]
                for index, phrase in enumerate(phrases):
                    waiting = json.loads(phrase.detail_json)["kind"] == "waiting"
                    await stub.ReportPlayback(
                        pb.PlaybackReport(
                            call_id="one",
                            generation_id="turn-1",
                            phrase_index=index,
                            sent_audio_ms=20 if waiting else 1000,
                            completed=not waiting,
                        ),
                        timeout=1,
                    )
                assert call.acknowledged_note_version == 1
                assert all("Kontrol" not in m["content"] for m in call.messages)
                if mode == "slow":
                    record = next(x for x in service.store.utterances if x[1] == "turn-1-w0")
                    assert record[3] == "" and record[4] == 20
        finally:
            await server.stop(0)

    asyncio.run(run())


def test_assets_and_omission_preserve_existing_releases(tmp_path):
    draft = AgentDraft(
        agent_name="Test",
        owner_display_name="Owner",
        owner_address="Owner",
        owner_dative="Owner",
        owner_genitive="Owner",
        instructions="Answer.",
    )
    preset = EnginePreset()
    old = speech_identity(draft, preset)
    assert "response_experience" not in draft.model_dump()
    source = pack(tmp_path, draft)
    old_manifest = json.loads((source / "manifest.json").read_text())
    assert "waiting" not in validate_manifest(old_manifest, draft, preset).model_dump()
    enabled = draft.model_copy(update={"response_experience": ResponseExperience(enabled=True)})
    assert speech_identity(enabled, preset) != old
    assert "waiting" in enabled.speech_texts()
    with pytest.raises(ValueError):
        validate_manifest(old_manifest, enabled, preset)
    other = draft.model_copy(update={"response_experience": ResponseExperience(enabled=False)})
    assert speech_identity(other, preset) == old


@pytest.mark.parametrize("text", ["", " ", "Teslim edildi?", "{secret}", "a\nb", "x" * 101])
def test_invalid_waiting_text_is_rejected(text):
    with pytest.raises(ValueError):
        ResponseExperience(enabled=True, waiting_text=text)
