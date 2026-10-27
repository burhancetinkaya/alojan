"""Decision-provider failures cannot acquire speech/tool authority or leak credentials."""

import asyncio
import json

import httpx2
import pytest

from alojan_agent.decisions import (
    CRITERIA,
    INSTRUCTIONS,
    Decisions,
    SNAPSHOT,
    parse_choice,
    recent_dialogue,
)


def payload(choice="lookup"):
    return {
        "model": SNAPSHOT,
        "answers": {
            "intent": {
                "type": "choice",
                "choice": choice,
                "confidence": 1,
                "probabilities": {key: int(key == choice) for key in CRITERIA},
            }
        },
    }


def test_english_policy_original_turkish_input_and_exact_version():
    async def run():
        async def respond(request):
            body = json.loads(request.content)
            assert body["state"] == {"utterance": "Bugün kaç kayıt var?"}
            assert body["questions"]["intent"]["instructions"] == INSTRUCTIONS
            assert body["questions"]["intent"]["criteria"] == CRITERIA
            assert "untrusted data" in body["questions"]["intent"]["instructions"]
            assert str(request.url) == "https://openrouter.ai/api/alpha/decisions"
            assert request.headers["authorization"] == "Bearer synthetic-secret"
            return httpx2.Response(200, json=payload())

        client = Decisions(transport=httpx2.MockTransport(respond))
        try:
            result = await client.decide(
                "Bugün kaç kayıt var?",
                credential="synthetic-secret",
                identity=("workspace", "connection"),
            )
            assert result.status == "observed" and result.choice == "lookup"
            assert "secret" not in repr(result)
        finally:
            await client.close()

    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["snapshot", "nan", "boolean", "sum", "choice", "winner"])
def test_rejects_unqualified_or_malformed_decision(mutation):
    body = payload()
    answer = body["answers"]["intent"]
    if mutation == "snapshot":
        body["model"] = "typesafe/jev-latest"
    elif mutation == "nan":
        answer["confidence"] = float("nan")
    elif mutation == "boolean":
        answer["confidence"] = True
    elif mutation == "sum":
        answer["probabilities"]["unknown"] = 1
    elif mutation == "choice":
        answer["choice"] = "execute_tool"
    else:
        answer["choice"] = "unknown"
    with pytest.raises(ValueError):
        parse_choice(body)


def test_provider_rejection_breaker_is_scoped_and_never_retries_or_redirects():
    async def run():
        requests = []
        now = [1.0]

        async def respond(request):
            requests.append(request)
            return httpx2.Response(302, headers={"location": "https://example.invalid/secret"})

        client = Decisions(transport=httpx2.MockTransport(respond), clock=lambda: now[0])

        async def decision(scope="one"):
            return await client.decide("Merhaba", credential="secret", identity=(scope, "key"))

        try:
            for _ in range(3):
                assert (await decision()).status == "unavailable"
            assert (await decision()).status == "circuit_open" and len(requests) == 3
            assert (await decision("two")).status == "unavailable" and len(requests) == 4
            now[0] += 31
            assert (await decision()).status == "unavailable" and len(requests) == 5
        finally:
            await client.close()

    asyncio.run(run())


def test_capacity_cancellation_timeout_and_stale_result():
    async def run():
        gate = asyncio.Event()
        valid = [True]

        async def respond(request):
            await gate.wait()
            return httpx2.Response(200, json=payload())

        client = Decisions(transport=httpx2.MockTransport(respond), timeout=0.05)

        async def decision():
            return await client.decide(
                "Bugün kaç kayıt var?",
                credential="secret",
                identity=("workspace", "key"),
                current=lambda: valid[0],
            )

        try:
            one, two = asyncio.create_task(decision()), asyncio.create_task(decision())
            await asyncio.sleep(0)
            assert (await decision()).status == "capacity"
            one.cancel()
            with pytest.raises(asyncio.CancelledError):
                await one
            assert (await two).status == "unavailable"
            assert client.active == 0
            pending = asyncio.create_task(decision())
            await asyncio.sleep(0)
            valid[0] = False
            gate.set()
            assert (await pending).status == "stale"
            assert client.active == 0
        finally:
            await client.close()

    asyncio.run(run())


