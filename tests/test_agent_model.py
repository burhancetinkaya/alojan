"""GPT-OSS wire settings and reasoning isolation; no real model inference."""

import asyncio
import json

import httpx2 as httpx
import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from openai import AsyncOpenAI, AuthenticationError
from openai.types.responses import ResponseReasoningTextDeltaEvent

from test_agent import speech_tool

from alojan_agent.backend import Backend, CLARIFICATION, FURTHER_HELP
from alojan_agent.models import Call, Note
from alojan_agent.timing import TurnTiming


@pytest.mark.parametrize("updated", [False, True])
@pytest.mark.parametrize(
    "closing",
    ["Mesajınızı kaydettim, iyi günler.", "Burhan Bey sizi arayacak, iyi günler."],
)
def test_closing_repair_does_not_reannounce_an_acknowledged_unchanged_note(updated, closing):
    async def run():
        call = Call(last_user="Başka bir şey yok, iyi günler.")
        call.take_note(Note(subject="Ziyaret", message="Pazartesi geleceğim."))
        call.note_id = "durable-1"
        call.acknowledged_note_version = 1
        if updated:
            call.take_note(Note(subject="Ziyaret", message="Salı geleceğim."))
            call.note_id = "durable-2"
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[
                            function_call(
                                "finish_call",
                                {
                                    "reason": "caller_finished",
                                    "confirmed_message": None,
                                    "closing_text": closing,
                                },
                                call_id="close",
                            )
                        ]
                    )
                ]
            ),
        )

        async def save(*args):
            raise AssertionError("unchanged note must not be rewritten")

        try:
            reply = "".join([part async for part in backend.stream(call, save)])
            assert call.finish
            if updated:
                assert "not aldım" in reply or "kaydettim" in reply
            else:
                assert "not aldım" not in reply and "kaydettim" not in reply
            assert "arayacak" not in reply
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "essential_question,stored_note", [(True, False), (False, True), (False, False)]
)
def test_thanks_does_not_repeat_optional_questions(essential_question, stored_note):
    async def run():
        question = (
            "Hangi konuda görüşmek istemiştiniz?"
            if essential_question
            else "Eklemek istediğiniz başka bir şey var mı?"
        )
        reply = CLARIFICATION if essential_question else "İyi günler dilerim."
        action = (
            speech_tool(reply)
            if essential_question
            else function_call(
                "finish_call",
                {"reason": "caller_finished", "confirmed_message": None, "closing_text": reply},
                call_id="close",
            )
        )
        model = ScriptedModel([ModelStep(output=[action])])
        captured = []
        original = model.stream_response

        async def stream(*args, **kwargs):
            captured.append(args[1])
            async for event in original(*args, **kwargs):
                yield event

        model.stream_response = stream
        call = Call(last_user="Teşekkür ederim.")
        if stored_note:
            call.take_note(Note(subject="Arama", message="Yarın beni arasın."))
            call.note_id = "durable-synthetic-note"
            call.add_message("user", call.note.message)
            call.add_message("assistant", "Talebinizi not aldım.")
        call.add_message("assistant", question)
        call.further_help_offered = not essential_question
        call.add_message("user", call.last_user)
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)

        async def save(*args):
            raise AssertionError("thanks is not a new message")

        try:
            assert [part async for part in backend.stream(call, save)] == [reply]
            assert call.finish is not essential_question
            if essential_question:
                assert not captured
            else:
                assert len(captured) == 1
                assert captured[0][-2:] == call.messages[-2:]
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "unsafe,expected",
    [
        ("Mesajınızı not aldım. Başka bir şey var mı?", FURTHER_HELP),
        ("Burhan Bey sizi arayacak.", "Burhan Bey'in dönüş zamanı hakkında kesin bir bilgim yok."),
    ],
)
def test_speech_repair_does_not_repeat_an_already_delivered_note_acknowledgement(unsafe, expected):
    async def run():
        call = Call(last_user="Bir de başka bir sorum var.")
        call.take_note(Note(subject="Arama", message="Yarın arayın."))
        call.note_id = "durable"
        call.acknowledged_note_version = call.version
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel([ModelStep(output=[speech_tool(unsafe)])]),
        )

        async def save(*args):
            raise AssertionError("no new message")

        try:
            assert [part async for part in backend.stream(call, save)] == [expected]
            assert not call.finish
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["stream", "summary"])
def test_openrouter_wire_pins_cerebras_and_supported_reasoning(operation):
    async def run():
        requests = []

        def respond(request):
            assert str(request.url) == "https://openrouter.ai/api/v1/responses"
            requests.append(json.loads(request.content))
            return httpx.Response(401, json={"error": {"message": "synthetic rejection"}})

        client = AsyncOpenAI(
            api_key="synthetic-not-a-secret",
            base_url="https://openrouter.ai/api/v1",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
        backend = Backend(client=client, routing="default")
        call = Call(last_user="Bir sorum var.")
        call.add_message("user", call.last_user)

        async def save(*args):
            raise AssertionError("unexpected write")

        try:
            with pytest.raises(AuthenticationError):
                if operation == "stream":
                    async for _ in backend.stream(call, save):
                        pass
                else:
                    await backend.summarize({"utterances": []})
            assert len(requests) == 1
            body = requests[0]
            assert body["model"] == "openai/gpt-oss-120b"
            assert body["reasoning"]["effort"] == "medium"
            assert body["provider"] == {"only": ["cerebras"], "allow_fallbacks": False}
            assert body["store"] is False
            assert "verbosity" not in body.get("text", {})
            assert body["max_output_tokens"] == 4096
            assert body["temperature"] == 0.2
            if operation == "stream":
                assert body["stream"] is True and body["parallel_tool_calls"] is False
                assert body["tool_choice"] == "required"
                assert {tool["name"] for tool in body["tools"]} == {
                    "take_note",
                    "finish_call",
                    "respond",
                }
                assert all(tool["strict"] for tool in body["tools"])
            else:
                assert body["text"]["format"]["type"] == "json_schema"
                assert body.get("tool_choice") is None
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("persisted", [True, False])
def test_repeated_note_skips_io_only_with_durable_identical_state(persisted):
    async def run():
        note = Note(subject="Arama", message="Yarın beni arasın.")
        call = Call(last_user="Başka bir şey yok, iyi günler.")
        call.take_note(note)
        call.note_id = "existing-note" if persisted else None
        call.add_message("user", call.last_user)
        version = call.version
        model = ScriptedModel(
            [
                ModelStep(output=[function_call("take_note", note.model_dump(), call_id="save")]),
                ModelStep(
                    output=[
                        function_call(
                            "finish_call",
                            {
                                "reason": "caller_finished",
                                "confirmed_message": None,
                                "closing_text": "İyi günler.",
                            },
                            call_id="close",
                        )
                    ]
                ),
            ]
        )
        writes = []

        async def save(value, current):
            writes.append((value, current))
            return "new-note"

        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)
        try:
            assert [part async for part in backend.stream(call, save)] == ["İyi günler."]
            assert writes == ([] if persisted else [(note, version)])
            assert call.finish and call.version == version
            assert call.note_id == ("existing-note" if persisted else "new-note")
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("phase", [None, "commentary", "final_answer"])
def test_mislabeled_reasoning_and_tool_text_cannot_be_spoken(phase):
    async def run():
        leaked = assistant_message(
            'Internal reasoning. {"name":"finish_call","reason":"caller_finished"}'
        ).model_copy(update={"phase": phase})
        model = ScriptedModel([ModelStep(output=[leaked, speech_tool("Sorunuzu alabilir miyim?")])])
        timing = TurnTiming()
        call = Call(last_user="Bir sorum var.", timing=timing)
        call.add_message("user", call.last_user)
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)

        async def save(*args):
            raise AssertionError("unexpected write")

        try:
            assert [part async for part in backend.stream(call, save)] == [
                "Sorunuzu alabilir miyim?"
            ]
            assert not call.finish and call.note is None
            assert timing.first_spoken_delta_ms >= timing.tools[-1]["end_ms"]
            assert [item["name"] for item in timing.tools] == ["respond"]
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "invalid",
    [
        " ",
        "x" * 401,
        "Adınız? Konu?",
        "Talebinizi not aldım. Başka bir şey var mı?",
    ],
)
def test_invalid_speech_tool_recovers_without_unvalidated_audio(invalid):
    async def run():
        model = ScriptedModel(
            [
                ModelStep(output=[function_call("respond", {"text": invalid}, call_id="invalid")]),
                ModelStep(output=[speech_tool("Sizi dinliyorum.")]),
            ]
        )
        captured = []
        original = model.stream_response

        async def inspect(*args, **kwargs):
            captured.append(args[2].tool_choice)
            async for event in original(*args, **kwargs):
                yield event

        model.stream_response = inspect
        call = Call(last_user="Bir sorum var.")
        call.add_message("user", call.last_user)
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)

        async def save(*args):
            raise AssertionError("unexpected write")

        try:
            assert [part async for part in backend.stream(call, save)] == ["Sizi dinliyorum."]
            assert captured == ["required", "required"]
            assert not call.finish and call.note is None
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("durable", [True, False])
@pytest.mark.parametrize(
    "unsafe",
    [
        "Burhan Bey sizi arayacak.",
        "Burhan Bey uygun olduğunda sizi arar.",
        "Burhan Bey size döner.",
        "En kısa sürede size ulaşacağız.",
        "En kısa sürede dönüş yapılmasını sağlayacağım.",
        "Geri dönüş yapamayacağımızı belirtmek isterim.",
        "En kısa sürede kendisi sizinle iletişime geçecek.",
    ],
)
def test_callback_claim_repair_requires_durable_note_for_acknowledgement(unsafe, durable):
    async def run():
        call = Call(last_user="Bana dönüş yapabilir mi?")
        call.take_note(Note(subject="Arama", message=call.last_user))
        call.note_id = "durable-note" if durable else None
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel([ModelStep(output=[speech_tool(unsafe)])]),
        )

        async def save(*args):
            raise AssertionError("repair must not write a note")

        try:
            output = [part async for part in backend.stream(call, save)]
            assert output == [
                "Talebinizi Burhan Bey'e iletmek üzere not aldım. " + FURTHER_HELP
                if durable
                else "Burhan Bey'in dönüş zamanı hakkında kesin bir bilgim yok."
            ]
            assert not call.finish
        finally:
            await backend.close()

    asyncio.run(run())


