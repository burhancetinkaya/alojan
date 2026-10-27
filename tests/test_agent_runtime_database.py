"""Pinned post-call configuration in disposable PostgreSQL schemas."""

import asyncio

import psycopg
import pytest

import test_number_routing as routing
from alojan.auth import AuthError, connection
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_agent.store import Store, call_uuid
from test_agent_drafts import content

accounts = routing.accounts
database = routing.database
author = routing.author
published = routing.published
dedicated = routing.dedicated


def test_summary_reads_pinned_release_after_draft_change_and_number_deactivation(
    accounts, published
):
    token, scope, agent, _ = published
    number = routing.bound(accounts, published)
    routing.initialize(accounts, "pinned-summary")
    Profiles(accounts).update(token, scope, agent, content("Changed Assistant", "Changed Owner"), 1)
    routing.Numbers(accounts).deactivate(token, scope, number, 3)

    async def run():
        store = Store(accounts.dsn)
        await store.utterance("pinned-summary", "turn", "caller", "Sentetik mesaj.")
        data = await store.summary_input(call_uuid("pinned-summary"))
        assert data["runtime"].name == "Example Assistant"
        assert "Example Owner" in data["runtime"].summary_instructions
        assert "Changed Owner" not in data["runtime"].summary_instructions
        assert data["utterances"] == [("caller", "Sentetik mesaj.")]
        assert data["last_note"] is None
        await store.start("legacy-summary", None)
        assert (await store.summary_input(call_uuid("legacy-summary")))["runtime"] is None

    asyncio.run(run())


def test_hidden_route_cannot_silently_select_legacy_summary_identity(
    accounts, published, dedicated
):
    routing.bound(accounts, published)
    routing.initialize(accounts, "restricted-summary")
    # The directory role may discover routing but is not the future scoped summary worker.
    store = Store(dedicated("routing"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        asyncio.run(store.summary_input(call_uuid("restricted-summary")))


def test_unusable_fallback_is_rejected_before_asset_preparation(accounts, author):
    token, scope, agent = author
    Profiles(accounts).update(token, scope, agent, {**content(), "farewell_text": "Soru?"}, 1)
    with pytest.raises(AuthError, match="unsupported_agent_runtime"):
        Releases(accounts).prepare(token, scope, agent, 2)
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM agent_preparations").fetchone()[0] == 0
