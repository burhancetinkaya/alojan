"""Linux supervisor boundaries without GPU, carrier or external services."""

import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "voice_supervisor", ROOT / "infra/docker/supervise.py"
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


def test_only_bounded_regular_explicit_open_record_permits_admission(tmp_path):
    state = tmp_path / "state"
    assert not supervisor.admission_open(state)
    for content in (b"", b"open", b"OPEN\n", b"drained\n", b"open\nextra", b"x" * 10000):
        state.write_bytes(content)
        assert not supervisor.admission_open(state)
    state.write_bytes(b"open\n")
    assert supervisor.admission_open(state)
    link = tmp_path / "link"
    link.symlink_to(state)
    assert not supervisor.admission_open(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert not supervisor.admission_open(fifo)
    assert not supervisor.admission_open(tmp_path)


def test_launch_failure_restores_signal_handlers():
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    with pytest.raises(FileNotFoundError):
        supervisor.supervise(["/nonexistent-alojan-worker"], [])
    assert {sig: signal.getsignal(sig) for sig in previous} == previous


def test_health_failure_reaps_unresponsive_worker(tmp_path):
    pid_file = tmp_path / "pid"
    command = [
        sys.executable,
        "-c",
        (
            "import os, signal, time; from pathlib import Path; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)"
        ),
    ]
    result = supervisor.supervise(
        command,
        [sys.executable, "-c", "raise SystemExit(1)"],
        interval=0.15,
        grace=0,
        failures=2,
        stop_timeout=0.1,
    )
    assert result == 1
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


def test_open_file_never_signals_child_before_native_admission_ack(tmp_path):
    state = tmp_path / "state"
    state.write_text("open\n")
    finished = tmp_path / "finished"
    # A generic listener-ready log must not authorize a USR2 signal during startup.
    command = [
        sys.executable,
        "-c",
        (
            "import time; from pathlib import Path; print('event=ready', flush=True); "
            f"time.sleep(0.4); Path({str(finished)!r}).touch()"
        ),
    ]
    assert (
        supervisor.supervise(
            command,
            [sys.executable, "-c", "pass"],
            interval=0.05,
            admission_file=state,
        )
        == 1
    )
    assert finished.exists()


@pytest.mark.parametrize("profile", ["greeting", "interruption", "agent"])
def test_netgsm_launcher_execs_gateway_and_forwards_closed_startup(tmp_path, profile):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "build/local").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/run-netgsm.sh", tmp_path / "scripts/run-netgsm.sh")
    native = tmp_path / "build/local/voice-gateway"
    native.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    native.chmod(0o700)
    private = tmp_path / "netgsm.env"
    private.write_text(
        "ALOJAN_SIP_BIND=127.0.0.1\nALOJAN_SIP_PUBLIC=127.0.0.1\nALOJAN_SIP_SOURCE=127.0.0.1\n"
    )
    result = subprocess.run(
        ["sh", str(tmp_path / "scripts/run-netgsm.sh"), "--start-drained", "1"],
        env={**os.environ, "ALOJAN_NETGSM_ENV": str(private), "ALOJAN_VOICE_PROFILE": profile},
        capture_output=True,
        text=True,
        check=True,
    )
    arguments = result.stdout.splitlines()
    assert arguments[-2:] == ["--start-drained", "1"]
    assert arguments.count("--start-drained") == 1
    assert "--allow-sip-ip" in arguments and "--trusted-identity-ip" in arguments
