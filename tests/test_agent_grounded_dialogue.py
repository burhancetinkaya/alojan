"""Delivered-response repetition must be repaired before it reaches speech."""

import asyncio

import pytest
from agents.testing import ModelStep, ScriptedModel, function_call
from openai import AsyncOpenAI

from alojan_agent.backend import Backend
from alojan_agent.models import Call, Note


@pytest.mark.parametrize("repeat_requested", [False, True])
def test_repeated_opening_is_repaired_unless_explicitly_requested(repeat_requested):
    async def run():
        old = "Bu konuda doğrulanmış bilgim yok."
        revised = "Elimde bu soruyu yanıtlayacak bir bilgi bulunmuyor."
        call = Call(last_user="Son cümlenizi tekrar edin." if repeat_requested else "Neden?")
        call.add_message("assistant", old)
        call.add_message("assistant", "Başka yardımcı olabileceğim bir konu var mı?")
        call.add_message("user", call.last_user)
        arguments = {"text": old + " Sorunuzu biraz açar mısınız?"}
        if repeat_requested:
            arguments["repeat_requested"] = True
        steps = [ModelStep(output=[function_call("respond", arguments, call_id="first")])]
        if not repeat_requested:
            steps.append(
                ModelStep(output=[function_call("respond", {"text": revised}, call_id="repair")])
            )
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-test-key"), model=ScriptedModel(steps)
        )

        async def save(*args):
            raise AssertionError("No storage or external action is needed")

        try:
            speech = [text async for text in backend.stream(call, save)]
            assert speech == [arguments["text"] if repeat_requested else revised]
            assert not call.finish
        finally:
            await backend.close()

    asyncio.run(run())


def test_another_calls_history_does_not_block_a_response():
    async def run():
        text = "Bu konuda doğrulanmış bilgim yok."
        other = Call()
        other.add_message("assistant", text)
        call = Call(last_user="Bu bilgi sizde var mı?")
        call.add_message("user", call.last_user)
        model = ScriptedModel(
            [ModelStep(output=[function_call("respond", {"text": text}, call_id="isolated")])]
        )
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-test-key"), model=model)
        try:
            output = [part async for part in backend.stream(call, None)]
            assert output == [text]
            assert other.messages == [{"role": "assistant", "content": text}]
        finally:
            await backend.close()

    asyncio.run(run())


def test_rephrase_budget_exhaustion_keeps_call_open():
    async def run():
        from alojan_agent.backend import CLARIFICATION

        text = "Bu konuda doğrulanmış bilgim yok."
        call = Call(last_user="Neden?")
        call.add_message("assistant", text)
        call.add_message("user", call.last_user)
        steps = [
            ModelStep(output=[function_call("respond", {"text": text}, call_id=f"repeat-{i}")])
            for i in range(5)
        ]
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-test-key"), model=ScriptedModel(steps)
        )
        try:
            output = [part async for part in backend.stream(call, None)]
            assert output == [CLARIFICATION]
            assert not call.finish and call.note is None
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "acknowledged,repeat_requested", [(True, False), (True, True), (False, False)]
)
@pytest.mark.parametrize("semantic_intent", [False, True])
def test_note_acknowledgement_is_not_repeated_with_different_words(
    acknowledged, repeat_requested, semantic_intent
):
    async def run():
        call = Call(
            last_user="Not aldınız mı?" if repeat_requested else "Bir şey daha ekleyebilir miyim?"
        )
        call.take_note(Note(subject="Rapor", message="Raporu göndereceğim."))
        call.note_id = "synthetic-durable"
        call.further_help_offered = True
        if acknowledged:
            call.acknowledged_note_version = call.version
        call.add_message("assistant", "Mesajınızı not aldım.")
        call.add_message("user", call.last_user)
        speech = "Değişikliği de ekledim." if semantic_intent else "Talebinizi kaydettim."
        repair = "Tabii, sizi dinliyorum."
        args = {
            "text": speech,
            "repeat_requested": repeat_requested,
            "acknowledges_saved_note": semantic_intent,
        }
        steps = [ModelStep(output=[function_call("respond", args, call_id="first")])]
        rejected = acknowledged and not repeat_requested
        if rejected:
            steps.append(
                ModelStep(output=[function_call("respond", {"text": repair}, call_id="repair")])
            )
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-test-key"), model=ScriptedModel(steps)
        )

        async def save(*args):
            raise AssertionError("No note change is needed")

        try:
            assert [part async for part in backend.stream(call, save)] == [
                repair if rejected else speech
            ]
            assert call.version == 1 and not call.finish
            assert call.response_ack_version == (0 if rejected else call.version)
        finally:
            await backend.close()

    asyncio.run(run())
