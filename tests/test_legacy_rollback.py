"""The rollback identity cannot read or mutate managed calls, even with forged scope."""

import asyncio
import importlib
import os
from pathlib import Path
import sys
import types
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from alojan.auth import connection
from alojan.legacy_roles import grant_legacy_rollback
from alojan_agent.records import CallRecords
from alojan_agent.store import call_uuid
import test_scoped_call_records as scoped

accounts = scoped.accounts
database = scoped.database
author = scoped.author
published = scoped.published
route = scoped.route


@pytest.fixture
def rollback(accounts):
    name = "test_rollback_" + uuid.uuid4().hex
    target = psycopg.sql.Identifier(name)
    with connection(accounts.dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(target))
    try:
        grant_legacy_rollback(accounts.dsn, name)
        grant_legacy_rollback(accounts.dsn, name)
        options = conninfo_to_dict(accounts.dsn)["options"] + f" -c role={name}"
        yield name, make_conninfo(accounts.dsn, options=options)
    finally:
        with connection(accounts.dsn) as conn:
            for table, policy in conn.execute(
                "SELECT tablename,policyname FROM pg_policies "
                "WHERE schemaname=current_schema() AND %s=ANY(roles)",
                (name,),
            ).fetchall():
                conn.execute(
                    psycopg.sql.SQL("DROP POLICY {} ON {}").format(
                        psycopg.sql.Identifier(policy), psycopg.sql.Identifier(table)
                    )
                )
            conn.execute(psycopg.sql.SQL("DROP OWNED BY {}").format(target))
            conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(target))


def create_legacy(dsn):
    cid = call_uuid("synthetic-rollback")
    with connection(dsn) as conn:
        conn.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status,ended_at) "
            "VALUES(%s,'synthetic-rollback','inbound','ended',now())",
            (cid,),
        )
        conn.execute("INSERT INTO summary_jobs(call_id) VALUES(%s)", (cid,))
    return cid


@pytest.mark.parametrize("scope", ["unset", "correct", "other"])
def test_unfiltered_old_queries_cannot_cross_boundary(accounts, route, rollback, scope):
    asyncio.run(scoped.ended(CallRecords(accounts.dsn, route)))
    cid = create_legacy(rollback[1])
    with connection(rollback[1]) as conn:
        if scope != "unset":
            conn.execute(
                "SELECT set_config('alojan.scope_id',%s,true)",
                (route.scope_id if scope == "correct" else str(uuid.uuid4()),),
            )
        assert conn.execute("SELECT id FROM calls").fetchall() == [(cid,)]
        assert conn.execute(
            "SELECT call_id FROM summary_jobs WHERE status='pending'"
        ).fetchall() == [(cid,)]
        assert conn.execute("SELECT text FROM utterances").fetchall() == []
        assert conn.execute(
            "UPDATE summary_jobs SET status='failed' RETURNING call_id"
        ).fetchall() == [(cid,)]
        assert conn.execute(
            "UPDATE calls SET failure_code='synthetic' RETURNING id"
        ).fetchall() == [(cid,)]
    with connection(accounts.dsn) as conn:
        assert conn.execute(
            "SELECT status FROM summary_jobs WHERE call_id=%s", (call_uuid(route.call_id),)
        ).fetchone() == ("pending",)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO notes(id,call_id,note_version,text) VALUES(gen_random_uuid(),%s,1,'forged')",
        "INSERT INTO utterances(id,call_id,speaker,text) VALUES(gen_random_uuid(),%s,'caller','forged')",
        "INSERT INTO notification_outbox(id,call_id,target,payload_jsonb) VALUES(gen_random_uuid(),%s,'synthetic','{}')",
        "INSERT INTO summary_jobs(call_id) VALUES(%s)",
    ],
)
def test_known_managed_identifier_cannot_be_used_for_legacy_writes(
    accounts, route, rollback, query
):
    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation)):
        with connection(rollback[1]) as conn:
            conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (route.scope_id,))
            conn.execute(query, (call_uuid(route.call_id),))


