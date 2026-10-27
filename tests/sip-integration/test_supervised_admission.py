"""Exercise the actual supervisor and native gateway together on loopback."""

from contextlib import contextmanager
import sys

import pytest

from test_sip import ROOT, Peer, run_gateway, connect, pump_audio, assert_isolated_tone
from test_admission_drain import wait_log, close_call, reject


def set_state(path, value):
    temporary = path.with_suffix(".next")
    temporary.write_text(value)
    temporary.replace(path)


@contextmanager
def supervised(tmp_path, state):
    config = {
        "command_prefix": [
            sys.executable,
            str(ROOT / "infra/docker/supervise.py"),
            "gateway",
            "--",
        ],
        "env": {"ALOJAN_ADMISSION_FILE": str(state), "ALOJAN_SIP_BIND": "127.0.0.1"},
        "test_max_calls": 2,
        "wav_seconds": 12,
        "max_call_seconds": 20,
    }
    yield from run_gateway(tmp_path, config)


@pytest.mark.parametrize("codec", [0, 8])
def test_supervised_drain_preserves_call_and_persists_on_restart(tmp_path, codec):
    state = tmp_path / "state"
    set_state(state, "open\n")
    with supervised(tmp_path, state) as (port, log, process):
        wait_log(log, "event=admission_state mode=open")
        first, blocked = Peer(port, codec), Peer(port, codec)
        try:
            media = connect(first)
            set_state(state, "drained\n")
            wait_log(log, "event=admission_state mode=draining", count=2)
            reject(blocked)
            received = pump_audio([(first, media, 0xD5 if codec == 8 else 0xFF)], 1.3)
            assert_isolated_tone(received[first], codec, 440, 880)
            assert process.poll() is None
            close_call(first)
            wait_log(log, "event=admission_drained local_calls=0", count=2)
        finally:
            first.close()
            blocked.close()
    # Fresh supervisor + native process using the same operator-owned directory.
    with supervised(tmp_path, state) as (port, log, process):
        wait_log(log, "event=admission_drained local_calls=0")
        blocked, accepted = Peer(port), Peer(port)
        try:
            reject(blocked)
            assert "event=admission_state mode=open" not in log.read_text()
            set_state(state, "open\n")
            wait_log(log, "event=admission_state mode=open")
            connect(accepted)
            close_call(accepted)
        finally:
            blocked.close()
            accepted.close()


@pytest.mark.parametrize("invalid", [None, "OPEN\n", "open\nextra"])
def test_missing_or_invalid_state_starts_closed_and_closes_open_gateway(tmp_path, invalid):
    state = tmp_path / "state"
    if invalid is not None:
        set_state(state, invalid)
    with supervised(tmp_path, state) as (port, log, process):
        wait_log(log, "event=admission_drained local_calls=0")
        blocked = Peer(port)
        try:
            reject(blocked)
        finally:
            blocked.close()
        set_state(state, "open\n")
        wait_log(log, "event=admission_state mode=open")
        if invalid is None:
            state.unlink()
        else:
            set_state(state, invalid)
        wait_log(log, "event=admission_state mode=draining", count=2)
        blocked = Peer(port)
        try:
            reject(blocked)
            assert process.poll() is None
        finally:
            blocked.close()
