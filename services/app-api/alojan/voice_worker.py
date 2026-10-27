"""Operator-owned audio queue runner. Run on the Linux host, never inside HTTP."""

import argparse
import json
import os
from pathlib import Path
import tempfile
import subprocess
import time

import grpc
import psycopg
from psycopg import sql

from alojan.auth import AuthError, connection
from alojan.catalog import qualified_model
from alojan.profiles import validate_draft
from alojan.roles import dedicated_role
from alojan.voice_assets import import_pack
from alojan.voice_generation import generate_pack
from alojan.voice_window import DockerWindow, WindowError
from alojan_contracts.configuration import EnginePreset
from alojan_contracts.assets import speech_identity

LOCK_ID = 41609736201026


def grant_worker(dsn, role):
    with connection(dsn) as conn:
        schema, target = dedicated_role(conn, role)
        for table, permission in {
            "voice_preparation_jobs": "SELECT, UPDATE(status,failure_code,updated_at)",
            "phone_numbers": "SELECT(scope_id,active_binding_id,status,enabled)",
            "number_bindings": "SELECT(id,scope_id,node_id,release_id)",
            "release_readiness": "SELECT(scope_id,release_id,node_id,ready,valid_until,consumer_id)",
            "agent_preparations": "SELECT",
            "agent_drafts": "SELECT",
            "engine_presets": "SELECT",
            "model_catalog": "SELECT",
            "model_catalog_status": "SELECT, UPDATE(updated_at)",
            "prepared_voice_assets": "SELECT, INSERT",
            "management_audit": "INSERT",
        }.items():
            conn.execute(
                sql.SQL("GRANT {} ON {}.{} TO {}").format(
                    sql.SQL(permission), sql.Identifier(schema), sql.Identifier(table), target
                )
            )
        conn.execute(
            sql.SQL("GRANT USAGE ON SEQUENCE {}.management_audit_id_seq TO {}").format(
                sql.Identifier(schema), target
            )
        )
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0]
        for table in (
            "voice_preparation_jobs",
            "phone_numbers",
            "number_bindings",
            "release_readiness",
        ):
            policy = sql.Identifier("voice_queue_reader_" + str(oid))
            relation = sql.Identifier(schema, table)
            conn.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(policy, relation))
            conn.execute(
                sql.SQL("CREATE POLICY {} ON {} FOR SELECT TO {} USING (true)").format(
                    policy, relation, target
                )
            )
        for table, privilege in [
            ("users", "SELECT"),
            ("agent_drafts", "UPDATE"),
            ("agent_releases", "INSERT"),
            ("phone_numbers", "UPDATE"),
            ("action_jobs", "UPDATE"),
        ]:
            if conn.execute(
                "SELECT has_table_privilege(%s,%s,%s)",
                (role, sql.Identifier(schema, table).as_string(conn), privilege),
            ).fetchone()[0]:
                raise ValueError("Audio worker has unexpected privileges")


def scoped(conn, scope):
    conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))


def finish(dsn, job, status, failure=None):
    with connection(dsn) as conn:
        scoped(conn, job[1])
        conn.execute(
            """UPDATE voice_preparation_jobs SET status=%s,failure_code=%s,updated_at=now()
                        WHERE id=%s AND scope_id=%s""",
            (status, failure, job[0], job[1]),
        )