def test_closing_repairs_callback_promise_without_another_model_request():
    async def run():
        def closing(text, cid):
            return function_call(
                "finish_call",
                {"reason": "caller_finished", "confirmed_message": None, "closing_text": text},
                call_id=cid,
            )

        call = Call(last_user="Başka bir şey yok, teşekkür ederim.")
        call.add_message("user", call.last_user)
        model = ScriptedModel(
            [
                ModelStep(output=[closing("Burhan Bey sizi arayacak, iyi günler.", "bad")]),
            ]
        )
        original = model.stream_response
        finish_before_step = []

        async def stream(*args, **kwargs):
            finish_before_step.append(call.finish)
            async for event in original(*args, **kwargs):
                yield event

        model.stream_response = stream
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)

        async def save(*args):
            raise AssertionError("no message to store")

        try:
            assert [part async for part in backend.stream(call, save)] == ["İyi günler dilerim."]
            assert finish_before_step == [False]
            assert call.finish
        finally:
            await backend.close()

    asyncio.run(run())


def test_raw_reasoning_never_becomes_speech_or_first_spoken_delta():
    async def run():
        note = Note(subject="Synthetic", message="Cuma arasın.")
        model = ScriptedModel(
            [
                ModelStep(output=[function_call("take_note", note.model_dump(), call_id="save")]),
                ModelStep(output=[speech_tool("Talebinizi Burhan Bey’e iletmek üzere not aldım.")]),
            ]
        )
        original = model.stream_response
        timing = TurnTiming()
        checks = []

        async def with_reasoning(*args, **kwargs):
            yield ResponseReasoningTextDeltaEvent(
                content_index=0,
                delta="Synthetic private reasoning.",
                item_id="reasoning",
                output_index=0,
                sequence_number=0,
                type="response.reasoning_text.delta",
            )
            checks.append((timing.first_delta_ms, timing.first_spoken_delta_ms))
            async for event in original(*args, **kwargs):
                yield event

        model.stream_response = with_reasoning
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)
        call = Call(last_user="Cuma arasın.", timing=timing)
        call.add_message("user", call.last_user)
        saves = []

        async def save(value, version):
            saves.append(value)
            return "synthetic-note"

        try:
            speech = "".join([part async for part in backend.stream(call, save)])
            assert speech == "Talebinizi Burhan Bey’e iletmek üzere not aldım. " + FURTHER_HELP
            assert checks == [(-1, -1), (-1, -1)]
            assert saves == [note] and not call.finish
            assert timing.first_spoken_delta_ms >= 0
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("offered", [False, True])
def test_bare_thanks_cannot_skip_the_once_per_call_invitation(offered):
    async def run():
        call = Call(last_user="Tamam, teşekkür ederim.", further_help_offered=offered)
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[
                            function_call(
                                "finish_call",
                                {
                                    "reason": "caller_finished",
                                    "confirmed_message": None,
                                    "closing_text": "İyi günler.",
                                },
                                call_id="close",
                            )
                        ]
                    )
                ]
            ),
        )

        async def save(*args):
            raise AssertionError("thanks cannot save a note")

        try:
            assert [part async for part in backend.stream(call, save)] == [
                "İyi günler." if offered else FURTHER_HELP
            ]
            assert call.finish == offered
        finally:
            await backend.close()

    asyncio.run(run())