def test_role_cannot_disable_rls_or_read_platform_state(accounts, rollback):
    for query in (
        "SELECT password_hash FROM users",
        "SELECT * FROM action_jobs",
        "SELECT ciphertext FROM telegram_connections",
        "SELECT ciphertext FROM provider_connections",
        "SELECT called_e164 FROM call_route_snapshots",
        "SELECT manifest FROM agent_releases",
        "TRUNCATE calls",
        "DELETE FROM calls",
        "UPDATE notification_channels SET enabled_at=now()",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection(rollback[1]) as conn:
            conn.execute(query)
    with pytest.raises(psycopg.errors.InsufficientPrivilege), connection(rollback[1]) as conn:
        conn.execute("SET LOCAL row_security=off")
        conn.execute("SELECT * FROM calls")


@pytest.mark.parametrize(
    "extra",
    [
        "SELECT(password_hash) ON users",
        "UPDATE(scope_id) ON summary_jobs",
        "SELECT(called_e164) ON call_route_snapshots",
        "TRUNCATE ON calls",
    ],
)
def test_provisioner_rejects_preexisting_excess_privileges(accounts, rollback, extra):
    with connection(accounts.dsn) as conn:
        conn.execute(
            psycopg.sql.SQL("GRANT {} TO {}").format(
                psycopg.sql.SQL(extra), psycopg.sql.Identifier(rollback[0])
            )
        )
    with pytest.raises(ValueError, match="unexpected"):
        grant_legacy_rollback(accounts.dsn, rollback[0])


def test_restrictive_policy_survives_extra_permissive_policy(accounts, route, rollback):
    with connection(accounts.dsn) as conn:
        conn.execute(
            psycopg.sql.SQL("CREATE POLICY test_extra ON calls TO {} USING(true)").format(
                psycopg.sql.Identifier(rollback[0])
            )
        )
    with connection(rollback[1]) as conn:
        assert conn.execute("SELECT id FROM calls").fetchall() == []


def test_preserved_consumer_source_with_managed_backlog(accounts, route, rollback):
    root = os.environ.get("ALOJAN_ROLLBACK_SOURCE")
    if not root:
        pytest.skip("Requires explicitly selected preserved Linux consumer artifact")
    package = types.ModuleType("alojan_rollback_fixture")
    package.__path__ = [str(Path(root).resolve())]
    sys.modules[package.__name__] = package
    try:
        old_store = importlib.import_module(package.__name__ + ".store")
        old_notifications = importlib.import_module(package.__name__ + ".notifications")
        old_models = importlib.import_module(package.__name__ + ".models")
        asyncio.run(scoped.ended(CallRecords(accounts.dsn, route)))
        store = old_store.Store(rollback[1])
        # A synthetic existing legacy channel; never call activate or the real transport.
        with connection(accounts.dsn) as conn:
            conn.execute(
                "INSERT INTO notification_channels(target,enabled_at) VALUES('telegram:123',now()-interval '1 minute')"
            )

        async def run():
            await store.start("synthetic-rollback-artifact", None)
            await store.utterance("synthetic-rollback-artifact", "g1", "caller", "Sentetik mesaj.")
            await store.note(
                "synthetic-rollback-artifact",
                old_models.Note(subject="Test", message="Sentetik"),
                1,
            )
            await store.end("synthetic-rollback-artifact", "completed")
            cid = call_uuid("synthetic-rollback-artifact")
            assert await store.pending() == (cid,)
            assert (await store.summary_input(cid))["utterances"] == [("caller", "Sentetik mesaj.")]
            await store.summary_result(
                cid, old_models.Summary.model_validate(scoped.summary().model_dump())
            )
            assert await store.pending() is None
            assert (await store.summary_input(call_uuid(route.call_id)))["utterances"] == []

        asyncio.run(run())

        class SyntheticTelegram:
            sent = []

            def send(self, chat_id, text):
                assert chat_id == 123
                assert str(call_uuid(route.call_id)) not in text
                self.sent.append(text)
                return 42

        transport = SyntheticTelegram()
        worker = old_notifications.Notifications(rollback[1], transport, 123)
        assert worker.enqueue() == 1
        assert worker.deliver_one() == "delivered"
        assert worker.enqueue() == 0
        assert worker.deliver_one() == "idle"
        assert len(transport.sent) == 1
        with connection(accounts.dsn) as conn:
            assert conn.execute(
                "SELECT status FROM summary_jobs WHERE call_id=%s", (call_uuid(route.call_id),)
            ).fetchone() == ("pending",)
            assert conn.execute(
                "SELECT count(*) FROM notification_outbox WHERE call_id=%s",
                (call_uuid(route.call_id),),
            ).fetchone() == (0,)
    finally:
        for name in list(sys.modules):
            if name == package.__name__ or name.startswith(package.__name__ + "."):
                del sys.modules[name]
