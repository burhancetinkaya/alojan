"""Opt-in real resident EMA/native SIP comparison; ASR and tool/model delays are scripted.

Run only inside the voice-preparer's exclusive operator window. No carrier routing
or production agent is modified; fixtures use a disposable PostgreSQL schema.
"""

import asyncio
import audioop
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import wave

import pytest

from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.voice_assets import import_pack
from alojan_contracts.assets import speech_identity
from alojan_contracts.configuration import EnginePreset
from test_answered_lifecycle import running
from test_managed_session import ObservedReady, Script, bind, config
from test_recognition_setup import recognition
from test_sip import Peer, connect, run_gateway
from test_speech import drive
from test_prepared_setup import wait_for
import test_number_routing as routing

accounts, database = routing.accounts, routing.database
author, dedicated = routing.author, routing.dedicated
pytestmark = pytest.mark.skipif(
    os.getenv("ALOJAN_WAITING_EMA_WINDOW") != "1", reason="requires exclusive resident EMA window"
)
DELAYS = (0.05, 1.6, 2.1, 3.0, 2.1, 0.05, 3.0)
ANSWERS = (
    "Üç oturum var.",
    "Toplam maliyet iki lira.",
    "İki kullanıcı var.",
    "Şu anda kayıtları alamıyorum.",
    "Beş oturum var.",
    "Veri bulunamadı.",
    "Sonuç üç.",
)


@pytest.mark.parametrize("position,enabled", [(0, False), (1, True), (2, True), (3, False)])
def test_paired_real_ema(position, enabled, accounts, author, tmp_path, dedicated):
    evidence = Path(os.environ["ALOJAN_WAITING_EMA_EVIDENCE"])
    source = evidence / "pack"
    base = json.loads((evidence / "draft.json").read_text())
    base["response_experience"]["enabled"] = enabled
    token, scope, agent = author
    profiles = Profiles(accounts)
    profiles.update(token, scope, agent, base, 1)
    draft = validate_draft(base)
    preparation = Releases(accounts).prepare(token, scope, agent, 2)
    pack = tmp_path / "ema-pack"
    shutil.copytree(source, pack)
    manifest = json.loads((pack / "manifest.json").read_text())
    manifest["speech_digest"] = speech_identity(draft, EnginePreset())
    if not enabled:
        manifest.pop("waiting")
        (pack / "waiting.wav").unlink()
    (pack / "manifest.json").write_text(json.dumps(manifest))
    import_pack(accounts.dsn, scope, preparation["id"], pack, tmp_path / "store")
    release = Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"]
    published = (*author, release)
    bind(accounts, published, routing.DID)
    record_dsn, router_dsn = dedicated("records"), dedicated("routing")
    turns = int(os.getenv("ALOJAN_WAITING_EMA_TURNS", "14"))
    assert 1 <= turns <= 14

    class TimedScript(Script):
        async def stream(self, call, save_note):
            self.started += 1
            index = (call.turns - 1) % len(DELAYS)
            state = call.response_lifecycle
            try:
                if state:
                    state.dispatch("synthetic-read", call.turns)
                await asyncio.sleep(DELAYS[index])
                if state:
                    state.settle("synthetic-read")
                call.finish = call.turns == turns
                yield ANSWERS[index]
            finally:
                self.closed += 1

    async def run():
        async with (
            running(accounts, published, tmp_path, record_dsn, router_dsn, ObservedReady) as (
                svc,
                port,
                _,
                __,
            ),
            recognition() as (asr, asr_port),
        ):
            svc.backend = TimedScript()
            svc.playback, svc.ended = [], []

            def scenario():
                with contextmanager(run_gateway)(
                    tmp_path, config(port, asr_port, 15072, max_call_seconds=120)
                ) as (sip, log, process):
                    peer = Peer(sip)
                    peer.request_user = routing.DID
                    peer.sip.settimeout(5)
                    try:
                        media = connect(peer)
                        frames, _, ended = drive(peer, media, log, duration=115)
                        assert ended and process.poll() is None, "Call did not finish"
                        wait_for(lambda: not svc.leases and not asr.leases)
                    finally:
                        peer.close()
                    contents = log.read_text()
                    assert "event=speech_fallback" not in contents
                    rows = []
                    feedback = []
                    for line in contents.splitlines():
                        if line.startswith("event=turn_latency "):
                            row = dict(item.split("=", 1) for item in line.split())
                            row.pop("call_trace", None)
                            rows.append(row)
                        if line.startswith("event=sent_speech ") and "kind=waiting" in line:
                            feedback.append(dict(item.split("=", 1) for item in line.split()))
                    assert len(rows) == turns and all(r["status"] == "completed" for r in rows)
                    assert len(svc.playback) >= turns
                    result = {
                        "position": position,
                        "enabled": enabled,
                        "rows": rows,
                        "waiting": feedback,
                        "receipts": [
                            {
                                "generation": r.generation_id,
                                "index": r.phrase_index,
                                "sent_ms": r.sent_audio_ms,
                                "completed": r.completed,
                            }
                            for r, _ in svc.playback
                        ],
                    }
                    (evidence / f"call-{position}.json").write_text(json.dumps(result, indent=2))
                    # All audio is synthetic fixture output, never a real caller recording.
                    with wave.open(str(evidence / f"call-{position}.wav"), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(8000)
                        wav.writeframes(
                            b"".join(audioop.alaw2lin(frame[12:], 2) for frame in frames)
                        )
                    print(
                        f"ema_comparison position={position} enabled={enabled} turns={len(rows)} waiting={len(feedback)}",
                        flush=True,
                    )

            await asyncio.to_thread(scenario)
            assert svc.backend.started == svc.backend.closed == turns
            assert len(svc.ended) == 1 and svc.ended[0].reason == "completed"

    asyncio.run(run())
