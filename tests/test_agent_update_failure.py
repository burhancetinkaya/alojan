"""A failed replacement must preserve the durable note and never announce success."""

import asyncio

import pytest
from agents.exceptions import UserError
from agents.testing import ModelStep, ScriptedModel, function_call
from openai import AsyncOpenAI

from alojan_agent.backend import Backend
from alojan_agent.models import Call, Note
from test_agent import speech_tool


@pytest.mark.parametrize("failure", [OSError, asyncio.CancelledError])
def test_failed_update_preserves_version_and_cannot_reach_success_speech(failure):
    async def run():
        original = Note(subject="Teslim", message="Salı rapor, cuma sözleşme gelecek.")
        replacement = original.model_copy(
            update={"message": "Çarşamba rapor, cuma sözleşme gelecek."}
        )
        call = Call(last_user="Rapor çarşamba olacak.")
        call.take_note(original)
        call.note_id = "durable-original"
        call.acknowledged_note_version = call.version
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[
                            function_call("take_note", replacement.model_dump(), call_id="update")
                        ]
                    ),
                    ModelStep(output=[speech_tool("Notunuzu güncelledim.")]),
                ]
            ),
        )

        async def save(note, version):
            assert note == replacement and version == 2
            raise failure()

        spoken = []
        try:
            with pytest.raises(UserError if failure is OSError else failure) as caught:
                async for phrase in backend.stream(call, save):
                    spoken.append(phrase)
            if failure is OSError:
                assert isinstance(caught.value.__cause__, OSError)
            assert not spoken and not call.finish
            assert call.note == original and call.note_id == "durable-original"
            assert call.version == call.acknowledged_note_version == 1
        finally:
            await backend.close()

    asyncio.run(run())
