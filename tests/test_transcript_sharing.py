"""Opt-in transcript scope, disclosure, bounded projection and consent; synthetic sends only."""

import asyncio
import copy
import json
import uuid

import pytest

from alojan.auth import AuthError, connection
from alojan.action_grants import ActionGrants
from alojan.profiles import Profiles, validate_draft
from alojan_contracts.actions import ActionReview
from alojan_contracts.assets import speech_identity, validate_manifest
from alojan_contracts.configuration import EnginePreset
from alojan_contracts.http_actions import HTTPAction, ReviewedHTTPAction, request_data
from alojan_contracts.transcript import (
    DISCLOSURE,
    MAX_BYTES,
    bounded_transcript,
    validate_projection,
)
import test_action_conditions as conditions
from test_action_delivery import Transport
from test_action_grants import action
from test_agent_drafts import content
from test_agent_releases import pack
from test_http_actions import config, source, HTTPTransport, URL
from test_scoped_call_records import summary


prepared, accounts, database, dedicated = (
    conditions.prepared,
    conditions.accounts,
    conditions.database,
    conditions.dedicated,
)


def shared(ref, **changes):
    return config(
        ref,
        transcript_policy="bounded_text.v1",
        body={
            "text": source("transcript.text"),
            "state": source("transcript.status"),
            "call": source("call_id", "fail"),
        },
        **changes,
    )


def test_sharing_requires_explicit_closed_policy_body_and_status():
    ref = str(uuid.uuid4())
    legacy = HTTPAction(**config(ref)).model_dump()
    assert "transcript_policy" not in legacy
    assert HTTPAction(**config(ref, transcript_policy=None)).model_dump() == legacy
    for patch in [
        {"transcript_policy": None},
        {"transcript_policy": "unlimited"},
        {"body": {"text": source("transcript.text")}},
        {"query": {"text": source("transcript.text")}},
        {"body": {"x": source("transcript.audio")}},
    ]:
        with pytest.raises(ValueError):
            HTTPAction(**(shared(ref) | patch))
    with pytest.raises(AuthError):
        validate_draft(content() | {"post_call_actions": [action(ref, fields=["transcript.text"])]})
    selected = ReviewedHTTPAction(
        **shared(ref), endpoint=URL, auth_type="none", connection_label="Test"
    )
    for version in (1, 2, 3, 4):
        with pytest.raises(ValueError):
            ActionReview(schema_version=version, scope_id=ref, profile_id=ref, actions=[selected])
    assert ActionReview(schema_version=5, scope_id=ref, profile_id=ref, actions=[selected]).digest()
    payload = {
        "transcript.text": "Arayan: <script>untrusted</script>",
        "transcript.status": "complete",
        "call_id": ref,
        "agent_name": "Test",
    }
    assert json.loads(request_data(selected, payload)["body"])["text"] == payload["transcript.text"]
    with pytest.raises(ValueError):
        request_data(selected, payload | {"transcript.text": "x" * (MAX_BYTES + 1)})


def test_bounded_export_keeps_utf8_and_explicit_truncation():
    assert bounded_transcript([]) == {"text": None, "status": "empty"}
    assert bounded_transcript([("caller", "Merhaba\u202e\x01", False)]) == {
        "text": "Arayan: Merhaba",
        "status": "complete",
    }
    for rows in [
        [("caller", "ğ🙂" * 5000, False)],
        [("caller", str(i), False) for i in range(101)],
        [("caller", "database clipped", True)],
    ]:
        result = bounded_transcript(rows)
        assert result["status"] == "truncated"
        assert len(result["text"].encode()) <= MAX_BYTES
        assert "�" not in result["text"]
        validate_projection({"transcript." + k: v for k, v in result.items()})
    for text, state in [
        (None, "complete"),
        ("x", "empty"),
        (None, "unknown"),
        ("\x00", "complete"),
    ]:
        with pytest.raises(ValueError):
            validate_projection({"transcript.text": text, "transcript.status": state})


def test_disclosure_changes_prepared_speech_identity_and_rejects_old_audio(tmp_path):
    ref = str(uuid.uuid4())
    old = validate_draft(content() | {"post_call_actions": [config(ref)]})
    draft = validate_draft(content() | {"post_call_actions": [shared(ref)]})
    preset = EnginePreset()
    assert DISCLOSURE not in old.greeting()
    assert draft.greeting().count(DISCLOSURE) == 1
    assert draft.greeting().index(DISCLOSURE) < draft.greeting().index(draft.greeting_text)
    assert speech_identity(old, preset) != speech_identity(draft, preset)
    manifest = json.loads((pack(tmp_path, old) / "manifest.json").read_text())
    with pytest.raises(ValueError, match="does not match"):
        validate_manifest(manifest, draft, preset)


