"""Opt-in real managed summary quality with disposable scoped records and no sends."""

import asyncio
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

from alojan.auth import Accounts, connection
from alojan.connections import Connections
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_agent.models import Note, Summary
from alojan_agent.records import CallRecords, CallSummaries
from alojan_agent.summary_worker import process_one
from alojan_contracts.secrets import SecretBox
from test_agent_drafts import content
from test_agent_releases import qualify, prepare_assets
from test_agent_summary_live import CASES, assert_final_meaning, provider_diagnostics  # noqa: F401
from test_provider_connections import owner
import test_number_routing as routing

accounts, database, dedicated = routing.accounts, routing.database, routing.dedicated
pytestmark = pytest.mark.skipif(
    os.environ.get("ALOJAN_REAL_SUMMARY") != "1", reason="explicit real model opt-in required"
)


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_final_meaning_through_real_managed_worker(accounts, dedicated, tmp_path, case, repeat):
    output = Path(os.environ["ALOJAN_SUMMARY_EVIDENCE_DIR"]) / "managed"
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    who = owner(accounts)
    scoped = Accounts(dedicated("management"))
    box = SecretBox(Fernet.generate_key())
    key = os.environ.get("OPENROUTER_API_KEY")
    assert key, "Real provider credential must be supplied through the private environment"
    reference = Connections(scoped, box).create(
        *who, dict(provider="openrouter", label="Managed summary acceptance", api_key=key)
    )["id"]
    draft = content("Test Asistanı", "Test Sahibi") | {"model_connection": reference}
    author = (*who, Profiles(scoped).create(*who, draft)["id"])
    qualify(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    release = Releases(scoped).publish(*author, preparation["id"], 0)["id"]
    routing.bound(accounts, (*author, release))
    name, utterances, saved, later, _, _ = case
    route = routing.initialize(accounts, f"managed-summary-{name}-{repeat}")
    # The call keeps its published recipient/style even after a future draft edit.
    Profiles(scoped).update(*author, draft | {"summary_role_template": "Future draft style"}, 1)

    async def run():
        records = CallRecords(dedicated("records"), route)
        await records.answered(route.call_id)
        for index, text in enumerate(utterances):
            await records.utterance(route.call_id, f"u-{index}", "caller", text)
        await records.note(route.call_id, Note(subject="Talep", message=saved), 1)
        if later:
            await records.utterance(route.call_id, "u-later", "caller", later)
        await records.end(route.call_id, "disconnected")
        store = CallSummaries(dedicated("summaries"))
        assert await process_one(store, dedicated("credentials"), box)
        assert not await process_one(store, dedicated("credentials"), box)

    asyncio.run(run())
    with connection(accounts.dsn) as conn:
        row = conn.execute("SELECT summary_status,payload FROM call_finalizations").fetchone()
        assert row is not None, "Summary deferred or unfinished; no acceptance result"
        status, event = row
        assert status == "done", "Real managed summary failed"
        summary = Summary.model_validate(event["summary"])
        assert conn.execute("SELECT count(*) FROM action_jobs").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM mcp_tool_executions").fetchone() == (0,)
        assert conn.execute("SELECT status,attempts FROM summary_jobs").fetchone() == ("done", 1)
    (output / f"{name}-{repeat}.json").write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2)
    )
    assert_final_meaning(summary, case)
