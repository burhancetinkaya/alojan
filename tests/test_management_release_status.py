"""Read-only release readiness snapshots never reserve or activate a phone number."""

import uuid

import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection
from alojan.profiles import Profiles
from alojan.releases import Releases
from test_agent_drafts import content
from test_native_auth import ORIGIN, register
import test_number_routing as fixtures

accounts, database, author = fixtures.accounts, fixtures.database, fixtures.author
published, dedicated = fixtures.published, fixtures.dedicated


def test_status_is_scoped_and_observes_only_configured_node(accounts, published, dedicated):
    session, scope, agent, release = published
    store = Releases(Accounts(dedicated("management")), fixtures.NODE)
    status = store.status(session, scope, agent, release)
    assert status["current_publication"] and not status["node_ready"]
    assert status["status"] == "awaiting_node" and status["retry_after_seconds"] == 5
    fixtures.ready(accounts, scope, release, node="other-node")
    assert not store.status(session, scope, agent, release)["node_ready"]
    fixtures.ready(accounts, scope, release)
    status = store.status(session, scope, agent, release)
    assert status["node_ready"] and status["checked_at"] and status["valid_until"]
    assert status["retry_after_seconds"] is None
    assert (
        Releases(accounts).status(session, scope, agent, release)["status"] == "node_not_configured"
    )
    wrong_agent = Profiles(accounts).create(session, scope, content())["id"]
    with pytest.raises(AuthError, match="not_found"):
        store.status(session, scope, wrong_agent, release)
    other = register(accounts, "foreign.release.status")
    with pytest.raises(AuthError, match="not_found"):
        store.status(other, scope, agent, release)
    with TestClient(
        create_app(store.accounts, ORIGIN, voice_node_id=fixtures.NODE), base_url=ORIGIN
    ) as client:
        client.cookies.set(COOKIE, session)
        path = f"/v1/workspaces/{scope}/agents/{agent}/releases/{release}/status"
        response = client.get(path)
        assert response.status_code == 200 and response.json()["node_ready"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get(path + "?node_id=other-node").status_code == 400
        assert client.post(path, json={}).status_code == 405
        assert client.get(path.replace(release, str(uuid.uuid4()))).status_code == 404
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM number_bindings").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["expired", "future", "withdrawn"])
def test_status_does_not_accept_stale_or_future_acknowledgements(accounts, published, change):
    session, scope, agent, release = published
    fixtures.ready(accounts, scope, release)
    with connection(accounts.dsn) as conn:
        if change == "expired":
            conn.execute(
                "UPDATE release_readiness SET acknowledged_at=now()-interval '30 seconds',valid_until=now()-interval '5 seconds'"
            )
        elif change == "future":
            conn.execute(
                "UPDATE release_readiness SET acknowledged_at=now()+interval '1 minute',valid_until=now()+interval '80 seconds'"
            )
        else:
            conn.execute("UPDATE release_readiness SET ready=false")
    status = Releases(accounts, fixtures.NODE).status(session, scope, agent, release)
    assert status["status"] == "not_ready" and status["node_ready"] is False