@pytest.mark.parametrize("succeeded", [True, False])
def test_scoped_finalization_exports_only_final_caller_and_sent_assistant_text(
    prepared, accounts, succeeded
):
    create, scoped, summaries, worker, actions = prepared
    ref = actions[0]["connection_id"]
    author, draft, release = create([shared(ref), config(ref, alias="without_transcript")])
    with connection(accounts.dsn) as c:
        call = c.execute("SELECT call_id FROM summary_jobs").fetchone()[0]
        for speaker, text, final, sent in [
            ("caller", "Visible caller", True, None),
            ("caller", "Hidden partial", False, None),
            ("assistant", "Visible sent", True, 400),
            ("assistant", "Hidden unsent", True, 0),
        ]:
            c.execute(
                "INSERT INTO utterances(id,call_id,speaker,text,is_final,audio_sent_start_ms,audio_sent_end_ms) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (uuid.uuid4(), call, speaker, text, final, 0 if sent is not None else None, sent),
            )
        other = uuid.uuid4()
        c.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status) VALUES(%s,%s,'inbound','ended')",
            (other, str(other)),
        )
        c.execute(
            "INSERT INTO utterances(id,call_id,speaker,text,is_final) VALUES(%s,%s,'caller','Other call private text',true)",
            (uuid.uuid4(), other),
        )
        manifest = c.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (release,)
        ).fetchone()[0]
    assert manifest["schema_version"] == 6
    assert manifest["action_grant"]["review"]["schema_version"] == 5
    changed = copy.deepcopy(draft)
    changed["post_call_actions"][0] = config(ref)
    Profiles(scoped).update(*author, changed, 1)
    assert (
        ActionGrants(scoped).review(*author)["review_digest"]
        != ActionReview.model_validate(manifest["action_grant"]["review"]).digest()
    )

    async def run():
        job = await summaries.claim()
        await summaries.finish(job, summary() if succeeded else None)
        http = HTTPTransport()
        from test_action_delivery import due

        for _ in range(2):
            due(accounts)
            assert await worker.process_one(Transport(), http_transport=http)
        payloads = [json.loads(x[1]["body"]) for x in http.calls]
        exported = next(x for x in payloads if "text" in x)
        assert "Visible caller" in exported["text"] and "Visible sent" in exported["text"]
        assert "Hidden" not in exported["text"] and "Other call" not in exported["text"]
        assert exported["state"] == "complete"
        assert sum("text" in x for x in payloads) == 1

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        event = c.execute("SELECT payload FROM call_finalizations").fetchone()[0]
        assert event["schema_version"] == 3 and event["transcript"]["status"] == "complete"


def test_unmatched_sharing_does_not_copy_transcript(prepared, accounts):
    create, _, summaries, _, actions = prepared
    create([shared(actions[0]["connection_id"], condition="summary_ready")])

    async def run():
        await summaries.finish(await summaries.claim())

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        event = c.execute("SELECT payload FROM call_finalizations").fetchone()[0]
        assert "transcript" not in event
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0


def test_readonly_transcript_example_requires_disclosure(accounts):
    from pathlib import Path

    with connection(accounts.dsn) as c:
        example = c.execute(Path("infra/examples/transcript-sharing.sql").read_text()).fetchone()[0]
        draft = validate_draft(content() | {"post_call_actions": [example]})
        assert DISCLOSURE in draft.greeting()
        assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 0


def test_event_budget_omits_transcript_without_losing_finalization(prepared, accounts, monkeypatch):
    create, _, summaries, worker, actions = prepared
    create([shared(actions[0]["connection_id"])])
    with connection(accounts.dsn) as c:
        call = c.execute("SELECT call_id FROM summary_jobs").fetchone()[0]
        c.execute(
            "INSERT INTO utterances(id,call_id,speaker,text,is_final) VALUES(%s,%s,'caller',%s,true)",
            (uuid.uuid4(), call, "x" * 8000),
        )
    original = summaries._input

    def expanded_metadata(c, job):
        data = original(c, job)
        # Exercise the envelope guard independently of today's summary/field sub-budgets.
        data["event"]["future_metadata"] = "x" * 58000
        return data

    monkeypatch.setattr(summaries, "_input", expanded_metadata)

    async def run():
        await summaries.finish(await summaries.claim(), summary())
        http = HTTPTransport()
        assert await worker.process_one(Transport(), http_transport=http)
        body = json.loads(http.calls[0][1]["body"])
        assert body["text"] is None and body["state"] == "omitted_size_limit"

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        event, size = c.execute(
            "SELECT payload,octet_length(payload::text) FROM call_finalizations"
        ).fetchone()
        assert size < 65536
        assert event["summary_status"] == "done" and event["summary"] is not None
        assert event["transcript"] == {"text": None, "status": "omitted_size_limit"}
        assert c.execute("SELECT status FROM summary_jobs").fetchone()[0] == "done"


def test_disabled_sharing_does_not_copy_retained_transcript(prepared, accounts):
    create, _, summaries, _, actions = prepared
    create([config(actions[0]["connection_id"])])
    with connection(accounts.dsn) as c:
        call = c.execute("SELECT call_id FROM summary_jobs").fetchone()[0]
        c.execute(
            "INSERT INTO utterances(id,call_id,speaker,text,is_final) VALUES(%s,%s,'caller','Private retained text',true)",
            (uuid.uuid4(), call),
        )

    async def run():
        await summaries.finish(await summaries.claim(), summary())

    asyncio.run(run())
    with connection(accounts.dsn) as c:
        assert "transcript" not in c.execute("SELECT payload FROM call_finalizations").fetchone()[0]
        payload = c.execute("SELECT payload FROM action_jobs").fetchone()[0]
        assert not any(k.startswith("transcript.") for k in payload)
        assert "Private retained text" not in json.dumps(payload)
