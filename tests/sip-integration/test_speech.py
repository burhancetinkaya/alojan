"""M2-03 real SIP/RTP/gRPC integration with explicitly fake speech inference."""

import audioop
import math
import os
import re
import select
import socket
import struct
import subprocess
import sys
import time

import pytest
from test_sip import ROOT, Peer, assert_isolated_tone, connect, drain_rtp, run_gateway


def tcp_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def speech_services(tmp_path, request):
    mode = getattr(request, "param", "normal")
    asr, tts = tcp_port(), tcp_port()
    while tts == asr:
        tts = tcp_port()
    env = os.environ | {
        "PYTHONPATH": ":".join(
            str(ROOT / p)
            for p in [
                "tests",
                "generated/python",
                "services/asr",
                "services/tts",
                "services/voice-contracts",
            ]
        )
    }
    log = tmp_path / "fake-speech.log"
    with log.open("w") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "support.speech_server",
                "--asr-port",
                str(asr),
                "--tts-port",
                str(tts),
                "--mode",
                mode,
            ],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            limit = time.monotonic() + 5
            while "event=fake_speech_ready" not in log.read_text():
                assert process.poll() is None and time.monotonic() < limit, log.read_text()
                time.sleep(0.01)
            yield asr, tts, log, process
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("fake speech worker did not stop")


@pytest.fixture
def speech_gateway(speech_services, tmp_path, request):
    asr, tts, _, _ = speech_services
    config = {
        "speech_profile": True,
        "answer_delay_ms": 0,
        "speech_options": [
            "--speech-test-ms",
            "1000",
            "--asr-port",
            str(asr),
            "--tts-port",
            str(tts),
        ],
    }
    config.update(getattr(request, "param", {}))
    yield from run_gateway(tmp_path, config)


def drive(peer, media_port, log, duration=15, until=None, source=None):
    """Paced synthetic input and in-memory received RTP; no caller recordings."""
    frames, arrivals = [], []
    start = next_frame = time.monotonic()
    capture_start = None
    source_offset = 0
    encode = audioop.lin2alaw if peer.codec == 8 else audioop.lin2ulaw
    tone = b"".join(
        struct.pack("<h", round(9000 * math.sin(i * math.tau * 440 / 8000))) for i in range(160)
    )
    while time.monotonic() - start < duration:
        now = time.monotonic()
        contents = log.read_text()
        if until and until in contents:
            return frames, arrivals, False
        if capture_start is None and "event=speech_test_capture" in contents:
            capture_start = now
        if now >= next_frame:
            if source is not None:
                pcm = (source[source_offset : source_offset + 320] if capture_start else b"").ljust(
                    320, b"\0"
                )
                if capture_start:
                    source_offset += 320
            else:
                pcm = tone
            seq = peer.audio_sequence
            peer.audio_sequence += 1
            packet = struct.pack(
                "!BBHII", 0x80, peer.codec, seq % 65536, (seq * 160) % 2**32, 12345
            ) + encode(pcm, 2)
            peer.rtp.sendto(packet, ("127.0.0.1", media_port))
            next_frame += 0.02
        ready, _, _ = select.select([peer.rtp, peer.sip], [], [], 0.005)
        if peer.rtp in ready:
            packet, sender = peer.rtp.recvfrom(2048)
            assert sender == ("127.0.0.1", media_port) and len(packet) == 172
            frames.append(packet)
            arrivals.append(time.monotonic())
        if peer.sip in ready:
            message = peer.sip.recv(65535).decode()
            if message.startswith("BYE "):
                peer.answer_request(message)
                time.sleep(0.05)
                return frames, arrivals, True
    return frames, arrivals, False


@pytest.mark.parametrize("codec", [8, 0])
def test_speech_pipeline_paces_tts_and_finalizes_asr(speech_gateway, speech_services, codec):
    port, log, _ = speech_gateway
    peer = Peer(port, codec)
    try:
        media_port = connect(peer)
        frames, arrivals, ended = drive(peer, media_port, log)
        assert ended, log.read_text()
        contents = log.read_text()
        assert (
            "event=speech_test_complete" in contents and "reason=speech_test_complete" in contents
        )
        assert (
            "asr_frames=50 asr_partials=1" in contents
            and "tts_frames=100 output_port_ms=2000" in contents
        )
        assert "private" not in contents and "Synthetic speech test" not in contents
        assert_isolated_tone(frames[-65:-10], codec, 880, 440)
        timestamps = [struct.unpack("!I", f[4:8])[0] for f in frames]
        assert all((b - a) % 2**32 == 160 for a, b in zip(timestamps, timestamps[1:]))
        assert 0.017 < (arrivals[-1] - arrivals[0]) / (len(arrivals) - 1) < 0.023
        assert "event=fake_asr samples=16000" in speech_services[2].read_text()
    finally:
        peer.close()


@pytest.mark.parametrize(
    "speech_services",
    [
        "asr-fail",
        "asr-empty",
        "asr-early-final",
        "tts-fail",
        "tts-stale",
        "tts-sequence",
        "tts-format",
    ],
    indirect=True,
)
def test_speech_failure_plays_fallback(speech_gateway):
    port, log, _ = speech_gateway
    peer = Peer(port)
    try:
        packets, _, ended = drive(peer, connect(peer), log)
        assert ended and len(packets) > 350, log.read_text()
        contents = log.read_text()
        assert "event=speech_fallback" in contents and "reason=dependencies_unavailable" in contents
        assert (
            "event=speech_test_complete" not in contents and "speech_output_port_ms=0" in contents
        )
        assert "private" not in contents
        decoded = audioop.alaw2lin(b"".join(p[12:] for p in packets[-160:-20]), 2)
        assert audioop.rms(decoded, 2) > 200
    finally:
        peer.close()


