"""Optional observations have no authority over a call or another workspace."""

import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace
import uuid

import httpx2
import pytest

from alojan_agent.backend import Backend
from alojan_agent.credentials import ProviderClients
from alojan_agent.decisions import Decisions
from alojan_agent.legacy import LEGACY_RUNTIME
from alojan_agent.models import Call
from alojan_agent.timing import TurnTiming
from test_decisions import payload


@pytest.mark.parametrize(
    "finish", ["observe", "new_turn", "runtime_changed", "cancel", "provider_error"]
)
def test_shadow_is_parallel_scoped_bounded_and_stale_safe(finish):
    async def run():
        gate = asyncio.Event()
        sent = []

        async def respond(request):
            sent.append((request.headers["authorization"], json.loads(request.content)["state"]))
            await gate.wait()
            return httpx2.Response(503 if finish == "provider_error" else 200, json=payload())

        class Credentials:
            key = staticmethod(ProviderClients.key)

            def get(self, runtime):
                return SimpleNamespace(api_key=runtime.scope_id)

            async def close(self):
                pass

        decisions = Decisions(transport=httpx2.MockTransport(respond))
        backend = Backend(credentials=Credentials(), decisions=decisions)
        calls = [
            Call(
                runtime=replace(
                    LEGACY_RUNTIME,
                    scope_id=str(uuid.uuid4()),
                    model_connection=str(uuid.uuid4()),
                    mcp_grant_json="synthetic-prevalidated-grant",
                ),
                active=True,
                turns=1,
                last_user="Bugün kaç kayıt var?",
            )
            for _ in range(2)
        ]
        timings = [TurnTiming(), TurnTiming()]
        for index, call in enumerate(calls):
            call.add_message("user", f"Synthetic question for workspace {index}")
            call.add_message("assistant", f"Synthetic answer for workspace {index}")
            call.add_message("user", call.last_user)
        try:
            tasks = [backend.start_shadow(c, t) for c, t in zip(calls, timings)]
            assert not sent  # Scheduling cannot await HTTP on the model dispatch path.
            assert backend.start_shadow(calls[0], timings[0]) is None
            await asyncio.sleep(0)
            for index, (authorization, state) in enumerate(sent):
                assert authorization == "Bearer " + calls[index].runtime.scope_id
                assert state["recent_dialogue"] == calls[index].messages[:-1]
                assert f"workspace {1 - index}" not in str(state)
            assert len(sent) == 2
            if finish == "new_turn":
                calls[0].turns += 1
            elif finish == "runtime_changed":
                calls[0].runtime = replace(calls[0].runtime)
            elif finish == "cancel":
                tasks[0].cancel()
            gate.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0)
            assert not backend.decision_tasks
            if finish in {"new_turn", "runtime_changed", "cancel"}:
                assert timings[0].decision is None
            else:
                assert timings[0].decision["status"] == (
                    "unavailable" if finish == "provider_error" else "observed"
                )
            assert timings[1].decision is not None
            for call in calls:
                assert len(call.messages) == 3 and not call.ended and call.note is None
            assert "Bugün" not in str([t.snapshot() for t in timings])
        finally:
            await backend.close()

    asyncio.run(run())


def test_shadow_snapshots_call_local_history_before_scheduling_and_sanitizes_suspect_asr():
    async def run():
        sent = []

        async def respond(request):
            sent.append(json.loads(request.content)["state"])
            return httpx2.Response(200, json=payload())

        class Credentials:
            key = staticmethod(ProviderClients.key)

            def get(self, runtime):
                return SimpleNamespace(api_key="synthetic-secret")

            async def close(self):
                pass

        backend = Backend(
            credentials=Credentials(), decisions=Decisions(transport=httpx2.MockTransport(respond))
        )
        call = Call(
            runtime=replace(
                LEGACY_RUNTIME,
                scope_id=str(uuid.uuid4()),
                model_connection=str(uuid.uuid4()),
                mcp_grant_json="synthetic-prevalidated-grant",
            ),
            active=True,
            turns=2,
            last_user="Hayır, dün.",
        )
        call.add_message("user", "İzlediğiniz için teşekkür ederim.")
        call.add_message("assistant", "Tekrar eder misiniz?")
        call.add_message("user", "Bugünkü kayıtları getir.")
        call.add_message("assistant", "Bugün iki kayıt var.")
        call.add_message("user", call.last_user)
        original = [dict(m) for m in call.messages]
        timing = TurnTiming()
        try:
            task = backend.start_shadow(call, timing)
            call.last_user = "Mutated after scheduling"
            call.messages[-2]["content"] = "Unrelated later content"
            await task
            assert len(sent) == 1
            assert sent[0]["utterance"] == "Hayır, dün."
            history = sent[0]["recent_dialogue"]
            assert history[0]["content"] == "[Unreliable speech recognition; caller words unknown.]"
            assert history[1:] == original[1:-1]
            assert call.messages[0] == original[0]
            assert timing.decision["status"] == "observed"
            assert "kayıt" not in str(timing.snapshot())
        finally:
            await backend.close()

    asyncio.run(run())


@pytest.mark.parametrize("runtime", [None, LEGACY_RUNTIME])
def test_without_published_mcp_tools_never_accesses_credentials_or_dispatches(runtime):
    class Credentials:
        def get(self, runtime):
            pytest.fail("Non-MCP agent accessed Jev credentials")

    backend = Backend(credentials=Credentials(), decisions=object())
    call = Call(runtime=runtime, active=True, last_user="Bugünkü kayıtlar?")
    assert backend.start_shadow(call, TurnTiming()) is None
    assert not backend.decision_tasks


@pytest.mark.parametrize("flag,enabled", [(None, True), ("1", True), ("0", False)])
def test_managed_jev_defaults_on_and_operator_can_disable(monkeypatch, flag, enabled):
    from alojan_agent import decisions, managed

    events = []

    class StopStartup(Exception):
        pass

    class Probe:
        def __init__(self):
            events.append("created")

        async def close(self):
            events.append("closed")

    def stop_credentials(*args):
        raise StopStartup

    if flag is None:
        monkeypatch.delenv("ALOJAN_JEV_SHADOW", raising=False)
    else:
        monkeypatch.setenv("ALOJAN_JEV_SHADOW", flag)
    monkeypatch.delenv("ALOJAN_MCP_DATABASE_URL", raising=False)
    for name in ("RECORDS", "ROUTING", "READINESS", "CREDENTIALS"):
        monkeypatch.setenv(f"ALOJAN_{name}_DATABASE_URL", "synthetic-unused")
    monkeypatch.setenv("ALOJAN_CREDENTIAL_KEY_FILE", "synthetic-unused")
    monkeypatch.setattr(decisions, "Decisions", Probe)
    monkeypatch.setattr(managed.SecretBox, "from_file", lambda path: None)
    monkeypatch.setattr(managed, "ProviderClients", stop_credentials)
    with pytest.raises(StopStartup):
        asyncio.run(managed.serve(None, None))
    assert events == (["created", "closed"] if enabled else [])


def test_invalid_shadow_flag_fails_before_startup(monkeypatch):
    from alojan_agent.managed import serve

    monkeypatch.setenv("ALOJAN_JEV_SHADOW", "invalid")
    with pytest.raises(ValueError, match="invalid decision shadow mode"):
        asyncio.run(serve(None, None))
