"""Real isolated SIP/RTP with prepared tones and scripted inference, not EMA acceptance."""

import asyncio
from contextlib import contextmanager

import pytest

from alojan.auth import connection
from alojan.profiles import Profiles
from alojan.releases import Releases
from test_agent_releases import prepare_assets
from test_answered_lifecycle import running
from test_managed_session import ObservedReady, Script, bind, config
from test_recognition_setup import recognition, synthesis
from test_sip import Peer, connect, run_gateway
from test_speech import drive
from test_prepared_setup import wait_for
import test_number_routing as routing

accounts = routing.accounts
database = routing.database
author = routing.author
dedicated = routing.dedicated


@pytest.mark.parametrize("slow", [False, True])
def test_waiting_is_prepared_preemptible_and_not_final(accounts, author, tmp_path, dedicated, slow):
    token, scope, agent = author
    profiles = Profiles(accounts)
    draft = profiles.get(token, scope, agent)["content"]
    draft["response_experience"] = {"enabled": True}
    profiles.update(token, scope, agent, draft, 1)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    release = Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"]
    published = (*author, release)
    bind(accounts, published, routing.DID)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")

    class WaitingScript(Script):
        async def stream(self, call, save_note):
            if call.turns == 1:
                state = call.response_lifecycle
                state.dispatch("synthetic-read", call.turns)
                if slow:
                    await asyncio.sleep(2.1)
                state.settle("synthetic-read")
            async for text in super().stream(call, save_note):
                yield text

    async def run():
        async with (
            running(accounts, published, tmp_path, record_dsn, router_dsn, ObservedReady) as (
                svc,
                port,
                _,
                __,
            ),
            recognition() as (asr, asr_port),
            synthesis() as (tts, tts_port),
        ):
            svc.backend = WaitingScript()
            svc.playback, svc.ended = [], []

            def scenario():
                with contextmanager(run_gateway)(tmp_path, config(port, asr_port, tts_port)) as (
                    sip,
                    log,
                    _,
                ):
                    peer = Peer(sip)
                    peer.request_user = routing.DID
                    peer.sip.settimeout(5)
                    try:
                        media = connect(peer)
                        _, _, ended = drive(peer, media, log, duration=18)
                        assert ended and "event=speech_fallback" not in log.read_text(), (
                            log.read_text()
                        )
                        wait_for(lambda: not svc.leases and not asr.leases and not tts.leases)
                    finally:
                        peer.close()

            await asyncio.to_thread(scenario)
            assert len(tts.requests) == 2  # Waiting never acquires the TTS/GPU worker.
            assert all("kontrol" not in r.text.casefold() for r in tts.requests)
            assert len(svc.playback) == (3 if slow else 2)
            if slow:
                waiting = svc.playback[0][0]
                assert waiting.phrase_index == 0 and 0 < waiting.sent_audio_ms < 1000
                assert not waiting.completed  # One-second tone was preempted by useful speech.
                assert svc.playback[1][0].phrase_index == 1
            assert all(r.completed for r, _ in svc.playback[int(slow) :])

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        rows = conn.execute(
            "SELECT text,audio_sent_end_ms FROM utterances WHERE source_generation_id ~ '-w[0-9]+$'"
        ).fetchall()
        assert len(rows) == int(slow)
        if slow:
            assert rows[0][0] == "" and rows[0][1] > 0
