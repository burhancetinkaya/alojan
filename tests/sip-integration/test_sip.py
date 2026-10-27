"""Loopback SIP peer. No carrier traffic, device capture, or private audio."""

# shortcut: Python is pinned to 3.12; replace audioop before adopting Python 3.13.
import audioop
import math
import os
import re
import select
import shutil
import socket
import struct
import subprocess
import time
import uuid
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(3)
    return sock


class Peer:
    def __init__(self, port, codec=8):
        self.sip, self.rtp = udp(), udp()
        self.target = ("127.0.0.1", port)
        self.id = uuid.uuid4().hex
        self.branch = "z9hG4bK" + self.id
        self.local = f"<sip:test@127.0.0.1>;tag={self.id}"
        self.remote = "<sip:alojan@127.0.0.1>"
        self.codec = codec
        self.audio_sequence = 0
        self.identity_headers = []
        self.request_user = "alojan"

    def send_audio(self, media_port, payload, sequence=None):
        if sequence is None:
            sequence = self.audio_sequence
            self.audio_sequence += 1
        header = struct.pack(
            "!BBHII", 0x80, self.codec, sequence % 65536, (sequence * 160) % (2**32), 12345
        )
        self.rtp.sendto(header + bytes([payload]) * 160, ("127.0.0.1", media_port))

    def close(self):
        self.sip.close()
        self.rtp.close()

    def send(self, method, sequence=1, body="", branch=None):
        headers = [
            f"{method} sip:{self.request_user}@127.0.0.1:{self.target[1]} SIP/2.0",
            f"Via: SIP/2.0/UDP 127.0.0.1:{self.sip.getsockname()[1]};branch={branch or self.branch}",
            "Max-Forwards: 70",
            f"From: {self.local}",
            f"To: {self.remote}",
            f"Call-ID: {self.id}",
            f"CSeq: {sequence} {method}",
            f"Contact: <sip:test@127.0.0.1:{self.sip.getsockname()[1]}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(body.encode())}",
        ]
        if method == "INVITE":
            headers.extend(self.identity_headers)
        self.sip.sendto(("\r\n".join(headers) + "\r\n\r\n" + body).encode(), self.target)

    def invite(self):
        codec_name = "PCMA" if self.codec == 8 else "PCMU"
        body = (
            "v=0\r\no=test 1 1 IN IP4 127.0.0.1\r\ns=test\r\n"
            f"c=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio {self.rtp.getsockname()[1]} RTP/AVP {self.codec}\r\n"
            f"a=rtpmap:{self.codec} {codec_name}/8000\r\na=sendrecv\r\na=ptime:20\r\n"
        )
        self.send("INVITE", body=body)

    def response(self, code, method="INVITE"):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            data = self.sip.recv(65535).decode()
            if data.startswith(f"SIP/2.0 {code}") and re.search(
                rf"CSeq: \d+ {method}\r", data, re.I
            ):
                self.remote = re.search(r"^To: (.+)\r$", data, re.M | re.I)[1]
                return data
        raise AssertionError(f"missing {code} {method}")

    def answer_request(self, request):
        headers = ["SIP/2.0 200 OK"]
        for name in ["Via", "From", "To", "Call-ID", "CSeq"]:
            headers.append(re.search(rf"^{name}: .+\r$", request, re.M | re.I)[0].rstrip())
        self.sip.sendto(
            ("\r\n".join(headers) + "\r\nContent-Length: 0\r\n\r\n").encode(), self.target
        )


@pytest.fixture
def gateway(tmp_path, request):
    yield from run_gateway(tmp_path, getattr(request, "param", {}))


