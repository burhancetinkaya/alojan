"""Carrier configuration using synthetic loopback peers, never a live carrier."""

from contextlib import contextmanager
import audioop
import re
import subprocess
import struct
import time
import wave

import pytest
from test_sip import ROOT, Peer, run_gateway


@pytest.mark.parametrize("codec", [8, 0])
@pytest.mark.parametrize("answer_delay_ms", [0, 3000])
def test_public_contact_sdp_and_greeting(tmp_path, codec, answer_delay_ms):
    config = {
        "speech_profile": True,
        "answer_delay_ms": answer_delay_ms,
        "network_options": [
            "--public-address",
            "192.0.2.20",
            "--allow-sip-ip",
            "127.0.0.1",
            "--rtp-port-range",
            "0",
            "--prompt-dir",
            str(ROOT / "assets/prompts/tr-v5-kubra"),
        ],
    }
    with contextmanager(run_gateway)(tmp_path, config) as (port, log, _):
        peer = Peer(port, codec)
        try:
            started = time.monotonic()
            peer.invite()
            peer.response(180)
            ringing_at = time.monotonic()
            assert ringing_at - started < 0.5
            peer.sip.settimeout(5)
            response = peer.response(200)
            answered_at = time.monotonic()
            assert answer_delay_ms / 1000 <= answered_at - started < answer_delay_ms / 1000 + 0.5
            assert answered_at - ringing_at >= answer_delay_ms / 1000 - 0.02
            assert re.search(r"^Contact: .*@192\.0\.2\.20:" + str(port), response, re.M)
            assert "c=IN IP4 192.0.2.20\r\n" in response
            media = int(re.search(r"m=audio (\d+)", response)[1])
            assert media % 2 == 0
            peer.send("ACK", branch="z9hG4bKcarrier-ack" + peer.id)
            ack_at = time.monotonic()
            heard = False
            packets = []
            first_audio_at = None
            while time.monotonic() - ack_at < 1.8:
                peer.send_audio(media, 0xAA if codec == 8 else 0x80)
                packet, sender = peer.rtp.recvfrom(2048)
                assert sender == ("127.0.0.1", media)
                packets.append(packet)
                if len(set(packet[12:])) > 8:
                    heard = True
                    if first_audio_at is None:
                        first_audio_at = time.monotonic() - ack_at
            assert heard, "No greeting audio within one second of ACK"
            assert 0.35 <= first_audio_at < 1
            decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
            received = decode(b"".join(p[12:] for p in packets), 2)
            # Emulate a handset losing the first 300 ms of connection audio.
            received = received[4800:]
            with wave.open(str(ROOT / "assets/prompts/tr-v5-kubra/greeting.wav")) as source:
                greeting = source.readframes(source.getnframes())[6400:]

            def onset(pcm):
                return next(
                    i
                    for i, (value,) in enumerate(struct.iter_unpack("<h", pcm))
                    if abs(value) > 500
                )

            estimate = onset(received) - onset(greeting)
            assert estimate >= 0, "opening word was consumed before handset readiness"
            # Unscaled comparison avoids findfit treating digital silence as a perfect fit.
            errors = []
            for offset in range(max(0, estimate - 80), estimate + 81):
                actual = received[offset * 2 : offset * 2 + 12800]
                if len(actual) == 12800:
                    errors.append(
                        audioop.rms(audioop.add(actual, audioop.mul(greeting[:12800], 2, -1), 2), 2)
                    )
            assert errors and min(errors) < audioop.rms(greeting[:12800], 2) * 0.04
            peer.send("BYE", 2, branch="z9hG4bKcarrier-bye" + peer.id)
            peer.response(200, "BYE")
            assert "invite_to_media_ms=" in log.read_text()
        finally:
            peer.close()


def test_unallowed_transport_source_cannot_claim_allowed_identity(tmp_path):
    config = {"network_options": ["--allow-sip-ip", "127.0.0.2"]}
    with contextmanager(run_gateway)(tmp_path, config) as (port, log, _):
        peer = Peer(port)
        try:
            peer.local = "<sip:test@127.0.0.2>;tag=spoofed"
            peer.identity_headers = ["P-Asserted-Identity: <sip:test@127.0.0.2>"]
            peer.invite()
            peer.response(403)
            peer.send("ACK")
            assert "reason=source_not_allowed" in log.read_text()
            assert "event=media_started" not in log.read_text()
            assert "event=caller_identity" not in log.read_text()
        finally:
            peer.close()


@pytest.mark.parametrize(
    "options",
    [
        ["--bind-address", "192.0.2.10"],
        ["--public-address", "192.0.2.20"],
        ["--bind-address", "example.com"],
        ["--public-address", "0.0.0.0"],
        ["--allow-sip-ip", "224.0.0.1"],
        ["--rtp-port-range", "3"],
        ["--rtp-port", "65500", "--rtp-port-range", "100"],
    ],
)
def test_unsafe_network_configuration_fails_closed(options):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), *options],
        cwd=ROOT,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert b"event=ready" not in result.stdout
