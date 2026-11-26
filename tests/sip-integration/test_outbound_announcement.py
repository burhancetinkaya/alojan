"""Real native SIP/RTP loopback, one synthetic recipient per test."""

import re
import socket
import time
import uuid
from contextlib import contextmanager

import pytest

from test_sip import Peer, run_gateway, udp


def response(sock, target, request, code, body=""):
    fields = []
    for name in ("Via", "From", "To", "Call-ID", "CSeq"):
        header = re.search(rf"^{name}: (.+)\r$", request, re.M | re.I)[1]
        if name == "To" and ";tag=" not in header:
            header += ";tag=outbound-trial"
        fields.append(f"{name}: {header}")
    fields.extend(
        [
            f"Contact: <sip:peer@127.0.0.1:{sock.getsockname()[1]}>",
            "Content-Type: application/sdp",
            f"Content-Length: {len(body)}",
        ]
    )
    sock.sendto(
        (f"SIP/2.0 {code} Test\r\n" + "\r\n".join(fields) + "\r\n\r\n" + body).encode(), target
    )


@pytest.mark.parametrize(
    "outcome,delay",
    [
        ("completed", 0),
        ("completed", 2),
        ("busy", 0),
        ("rejected", 0),
        ("no_answer", 0),
        ("interrupted", 0),
    ],
)
def test_announcement(tmp_path, monkeypatch, outcome, delay):
    sip, rtp = udp(), udp()
    root = tmp_path / "outbound"
    root.mkdir(mode=0o700)
    job = uuid.uuid4().hex
    for k, v in {
        "DIR": str(root),
        "SIP_USER": "8500000000",
        "SIP_PASSWORD": "synthetic",
        "SIP_DOMAIN": f"127.0.0.1:{sip.getsockname()[1]}",
    }.items():
        monkeypatch.setenv("ALOJAN_OUTBOUND_" + k, v)
    try:
        with contextmanager(run_gateway)(tmp_path, {"wav_seconds": 1}) as (port, log, _):
            (root / (job + ".wav")).write_bytes((tmp_path / "synthetic-tone.wav").read_bytes())
            (root / "pending").write_text(f"{job} +908500000000 +905320000000 2 {delay}")
            data, target = sip.recvfrom(4096)
            invite = data.decode()
            assert invite.startswith("INVITE sip:05320000000@")
            if outcome in ("busy", "rejected"):
                response(sip, target, invite, 486 if outcome == "busy" else 603)
            elif outcome == "no_answer":
                response(sip, target, invite, 180)
                while True:
                    msg = sip.recv(4096).decode()
                    if msg.startswith("CANCEL "):
                        response(sip, target, msg, 200)
                        response(sip, target, invite, 487)
                        break
            else:
                body = (
                    "v=0\r\no=peer 1 1 IN IP4 127.0.0.1\r\ns=test\r\nc=IN IP4 127.0.0.1\r\n"
                    f"t=0 0\r\nm=audio {rtp.getsockname()[1]} RTP/AVP 8\r\na=rtpmap:8 PCMA/8000\r\n"
                )
                response(sip, target, invite, 183, body)
                # Early media may carry silence, but it must not consume the announcement.
                rtp.settimeout(0.12)
                try:
                    packet = rtp.recv(2048)
                    assert len(set(packet[12:])) <= 2
                except socket.timeout:
                    pass
                competing = Peer(port)
                try:
                    competing.invite()
                    competing.response(486)
                finally:
                    competing.close()
                answered = time.monotonic()
                response(sip, target, invite, 200, body)
                rtp.settimeout(2)
                while len(set(rtp.recv(2048)[12:])) < 8:
                    assert time.monotonic() - answered < 2
                if outcome == "interrupted":
                    headers = dict(re.findall(r"^(From|To|Call-ID): (.+)\r$", invite, re.M))
                    branch = "z9hG4bK" + uuid.uuid4().hex
                    bye = (
                        f"BYE sip:gateway@127.0.0.1:{port} SIP/2.0\r\n"
                        f"Via: SIP/2.0/UDP 127.0.0.1:{sip.getsockname()[1]};branch={branch}\r\n"
                        f"From: {headers['To']};tag=outbound-trial\r\nTo: {headers['From']}\r\n"
                        f"Call-ID: {headers['Call-ID']}\r\nCSeq: 10 BYE\r\nMax-Forwards: 70\r\nContent-Length: 0\r\n\r\n"
                    )
                    sip.sendto(bye.encode(), target)
                else:
                    sip.settimeout(6)
                    while True:
                        msg = sip.recv(4096).decode()
                        if msg.startswith("BYE "):
                            break
                    assert 0.94 + delay <= time.monotonic() - answered < 1.9 + delay
                    response(sip, target, msg, 200)
            deadline = time.monotonic() + 5
            while (root / "running").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert (root / (job + ".status")).read_text().strip() == outcome
    finally:
        sip.close()
        rtp.close()


def test_restart_before_result_never_dials_again(tmp_path, monkeypatch):
    sip = udp()
    root = tmp_path / "outbound"
    root.mkdir(mode=0o700)
    job = uuid.uuid4().hex
    (root / "running").write_text(f"{job} +908500000000 +905320000000 30 2")
    for k, v in {
        "DIR": str(root),
        "SIP_USER": "8500000000",
        "SIP_PASSWORD": "synthetic",
        "SIP_DOMAIN": f"127.0.0.1:{sip.getsockname()[1]}",
    }.items():
        monkeypatch.setenv("ALOJAN_OUTBOUND_" + k, v)
    try:
        with contextmanager(run_gateway)(tmp_path, {}) as _gateway:
            assert (root / (job + ".status")).read_text().strip() == "uncertain"
            sip.settimeout(0.25)
            with pytest.raises(socket.timeout):
                sip.recv(4096)
    finally:
        sip.close()