def run_gateway(tmp_path, config):
    executable = ROOT / "build/local/voice-gateway"
    assert executable.exists(), "Build voice-gateway before running SIP integration tests"
    wav = tmp_path / "synthetic-tone.wav"
    with wave.open(str(wav), "wb") as output:
        output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        output.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    int(
                        9000
                        * math.sin(
                            i
                            * math.tau
                            * (880 if config.get("changing_tone") and i >= 16000 else 440)
                            / 8000
                        )
                    ),
                )
                for i in range(8000 * config.get("wav_seconds", 3))
            )
        )
    playback_options = ["--wav", str(wav)]
    if config.get("speech_profile"):
        playback_options = []
    if config.get("mutable_prompts"):
        prompt_dir = tmp_path / "prompts"
        shutil.copytree(ROOT / "assets/prompts/tr-v3-ema", prompt_dir)
        playback_options = ["--prompt-dir", str(prompt_dir)]
    with udp() as reservation:
        port = reservation.getsockname()[1]
    # PJMEDIA needs an even base and a small consecutive media range.
    with udp() as reservation:
        rtp_port = min(reservation.getsockname()[1] // 2 * 2, 65000)
    log = tmp_path / "gateway.log"
    with log.open("w") as output:
        process = subprocess.Popen(
            config.get("command_prefix", [])
            + [
                str(executable),
                "--port",
                str(port),
                "--rtp-port",
                str(rtp_port),
                "--answer-delay-ms",
                str(config.get("answer_delay_ms", 500)),
                "--max-call-seconds",
                str(config.get("max_call_seconds", 20 if config.get("speech_profile") else 8)),
                "--rtp-timeout-ms",
                str(config.get("rtp_timeout_ms", 10000)),
            ]
            + (
                ["--test-max-calls", str(config["test_max_calls"])]
                if "test_max_calls" in config
                else []
            )
            + playback_options
            + config.get("identity_options", [])
            + config.get("network_options", [])
            + config.get("speech_options", []),
            cwd=ROOT,
            env={**os.environ, "ALOJAN_SIP_PORT": str(port), **config.get("env", {})},
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 5
            while "event=ready" not in log.read_text():
                assert process.poll() is None, log.read_text()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(0.02)
            yield port, log, process
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            assert process.returncode == 0, log.read_text()


@pytest.mark.parametrize("codec", [0, 8])
@pytest.mark.parametrize("impairment", ["clean", "loss-reorder-jitter", "reorder-only"])
def test_two_way_rtp_and_playback_completion(gateway, codec, impairment):
    port, log, _ = gateway
    peer = Peer(port, codec)
    try:
        peer.invite()
        answer = peer.response(200)
        media_port = int(re.search(r"m=audio (\d+)", answer)[1])
        peer.send("ACK", branch="z9hG4bKack" + peer.id)
        packets, arrivals = [], []
        start = time.monotonic()
        next_frame, sequence = start, 0
        ended = False
        while time.monotonic() - start < 6:
            now = time.monotonic()
            if now >= next_frame:
                sent = [sequence]
                if impairment != "clean" and sequence >= 20:
                    offset = sequence % 20
                    if offset == 8:
                        sent = [sequence + 1, sequence]
                    elif offset == 9:
                        sent = []
                    if impairment == "loss-reorder-jitter":
                        # Two losses, a reordered pair, a duplicate and a delayed frame per 20.
                        # RTCP net loss counts duplicates as received, so losses exceed duplicates.
                        if offset in (3, 4, 16):
                            sent = []
                        elif offset == 13:
                            sent = [sequence, sequence]
                        elif offset == 17:
                            sent = [sequence - 1, sequence]
                for frame in sent:
                    # Exercise sequence and timestamp wrap independently of arrival ordering.
                    peer.send_audio(media_port, 0x80 if codec == 0 else 0xAA, frame + 268435420)
                sequence += 1
                next_frame += 0.02
            ready, _, _ = select.select([peer.rtp, peer.sip], [], [], 0.005)
            for sock in ready:
                data = sock.recv(65535)
                if sock is peer.rtp:
                    packets.append(data)
                    arrivals.append(time.monotonic())
                elif data.startswith(b"BYE "):
                    peer.answer_request(data.decode())
                    ended = True
            if ended:
                break
        assert ended, "Gateway did not finish after WAV playback"
        assert len(packets) >= 100
        assert all(packet[1] & 0x7F == codec for packet in packets)
        assert any(len(set(packet[12:])) > 8 for packet in packets), "No tone in outgoing RTP"
        timestamps = [struct.unpack("!I", packet[4:8])[0] for packet in packets]
        assert all((b - a) % (2**32) == 160 for a, b in zip(timestamps, timestamps[1:]))
        assert arrivals[-1] - arrivals[0] >= 2, "Playback was sent as a burst"
        deadline = time.monotonic() + 2
        while "event=call_closed" not in log.read_text() and time.monotonic() < deadline:
            time.sleep(0.02)
        samples = re.findall(r"nonzero_samples=(\d+)", log.read_text())
        assert samples and int(samples[0]) > 1000, log.read_text()
        counters = dict(re.findall(r"\b(input_\w+)=(\d+)", log.read_text()))
        assert int(counters["input_rate_hz"]) == 16000
        assert int(counters["input_bad_frames"]) == 0
        assert int(counters["input_frames"]) >= 100
        assert int(counters["input_samples"]) == int(counters["input_frames"]) * 320
        assert "reason=playback_complete" in log.read_text(), log.read_text()
        if impairment == "loss-reorder-jitter":
            for field in ("rx_loss", "rx_reorder", "rx_duplicates", "rx_jitter_max_us"):
                assert int(re.search(rf"{field}=(\d+)", log.read_text())[1]) > 0, log.read_text()
        elif impairment == "reorder-only":
            assert int(re.search(r"rx_reorder=(\d+)", log.read_text())[1]) > 0, log.read_text()
            assert int(re.search(r"rx_loss=(\d+)", log.read_text())[1]) == 0, log.read_text()
            assert int(re.search(r"rx_duplicates=(\d+)", log.read_text())[1]) == 0, log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("gateway", [{"answer_delay_ms": 3000}], indirect=True)
def test_cancel_before_answer_and_reuse(gateway):
    port, log, _ = gateway
    peer = Peer(port)
    try:
        peer.invite()
        peer.response(180)
        peer.send("CANCEL")
        peer.response(200, "CANCEL")
        peer.response(487)
        peer.send("ACK")
        time.sleep(3.15)
        assert "state=DISCONNECTED" in log.read_text()
        assert "state=CONNECTING" not in log.read_text()
        assert "event=media_started" not in log.read_text()
    finally:
        peer.close()
    next_peer = Peer(port)
    try:
        next_peer.sip.settimeout(5)
        next_peer.invite()
        next_peer.response(200)
        next_peer.send("ACK", branch="z9hG4bKack" + next_peer.id)
        next_peer.send("BYE", 2, branch="z9hG4bKbye" + next_peer.id)
        next_peer.response(200, "BYE")
    finally:
        next_peer.close()


def test_busy_and_remote_bye(gateway):
    port, _, _ = gateway
    first, second = Peer(port), Peer(port)
    try:
        first.invite()
        first.response(200)
        first.send("ACK", branch="z9hG4bKack" + first.id)
        second.invite()
        second.response(486)
        second.send("ACK")
        first.send("BYE", 2, branch="z9hG4bKbye" + first.id)
        first.response(200, "BYE")
    finally:
        first.close()
        second.close()


def await_bye(peer, timeout=4):
    deadline = time.monotonic() + timeout
    peer.sip.settimeout(timeout)
    while time.monotonic() < deadline:
        request = peer.sip.recv(65535).decode()
        if request.startswith("BYE "):
            peer.answer_request(request)
            return
    raise AssertionError("Gateway did not send BYE")


def connect(peer):
    peer.invite()
    answer = peer.response(200)
    peer.send("ACK", branch="z9hG4bKack" + peer.id)
    return int(re.search(r"m=audio (\d+)", answer)[1])


@pytest.mark.parametrize("gateway", [{"rtp_timeout_ms": 500, "wav_seconds": 6}], indirect=True)
def test_missing_rtp_ends_call_and_releases_slot(gateway):
    port, log, _ = gateway
    peer = Peer(port)
    try:
        connect(peer)
        started = time.monotonic()
        await_bye(peer, 3)
        assert 0.3 <= time.monotonic() - started < 2
        assert "reason=rtp_inactivity" in log.read_text()
    finally:
        peer.close()
    # Receiving a fresh 200 after timeout proves admission was released.
    replacement = Peer(port)
    try:
        connect(replacement)
        replacement.send("BYE", 2, branch="z9hG4bKbye" + replacement.id)
        replacement.response(200, "BYE")
    finally:
        replacement.close()


@pytest.mark.parametrize("gateway", [{"rtp_timeout_ms": 500, "wav_seconds": 6}], indirect=True)
def test_silent_rtp_keeps_call_alive_until_packets_stop(gateway):
    port, log, _ = gateway
    peer = Peer(port, 0)
    try:
        media_port = connect(peer)
        for seq in range(70):
            packet = struct.pack("!BBHII", 0x80, 0, seq, seq * 160, 56789) + b"\xff" * 160
            peer.rtp.sendto(packet, ("127.0.0.1", media_port))
            time.sleep(0.02)
        assert "reason=rtp_inactivity" not in log.read_text(), log.read_text()
        stopped = time.monotonic()
        await_bye(peer, 3)
        assert 0.25 <= time.monotonic() - stopped < 2
        assert "reason=rtp_inactivity" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("gateway", [{"max_call_seconds": 2, "wav_seconds": 6}], indirect=True)
def test_max_duration_ends_before_wav_finishes(gateway):
    port, log, _ = gateway
    peer = Peer(port)
    try:
        started = time.monotonic()
        connect(peer)
        await_bye(peer, 4)
        assert 1.5 <= time.monotonic() - started < 4
        assert "reason=max_duration" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("acknowledge", [True, False])
@pytest.mark.parametrize("gateway", [{}, {"test_max_calls": 2}], indirect=True)
def test_shutdown_active_call_is_bounded(gateway, acknowledge):
    port, log, process = gateway
    count = 2 if "admission_limit=2" in log.read_text() else 1
    peers = [Peer(port) for _ in range(count)]
    try:
        for peer in peers:
            connect(peer)
        started = time.monotonic()
        process.terminate()
        if acknowledge:
            for peer in peers:
                await_bye(peer, 3)
        process.wait(timeout=4)
        assert process.returncode == 0, log.read_text()
        assert time.monotonic() - started < 4
        assert log.read_text().count("reason=shutdown") == count
        for serial in range(1, count + 1):
            closed = log.read_text().count(f"event=call_closed call={serial} ")
            assert closed <= 1
            if acknowledge:
                assert closed == 1, log.read_text()
    finally:
        for peer in peers:
            peer.close()


def pump_audio(streams, duration):
    """Send paced input and collect in-memory RTP; an unexpected hangup fails the test."""
    captured = {peer: [] for peer, _, _ in streams}
    started = next_frame = time.monotonic()
    sockets = [sock for peer, _, _ in streams for sock in (peer.rtp, peer.sip)]
    while time.monotonic() - started < duration:
        now = time.monotonic()
        if now >= next_frame:
            for peer, media_port, payload in streams:
                peer.send_audio(media_port, payload)
            next_frame += 0.02
        ready, _, _ = select.select(sockets, [], [], 0.005)
        for peer, media_port, _ in streams:
            if peer.rtp in ready:
                data, source = peer.rtp.recvfrom(2048)
                assert source == ("127.0.0.1", media_port)
                assert len(data) == 172 and data[1] & 0x7F == peer.codec
                captured[peer].append(data)
            if peer.sip in ready:
                data = peer.sip.recv(65535)
                if data.startswith(b"BYE "):
                    peer.answer_request(data.decode())
                    pytest.fail("A call ended while its peer was still active")
    return captured


def drain_rtp(peer):
    # Remove packets queued while the test was waiting for the other SIP dialog.
    while select.select([peer.rtp], [], [], 0)[0]:
        peer.rtp.recv(2048)


def assert_isolated_tone(packets, codec, expected, other):
    assert len(packets) >= 30, "Too few packets to measure independent playback"
    payload = b"".join(packet[12:] for packet in packets[-25:])
    decode = audioop.ulaw2lin if codec == 0 else audioop.alaw2lin
    samples = struct.unpack(f"={len(payload)}h", decode(payload, 2))

    def amplitude(frequency):
        return abs(
            sum(
                sample
                * complex(
                    math.cos(i * math.tau * frequency / 8000),
                    math.sin(i * math.tau * frequency / 8000),
                )
                for i, sample in enumerate(samples)
            )
        ) / len(samples)

    intended, leaked = amplitude(expected), amplitude(other)
    assert intended > 2000, (expected, intended)
    assert leaked < intended / 8, (expected, other, intended, leaked)


@pytest.mark.parametrize("first_codec", [8, 0])
@pytest.mark.parametrize(
    "gateway",
    [{"test_max_calls": 2, "wav_seconds": 10, "max_call_seconds": 15, "changing_tone": True}],
    indirect=True,
)
def test_two_call_media_and_cleanup_isolation(gateway, first_codec):
    port, log, _ = gateway
    first, second = Peer(port, first_codec), Peer(port, 8 if first_codec == 0 else 0)
    rejected, replacement = Peer(port), Peer(port)
    try:
        first_port = connect(first)
        first_stream = (first, first_port, 0x80 if first.codec == 0 else 0xAA)
        pump_audio([first_stream], 2.1)
        second_port = connect(second)
        assert first_port != second_port
        second_stream = (second, second_port, 0xFF if second.codec == 0 else 0xD5)
        rejected.invite()
        rejected.response(486)
        rejected.send("ACK")
        drain_rtp(first)
        drain_rtp(second)
        audio = pump_audio([first_stream, second_stream], 1.0)
        assert_isolated_tone(audio[first], first.codec, 880, 440)
        assert_isolated_tone(audio[second], second.codec, 440, 880)
        first_ssrc, second_ssrc = audio[first][-1][8:12], audio[second][-1][8:12]
        assert first_ssrc != second_ssrc

        first.send("BYE", 2, branch="z9hG4bKbye" + first.id)
        first.response(200, "BYE")
        drain_rtp(second)
        continuing = pump_audio([second_stream], 0.5)[second]
        assert len(continuing) >= 15
        assert all(packet[8:12] == second_ssrc for packet in continuing)
        # A released slot can be reused without disturbing the surviving session.
        connect(replacement)
        replacement.send("BYE", 2, branch="z9hG4bKbye" + replacement.id)
        replacement.response(200, "BYE")
        drain_rtp(second)
        assert len(pump_audio([second_stream], 0.4)[second]) >= 12
        second.send("BYE", 2, branch="z9hG4bKbye" + second.id)
        second.response(200, "BYE")
        deadline = time.monotonic() + 2
        while "event=call_closed call=2 " not in log.read_text() and time.monotonic() < deadline:
            time.sleep(0.02)
        closed = re.findall(r"event=call_closed call=(\d+) ([^\n]+)", log.read_text())
        for serial in ("1", "2"):
            assert sum(call == serial for call, _ in closed) == 1, log.read_text()
        meters = dict(closed)
        assert int(re.search(r"nonzero_samples=(\d+)", meters["1"])[1]) > 1000
        assert int(re.search(r"nonzero_samples=(\d+)", meters["2"])[1]) == 0
        assert int(re.search(r"input_frames=(\d+)", meters["2"])[1]) > 30
    finally:
        for peer in (first, second, rejected, replacement):
            peer.close()


@pytest.mark.parametrize("value", ["0", "3", "-1", "2x"])
def test_invalid_test_admission_limit(value):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), "--test-max-calls", value],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "numeric option out of range" in result.stderr
    assert "event=ready" not in result.stdout


