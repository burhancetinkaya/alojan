"""Native CPU interruption with real SIP/RTP, explicit fake ASR/TTS and synthetic audio."""

import audioop
from contextlib import contextmanager
import math
import hashlib
import json
import wave
import select
import struct
import time
import re
import subprocess

import pytest
import test_speech
from test_sip import ROOT, Peer, assert_isolated_tone, connect, run_gateway
from test_speech import drive
from test_turn import MODELS, phone, profile

speech_services = test_speech.speech_services
pytestmark = pytest.mark.skipif(not MODELS.is_dir(), reason="native CPU models required")


def configuration(services):
    config = profile(services)
    config["speech_options"] += ["--barge-in", "1"]
    config["max_call_seconds"] = 60
    return config


@pytest.mark.parametrize("speech_services", ["barge-normal"], indirect=True)
@pytest.mark.parametrize("codec", [8, 0])
def test_interruption_cancels_old_output_and_recognizes_correction(
    tmp_path, speech_services, codec
):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port, codec)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            # A second synthetic utterance begins while the first response is playing.
            frames, arrivals, ended = drive(peer, media, log, source=phone(), duration=30)
            contents = log.read_text()
            assert ended and "event=speech_fallback" not in contents, contents
            assert "event=speech_interrupted call=1 cancelled_generation=turn-1" in contents
            assert "event=speech_speaking call=1 generation=turn-2" in contents
            assert "interruptions=1" in contents
            total_generated = int(re.search(r"tts_frames=(\d+)", contents)[1])
            total_sent = sum(
                int(n) // 20 for n in re.findall(r"(?<!\w)sent_audio_ms=(\d+)", contents)
            )
            assert total_generated > total_sent, (
                "test must leave queued old-generation PCM to discard"
            )
            records = [
                line for line in contents.splitlines() if line.startswith("event=sent_speech")
            ]
            assert len(records) == 2, contents
            assert (
                "generation=turn-1" in records[0]
                and "aligned_text_bytes=0 interrupted=1" in records[0]
            )
            assert "sent_audio_ms=2000" in records[1] and "interrupted=0" in records[1]
            assert int(re.search(r"aligned_text_bytes=(\d+)", records[1])[1]) > 0
            assert_isolated_tone(frames[-65:-10], codec, 660, 880)
            assert "event=fake_cancel service=tts" in speech_services[2].read_text()
            decision = int(re.search(r"decision_ms=(\d+)", contents)[1]) / 1000
            decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
            old = []
            for packet, at in zip(frames, arrivals):
                samples = struct.unpack("<160h", decode(packet[12:], 2))
                power = (
                    abs(
                        sum(
                            v
                            * complex(
                                math.cos(i * math.tau * 880 / 8000),
                                math.sin(i * math.tau * 880 / 8000),
                            )
                            for i, v in enumerate(samples)
                        )
                    )
                    / 80
                )
                if power > 3000:
                    old.append(at)
            assert old and max(old) - decision < 0.10, (max(old), decision)
            print(
                f"codec={codec} last_old_packet_after_decision_ms={(max(old) - decision) * 1000:.2f}"
            )
            assert "Synthetic" not in contents
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["barge-normal"], indirect=True)
def test_silence_during_output_does_not_interrupt(tmp_path, speech_services):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            _, _, ended = drive(peer, media, log, source=b"", duration=12)
            contents = log.read_text()
            assert ended and "event=speech_fallback" not in contents, contents
            assert "interruptions=0" in contents and "event=speech_interrupted" not in contents
            assert "sent_audio_ms=8000" in contents and "interrupted=0" in contents
        finally:
            peer.close()


def test_barge_in_requires_cpu_models():
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), "--barge-in", "1"],
        cwd=ROOT,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode != 0 and b"event=ready" not in result.stdout


