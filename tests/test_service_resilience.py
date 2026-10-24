"""Recovery boundaries with disposable PostgreSQL schemas and synthetic child processes."""

import asyncio
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

import psycopg
import pytest
from alojan.migrate import migrate
from alojan_agent.store import Store, call_uuid
import test_database

database = test_database.database
ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "infra/docker" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconcile_preserves_live_calls_notes_and_end_events(database):
    async def run():
        migrate(database)
        store = Store(database)
        for key in ("orphan", "active", "finished"):
            await store.start(key, None)
            await store.utterance(key, "g1", "caller", "Sentetik mesaj")
        await store.end("finished", "completed")
        with psycopg.connect(database) as conn:
            conn.execute(
                "UPDATE calls SET started_at=now()-interval '10 minutes' WHERE id=%s",
                (call_uuid("orphan"),),
            )
        # Concurrent recovery cannot queue or record the same end twice.
        results = await asyncio.gather(store.reconcile_stale(300), store.reconcile_stale(300))
        assert sum(results) == 1
        assert await store.reconcile_stale(300) == 0
        with psycopg.connect(database) as conn:
            assert conn.execute(
                "SELECT status,ended_at IS NULL FROM calls WHERE id=%s", (call_uuid("active"),)
            ).fetchone() == ("active", True)
            assert conn.execute(
                "SELECT status,hangup_reason,failure_code,duration_ms FROM calls WHERE id=%s",
                (call_uuid("orphan"),),
            ).fetchone() == ("ended", "failed", "missing_end_event", None)
            assert conn.execute("SELECT count(*) FROM utterances").fetchone()[0] == 3
            assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 2
            assert conn.execute("SELECT count(*) FROM call_events").fetchone()[0] == 1
            assert conn.execute(
                "SELECT hangup_reason,failure_code FROM calls WHERE id=%s",
                (call_uuid("finished"),),
            ).fetchone() == ("completed", None)
        with pytest.raises(ValueError):
            await store.reconcile_stale(120)
        # A late normal end preserves the recovery reason and durable queue.
        await store.end("orphan", "completed")
        with psycopg.connect(database) as conn:
            assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 2

    asyncio.run(run())


def test_watchdog_reaps_unresponsive_child(tmp_path):
    pidfile = tmp_path / "pid"
    child = [
        sys.executable,
        "-c",
        f"import os,time,pathlib; pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)",
    ]
    supervisor = load("supervise")
    started = time.monotonic()
    assert (
        supervisor.supervise(
            child,
            [sys.executable, "-c", "raise SystemExit(1)"],
            interval=0.1,
            grace=0,
            failures=3,
            stop_timeout=1,
        )
        == 1
    )
    assert time.monotonic() - started < 5
    with pytest.raises(ProcessLookupError):
        import os

        os.kill(int(pidfile.read_text()), 0)


def test_recovery_rolls_back_end_and_job_if_audit_write_fails(database):
    async def run():
        migrate(database)
        store = Store(database)
        await store.start("orphan", None)
        with psycopg.connect(database) as conn:
            conn.execute("UPDATE calls SET started_at=now()-interval '10 minutes'")
            conn.execute(
                "CREATE FUNCTION fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'synthetic failure'; END $$"
            )
            conn.execute(
                "CREATE TRIGGER fail_audit BEFORE INSERT ON call_events "
                "FOR EACH ROW EXECUTE FUNCTION fail_audit()"
            )
        with pytest.raises(psycopg.errors.RaiseException):
            await store.reconcile_stale(300)
        with psycopg.connect(database) as conn:
            assert conn.execute("SELECT status,ended_at FROM calls").fetchone() == ("active", None)
            assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 0
            conn.execute("DROP TRIGGER fail_audit ON call_events")
        assert await store.reconcile_stale(300) == 1

    asyncio.run(run())


def test_watchdog_forwards_stop_to_healthy_worker(tmp_path):
    # Exercise actual OS signal forwarding in a separate process (no global test handlers).
    script = tmp_path / "runner.py"
    script.write_text(
        f"import sys; sys.path.insert(0, {str(ROOT / 'infra/docker')!r})\n"
        "from supervise import supervise\n"
        "raise SystemExit(supervise([sys.executable,'-c','import time; time.sleep(60)'],"
        "[sys.executable,'-c','pass'], interval=0.1, grace=0, stop_timeout=1))\n"
    )
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        time.sleep(0.5)
        proc.terminate()
        assert proc.wait(timeout=5) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_notification_heartbeat_is_bounded(tmp_path, monkeypatch):
    import os

    health = load("health")
    heartbeat = tmp_path / "heartbeat"
    heartbeat.touch()
    monkeypatch.setattr(health, "Path", lambda _: heartbeat)
    assert health.healthy("telegram")
    os.utime(heartbeat, (time.time() - 100, time.time() - 100))
    assert not health.healthy("telegram")