@pytest.mark.parametrize(
    "gateway,caller,headers,expected",
    [
        ({}, "+905550000001", [], "identity_status=available identity_source=from"),
        (
            {},
            "+905550000001",
            ["P-Asserted-Identity: <tel:+905550000002>"],
            "operator_trusted=0 pai_ignored=1",
        ),
        (
            {"identity_options": ["--trusted-identity-ip", "127.0.0.2"]},
            "+905550000001",
            ["P-Asserted-Identity: <tel:+905550000002>"],
            "operator_trusted=0 pai_ignored=1",
        ),
        (
            {"identity_options": ["--trusted-identity-ip", "127.0.0.1"]},
            "+905550000001",
            ["P-Asserted-Identity: <tel:+905550000002>"],
            "identity_status=available identity_source=pai",
        ),
        (
            {"identity_options": ["--caller-national-prefix", "0"]},
            "05550000001",
            [],
            "identity_status=available identity_source=from",
        ),
        ({}, "05550000001", [], "identity_status=invalid identity_source=from"),
        (
            {"identity_options": ["--trusted-identity-ip", "127.0.0.1"]},
            "anonymous",
            ["P-Asserted-Identity: <tel:+905550000002>"],
            "identity_status=anonymous identity_source=none caller_number=unknown",
        ),
        (
            {"identity_options": ["--trusted-identity-ip", "127.0.0.1"]},
            "+905550000001",
            ["Privacy: id", "P-Asserted-Identity: <tel:+905550000002>"],
            "identity_status=withheld identity_source=none caller_number=unknown",
        ),
        (
            {"identity_options": ["--trusted-identity-ip", "127.0.0.1"]},
            "+905550000001",
            [
                "Diversion: <sip:+905550000003@example.invalid>;reason=unconditional",
                "History-Info: <sip:+905550000004@example.invalid>;index=1",
            ],
            "redirects=2 redirects_ignored=0",
        ),
        (
            {},
            "+905550000001",
            ["Diversion: <sip:+905550000003@example.invalid>;reason=unconditional"],
            "redirects=0 redirects_ignored=1",
        ),
    ],
    indirect=["gateway"],
)
def test_caller_identity_policy_and_redacted_logs(gateway, caller, headers, expected):
    port, log, _ = gateway
    peer = Peer(port)
    peer.local = f'"Synthetic Caller" <sip:{caller}@example.invalid>;tag={peer.id}'
    peer.identity_headers = headers
    try:
        connect(peer)
        peer.send("BYE", sequence=2, branch="z9hG4bKidentity-bye")
        peer.response(200, "BYE")
        contents = log.read_text()
        assert expected in contents
        assert contents.count("event=caller_identity call=1 ") == 1
        for forbidden in [
            caller,
            "905550000002",
            "905550000003",
            "905550000004",
            "Synthetic Caller",
        ]:
            if caller != "anonymous" or forbidden != caller:
                assert forbidden not in contents
        assert "example.invalid" not in contents
    finally:
        peer.close()


