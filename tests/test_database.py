import os
import threading
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from alojan.health import Handler
from alojan.migrate import MIGRATIONS, migrate


class PrivateDSN(str):
    def __repr__(self):
        return "<private test database DSN>"


@pytest.fixture
def database():
    dsn = os.environ.get("ALOJAN_DATABASE_URL")
    if not dsn:
        pytest.skip("Database integration requires explicit ALOJAN_DATABASE_URL")
    # Isolate each test in its own schema; never truncate application tables.
    schema = "test_" + uuid.uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
    isolated = make_conninfo(dsn, options=f"-c search_path={schema}")
    try:
        yield PrivateDSN(isolated)
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


def test_migration_repeat_and_checksum(database, tmp_path):
    migrate(database)
    migrate(database)
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == len(
            list(MIGRATIONS.glob("*.sql"))
        )
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="Applied migration changed"):
        migrate(database, tmp_path)


def test_note_idempotency_and_outbox_transaction_rollback(database):
    migrate(database)
    call_id = uuid.uuid4()
    with psycopg.connect(database) as conn:
        conn.execute(
            "INSERT INTO calls (id, sip_call_id, direction, status) VALUES (%s, 'synthetic', 'inbound', 'ended')",
            (call_id,),
        )
        conn.execute(
            "INSERT INTO notes (id, call_id, note_version, text) VALUES (%s, %s, 1, 'synthetic')",
            (uuid.uuid4(), call_id),
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(database) as conn:
            conn.execute(
                "INSERT INTO notification_outbox (id, call_id, target, payload_jsonb) VALUES (%s, %s, 'test', '{}')",
                (uuid.uuid4(), call_id),
            )
            conn.execute(
                "INSERT INTO notes (id, call_id, note_version, text) VALUES (%s, %s, 1, 'duplicate')",
                (uuid.uuid4(), call_id),
            )
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "INSERT INTO notes (id, call_id, note_version, text) VALUES (%s, %s, 1, 'orphan')",
                (uuid.uuid4(), uuid.uuid4()),
            )


def test_failed_migration_rolls_back_all_ddl(database, tmp_path):
    (tmp_path / "0001_initial.sql").write_text((MIGRATIONS / "0001_initial.sql").read_text())
    (tmp_path / "0002_invalid.sql").write_text("THIS IS NOT SQL;")
    with pytest.raises(psycopg.Error):
        migrate(database, tmp_path)
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT to_regclass('calls')").fetchone()[0] is None


def test_health_is_not_voice_readiness(database, monkeypatch):
    monkeypatch.setenv("ALOJAN_DATABASE_URL", database)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    client = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        client.request("GET", "/health/live")
        response = client.getresponse()
        assert response.status == 200
        response.read()
        client.request("GET", "/health/ready")
        response = client.getresponse()
        assert response.status == 503
        response.read()
        migrate(database)
        client.request("GET", "/health/ready")
        response = client.getresponse()
        assert response.status == 200
        assert b'"voice_pipeline_ready": false' in response.read()
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        worker.join()
