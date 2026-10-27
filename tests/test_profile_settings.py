from pathlib import Path

import psycopg
import pytest

from alojan.migrate import MIGRATIONS, migrate
import test_database

database = test_database.database

EXAMPLE = Path(__file__).resolve().parents[1] / "infra/examples/profile_settings.sql"


def seed(conn):
    conn.execute(EXAMPLE.read_text())


def test_upgrade_preserves_calls_and_repeated_seed_preserves_settings(database, tmp_path):
    for name in ("0001_initial.sql", "0002_agent_summary.sql"):
        (tmp_path / name).write_text((MIGRATIONS / name).read_text())
    migrate(database, tmp_path)
    with psycopg.connect(database) as conn:
        conn.execute(
            "INSERT INTO calls(id, sip_call_id, direction, status) "
            "VALUES('30000000-0000-4000-8000-000000000001', 'synthetic', 'inbound', 'ended')"
        )
    migrate(database)
    with psycopg.connect(database, autocommit=True) as conn:
        seed(conn)
        conn.execute("UPDATE system_settings SET max_call_seconds = 180 WHERE id = 1")
        seed(conn)
    migrate(database)
    with psycopg.connect(database) as conn:
        assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 1
        assert conn.execute("SELECT max_call_seconds FROM system_settings").fetchone()[0] == 180
        assert conn.execute("SELECT count(*) FROM assistant_profile_revisions").fetchone()[0] == 2
        assert (
            conn.execute("SELECT count(*) FROM assistant_profiles WHERE enabled").fetchone()[0] == 0
        )
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0


def test_cross_scope_profile_revision_rejected(database):
    migrate(database)
    with psycopg.connect(database, autocommit=True) as conn:
        seed(conn)
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "INSERT INTO assistant_profiles(id, scope_id, label) "
                "VALUES('20000000-0000-4000-8000-000000000003', "
                "'10000000-0000-4000-8000-000000000099', 'orphan')"
            )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                "INSERT INTO assistant_profile_revisions "
                "SELECT (jsonb_populate_record(NULL::assistant_profile_revisions, "
                'to_jsonb(r) || \'{"scope_id": "10000000-0000-4000-8000-000000000002", '
                '"revision": 2}\'::jsonb)).* '
                "FROM assistant_profile_revisions r WHERE agent_name = 'Kübra'"
            )


def test_rename_creates_revision_and_cannot_rewrite_history(database):
    migrate(database)
    with psycopg.connect(database, autocommit=True) as conn:
        seed(conn)
        conn.execute(
            "INSERT INTO assistant_profile_revisions "
            "SELECT (jsonb_populate_record(NULL::assistant_profile_revisions, "
            'to_jsonb(r) || \'{"revision": 2, "agent_name": "Deniz", '
            '"owner_display_name": "Öykü", "owner_address": "Öykü Hanım", '
            '"owner_dative": "Öykü Hanıma", "owner_genitive": "Öykü Hanımın"}\'::jsonb)).* '
            "FROM assistant_profile_revisions r WHERE agent_name = 'Kübra'"
        )
        rows = conn.execute(
            "SELECT revision, agent_name FROM assistant_profile_revisions "
            "WHERE owner_display_name IN ('Burhan', 'Öykü') ORDER BY revision"
        ).fetchall()
        assert rows == [(1, "Kübra"), (2, "Deniz")]
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE assistant_profile_revisions SET agent_name = 'Changed'")
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("DELETE FROM assistant_profile_revisions")


@pytest.mark.parametrize(
    "patch",
    [
        {"agent_name": ""},
        {"owner_display_name": " "},
        {"agent_name": "x" * 101},
        {"agent_name": "bad\nname"},
        {"response_max_chars": 0},
        {"voice_ref": "other"},
    ],
)
def test_invalid_profile_data_rejected(database, patch):
    from psycopg.types.json import Jsonb

    migrate(database)
    with psycopg.connect(database, autocommit=True) as conn:
        seed(conn)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO assistant_profile_revisions "
                "SELECT (jsonb_populate_record(NULL::assistant_profile_revisions, "
                "to_jsonb(r) || %s)).* FROM assistant_profile_revisions r "
                "WHERE agent_name = 'Kübra'",
                (Jsonb({"revision": 2, **patch}),),
            )


@pytest.mark.parametrize(
    "assignment",
    [
        "max_call_seconds = -1",
        "llm_temperature = 3",
        "llm_timeout_seconds = 100",
        "max_active_agent_turns = 51",
        "require_ai_disclosure = false",
        "require_scope_isolation = false",
        "require_durable_note_before_ack = false",
        "require_external_write_approval = false",
        "raw_recording_enabled = true",
        "llm_base_url = 'http://untrusted.invalid'",
        "id = 2",
    ],
)
def test_invalid_system_settings_rejected(database, assignment):
    migrate(database)
    with psycopg.connect(database, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE system_settings SET " + assignment)