@pytest.mark.parametrize(
    "flag,value",
    [
        ("--trusted-identity-ip", "localhost"),
        ("--trusted-identity-ip", "127.0.0.0/8"),
        ("--trusted-identity-ip", "127.0.0.1:5060"),
        ("--identity-precedence", "diversion-first"),
        ("--caller-national-prefix", "+90"),
    ],
)
def test_invalid_identity_configuration(flag, value):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), flag, value],
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "event=ready" not in result.stdout
    assert value not in result.stderr


def prompt_pcm():
    parts = []
    for name in ("greeting", "unavailable"):
        with wave.open(str(ROOT / f"assets/prompts/tr-v3-ema/{name}.wav"), "rb") as speech:
            parts.append(speech.readframes(speech.getnframes()))
    return parts


@pytest.mark.parametrize("gateway", [{"speech_profile": True}], indirect=True)
@pytest.mark.parametrize("codec", [0, 8])
def test_spoken_greeting_and_unavailable_finish_before_bye(gateway, codec):
    port, log, _ = gateway
    peer = Peer(port, codec)
    try:
        media_port = connect(peer)
        start = time.monotonic()
        next_frame = start
        packets = []
        ended = False
        while time.monotonic() - start < 16:
            if time.monotonic() >= next_frame:
                peer.send_audio(media_port, 0xFF if codec == 0 else 0xD5)
                next_frame += 0.02
            for sock in select.select([peer.sip, peer.rtp], [], [], 0.005)[0]:
                packet = sock.recv(2048)
                if sock is peer.rtp:
                    assert len(packet) == 172 and packet[1] & 0x7F == codec
                    packets.append(packet)
                elif packet.startswith(b"BYE "):
                    peer.answer_request(packet.decode())
                    ended = True
            if ended:
                break
        assert ended, log.read_text()
        decode = audioop.ulaw2lin if codec == 0 else audioop.alaw2lin
        received = decode(b"".join(packet[12:] for packet in packets), 2)
        greeting, fallback = prompt_pcm()
        expected = greeting + fallback
        # Align within initial media startup silence, then compare every source sample.
        offset, _ = audioop.findfit(received[:16000], expected[1600:3200])
        begin = (offset - 800) * 2
        assert 0 <= begin < 8000
        # Separate players may introduce a short handoff gap, but must preserve every sample.
        fallback_start = begin + len(greeting)
        offset, _ = audioop.findfit(
            received[fallback_start : fallback_start + 4800], fallback[1600:3200]
        )
        handoff_bytes = offset * 2 - 1600
        assert 0 <= handoff_bytes <= 1600, "More than 100 ms between announcements"
        fallback_start += handoff_bytes
        for part_start, reference in [(begin, greeting), (fallback_start, fallback)]:
            actual = received[part_start : part_start + len(reference)]
            assert len(actual) == len(reference), "Speech was truncated"
            error = audioop.add(actual, audioop.mul(reference, 2, -1), 2)
            assert audioop.rms(error, 2) < audioop.rms(reference, 2) * 0.04
        duration = len(expected) / 16000
        assert duration <= time.monotonic() - start < duration + 2
        timestamps = [struct.unpack("!I", packet[4:8])[0] for packet in packets]
        assert all((b - a) % 2**32 == 160 for a, b in zip(timestamps, timestamps[1:]))
        assert "mode=dependency_fallback voice_pipeline_ready=0" in log.read_text()
        assert "playback=ai_greeting_fallback" in log.read_text()
        assert "reason=dependencies_unavailable" in log.read_text()
    finally:
        peer.close()


