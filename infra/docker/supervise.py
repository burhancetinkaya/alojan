"""Exit a stuck worker's container so Docker can apply its restart policy."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def supervise(command, probe, *, interval=10, grace=180, failures=3, stop_timeout=15):
    stopping = threading.Event()
    previous = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda *_: stopping.set())
    child = subprocess.Popen(command, start_new_session=True)
    deadline = time.monotonic() + grace
    failed = 0
    result = 1
    try:
        while not stopping.wait(interval):
            if child.poll() is not None:
                break
            try:
                check = subprocess.run(probe, timeout=5, capture_output=True, check=False)
                ok = check.returncode == 0
            except subprocess.TimeoutExpired:
                ok = False
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
        # Kill the process group, including uv/compile children, before releasing the GPU.
        if child.poll() is None:
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
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


if __name__ == "__main__":
    service, *command = sys.argv[1:]
    if command and command[0] == "--":
        command.pop(0)
    probe = [sys.executable, str(Path(__file__).with_name("health.py")), service]
    sys.exit(supervise(command, probe))