def test_new_note_version_does_not_allow_a_second_invitation():
    async def run():
        call = Call(last_user="Salı geleceğim.", further_help_offered=True)
        call.take_note(Note(subject="Ziyaret", message="Pazartesi geleceğim."))
        call.take_note(Note(subject="Ziyaret", message="Salı geleceğim."))
        call.note_id = "durable-2"
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(output=[speech_tool("Güncelledim. " + FURTHER_HELP)]),
                    ModelStep(
                        output=[
                            function_call(
                                "respond", {"text": "Notunuzu güncelledim."}, call_id="corrected"
                            )
                        ]
                    ),
                ]
            ),
        )

        async def save(*args):
            raise AssertionError("already saved")

        try:
            assert [part async for part in backend.stream(call, save)] == ["Notunuzu güncelledim."]
            assert not call.finish and call.version == 2
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "text,new_detail",
    [
        ("Hepsi bu, iyi günler.", False),
        ("Duymadım, not aldınız mı?", False),
        ("Bir de faturamı istiyorum.", True),
    ],
)
def test_note_rewrite_requires_more_than_a_content_free_closing(text, new_detail):
    async def run():
        original = Note(subject="Hesap", message="Orion Ledger hesabı açılmıyor.")
        changed = Note(
            subject="Hesap ve fatura", message="Orion Ledger hesabı açılmıyor. Faturamı istiyorum."
        )
        call = Call(last_user=text, further_help_offered=True)
        call.take_note(original)
        call.note_id = "durable-1"
        call.add_message("user", text)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[function_call("take_note", changed.model_dump(), call_id="rewrite")]
                    ),
                    ModelStep(output=[speech_tool("Sizi dinliyorum.")]),
                ]
            ),
        )
        writes = []

        async def save(note, version):
            writes.append((note, version))
            return "durable-2"

        try:
            assert [x async for x in backend.stream(call, save)] == ["Sizi dinliyorum."]
            assert call.note == (changed if new_detail else original)
            assert call.version == (2 if new_detail else 1)
            assert len(writes) == int(new_detail)
        finally:
            await backend.close()

    asyncio.run(run())