@pytest.mark.parametrize("gateway", [{"speech_profile": True}], indirect=True)
@pytest.mark.parametrize("phase", ["greeting", "fallback"])
def test_remote_bye_stops_greeting_or_fallback(gateway, phase):
    interrupt_after = 0.4 + (len(prompt_pcm()[0]) / 16000 if phase == "fallback" else 0)
    port, log, _ = gateway
    peer = Peer(port)
    try:
        media_port = connect(peer)
        packets = pump_audio([(peer, media_port, 0xD5)], interrupt_after)[peer]
        assert packets
        peer.send("BYE", 2, branch="z9hG4bKspeech-stop")
        peer.response(200, "BYE")
        drain_rtp(peer)
        # Allow at most one already queued conference/UDP frame after BYE acknowledgement.
        late = []
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline:
            if select.select([peer.rtp], [], [], 0.02)[0]:
                late.append(peer.rtp.recv(2048))
        assert len(late) <= 1, "Playback continued after remote hangup"
        assert log.read_text().count("event=call_closed call=1 ") == 1
        assert "reason=dependencies_unavailable" not in log.read_text()
    finally:
        peer.close()
    replacement = Peer(port)
    try:
        media_port = connect(replacement)
        assert pump_audio([(replacement, media_port, 0xD5)], 0.3)[replacement]
        replacement.send("BYE", 2, branch="z9hG4bKspeech-reuse")
        replacement.response(200, "BYE")
    finally:
        replacement.close()