@pytest.mark.parametrize("phase", ["capture", "output"])
def test_remote_hangup_invalidates_speech_and_allows_next_call(
    speech_gateway, speech_services, phase
):
    port, log, _ = speech_gateway
    peer = Peer(port)
    try:
        media = connect(peer)
        drive(peer, media, log, until="event=speech_test_capture")
        if phase == "output":
            drive(peer, media, log, duration=1.5)
        began = time.monotonic()
        peer.send("BYE", 2, branch="z9hG4bKspeech-cancel")
        peer.response(200, "BYE")
        drain_rtp(peer)
        late = []
        while time.monotonic() - began < 0.4:
            if select.select([peer.rtp], [], [], 0.02)[0]:
                late.append(peer.rtp.recv(2048))
        assert len(late) <= 1
        assert "event=call_closed call=1 " in log.read_text()
        assert "event=fake_cancel service=asr" in speech_services[2].read_text()
        assert "event=fake_cancel service=tts" in speech_services[2].read_text()
    finally:
        peer.close()
    next_peer = Peer(port)
    try:
        _, _, ended = drive(next_peer, connect(next_peer), log)
        assert ended and "event=speech_test_complete call=2 " in log.read_text()
    finally:
        next_peer.close()


def test_worker_disappearing_mid_capture_uses_fallback(speech_gateway, speech_services):
    port, log, _ = speech_gateway
    peer = Peer(port)
    try:
        media = connect(peer)
        drive(peer, media, log, until="event=speech_test_capture")
        speech_services[3].terminate()
        speech_services[3].wait(timeout=3)
        _, _, ended = drive(peer, media, log)
        assert ended and "event=speech_fallback" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("speech_services", ["asr-stall"], indirect=True)
def test_native_stall_is_bounded_by_call_shutdown(speech_gateway):
    port, log, process = speech_gateway
    peer = Peer(port)
    try:
        media = connect(peer)
        drive(peer, media, log, duration=4.5)
        start = time.monotonic()
        process.terminate()
        _, _, ended = drive(peer, media, log, duration=3)
        process.wait(timeout=2)
        assert ended and time.monotonic() - start < 3
        assert "reason=shutdown" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("value", ["999", "1001", "10020"])
def test_invalid_capture_window(value):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), "--speech-test-ms", value],
        cwd=ROOT,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1


def test_stalled_playout_rejects_work_instead_of_growing_buffers(speech_services):
    asr, tts, _, _ = speech_services
    result = subprocess.run(
        [str(ROOT / "build/local/speech-bridge-probe"), str(asr), str(tts)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stalled_playout=1" in result.stdout


@pytest.mark.parametrize("speech_services", ["asr-stall"], indirect=True)
def test_asr_deadline_plays_fallback_before_call_limit(speech_gateway):
    port, log, _ = speech_gateway
    peer = Peer(port)
    try:
        started = time.monotonic()
        _, _, ended = drive(peer, connect(peer), log, duration=17)
        assert ended and time.monotonic() - started < 16
        assert "event=speech_fallback" in log.read_text()
        assert "reason=dependencies_unavailable" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("speech_gateway", [{"test_max_calls": 2}], indirect=True)
def test_speech_overload_isolated_to_second_call(speech_gateway):
    from concurrent.futures import ThreadPoolExecutor

    port, log, _ = speech_gateway
    peers = [Peer(port), Peer(port, 0)]
    try:
        media = [connect(peer) for peer in peers]
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(drive, peer, target, log) for peer, target in zip(peers, media)]
            results = [job.result(timeout=17) for job in jobs]
        assert all(ended for _, _, ended in results)
        contents = log.read_text()
        assert contents.count("event=speech_test_complete") == 1, contents
        assert contents.count("event=speech_fallback") == 1, contents
        assert contents.count("event=call_closed") == 2, contents
        completed = int(re.search(r"event=speech_test_complete call=(\d+)", contents)[1]) - 1
        assert_isolated_tone(results[completed][0][-65:-10], peers[completed].codec, 880, 440)
    finally:
        for peer in peers:
            peer.close()


def align_pcm(received, reference):
    """Compare complete speech at RTP frame boundaries, including a preceding silence gap."""
    negative = audioop.mul(reference, 2, -1)
    last = len(received) - len(reference)
    first = max(0, (last - 8000) // 320 * 320)
    candidates = range(first, last + 1, 320)
    best = min(
        candidates,
        key=lambda offset: audioop.rms(
            audioop.add(received[offset : offset + len(reference)], negative, 2), 2
        ),
    )
    actual = received[best : best + len(reference)]
    relative = audioop.rms(audioop.add(actual, negative, 2), 2) / audioop.rms(reference, 2)
    return actual, relative


def test_speech_alignment_handles_silence_and_detects_a_dropped_frame():
    reference = b"".join(
        struct.pack("<h", round(8000 * math.sin(i * math.tau * 443.7 / 8000) + (i % 251) * 5))
        for i in range(32000)
    )
    quantized = audioop.alaw2lin(audioop.lin2alaw(reference, 2), 2)
    received = b"\x08\x00" * 1600 + quantized + b"\x08\x00" * 1280
    actual, relative = align_pcm(received, reference)
    assert actual == quantized and relative < 0.04
    corrupted = received[:12800] + received[13120:] + b"\x08\x00" * 160
    _, error = align_pcm(corrupted, reference)
    assert error > 0.2
