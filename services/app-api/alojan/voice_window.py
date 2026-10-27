"""Private Linux coordinator. No Docker socket or admission controls belong in HTTP."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


class WindowError(RuntimeError):
    pass


def atomic_state(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


class DockerWindow:
    """Exclusive single-host window; any restart/timeout leaves persistent gates closed."""

    def __init__(self, configuration, *, resume_ready=None):
        self.config = configuration
        self.resume_ready = resume_ready
        self.root = Path(configuration["control_directory"])
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.paths = {name: Path(value) for name, value in configuration["state_files"].items()}
        if set(self.paths) != {"gateway", "tts", "asr", "agent"}:
            raise ValueError("All admission state files are required")
        if self.paths["tts"] in (self.paths["gateway"], self.paths["asr"], self.paths["agent"]):
            raise ValueError("TTS requires its own admission file")
        self.identities = {}
        self.last_check = 0.0
        self.generating = False

    def command(self, *args):
        result = subprocess.run(["docker", *args], capture_output=True, timeout=8, check=True)
        return result.stdout.decode()

    def identity(self, name):
        row = json.loads(self.command("inspect", self.config["containers"][name]))[0]
        if not row["State"]["Running"]:
            raise WindowError("Voice process is not running")
        return row["Id"], row["State"]["StartedAt"], row["State"]["Pid"], row["RestartCount"]

    def check(self, *, force=False):
        if not force and time.monotonic() - self.last_check < 0.5:
            return
        for name, identity in self.identities.items():
            if self.identity(name) != identity:
                raise WindowError("Voice process changed during reservation")
        if self.paths["gateway"].read_bytes() != b"closed\n":
            raise WindowError("Admission reservation was lost")
        if self.generating and any(
            self.paths[name].read_bytes() != (b"open\n" if name == "tts" else b"closed\n")
            for name in ("tts", "asr", "agent")
        ):
            raise WindowError("Worker reservation was lost")
        self.last_check = time.monotonic()

    def healthy(self, name, maintenance=False):
        args = [
            "exec",
            self.config["containers"][name],
            f"services/{name}/.venv/bin/python",
            "infra/docker/health.py",
            name,
        ]
        if maintenance:
            args.append("--maintenance")
        try:
            self.command(*args)
            return True
        except subprocess.CalledProcessError:
            return False

    def wait(self, predicate, seconds=150):
        deadline = time.monotonic() + seconds
        while True:
            self.check(force=True)
            if predicate():
                self.check(force=True)
                return
            if time.monotonic() >= deadline:
                raise WindowError("Fresh drain acknowledgement timed out")
            time.sleep(0.25)

    def gateway_log(self, since, text):
        result = subprocess.run(
            [
                "docker",
                "logs",
                "--since",
                since,
                "--tail",
                "2000",
                self.config["containers"]["gateway"],
            ],
            capture_output=True,
            timeout=8,
            check=True,
        )
        return text in (result.stdout + result.stderr).decode().splitlines()

    def close_workers(self):
        for path in set(self.paths.values()):
            atomic_state(path, b"closed\n")

    @contextmanager
    def reserve(self):
        with (self.root / "coordinator.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = self.root / "active.json"
            if journal.exists():
                self.close_workers()
                raise WindowError("Interrupted window requires operator recovery")
            if any(path.read_bytes() != b"open\n" for path in self.paths.values()):
                raise WindowError("Operator admission is already closed")
            self.identities = {name: self.identity(name) for name in self.paths}
            since = datetime.now(timezone.utc).isoformat()
            atomic_state(
                journal, json.dumps({"identities": self.identities, "started": since}).encode()
            )
            atomic_state(self.paths["gateway"], b"closed\n")
            try:
                self.wait(lambda: self.gateway_log(since, "event=admission_drained local_calls=0"))
                self.close_workers()
                self.wait(lambda: all(self.healthy(name, True) for name in ("asr", "tts", "agent")))
                atomic_state(self.paths["tts"], b"open\n")

                # Normal health alone cannot attest the gate has reopened; observe the new event.
                def tts_open():
                    log = self.command(
                        "logs", "--since", since, "--tail", "100", self.config["containers"]["tts"]
                    )
                    return bool(
                        re.search(r"event=worker_maintenance instance=[0-9a-f]+ mode=open", log)
                    )

                self.wait(tts_open, 10)
                lost = False
                self.generating = True
                try:
                    yield self.check
                except WindowError:
                    lost = True
                    raise
                finally:
                    self.generating = False
                    if lost:
                        self.close_workers()
                        raise WindowError("Reservation failed; operator recovery required")
                    atomic_state(self.paths["tts"], b"closed\n")
                    self.wait(
                        lambda: all(self.healthy(name, True) for name in ("asr", "tts", "agent"))
                    )
                    self.check(force=True)
                    resumed = datetime.now(timezone.utc).isoformat()
                    for name in ("tts", "asr", "agent"):
                        atomic_state(self.paths[name], b"open\n")
                    self.wait(
                        lambda: all(self.healthy(name) for name in ("asr", "tts", "agent")), 20
                    )

                    def reopened():
                        for name in ("tts", "asr", "agent"):
                            log = self.command(
                                "logs",
                                "--since",
                                resumed,
                                "--tail",
                                "100",
                                self.config["containers"][name],
                            )
                            if not re.search(
                                r"event=worker_maintenance instance=[0-9a-f]+ mode=open", log
                            ):
                                return False
                        return True

                    self.wait(reopened, 10)
                    if self.resume_ready is not None:
                        self.wait(self.resume_ready, 20)
                    self.check(force=True)
                    atomic_state(self.paths["gateway"], b"open\n")
                    deadline = time.monotonic() + 5
                    while not self.gateway_log(since, "event=admission_state mode=open"):
                        if time.monotonic() > deadline:
                            raise WindowError("Native reopening acknowledgement missing")
                        time.sleep(0.1)
                    for name, identity in self.identities.items():
                        if self.identity(name) != identity:
                            raise WindowError("Voice process changed while reopening")
                    journal.unlink()
                    fd = os.open(self.root, os.O_DIRECTORY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            except BaseException:
                if journal.exists():
                    self.close_workers()
                raise
