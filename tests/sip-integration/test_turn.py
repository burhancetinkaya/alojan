"""Real native Silero/Smart Turn + SIP/RTP with explicitly synthetic ASR/TTS services."""

import audioop
from contextlib import contextmanager
import re
import select
import subprocess
import time
import wave

import pytest
import test_speech
from test_sip import ROOT, Peer, connect, drain_rtp, run_gateway
from test_speech import drive

speech_services = test_speech.speech_services

MODELS = ROOT / ".local/turn-models"
pytestmark = pytest.mark.skipif(
    not MODELS.is_dir(), reason="opt-in native CPU model artifacts required"
)


def phone():
    with wave.open(str(ROOT / "assets/asr/tr-v1/phone.wav")) as wav:
        return audioop.ratecv(
            wav.readframes(wav.getnframes()), 2, 1, wav.getframerate(), 8000, None
        )[0]


def profile(speech_services):
    asr, tts, _, _ = speech_services
    return {
        "speech_profile": True,
        "answer_delay_ms": 0,
        "max_call_seconds": 30,
        "speech_options": [
            "--turn-model-dir",
            str(MODELS),
            "--asr-port",
            str(asr),
            "--tts-port",
            str(tts),
        ],
    }


def run_case(tmp_path, speech_services, source, codec=8, expected="complete"):
    with contextmanager(run_gateway)(tmp_path, profile(speech_services)) as (port, log, _):
        peer = Peer(port, codec)
        try:
            _, _, ended = drive(peer, connect(peer), log, duration=29, source=source)
            assert ended, log.read_text()
            contents = log.read_text()
            assert "mode=adaptive_turn_test voice_pipeline_ready=0" in contents
            assert "Synthetic" not in contents and "Çünkü" not in contents
            if expected == "complete":
                assert "event=speech_fallback" not in contents, contents
                line = next(
                    x for x in contents.splitlines() if x.startswith("event=speech_test_complete")
                )
                metrics = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", line)}
                assert metrics["asr_frames"] * 20 >= len(source) // 16
                assert 500 <= metrics["turn_silence_ms"] < 2000
                assert metrics["turn_probability_milli"] >= 500
                assert metrics["tts_frames"] == 100
                latency = next(
                    x for x in contents.splitlines() if x.startswith("event=turn_latency")
                )
                timings = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", latency)}
                assert timings["endpoint_silence_audio_ms"] == metrics["turn_silence_ms"]
                assert timings["vad_end_to_audio_estimate_ms"] == (
                    timings["endpoint_silence_audio_ms"] + timings["endpoint_to_audio_ms"]
                )
                return metrics
            assert "event=speech_fallback" in contents, contents
            assert "event=speech_test_complete" not in contents
        finally:
            peer.close()


@pytest.mark.parametrize("codec", [8, 0])
def test_native_adaptive_turn_completes_after_speech(tmp_path, speech_services, codec):
    run_case(tmp_path, speech_services, phone(), codec)


@pytest.mark.parametrize(
    "pause,speech_services",
    [(p, f"asr-pause-{p}") for p in [500, 1000, 1500, 2000]],
    indirect=["speech_services"],
)
def test_incomplete_phrase_survives_labeled_pause(tmp_path, speech_services, pause):
    source = phone()
    boundary = 3000 * 16
    source = source[:boundary] + b"\0" * (pause * 16) + source[boundary:]
    run_case(tmp_path, speech_services, source)


@pytest.mark.parametrize(
    "speech_services", ["asr-incomplete", "asr-invalid-coverage"], indirect=True
)
def test_adaptive_turn_rejects_incomplete_or_invalid_text(tmp_path, speech_services):
    run_case(tmp_path, speech_services, phone(), expected="fallback")


def test_digital_silence_never_becomes_a_turn(tmp_path, speech_services):
    run_case(tmp_path, speech_services, b"", expected="fallback")


def test_adaptive_hangup_cancels_and_allows_clean_next_call(tmp_path, speech_services):
    with contextmanager(run_gateway)(tmp_path, profile(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(peer, media, log, source=phone(), duration=9.5)
            peer.send("BYE", 2, branch="z9hG4bKturn-cancel")
            peer.response(200, "BYE")
            drain_rtp(peer)
            limit = time.monotonic() + 0.4
            late = []
            while time.monotonic() < limit:
                if select.select([peer.rtp], [], [], 0.02)[0]:
                    late.append(peer.rtp.recv(2048))
            assert len(late) <= 1
            assert "event=call_closed call=1 " in log.read_text()
            assert "event=speech_test_complete call=1 " not in log.read_text()
            assert "event=fake_cancel service=asr" in speech_services[2].read_text()
        finally:
            peer.close()
        next_peer = Peer(port)
        try:
            media = connect(next_peer)
            drive(next_peer, media, log, source=b"", until="event=speech_test_capture call=2")
            _, _, ended = drive(next_peer, media, log, source=phone())
            assert ended and "event=speech_test_complete call=2 " in log.read_text()
        finally:
            next_peer.close()


@pytest.mark.parametrize(
    "options",
    [
        ["--turn-context", "unknown"],
        ["--turn-vad-percent", "50"],
        ["--turn-model-dir", str(MODELS), "--turn-vad-percent", "91"],
        ["--turn-model-dir", str(MODELS), "--turn-vad-percent", "nan"],
        ["--turn-model-dir", str(MODELS), "--turn-open-ms", "300"],
        ["--turn-model-dir", str(MODELS), "--turn-open-ms", "1500"],
        ["--turn-model-dir", str(MODELS), "--turn-incomplete-ms", "2000"],
        ["--turn-context", "yes-no"],
        ["--turn-model-dir", "missing-models"],
        ["--turn-model-dir", str(MODELS), "--speech-test-ms", "1000"],
    ],
)
def test_adaptive_profile_rejects_invalid_configuration(options):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), *options],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0 and "event=ready" not in result.stdout


def test_runtime_open_wait_reaches_detector(tmp_path, speech_services):
    config = profile(speech_services)
    config["speech_options"] += ["--turn-open-ms", "900"]
    with contextmanager(run_gateway)(tmp_path, config) as (port, log, _):
        peer = Peer(port)
        try:
            _, _, ended = drive(peer, connect(peer), log, duration=29, source=phone())
            assert ended and "event=speech_fallback" not in log.read_text()
            silence = int(re.search(r"turn_silence_ms=(\d+)", log.read_text())[1])
            assert 900 <= silence < 2000
        finally:
            peer.close()