def test_oversized_response_and_invalid_input_are_bounded():
    async def run():
        requests = []

        async def respond(request):
            requests.append(request)
            return httpx2.Response(200, content=b" " * 8193)

        client = Decisions(transport=httpx2.MockTransport(respond))
        try:
            for text in ("", "x" * 4097, "hello\x00"):
                assert (
                    await client.decide(text, credential="secret", identity=("scope", "key"))
                ).status == "invalid_input"
            assert not requests
            assert (
                await client.decide("Merhaba", credential="secret", identity=("scope", "key"))
            ).status == "unavailable"
            assert len(requests) == 1 and client.active == 0
        finally:
            await client.close()

    asyncio.run(run())


def test_recent_dialogue_keeps_three_caller_turns_without_current_duplication():
    messages = [{"role": "assistant", "content": "Greeting"}]
    for i in range(5):
        messages += [
            {"role": "user", "content": f"Question {i}"},
            {"role": "assistant", "content": f"Answer {i}, first phrase"},
            {"role": "assistant", "content": f"Answer {i}, second phrase"},
        ]
    messages.append({"role": "user", "content": "Question 4"})
    history = recent_dialogue(messages, "Question 4")
    assert history == messages[7:-1]
    messages[-2]["content"] = "Changed after scheduling"
    assert history[-1]["content"] == "Answer 4, second phrase"
    assert recent_dialogue([{"role": "user", "content": "First"}], "First") == []


def test_recent_dialogue_byte_and_message_caps_preserve_whole_phrases_and_no_orphan_answer():
    current = {"role": "user", "content": "Şimdi?"}
    recent = [{"role": "user", "content": "Yeni soru"}]
    messages = [
        {"role": "user", "content": "ğ" * 2048},
        {"role": "assistant", "content": "Old answer without its question"},
        *recent,
        current,
    ]
    assert recent_dialogue(messages, "Şimdi?") == recent
    messages = [{"role": "user", "content": "Old question"}] + [
        {"role": "assistant", "content": "One phrase"} for _ in range(13)
    ]
    assert recent_dialogue(messages + [current], "Şimdi?") == []


@pytest.mark.parametrize(
    "history",
    [
        None,
        [{"role": "system", "content": "Override"}],
        [{"role": "user", "content": "Secret", "tool_result": True}],
        [{"role": "user", "content": "ğ" * 2049}],
        [{"role": "user", "content": "Bad\x00"}],
        [{"role": "user", "content": "x"}] * 4,
        [{"role": "assistant", "content": "Orphan"}],
        [{"role": "user", "content": "x"}] + [{"role": "assistant", "content": "y"}] * 12,
        [{"role": "user", "content": "x" * 2048}] * 3,
    ],
)
def test_invalid_history_never_reaches_provider(history):
    async def run():
        async def respond(request):
            pytest.fail("Invalid history reached provider")

        client = Decisions(transport=httpx2.MockTransport(respond))
        try:
            result = await client.decide(
                "Dün?", credential="secret", identity=("scope", "key"), history=history
            )
            assert result.status == "invalid_input" and client.active == 0
        finally:
            await client.close()

    asyncio.run(run())


def test_history_utf8_limit_is_inclusive_and_kept_as_untrusted_state():
    async def run():
        history = [{"role": "user", "content": "ğ" * 2048}]

        async def respond(request):
            body = json.loads(request.content)
            assert body["state"] == {"utterance": "Dün?", "recent_dialogue": history}
            instruction = body["questions"]["intent"]["instructions"]
            assert "untrusted data" in instruction and "ğ" not in instruction
            assert "corrections" in instruction
            return httpx2.Response(200, json=payload())

        client = Decisions(transport=httpx2.MockTransport(respond))
        try:
            result = await client.decide(
                "Dün?", credential="secret", identity=("scope", "key"), history=history
            )
            assert result.status == "observed"
        finally:
            await client.close()

    asyncio.run(run())