@pytest.mark.parametrize("speech_services", ["barge-backchannel"], indirect=True)
@pytest.mark.parametrize("offset_ms", [0, 20, 40])
def test_brief_acknowledgment_keeps_current_response(tmp_path, speech_services, offset_ms):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            # Complete EMA-generated word; cropping another utterance was VAD-unstable.
            fixture = ROOT / "assets/interruption/tr-v1/acknowledgment.wav"
            entry = json.loads((fixture.parent / "manifest.json").read_text())["files"][0]
            assert hashlib.sha256(fixture.read_bytes()).hexdigest() == entry["sha256"]
            with wave.open(str(fixture)) as wav:
                source = b"\0" * (offset_ms * 16) + wav.readframes(wav.getnframes())
            _, _, ended = drive(peer, media, log, source=source, duration=12)
            contents = log.read_text()
            assert ended and "event=speech_fallback" not in contents, contents
            assert "interruptions=0" in contents
            assert int(re.search(r"backchannels=(\d+)", contents)[1]) > 0, contents
        finally:
            peer.close()


def echo_output(peer, media, log, duration=12):
    from collections import deque

    pending = deque([b"\0" * 320] * 3)
    decode = audioop.alaw2lin if peer.codec == 8 else audioop.ulaw2lin
    encode = audioop.lin2alaw if peer.codec == 8 else audioop.lin2ulaw
    started = next_frame = time.monotonic()
    while time.monotonic() - started < duration:
        if time.monotonic() >= next_frame:
            pcm = pending.popleft() if pending else b"\0" * 320
            sequence = peer.audio_sequence
            peer.audio_sequence += 1
            peer.rtp.sendto(
                struct.pack(
                    "!BBHII", 0x80, peer.codec, sequence % 65536, sequence * 160 % 2**32, 12345
                )
                + encode(pcm, 2),
                ("127.0.0.1", media),
            )
            next_frame += 0.02
        ready, _, _ = select.select([peer.rtp, peer.sip], [], [], 0.005)
        if peer.rtp in ready:
            packet = peer.rtp.recv(2048)
            pending.append(audioop.mul(decode(packet[12:], 2), 2, 0.5))
        if peer.sip in ready:
            message = peer.sip.recv(65535).decode()
            if message.startswith("BYE "):
                peer.answer_request(message)
                return True
    return False


@pytest.mark.parametrize("speech_services", ["barge-echo"], indirect=True)
@pytest.mark.parametrize("codec", [8, 0])
def test_delayed_speech_echo_does_not_interrupt(tmp_path, speech_services, codec):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port, codec)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            assert echo_output(peer, media, log), log.read_text()
            contents = log.read_text()
            assert "event=speech_fallback" not in contents and "interruptions=0" in contents, (
                contents
            )
            assert int(re.search(r"echo_frames=(\d+)", contents)[1]) > 30, contents
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["barge-normal"], indirect=True)
def test_monitor_hangup_releases_call_and_services(tmp_path, speech_services):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            drive(peer, media, log, source=b"", duration=0.5)
            peer.send("BYE", 2, branch="z9hG4bKmonitor-cancel")
            peer.response(200, "BYE")
            deadline = time.monotonic() + 2
            while "event=fake_cancel service=tts" not in speech_services[2].read_text():
                assert time.monotonic() < deadline
                time.sleep(0.01)
        finally:
            peer.close()
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(peer, media, log, source=b"", until="event=speech_test_capture call=2")
            _, _, ended = drive(peer, media, log, source=phone(), duration=25)
            assert ended and "event=speech_test_complete call=2" in log.read_text(), log.read_text()
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["barge-normal"], indirect=True)
def test_seeded_background_noise_does_not_interrupt(tmp_path, speech_services):
    import random

    rng = random.Random(73)
    noise = b"".join(struct.pack("<h", rng.randint(-1000, 1000)) for _ in range(8000 * 9))
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                until="event=speech_speaking call=1 generation=turn-1",
            )
            _, _, ended = drive(peer, media, log, source=noise, duration=12)
            contents = log.read_text()
            assert ended and "event=speech_fallback" not in contents, contents
            assert "interruptions=0" in contents and "event=speech_interrupted" not in contents
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["barge-invalid-monitor"], indirect=True)
def test_invalid_monitor_coverage_uses_controlled_fallback(tmp_path, speech_services):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services)) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            _, _, ended = drive(peer, media, log, source=phone(), duration=25)
            contents = log.read_text()
            assert ended and "event=speech_fallback" in contents, contents
            assert "event=speech_test_complete" not in contents
            assert "event=speech_interrupted" not in contents
        finally:
            peer.close()
