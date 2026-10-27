"""Literal, bounded search under restricted management grants and transcript permissions."""

import asyncio
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from alojan.auth import AuthError, connection
from alojan.call_search import decode_cursor, filters
from alojan.personal_tokens import BearerCredential, PersonalTokens
from test_action_delivery import finalize
from test_native_auth import PASSWORD
import test_call_management as fixtures

accounts, database, dedicated = fixtures.accounts, fixtures.database, fixtures.dedicated
prepared, history = fixtures.prepared, fixtures.history


def window():
    now = datetime.now(timezone.utc)
    return dict(
        from_time=(now - timedelta(days=1)).isoformat(),
        to_time=(now + timedelta(days=1)).isoformat(),
    )


@pytest.mark.parametrize(
    "values",
    [
        {"query": "hello"},
        {"from_time": "2026-01-01T00:00:00Z"},
        {"from_time": "2026-01-01", "to_time": "2026-01-02"},
        {"from_time": "2026-01-01T00:00:00Z", "to_time": "2026-05-01T00:00:00Z"},
        {"caller": "' OR 1=1--"},
        {"search_in": "transcript"},
        {"unknown": "value"},
    ],
)
def test_invalid_or_unbounded_filters_fail(values):
    with pytest.raises(AuthError):
        filters(values)


@pytest.mark.parametrize("identifier", [12, None, {}, []])
def test_malformed_cursor_identifiers_are_client_errors(identifier):
    cursor = base64.urlsafe_b64encode(
        json.dumps({"id": identifier, "filter": "digest"}).encode()
    ).decode()
    with pytest.raises(AuthError, match="invalid_call_cursor"):
        decode_cursor(cursor, "digest", filtered=True)


def test_summary_search_uses_literal_text_time_bounds_and_scope(accounts, history):
    one, summaries, store = history
    token, scope, _ = one["author"]
    asyncio.run(finalize(summaries))
    found = store.list(token, scope, **window(), query="Sentetik konu")
    assert len(found["calls"]) == 1
    assert store.list(token, scope, **window(), query="%_")["calls"] == []
    assert store.list(token, scope, **window(), query="' OR true --")["calls"] == []
    assert store.list(token, scope, **window(), summary_status="pending")["calls"] == []
    assert len(store.list(token, scope, **window(), summary_status="done")["calls"]) == 1
    other = fixtures.owner(accounts, "foreign.search")
    assert store.list(*other, **window(), query="Sentetik konu")["calls"] == []
    future = dict(from_time="2100-01-01T00:00:00Z", to_time="2100-01-02T00:00:00Z")
    assert store.list(token, scope, **future, query="Sentetik konu")["calls"] == []


def test_transcript_search_excludes_hidden_speech_and_requires_permission(accounts, history):
    one, _, store = history
    session, scope, _ = one["author"]
    call = store.list(session, scope)["calls"][0]["id"]
    with connection(accounts.dsn) as conn:
        for speaker, text, final, sent in (
            ("caller", "Visible %_ synthetic", True, None),
            ("caller", "Partial hidden", False, None),
            ("assistant", "Unsent hidden", True, 0),
            ("assistant", "Sent visible", True, 10),
        ):
            conn.execute(
                "INSERT INTO utterances(id,call_id,speaker,text,is_final,audio_sent_start_ms,audio_sent_end_ms) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (uuid.uuid4(), call, speaker, text, final, 0 if sent is not None else None, sent),
            )
    created = PersonalTokens(accounts).create(
        session,
        scope,
        dict(
            name="Search", permissions=["calls:read"], expires_in_days=1, current_password=PASSWORD
        ),
    )
    token = BearerCredential(created["token"], scope, frozenset({"calls:read"}))
    with pytest.raises(AuthError, match="insufficient_scope"):
        store.list(token, scope, **window(), search_in="transcript", query="visible")
    with connection(accounts.dsn) as conn:
        conn.execute(
            "UPDATE personal_access_tokens SET permissions=array['calls:read','transcripts:read'] WHERE id=%s",
            (created["id"],),
        )
    for query in ("%_", "Sent visible"):
        assert (
            len(store.list(token, scope, **window(), search_in="transcript", query=query)["calls"])
            == 1
        )
    assert (
        store.list(token, scope, **window(), search_in="transcript", query="hidden")["calls"] == []
    )


def test_filtered_cursor_cannot_cross_filters_or_workspace(accounts, history, monkeypatch):
    import alojan.calls

    one, _, store = history
    token, scope, _ = one["author"]
    fixtures.routing.ready(accounts, scope, one["release"])
    fixtures.routing.initialize(accounts, "search-page")
    monkeypatch.setattr(alojan.calls, "PAGE_SIZE", 1)
    values = window()
    first = store.list(token, scope, **values)
    cursor = first["next_cursor"]
    assert cursor
    second = store.list(token, scope, **values, after=cursor)
    assert len(second["calls"]) == 1 and second["calls"][0]["id"] != first["calls"][0]["id"]
    with pytest.raises(AuthError, match="invalid_call_cursor"):
        store.list(token, scope, **values, after=cursor, status="ended")
    other = fixtures.owner(accounts, "cursor.foreign")
    with pytest.raises(AuthError, match="invalid_call_cursor"):
        store.list(*other, **values, after=cursor)
