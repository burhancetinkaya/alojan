"""PostgreSQL tests in isolated disposable schemas, never application tables."""

import asyncio
import json

import psycopg
import pytest
from alojan.migrate import migrate
from alojan_agent.models import Note, Summary
from alojan_agent.store import Store, call_uuid
import test_database

database = test_database.database


def test_durable_note_receipt_and_summary_failure_recovery(database):
    async def run():
        migrate(database)
        store = Store(database)
        await store.start("synthetic-call", None)
        note = Note(subject="Test", message="Yarın arayın.")
        first = await store.note("synthetic-call", note, 1)
        assert await store.note("synthetic-call", note, 1) == first
        note.confirmed = True
        assert await store.note("synthetic-call", note, 1) == first
        await store.utterance("synthetic-call", "turn-1", "caller", "Sentetik mesaj")
        await store.utterance("synthetic-call", "turn-1", "caller", "Sentetik mesaj")
        await store.utterance("synthetic-call", "turn-1-p0", "assistant", "", 200)
        with pytest.raises(ValueError, match="version conflict"):
            await store.note("synthetic-call", Note(subject="Test", message="Changed"), 1)
        await store.end("synthetic-call", "disconnected")
        with pytest.raises(ValueError, match="no longer"):
            await store.note("synthetic-call", note, 2)
        await store.end("synthetic-call", "disconnected")
        cid = call_uuid("synthetic-call")
        assert (await store.pending())[0] == cid
        inputs = await store.summary_input(cid)
        assert len(inputs["utterances"]) == 2 and inputs["last_note"][1]
        assert json.loads(inputs["last_note"][0])["message"] == "Yarın arayın."
        await store.summary_result(cid)
        assert await store.pending() is None
        with psycopg.connect(database) as conn:
            assert conn.execute("SELECT status,attempts FROM summary_jobs").fetchone() == (
                "failed",
                1,
            )
            conn.execute("UPDATE summary_jobs SET status='pending'")
        summary = Summary(
            caller_name=None,
            caller_number=None,
            subject="Test",
            summary="Test",
            requested_action="Geri arama",
            urgency="low",
            promised_action="none",
            confirmation_status="confirmed",
            unresolved_questions=[],
            confidence=0.8,
            privacy_flags=[],
        )
        await store.summary_result(cid, summary)
        revised = summary.model_copy(
            update={"subject": "Corrected", "urgency": "high", "requested_action": "Updated"}
        )
        await store.summary_result(cid, revised)
        with psycopg.connect(database) as conn:
            assert conn.execute("SELECT count(*) FROM notes").fetchone()[0] == 1
            assert conn.execute("SELECT status,attempts FROM summary_jobs").fetchone() == (
                "done",
                3,
            )
            assert (
                conn.execute(
                    "SELECT detail_jsonb->>'promised_action' FROM call_summaries"
                ).fetchone()[0]
                == "none"
            )
            assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
            assert conn.execute(
                "SELECT subject,urgency,requested_action FROM call_summaries"
            ).fetchone() == ("Corrected", "high", "Updated")

        await store.start("long-synthetic-call", None)
        for index in range(110):
            await store.utterance(
                "long-synthetic-call", f"turn-{index}", "caller", f"{index}:" + "ş" * 250
            )
        recent = (await store.summary_input(call_uuid("long-synthetic-call")))["utterances"]
        assert sum(len(text.encode()) for _, text in recent) <= 12000
        assert recent[-1][1].startswith("109:")
        assert len(recent) < 100 and not any(text.startswith("0:") for _, text in recent)

    asyncio.run(run())
