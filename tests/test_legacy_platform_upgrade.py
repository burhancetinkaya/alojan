"""Rehearse the deployed three-migration baseline without copying private live records."""

import asyncio
import uuid

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from alojan.migrate import MIGRATIONS, migrate
import test_database

database = test_database.database

LEGACY = ("0001_initial.sql", "0002_agent_summary.sql", "0003_telegram_outbox.sql")
TABLES = (
    "calls",
    "utterances",
    "call_events",
    "call_summaries",
    "action_items",
    "notes",
    "notification_outbox",
    "notification_channels",
    "summary_jobs",
)


def snapshot(conn, columns=None):
    if columns is None:
        columns = {
            table: [
                r[0]
                for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                    (table,),
                )
            ]
            for table in TABLES
        }
    rows = {}
    for table, names in columns.items():
        query = psycopg.sql.SQL("SELECT {} FROM {} ORDER BY 1").format(
            psycopg.sql.SQL(",").join(map(psycopg.sql.Identifier, names)),
            psycopg.sql.Identifier(table),
        )
        rows[table] = conn.execute(query).fetchall()
    return columns, rows


@pytest.fixture
def legacy(database, tmp_path):
    old = tmp_path / "legacy"
    old.mkdir()
    for name in LEGACY:
        (old / name).write_bytes((MIGRATIONS / name).read_bytes())
    migrate(database, old)
    with psycopg.connect(database) as conn:
        conn.execute("INSERT INTO notification_channels(target) VALUES('telegram:synthetic')")
        for index, status in enumerate(("pending", "done", "failed")):
            cid = uuid.uuid4()
            conn.execute(
                "INSERT INTO calls(id,sip_call_id,direction,status) "
                "VALUES(%s,%s,'inbound','ended')",
                (cid, f"synthetic-upgrade-{index}"),
            )
            conn.execute(
                "INSERT INTO summary_jobs(call_id,status,attempts) VALUES(%s,%s,%s)",
                (cid, status, index),
            )
            conn.execute(
                "INSERT INTO notes(id,call_id,note_version,text,confirmed) "
                "VALUES(%s,%s,1,'Synthetic approved note',true)",
                (uuid.uuid4(), cid),
            )
            conn.execute(
                "INSERT INTO utterances(id,call_id,speaker,text,is_final,source_generation_id) "
                "VALUES(%s,%s,'caller','Synthetic transcript',true,'g1')",
                (uuid.uuid4(), cid),
            )
            conn.execute(
                "INSERT INTO call_events(id,call_id,event_type,metadata_jsonb) "
                "VALUES(%s,%s,'synthetic',%s)",
                (uuid.uuid4(), cid, Jsonb({"test": True})),
            )
            conn.execute(
                "INSERT INTO call_summaries(call_id,subject,summary,urgency,confirmation_status,"
                "json_schema_version) VALUES(%s,'Synthetic','Synthetic summary','low','confirmed',1)",
                (cid,),
            )
            conn.execute(
                "INSERT INTO action_items(id,call_id,type,description) "
                "VALUES(%s,%s,'note','Synthetic action')",
                (uuid.uuid4(), cid),
            )
            conn.execute(
                "INSERT INTO notification_outbox(id,call_id,target,payload_jsonb,retry_count,"
                "delivered_at,failed_at,provider_message_id,last_error) "
                "VALUES(%s,%s,'telegram:synthetic','{}',%s,"
                "CASE WHEN %s='done' THEN now() END,CASE WHEN %s='failed' THEN now() END,"
                "CASE WHEN %s='done' THEN 123 END,CASE WHEN %s='failed' THEN 'synthetic' END)",
                (uuid.uuid4(), cid, index, status, status, status, status),
            )
        before = snapshot(conn)
    return database, before


