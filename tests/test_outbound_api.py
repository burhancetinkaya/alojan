import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient

import test_agent_releases as releases
import test_number_routing as numbers
from alojan.api import create_app
from alojan.auth import AuthError, connection
from alojan.outbound import OutboundCalls, destination
from alojan.personal_tokens import PersonalTokens
from alojan.profiles import Profiles
from alojan.releases import Releases
from test_agent_drafts import content
from test_native_auth import ORIGIN, PASSWORD

dedicated = numbers.dedicated
accounts, database, author = releases.accounts, releases.database, releases.author


@pytest.fixture
def line(accounts, author, tmp_path):
    session, scope, agent = author
    Profiles(accounts).update(session, scope, agent, content() | {"outbound": {"enabled": True}}, 1)
    prepared, _, _ = releases.prepare_assets(accounts, author, tmp_path, version=2)
    release = Releases(accounts).publish(session, scope, agent, prepared["id"], 0)["id"]
    numbers.bound(accounts, (*author, release))
    return author


def test_concurrent_submissions_pin_once_and_history_masks(accounts, line):
    session, scope, agent = line
    service = OutboundCalls(accounts)
    body = {
        "agent_id": agent,
        "to": "(0532) 000 00 00",
        "text": "Deneme.",
        "post_playback_seconds": 0,
    }
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda _: service.submit(session, scope, body, key), range(2)))
    assert rows[0] == rows[1]
    detail = service.history(session, scope, rows[0]["id"])
    assert detail["message"] == body["text"]
    assert detail["destination"] == "+905320000000"
    assert detail["ring_timeout_seconds"] == 30 and detail["post_playback_seconds"] == 0
    [item] = service.history(session, scope)["calls"]
    assert item["destination"] == "***0000" and "message" not in item
    with pytest.raises(AuthError, match="operation_key_conflict"):
        service.submit(session, scope, body | {"text": "Başka."}, key)
    assert service.agents(session, scope)["agents"][0]["caller"] == numbers.DID


def test_token_permissions_and_workspace_isolation(accounts, line):
    session, scope, agent = line

    def token(perm):
        value = PersonalTokens(accounts).create(
            session,
            scope,
            {
                "name": "Outbound",
                "permissions": [perm],
                "expires_in_days": 7,
                "current_password": PASSWORD,
            },
        )
        return {"Authorization": "Bearer " + value["token"], "Idempotency-Key": str(uuid.uuid4())}

    submit, read = token("outbound:submit"), token("outbound:read")
    path = f"/v1/workspaces/{scope}/outbound-calls"
    body = {"agent_id": agent, "to": "05320000000", "text": "Deneme"}
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        assert client.post(path, headers=read, json=body).status_code == 403
        first = client.post(path, headers=submit, json=body)
        assert first.status_code == 202
        assert client.post(path, headers=submit, json=body).json() == first.json()
        assert client.get(path, headers=submit).status_code == 403
        assert client.get(path + "/" + first.json()["id"], headers=read).status_code == 200
        assert (
            client.get(path.replace(str(scope), str(uuid.uuid4())), headers=read).status_code == 404
        )
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM outbound_calls").fetchone()[0] == 1


@pytest.mark.parametrize(
    "value", ["112", "+19005550100", "08500000000", "09000000000", "4441234", "sip:abc", None]
)
def test_non_geographic_or_international_target_rejected(value):
    with pytest.raises(AuthError):
        destination(value)


def test_queue_recovers_without_redial_and_expires_content(accounts, line, tmp_path, monkeypatch):
    import psycopg
    from pathlib import Path
    from alojan.outbound_worker import Worker

    token, scope, agent = line
    service = OutboundCalls(accounts)
    with psycopg.connect(accounts.dsn, autocommit=True) as conn:
        worker = Worker(conn, tmp_path, numbers.NODE, "unused")
        monkeypatch.setattr(
            "alojan.outbound_worker.synthesize",
            lambda job, path, endpoint: Path(path).write_bytes(b"synthetic"),
        )
        operation = str(uuid.uuid4())
        body = {"agent_id": agent, "to": "02120000000", "text": "Deneme"}
        job = service.submit(token, scope, body, operation)
        assert worker.step()
        key = uuid.UUID(job["id"]).hex
        (tmp_path / "pending").rename(tmp_path / "running")
        (tmp_path / (key + ".status")).write_text("answered")
        (tmp_path / (key + ".answered")).touch()
        assert not worker.step()
        assert service.history(token, scope, job["id"])["answered_at"]
        (tmp_path / (key + ".status")).write_text("uncertain")
        (tmp_path / "running").unlink()
        worker.step()
        assert service.history(token, scope, job["id"])["status"] == "uncertain"
        assert not (tmp_path / "pending").exists()
        conn.execute("UPDATE outbound_calls SET ended_at=now()-interval '91 days'")
        worker.expire()
        assert service.history(token, scope)["calls"] == []
        assert conn.execute("SELECT count(*) FROM outbound_calls").fetchone()[0] == 0
        assert service.submit(token, scope, body, operation) == job
        assert not worker.step()


def test_real_deployment_roles_can_submit_and_consume(
    accounts, line, dedicated, tmp_path, monkeypatch
):
    import psycopg
    from alojan.auth import Accounts
    from alojan.outbound_worker import Worker

    session, scope, agent = line
    service = OutboundCalls(Accounts(dedicated("management")))
    job = service.submit(
        session,
        scope,
        {"agent_id": agent, "to": "05320000000", "text": "Deneme."},
        str(uuid.uuid4()),
    )

    def fail(*args):
        raise ValueError("synthetic failure")

    monkeypatch.setattr("alojan.outbound_worker.synthesize", fail)
    with psycopg.connect(dedicated("outbound"), autocommit=True) as conn:
        worker = Worker(conn, tmp_path, numbers.NODE, "unused")
        worker.expire()
        assert worker.step()
    assert service.history(session, scope, job["id"])["failure_code"] == "synthesis_failed"
    assert not (tmp_path / "pending").exists()