def run_one(dsn, store, window, endpoint, *, generator=generate_pack):
    # Session lock is never leased/reclaimed by time. A second coordinator cannot infer concurrently.
    with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as guard:
        if not guard.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            return False
        if guard.execute(
            "SELECT 1 FROM voice_preparation_jobs WHERE status='preparing' LIMIT 1"
        ).fetchone():
            raise WindowError("Interrupted audio job requires operator recovery")
        job = guard.execute("""SELECT id,scope_id,preparation_id FROM voice_preparation_jobs
                              WHERE status='queued' ORDER BY created_at,id LIMIT 1""").fetchone()
        if not job:
            return False
        try:
            with connection(dsn) as conn:
                scoped(conn, job[1])
                row = conn.execute(
                    """SELECT p.content,p.content_digest,p.speech_digest,p.model_revision,
                    d.version=p.draft_version FROM agent_preparations p JOIN agent_drafts d
                    ON d.scope_id=p.scope_id AND d.profile_id=p.profile_id
                    WHERE p.scope_id=%s AND p.id=%s""",
                    (job[1], job[2]),
                ).fetchone()
                if not row or not row[4]:
                    finish(dsn, job, "failed", "superseded")
                    return True
                draft = validate_draft(row[0])
                model = qualified_model(conn, draft.model, row[3])
                preset = EnginePreset.model_validate(model["preset"])
                if draft.digest() != row[1] or speech_identity(draft, preset) != row[2]:
                    raise ValueError("Preparation identity mismatch")
                ready = conn.execute(
                    """SELECT 1 FROM prepared_voice_assets
                    WHERE scope_id=%s AND speech_digest=%s""",
                    (job[1], row[2]),
                ).fetchone()
            if ready:
                finish(dsn, job, "ready")
                return True
            # Files are installed before the DB commit. Recover that atomic pack after a
            # failed commit rather than generating different bytes for the same identity.
            installed = Path(store).resolve() / str(job[1]) / row[2]
            if installed.exists():
                if installed.resolve() != installed:
                    raise ValueError("Symlinked prepared pack")
                import_pack(dsn, job[1], job[2], installed, store)
                finish(dsn, job, "ready")
                return True
            with window.reserve() as check:
                finish(dsn, job, "preparing")

                # The lock connection must stay alive; never add one DB query per audio frame.
                checked = 0.0
                deadline = time.monotonic() + 90

                def verify():
                    nonlocal checked
                    check()
                    now = time.monotonic()
                    if now > deadline:
                        raise ValueError("Preparation exceeded its time budget")
                    if now - checked >= 1:
                        try:
                            guard.execute("SELECT 1")
                        except psycopg.Error as exc:
                            raise WindowError("Database reservation lost") from exc
                        checked = now

                with tempfile.TemporaryDirectory(prefix="alojan-voice-") as directory:
                    generator(endpoint, job[2], draft, preset, Path(directory), verify)
                    verify()
                    import_pack(dsn, job[1], job[2], directory, store)
            finish(dsn, job, "ready")
        except WindowError:
            finish(dsn, job, "failed", "interrupted")
            raise
        except (AuthError, ValueError, OSError, grpc.RpcError):
            finish(dsn, job, "failed", "generation_failed")
        return True


def routes_ready(dsn, node):
    with connection(dsn) as conn:
        return conn.execute(
            """SELECT NOT EXISTS (
            SELECT 1 FROM phone_numbers n JOIN number_bindings b
            ON b.scope_id=n.scope_id AND b.id=n.active_binding_id
            LEFT JOIN release_readiness r ON r.scope_id=b.scope_id
              AND r.release_id=b.release_id AND r.node_id=b.node_id
            WHERE n.enabled AND n.status='verified' AND b.node_id=%s
              AND (r.ready IS DISTINCT FROM true OR r.consumer_id IS NULL
                   OR r.valid_until <= clock_timestamp()+interval '1 second'))""",
            (node,),
        ).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--grant-role")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    if args.grant_role:
        grant_worker(dsn, args.grant_role)
        return
    os.umask(0o077)
    config = json.loads(args.config.read_text())
    window = DockerWindow(config, resume_ready=lambda: routes_ready(dsn, config["node_id"]))
    # Endpoint is operator-owned and loopback-only; never accept it from a queued request.
    endpoint = config["tts_endpoint"]
    if endpoint != "127.0.0.1:15072":
        raise ValueError("Expected resident loopback TTS")
    try:
        if (window.root / "active.json").exists():
            window.close_workers()
            raise WindowError("Interrupted reservation requires operator recovery")
        while True:
            ran = run_one(dsn, config["asset_store"], window, endpoint)
            print("event=voice_preparation result=" + ("processed" if ran else "idle"), flush=True)
            if args.once:
                break
            time.sleep(60 if ran else 10)
    except (WindowError, psycopg.Error, OSError, subprocess.SubprocessError):
        raise SystemExit(
            "Audio preparation stopped; inspect private admission journal before recovery"
        ) from None


if __name__ == "__main__":
    main()
