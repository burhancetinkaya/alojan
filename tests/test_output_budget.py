"""Pinned output budgets: historical compatibility, UTF-8 and real agent RPC."""

import asyncio
import json
from pathlib import Path
import re

import grpc
import pytest
from pydantic import ValidationError

from alojan_agent.models import Call
from alojan_contracts.configuration import AgentDraft, EnginePreset, OutputBudget, canonical_digest
from alojan_contracts.phrases import phrase_end
from test_agent import collect, request, scenario
from test_agent_runtime import configured


def test_historical_output_budget_and_catalog_digests_are_unchanged():
    for name in ("agent_catalog.sql", "agent_calibration.sql"):
        source = (Path(__file__).resolve().parents[1] / "infra/examples" / name).read_text()
        raw, digest = re.search(r"'({.*})'::jsonb,'([a-f0-9]{64})'", source).groups()
        engine = EnginePreset.model_validate_json(raw)
        assert engine.output is None and engine.model_dump() == json.loads(raw)
        assert canonical_digest(engine.model_dump()) == digest
        assert engine.output_budget.model_dump() == {
            "schema_version": 1,
            "phrase_max_chars": 240,
            "phrase_max_bytes": 1024,
            "max_phrases": 16,
            "turn_max_bytes": 4096,
        }


def test_explicit_budget_is_frozen_and_native_wire_is_complete():
    values = dict(phrase_max_chars=80, phrase_max_bytes=320, max_phrases=8, turn_max_bytes=2048)
    engine = EnginePreset(output=values)
    values["max_phrases"] = 1
    restored = EnginePreset.model_validate_json(engine.model_dump_json())
    assert restored == engine and restored.output_budget.max_phrases == 8
    native = engine.gateway_configuration()
    assert native.ByteSize() <= 256
    for field, value in engine.output.model_dump().items():
        assert getattr(native.output, field) == value
    native.output.max_phrases = 1
    assert engine.gateway_configuration().output.max_phrases == 8
    with pytest.raises(ValidationError):
        engine.output.max_phrases = 2


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"phrase_max_chars": 39},
        {"phrase_max_chars": 241},
        {"phrase_max_chars": True},
        {"phrase_max_bytes": 159},
        {"phrase_max_bytes": 1025},
        {"phrase_max_bytes": 959},
        {"max_phrases": 0},
        {"max_phrases": 17},
        {"turn_max_bytes": 1023},
        {"turn_max_bytes": 4097},
        {"unknown": 1},
    ],
)
def test_invalid_budgets_cannot_be_published(changes):
    with pytest.raises(ValidationError):
        EnginePreset(output=changes)


def test_user_cannot_override_engine_budget():
    from test_agent_drafts import content

    with pytest.raises(ValidationError):
        AgentDraft(**content(), output=OutputBudget().model_dump())


def test_utf8_chunks_preserve_text_and_obey_smaller_limit():
    text = "𐐀ğİ" * 45
    chunks, remaining = [], text
    while remaining:
        end = phrase_end(remaining, 40) or len(remaining)
        chunks.append(remaining[:end])
        remaining = remaining[end:]
    assert "".join(chunks) == text
    assert [len(part) for part in chunks] == [40, 40, 40, 15]
    assert all(len(part.encode()) <= 160 for part in chunks)
    text = "Dr. Örnek saat 12.50 için geldi."
    assert phrase_end(text, 40) == len(text)


def test_publication_rejects_unplayable_fixed_speech_before_activation():
    with pytest.raises(ValueError, match="engine limits"):
        configured(
            engine={"output": {"max_phrases": 1}},
            tools=[],
            offer_further_help=False,
            clarification_text="Tekrar eder misiniz? Sizi dinliyorum.",
        )


def test_speech_validation_counts_phrases_and_bytes_not_only_characters():
    from alojan_contracts.runtime import valid_speech

    engine = EnginePreset(reply_max_sentences=5, output={"max_phrases": 1, "turn_max_bytes": 1024})
    assert not valid_speech("Bir cümle. İkinci cümle.", engine)
    assert not valid_speech("𐐀" * 300, engine)
    assert valid_speech("ğ" * 200, engine)


def test_two_call_budgets_split_same_text_independently_over_real_rpc():
    async def check(stub, control, service):
        class Script:
            async def stream(self, call, save_note):
                yield "𐐀ğİ" * 45

        service.backend = Script()
        for cid, width in (("one", 40), ("two", 80)):
            service.calls[cid] = Call(
                runtime=configured(
                    engine={
                        "output": {
                            "phrase_max_chars": width,
                            "phrase_max_bytes": 4 * width,
                        }
                    }
                )
            )
        results = await asyncio.gather(collect(stub, request()), collect(stub, request("two")))
        for events, sizes in zip(results, ([40, 40, 40, 15], [80, 55])):
            assert events[-1].type == "end"
            assert [len(e.text) for e in events[:-1]] == sizes
            assert "".join(e.text for e in events[:-1]) == "𐐀ğİ" * 45
        assert not service.active and all(not c.active for c in service.calls.values())

    asyncio.run(scenario(check))


@pytest.mark.parametrize(
    "limit,text,emitted",
    [
        ({"max_phrases": 1}, "Bir cümle. İkinci cümle.", ["Bir cümle."]),
        ({"turn_max_bytes": 1024}, "𐐀" * 257, []),
    ],
)
def test_stream_over_budget_fails_without_end_or_false_playback_receipt(limit, text, emitted):
    async def check(stub, control, service):
        closed = []

        class Script:
            async def stream(self, call, save_note):
                try:
                    yield text
                finally:
                    closed.append(True)

        service.backend = Script()
        call = service.calls["one"] = Call(
            runtime=configured(
                engine={"output": limit},
                tools=[],
                offer_further_help=False,
                silence_timeout_text="Görüşmeyi bitiriyorum.",
            )
        )
        received = []
        with pytest.raises(grpc.aio.AioRpcError) as error:
            async for event in stub.RunTurn(request(), timeout=2):
                received.append(event)
        assert error.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
        assert [e.text for e in received] == emitted
        assert all(e.type == "text_delta" for e in received)
        assert closed == [True] and not call.active and not service.active
        assert not any(m["role"] == "assistant" for m in call.messages)
        assert list(call.phrases.values()) == emitted

    asyncio.run(scenario(check))


def test_sdk_tool_rejects_excess_phrases_before_speech():
    from agents.testing import ScriptedModel
    from openai import AsyncOpenAI
    from alojan_agent.backend import Backend
    from test_agent_runtime import step

    async def run():
        runtime = configured(
            engine={"output": {"max_phrases": 1}},
            tools=[],
            offer_further_help=False,
            silence_timeout_text="Görüşmeyi bitiriyorum.",
        )
        call = Call(runtime=runtime, last_user="Merhaba")
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-test"),
            model=ScriptedModel(
                [
                    step("respond", text="Bir cümle. İkinci cümle."),
                    step("respond", text="Tek cümle."),
                ]
            ),
        )
        try:
            assert [text async for text in backend.stream(call, None)] == ["Tek cümle."]
            assert not call.finish
        finally:
            await backend.close()

    asyncio.run(run())