@pytest.mark.parametrize("gateway", [{"speech_profile": True}], indirect=True)
def test_speech_waits_for_ack(gateway):
    port, log, _ = gateway
    peer = Peer(port)
    try:
        peer.invite()
        answer = peer.response(200)
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline:
            if select.select([peer.rtp], [], [], 0.02)[0]:
                packet = peer.rtp.recv(2048)
                # PJMEDIA may send keepalive/silence before ACK; no prompt audio is allowed.
                if len(packet) > 12:
                    assert audioop.max(audioop.alaw2lin(packet[12:], 2), 2) <= 8
        assert "event=media_started" not in log.read_text()
        peer.send("ACK", branch="z9hG4bKdelayed-ack")
        media_port = int(re.search(r"m=audio (\d+)", answer)[1])
        assert pump_audio([(peer, media_port, 0xD5)], 0.4)[peer]
        peer.send("BYE", 2, branch="z9hG4bKack-bye")
        peer.response(200, "BYE")
    finally:
        peer.close()


@pytest.mark.parametrize(
    "gateway", [{"speech_profile": True, "mutable_prompts": True}], indirect=True
)
def test_prompt_disappearing_after_startup_ends_call_without_crashing(gateway, tmp_path):
    port, log, process = gateway
    fallback = tmp_path / "prompts/unavailable.wav"
    original = fallback.read_bytes()
    fallback.unlink()
    peer = Peer(port)
    try:
        connect(peer)
        await_bye(peer, 2)
        assert "reason=playback_error" in log.read_text()
        assert process.poll() is None
    finally:
        peer.close()
        fallback.write_bytes(original)
    replacement = Peer(port)
    try:
        media_port = connect(replacement)
        assert pump_audio([(replacement, media_port, 0xD5)], 0.4)[replacement]
        replacement.send("BYE", 2, branch="z9hG4bKrestored-prompts")
        replacement.response(200, "BYE")
    finally:
        replacement.close()
