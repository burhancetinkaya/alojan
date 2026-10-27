"""Latency instrumentation must not change dialogue or leak content."""

import asyncio
import json

import grpc
import pytest
from agents.testing import ScriptedModel, ModelStep, function_call
from agents.usage import Usage
from openai import AsyncOpenAI
from openai.types.responses.response_usage import InputTokensDetails

from test_agent import speech_tool

from alojan_agent.backend import Backend
from alojan_agent.models import Call
from alojan_agent.service import AgentService, create_server
from alojan_agent.timing import TurnTiming
from test_agent import MemoryStore, collect, request, scenario
from voice.v1 import voice_pb2_grpc as rpc
from voice.v1 import voice_pb2 as pb


def test_model_tool_cache_and_phrase_timings_are_isolated_and_content_free(capsys):
    async def run():
        model = ScriptedModel(
            [
                ModelStep(
                    output=[
                        function_call(
                            "take_note",
                            {
                                "caller_name": None,
                                "caller_number": None,
                                "subject": "Synthetic",
                                "message": "Yarın arasın.",
                                "confirmed": False,
                            },
                            call_id="save",
                        )
                    ],
                    usage=Usage(
                        requests=1,
                        input_tokens=512,
                        output_tokens=30,
                        input_tokens_details=InputTokensDetails(
                            cached_tokens=256, cache_write_tokens=0
                        ),
                    ),
                ),
                ModelStep(output=[speech_tool("Mesajınızı not aldım.")]),
            ]
        )
        backend = Backend(client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model)
        service = AgentService(backend, MemoryStore())
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                events = await collect(rpc.AgentStub(channel), request(text="Yarın arasın."))
                assert "not aldım" in "".join(e.text for e in events)
                timing = service.calls["one"].timing.snapshot()
                assert len(timing["model_steps"]) == 2
                first, second = timing["model_steps"]
                assert first["input_tokens"] == 512 and first["cached_tokens"] == 256
                assert first["start_ms"] <= first["end_ms"] <= second["start_ms"]
                assert second["first_text_ms"] == -1
                assert timing["tools"][1]["name"] == "respond"
                assert timing["first_spoken_delta_ms"] >= second["end_ms"]
                assert timing["tools"][0]["name"] == "take_note"
                assert timing["tools"][0]["end_ms"] >= timing["tools"][0]["start_ms"]
                await collect(rpc.AgentStub(channel), request(gen="turn-2", text="Kapat."))
                assert service.calls["one"].timing.models == []
        finally:
            await server.stop(0)
            await backend.close()

    asyncio.run(run())
    lines = [x for x in capsys.readouterr().out.splitlines() if x.startswith("event=agent_latency")]
    assert len(lines) == 2
    assert "Yarın" not in str(lines) and "not aldım" not in str(lines)
    records = [json.loads(x.split("data=", 1)[1]) for x in lines]
    assert all(x["status"] == "completed" for x in records)
    assert records[0]["call_key"] == records[1]["call_key"]


def test_cancelled_turn_reports_missing_response_instead_of_zero_latency(capsys):
    async def check(stub, control, service):
        pending = asyncio.create_task(collect(stub, request(), timeout=2))
        await asyncio.sleep(0.05)
        await control.CancelGeneration(
            pb.CancelRequest(call_id="one", generation_id="turn-1"), timeout=1
        )
        with pytest.raises(grpc.aio.AioRpcError):
            await pending
        for _ in range(100):
            if not service.active:
                break
            await asyncio.sleep(0.01)
        assert not service.active

    asyncio.run(scenario(check, "wait"))
    line = next(
        x for x in capsys.readouterr().out.splitlines() if x.startswith("event=agent_latency")
    )
    record = json.loads(line.split("data=", 1)[1])
    assert record["status"] == "cancelled"
    assert record["first_phrase_ms"] == record["first_delta_ms"] == -1


@pytest.mark.parametrize("routing", ["default", "latency", "sticky", "latency-sticky"])
def test_routing_preserves_model_settings_and_isolates_sessions(routing):
    async def run():
        model = ScriptedModel(
            [ModelStep(output=[speech_tool("Sizi dinliyorum.")]) for _ in range(3)]
        )
        original = model.stream_response
        settings = []

        async def capture(*args, **kwargs):
            settings.append(args[2])
            async for item in original(*args, **kwargs):
                yield item

        model.stream_response = capture
        backend = Backend(
            client=AsyncOpenAI(api_key="synthetic-not-a-secret"), model=model, routing=routing
        )
        call = Call(last_user="Bir soru soracağım.")
        call.add_message("user", call.last_user)

        async def save(*args):
            raise AssertionError("unexpected write")

        try:
            for current in [call, call, Call(last_user="Başka soru.")]:
                current.timing = TurnTiming()
                assert "Sizi" in "".join([text async for text in backend.stream(current, save)])
            for item in settings:
                assert item.reasoning.effort == "medium" and item.verbosity is None
                assert item.store is False and item.parallel_tool_calls is False
                body = item.extra_body or {}
                assert body["provider"]["only"] == ["cerebras"]
                assert body["provider"]["allow_fallbacks"] is False
                assert body["provider"].get("sort") == ("latency" if "latency" in routing else None)
            if "sticky" in routing:
                assert settings[0].extra_body["session_id"] == settings[1].extra_body["session_id"]
                assert settings[0].extra_body["session_id"] != settings[2].extra_body["session_id"]
            else:
                assert all("session_id" not in (s.extra_body or {}) for s in settings)
        finally:
            await backend.close()

    asyncio.run(run())


def test_invalid_routing_fails_before_creating_api_client():
    with pytest.raises(ValueError, match="routing"):
        Backend(routing="unapproved-model")
