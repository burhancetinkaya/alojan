"""Exit a stuck worker's container so Docker can apply its restart policy."""

import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import time


def admission_open(path):
    """Only an explicit operator-owned open record permits new admission."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            return stat.S_ISREG(os.fstat(fd).st_mode) and os.read(fd, 16) == b"open\n"
        finally:
            os.close(fd)
    except OSError:
        return False


def gateway_output(source, ready):
    # No queue: retain bounded log chunks and never buffer call logs in memory.
    complete = True
    try:
        while chunk := source.readline(8192):
            if complete and chunk == b"event=admission_state mode=draining\n":
                ready.set()
            complete = chunk.endswith(b"\n")
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    finally:
        source.close()


def supervise(
    command,
    probe,
    *,
    interval=10,
    grace=180,
    failures=3,
    stop_timeout=15,
    admission_file=None,
):
    stopping = threading.Event()
    previous = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda *_: stopping.set())
    ready = threading.Event()
    reader = None
    child = None
    deadline = time.monotonic() + grace
    next_probe = time.monotonic() + interval
    failed = 0
    result = 1
    try:
        child = subprocess.Popen(
            [*command, "--start-drained", "1"] if admission_file else command,
            start_new_session=True,
            stdout=subprocess.PIPE if admission_file else None,
        )
        if admission_file:
            reader = threading.Thread(
                target=gateway_output, args=(child.stdout, ready), daemon=True
            )
            reader.start()
        opened = False
        while not stopping.wait(min(interval, 0.25) if admission_file else interval):
            if child.poll() is not None:
                break
            if admission_file and ready.is_set():
                desired = admission_open(admission_file)
                if desired != opened:
                    try:
                        # The launcher must exec the native gateway; never signal a group.
                        child.send_signal(signal.SIGUSR2 if desired else signal.SIGUSR1)
                    except ProcessLookupError:
                        break
                    opened = desired
                    print(
                        "event=admission_requested mode=" + ("open" if opened else "draining"),
                        flush=True,
                    )
            if time.monotonic() < next_probe:
                continue
            try:
                check = subprocess.run(probe, timeout=5, capture_output=True, check=False)
                ok = check.returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
            next_probe = time.monotonic() + interval
            if ok:
                deadline = 0
                failed = 0
            elif time.monotonic() >= deadline:
                failed += 1
                if failed >= failures:
                    print("event=worker_unresponsive restarting=1", flush=True)
                    break
        if stopping.is_set():
            result = 0
    finally:
        # Reap the process group; this does not acknowledge another service's GPU work.
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=stop_timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        if reader is not None:
            reader.join(timeout=1)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


if __name__ == "__main__":
    service, *command = sys.argv[1:]
    if command and command[0] == "--":
        command.pop(0)
    probe = [sys.executable, str(Path(__file__).with_name("health.py")), service]
    admission_file = os.environ.get("ALOJAN_ADMISSION_FILE")
    if admission_file and service != "gateway":
        raise ValueError("admission control is only supported for the native gateway")
    sys.exit(supervise(command, probe, admission_file=admission_file))