@pytest.mark.parametrize("schema_state", ["legacy", "partial", "upgraded"])
def test_agent_rejects_incompatible_schema_before_listening(legacy, monkeypatch, schema_state):
    from alojan_agent import __main__ as launcher

    dsn, _ = legacy
    if schema_state == "upgraded":
        migrate(dsn)
    elif schema_state == "partial":
        with psycopg.connect(dsn) as conn:
            conn.execute("CREATE TABLE call_route_snapshots(call_id uuid PRIMARY KEY)")

    class SchemaAccepted(Exception):
        pass

    def before_listen(service, **kwargs):
        raise SchemaAccepted

    monkeypatch.setenv("ALOJAN_DATABASE_URL", dsn)
    monkeypatch.setenv("ALOJAN_RECONCILE_AFTER_SECONDS", "0")
    monkeypatch.setattr(launcher, "Backend", object)
    monkeypatch.setattr(launcher, "create_server", before_listen)
    error = {
        "legacy": psycopg.errors.UndefinedTable,
        "partial": psycopg.errors.UndefinedColumn,
        "upgraded": SchemaAccepted,
    }[schema_state]
    with pytest.raises(error):
        asyncio.run(launcher.serve(15099))


def test_deployed_baseline_upgrade_preserves_history_without_assigning_owners(legacy):
    dsn, (columns, before) = legacy
    migrate(dsn)
    migrate(dsn)
    with psycopg.connect(dsn) as conn:
        assert snapshot(conn, columns)[1] == before
        assert conn.execute(
            "SELECT count(*) FROM summary_jobs WHERE scope_id IS NOT NULL OR release_id IS NOT NULL"
        ).fetchone() == (0,)
        for table in (
            "users",
            "recipient_scopes",
            "workspace_memberships",
            "assistant_profiles",
            "agent_releases",
            "phone_numbers",
            "number_bindings",
            "call_route_snapshots",
            "call_finalizations",
            "action_jobs",
            "action_retry_requests",
            "action_grants",
            "telegram_connections",
            "provider_connections",
        ):
            assert conn.execute(
                psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
            ).fetchone() == (0,), table
        # The deployed legacy consumer may finish its old queue before cutover.
        pending = conn.execute(
            "SELECT call_id FROM summary_jobs WHERE status='pending'"
        ).fetchone()[0]
        conn.execute(
            "UPDATE summary_jobs SET status='done',attempts=attempts+1 WHERE call_id=%s", (pending,)
        )
        conn.execute(
            "UPDATE notification_outbox SET delivered_at=now(),provider_message_id=124 "
            "WHERE call_id=%s AND delivered_at IS NULL AND failed_at IS NULL",
            (pending,),
        )
        assert conn.execute("SELECT count(*) FROM action_jobs").fetchone() == (0,)


def test_late_upgrade_failure_rolls_back_all_new_schema_and_retains_legacy(legacy, tmp_path):
    dsn, (columns, before) = legacy
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        (candidate / path.name).write_bytes(path.read_bytes())
    (candidate / "9999_rehearsal_failure.sql").write_text("SELECT 1 / 0;")
    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate(dsn, candidate)
    with psycopg.connect(dsn) as conn:
        assert snapshot(conn, columns)[1] == before
        assert conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall() == [
            (name,) for name in LEGACY
        ]
        assert conn.execute(
            "SELECT to_regclass('users'),to_regclass('action_jobs')"
        ).fetchone() == (None, None)
    migrate(dsn)


def test_busy_legacy_table_aborts_upgrade_with_operator_lock_budget(legacy):
    dsn, (columns, before) = legacy
    # Preserve the isolated search_path while bounding both lock and statement waits.
    with psycopg.connect(dsn) as conn:
        schema = conn.execute("SELECT current_schema()").fetchone()[0]
    bounded = make_conninfo(
        dsn, options=f"-c search_path={schema} -c lock_timeout=200ms -c statement_timeout=10s"
    )
    with psycopg.connect(dsn) as blocker:
        blocker.execute("LOCK TABLE calls IN ACCESS SHARE MODE")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            migrate(bounded)
    with psycopg.connect(dsn) as conn:
        assert snapshot(conn, columns)[1] == before
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone() == (3,)
        assert conn.execute("SELECT to_regclass('users')").fetchone() == (None,)
    migrate(bounded)