def test_malformed_provider_output_recovers_without_leaking_or_finishing():
    from agents.exceptions import ModelBehaviorError

    async def run():
        async def malformed(_call):
            raise ModelBehaviorError("synthetic private malformed provider payload")
            yield

        call = Call(last_user="Bir sorum var.", finish=True)
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel([ModelStep(stream_events=malformed)]),
        )

        async def save(*args):
            raise AssertionError("invalid output cannot write")

        try:
            assert [x async for x in backend.stream(call, save)] == [CLARIFICATION]
            assert not call.finish and call.note is None
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "text,expected",
    [
        ("İyi günler, bir dakika bir de faturamı istiyorum.", True),
        ("Hoşça kalın, ayrıca hesabım da kilitli.", True),
        ("Bir de faturamı istiyorum, iyi günler.", False),
        ("İyi günler, bir de faturamı istiyorum, hepsi bu.", False),
        ("Bir dakika, kapatma, daha konuşacağım.", False),
    ],
)
def test_continuation_marker_order_respects_a_later_final_exit(text, expected):
    from alojan_agent.models import continues_after_goodbye

    assert continues_after_goodbye(text) == expected


def test_premature_finish_rejected_before_saving_a_reopened_request():
    async def run():
        call = Call(
            last_user="İyi günler, bir dakika bir de faturamı istiyorum.", further_help_offered=True
        )
        call.take_note(Note(subject="Hesap", message="Orion Ledger hesabı açılmıyor."))
        call.note_id = "durable-1"
        call.add_message("user", call.last_user)
        updated = Note(
            subject="Hesap ve fatura", message="Orion Ledger hesabı açılmıyor. Faturamı istiyorum."
        )
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(
                        output=[
                            function_call(
                                "finish_call",
                                {
                                    "reason": "caller_finished",
                                    "confirmed_message": None,
                                    "closing_text": "İyi günler.",
                                },
                                call_id="premature",
                            )
                        ]
                    ),
                    ModelStep(
                        output=[function_call("take_note", updated.model_dump(), call_id="update")]
                    ),
                    ModelStep(output=[speech_tool("Fatura talebinizi de ekledim.")]),
                ]
            ),
        )
        writes = []

        async def save(note, version):
            writes.append((note, version))
            return "durable-2"

        try:
            assert [x async for x in backend.stream(call, save)] == [
                "Fatura talebinizi de ekledim."
            ]
            assert not call.finish and writes == [(updated, 2)] and call.note == updated
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "unbacked",
    [
        "Talebinizi kaydettim. Telefon numaranızı paylaşabilir misiniz?",
        "Mesajınızı not aldım.",
    ],
)
def test_storage_acknowledgement_requires_a_durable_note_even_with_essential_question(unbacked):
    async def run():
        call = Call(last_user="Burhan Bey cuma beni arasın.")
        call.add_message("user", call.last_user)
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"),
            model=ScriptedModel(
                [
                    ModelStep(output=[speech_tool(unbacked)]),
                    ModelStep(
                        output=[
                            function_call(
                                "respond",
                                {"text": "Telefon numaranızı paylaşabilir misiniz?"},
                                call_id="corrected",
                            )
                        ]
                    ),
                ]
            ),
        )

        async def save(*args):
            raise AssertionError("no write was requested")

        try:
            assert [x async for x in backend.stream(call, save)] == [
                "Telefon numaranızı paylaşabilir misiniz?"
            ]
            assert call.note is None and not call.finish
        finally:
            await backend.close()

    asyncio.run(run())
