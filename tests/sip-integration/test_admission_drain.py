"""Real local SIP/RTP maintenance drain; no carrier or inference traffic."""

import signal
import subprocess
import time

import pytest

from test_sip import ROOT, Peer, connect, pump_audio, assert_isolated_tone
import test_sip
import test_prepared_setup as managed

gateway = test_sip.gateway


def wait_log(log, text, count=1):
    deadline = time.monotonic() + 3
    while log.read_text().count(text) < count:
        assert time.monotonic() < deadline, log.read_text()
        time.sleep(0.01)


def close_call(peer):
    peer.send("BYE", 2, branch="z9hG4bKbye" + peer.id)
    peer.response(200, "BYE")


def reject(peer):
    peer.invite()
    peer.response(486)
    # Retransmission must remain rejected rather than reserve another call.
    peer.invite()
    peer.response(486)
    peer.send("ACK")


@pytest.mark.parametrize("codec", [0, 8])
@pytest.mark.parametrize(
    "gateway", [{"test_max_calls": 2, "wav_seconds": 12, "max_call_seconds": 20}], indirect=True
)
def test_drain_preserves_rtp_and_resume_with_active_call(gateway, codec):
    port, log, process = gateway
    first, blocked, second = Peer(port, codec), Peer(port, codec), Peer(port, codec)
    try:
        media = connect(first)
        process.send_signal(signal.SIGUSR1)
        wait_log(log, "event=admission_state mode=draining")
        reject(blocked)
        received = pump_audio([(first, media, 0xD5 if codec == 8 else 0xFF)], 2.3)
        assert_isolated_tone(received[first], codec, 440, 880)
        assert "event=admission_drained" not in log.read_text()
        assert process.poll() is None
        process.send_signal(signal.SIGUSR2)
        wait_log(log, "event=admission_state mode=open", count=2)
        second_media = connect(second)
        received = pump_audio(
            [(first, media, 0xD5 if codec == 8 else 0xFF), (second, second_media, 0xD5)], 0.4
        )
        assert len(received[first]) >= 5 and len(received[second]) >= 5
        close_call(first)
        close_call(second)
        process.send_signal(signal.SIGUSR1)
        wait_log(log, "event=admission_state mode=draining", count=2)
        wait_log(log, "event=admission_drained local_calls=0")
        process.send_signal(signal.SIGUSR1)
        time.sleep(0.05)
        assert log.read_text().count("event=admission_drained") == 1
        assert "reason=shutdown" not in log.read_text()
    finally:
        first.close()
        blocked.close()
        second.close()


@pytest.mark.parametrize("gateway", [{"answer_delay_ms": 1500}], indirect=True)
def test_ringing_call_finishes_setup_while_admission_is_closed(gateway):
    port, log, process = gateway
    first, blocked = Peer(port), Peer(port)
    try:
        first.invite()
        first.response(180)
        process.send_signal(signal.SIGUSR1)
        wait_log(log, "event=admission_state mode=draining")
        reject(blocked)
        first.response(200)
        first.send("ACK", branch="z9hG4bKack" + first.id)
        assert "event=admission_drained" not in log.read_text()
        close_call(first)
        wait_log(log, "event=admission_drained local_calls=0")
    finally:
        first.close()
        blocked.close()


@pytest.mark.parametrize("gateway", [{"network_options": ["--start-drained", "1"]}], indirect=True)
def test_start_drained_rejects_until_explicit_resume(gateway):
    port, log, process = gateway
    blocked, accepted = Peer(port), Peer(port)
    try:
        wait_log(log, "event=admission_drained local_calls=0")
        reject(blocked)
        process.send_signal(signal.SIGUSR2)
        wait_log(log, "event=admission_state mode=open")
        connect(accepted)
        close_call(accepted)
    finally:
        blocked.close()
        accepted.close()


def test_drain_waits_for_pending_setup_and_local_cleanup(tmp_path):
    with managed.gateway(tmp_path, "slow_initialize") as (port, log, process, service):
        first, blocked = managed.peer(port), managed.peer(port, 1)
        try:
            first.invite()
            first.response(180)
            managed.wait_for(lambda: any(name == "initialize" for name, _ in service.events))
            process.send_signal(signal.SIGUSR1)
            wait_log(log, "event=admission_state mode=draining")
            reject(blocked)
            assert "event=admission_drained" not in log.read_text()
            service.mode = "slow_cleanup"
            first.send("CANCEL")
            first.response(200, "CANCEL")
            first.response(487)
            first.send("ACK")
            wait_log(log, "event=admission_drained local_calls=0")
            text = log.read_text()
            assert text.index("event=setup_released") < text.index("event=admission_drained")
            assert "confirmed=0" in text  # Local drain does not claim remote acknowledgement.
            assert not service.leases
        finally:
            first.close()
            blocked.close()


@pytest.mark.parametrize("value", ["-1", "2", "invalid"])
def test_invalid_start_drained_fails_before_listening(value):
    result = subprocess.run(
        [str(ROOT / "build/local/voice-gateway"), "--start-drained", value],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "event=ready" not in result.stdout
