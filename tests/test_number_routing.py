import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from starlette.testclient import TestClient

import test_agent_releases
import test_native_auth
from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.number_verification import decide
from alojan.numbers import Numbers
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan.roles import (
    grant_call_records,
    grant_management,
    grant_routing,
    grant_readiness,
    grant_credentials,
    grant_actions,
)
from alojan_agent.routing import CallRouter, RoutingError
from alojan_agent.store import call_uuid
from test_agent_drafts import content
from test_agent_releases import prepare_assets
from test_native_auth import ORIGIN, PASSWORD, register

accounts = test_native_auth.accounts
database = test_native_auth.database
author = test_agent_releases.author
NODE = "synthetic-node"
DID = "+90850" + "1234567"
OTHER_DID = "+90850" + "7654321"


def ready(accounts, scope, release, node=NODE):
    with connection(accounts.dsn) as conn:
        conn.execute(
            """INSERT INTO release_readiness(scope_id,profile_id,release_id,node_id,manifest_digest,ready,valid_until)
            SELECT scope_id,profile_id,id,%s,manifest_digest,true,now()+interval '25 seconds'
            FROM agent_releases WHERE scope_id=%s AND id=%s
            ON CONFLICT (scope_id,release_id,node_id) DO UPDATE SET valid_until=excluded.valid_until,acknowledged_at=excluded.acknowledged_at,ready=true""",
            (node, scope, release),
        )


@pytest.fixture
def published(accounts, author, tmp_path):
    token, scope, agent = author
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    release = Releases(accounts).publish(token, scope, agent, preparation["id"], 0)["id"]
    return token, scope, agent, release


def verified(accounts, token, scope, did=DID):
    number = Numbers(accounts).create(token, scope, did)["id"]
    decide(
        accounts.dsn,
        scope,
        number,
        1,
        "synthetic-operator",
        ownership="test-ownership",
        routing="test-routing",
    )
    return number


def bound(accounts, published):
    token, scope, _, release = published
    number = verified(accounts, token, scope)
    ready(accounts, scope, release)
    Numbers(accounts, NODE).bind(token, scope, number, release, 2)
    return number


def initialize(accounts, identity="test-call", did=DID, node=NODE, source="request_uri"):
    return asyncio.run(CallRouter(accounts.dsn, node).initialize(identity, did, source))


def test_pending_guesses_do_not_reserve_ownership_and_exact_did_is_required(accounts):
    one, two = register(accounts), register(accounts, "other.owner")
    scopes = [accounts.session(t)["workspaces"][0]["id"] for t in (one, two)]
    numbers = Numbers(accounts)
    first = numbers.create(one, scopes[0], DID)
    second = numbers.create(two, scopes[1], DID)
    assert first["status"] == "pending" and not first["enabled"]
    with pytest.raises(AuthError, match="number_already_registered"):
        numbers.create(one, scopes[0], DID)
    for value in (
        "0" + DID[3:],
        "sip:" + DID + "@example.test",
        " " + DID,
        DID + "\n",
        OTHER_DID[:-1],
        1,
    ):
        with pytest.raises(AuthError, match="invalid_number"):
            numbers.create(one, scopes[0], value)
    decide(
        accounts.dsn,
        scopes[1],
        second["id"],
        1,
        "operator",
        ownership="proof-owner",
        routing="proof-route",
    )
    with pytest.raises(AuthError, match="number_ownership_conflict"):
        decide(
            accounts.dsn,
            scopes[0],
            first["id"],
            1,
            "operator",
            ownership="proof-owner",
            routing="proof-route",
        )
    with pytest.raises(AuthError, match="not_found"):
        numbers.list(two, scopes[0])
    assert numbers.list(one, scopes[0])[0]["status"] == "pending"


def test_binding_requires_verified_number_ready_node_and_exact_release_scope(accounts, published):
    token, scope, _, release = published
    number = Numbers(accounts).create(token, scope, DID)["id"]
    with pytest.raises(AuthError, match="number_not_verified"):
        Numbers(accounts, NODE).bind(token, scope, number, release, 1)
    decide(accounts.dsn, scope, number, 1, "operator", ownership="ownership", routing="route")
    with pytest.raises(AuthError, match="voice_node_not_configured"):
        Numbers(accounts).bind(token, scope, number, release, 2)
    with pytest.raises(AuthError, match="release_not_ready_on_node"):
        Numbers(accounts, NODE).bind(token, scope, number, release, 2)
    ready(accounts, scope, release, "other-node")
    with pytest.raises(AuthError, match="release_not_ready_on_node"):
        Numbers(accounts, NODE).bind(token, scope, number, release, 2)
    ready(accounts, scope, release)
    with pytest.raises(AuthError, match="stale_version"):
        Numbers(accounts, NODE).bind(token, scope, number, release, 1)
    binding = Numbers(accounts, NODE).bind(token, scope, number, release, 2)
    assert binding["enabled"] and binding["version"] == 3
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE number_bindings SET node_id='other'")


def test_call_snapshot_survives_rebinding_and_draft_changes(accounts, published, tmp_path):
    token, scope, agent, release = published
    number = bound(accounts, published)
    first = initialize(accounts)
    assert first.release_id == release
    with pytest.raises(FrozenInstanceError):
        first.release_id = "forged"
    Profiles(accounts).update(token, scope, agent, content("Another Assistant"), 1)
    prepared, _, _ = prepare_assets(accounts, (token, scope, agent), tmp_path, version=2)
    changed = Releases(accounts).publish(token, scope, agent, prepared["id"], 1)["id"]
    # Publishing alone does not silently switch a number's chosen release.
    assert initialize(accounts, "before-bind").release_id == release
    ready(accounts, scope, changed)
    Numbers(accounts, NODE).bind(token, scope, number, changed, 3)
    assert initialize(accounts) == first
    second = initialize(accounts, "after-bind")
    assert second.release_id == changed and second.binding_id != first.binding_id
    assert json.loads(second.manifest_json)["content"]["agent_name"] == "Another Assistant"
    assert json.loads(first.manifest_json)["content"]["agent_name"] != "Another Assistant"
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM call_route_snapshots").fetchone()[0] == 3
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE call_route_snapshots SET called_source='to'")


def test_unknown_disabled_unready_and_wrong_node_fail_without_fallback(accounts, published):
    token, scope, _, release = published
    number = bound(accounts, published)
    first = initialize(accounts)
    for did, node, error in (
        (OTHER_DID, NODE, "number_not_routed"),
        (DID, "other", "release_unavailable_on_node"),
    ):
        with pytest.raises(RoutingError, match=error):
            initialize(accounts, "rejected", did=did, node=node)
    with connection(accounts.dsn) as conn:
        conn.execute(
            "UPDATE release_readiness SET acknowledged_at=now()-interval '30 seconds',valid_until=now()-interval '1 second'"
        )
    with pytest.raises(RoutingError, match="release_unavailable_on_node"):
        initialize(accounts, "expired")
    assert initialize(accounts) == first
    ready(accounts, scope, release)
    Numbers(accounts).deactivate(token, scope, number, 3)
    assert initialize(accounts) == first
    with pytest.raises(RoutingError, match="number_not_routed"):
        initialize(accounts, "disabled")
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 1


def test_initialization_idempotency_conflict_and_cancellation(accounts, published):
    bound(accounts, published)
    first = initialize(accounts)
    with pytest.raises(RoutingError, match="conflicting_initialization"):
        initialize(accounts, source="to")
    with pytest.raises(RoutingError, match="conflicting_initialization"):
        initialize(accounts, did=OTHER_DID)
    assert initialize(accounts) == first
    router = CallRouter(accounts.dsn, NODE)
    assert asyncio.run(router.cancel_unanswered("test-call"))
    assert not asyncio.run(router.cancel_unanswered("test-call"))
    with pytest.raises(RoutingError, match="call_already_ended"):
        initialize(accounts)
    assert asyncio.run(router.cancel_unanswered("cancel-first"))
    with pytest.raises(RoutingError, match="call_already_ended"):
        initialize(accounts, "cancel-first")
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM summary_jobs").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0


def test_call_admission_and_bind_are_atomic_between_distinct_sessions(accounts, published):
    token, scope, _, release = published
    number = bound(accounts, published)
    token2 = accounts.login("test.owner", PASSWORD, peer="127.0.0.1")

    def bind(session):
        try:
            return Numbers(accounts, NODE).bind(session, scope, number, release, 3)["version"]
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(map(str, pool.map(bind, (token, token2)))) == ["4", "stale_version"]

    async def concurrent():
        router = CallRouter(accounts.dsn, NODE)
        return await asyncio.gather(
            *(router.initialize("same-call", DID, "request_uri") for _ in range(2))
        )

    one, two = asyncio.run(concurrent())
    assert one == two
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM call_route_snapshots").fetchone()[0] == 1


def test_ownership_transfer_requires_drained_calls_preserves_history(accounts, published):
    token, scope, _, _ = published
    number = bound(accounts, published)
    old = initialize(accounts)
    second_token = register(accounts, "other.owner")
    second_scope = accounts.session(second_token)["workspaces"][0]["id"]
    claim = Numbers(accounts).create(second_token, second_scope, DID)["id"]
    decide(accounts.dsn, scope, number, 3, "operator", reason="old-owner-release")
    with pytest.raises(AuthError, match="number_calls_not_drained"):
        decide(
            accounts.dsn,
            second_scope,
            claim,
            1,
            "operator",
            ownership="new-proof",
            routing="new-route",
        )
    assert initialize(accounts) == old
    asyncio.run(CallRouter(accounts.dsn, NODE).cancel_unanswered("test-call"))
    decide(
        accounts.dsn, second_scope, claim, 1, "operator", ownership="new-proof", routing="new-route"
    )
    assert Numbers(accounts).list(second_token, second_scope)[0]["enabled"] is False
    with connection(accounts.dsn) as conn:
        assert str(conn.execute("SELECT scope_id FROM call_route_snapshots").fetchone()[0]) == scope
        assert conn.execute("SELECT count(*) FROM number_verifications").fetchone()[0] == 3


def test_number_http_checks_and_viewer_rejection(accounts, published):
    token, scope, _, release = published
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token(token)}
    with TestClient(create_app(accounts, ORIGIN, voice_node_id=NODE), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, token)
        url = f"/v1/workspaces/{scope}/numbers"
        response = client.post(url, json={"number": DID, "status": "verified"}, headers=headers)
        assert response.status_code == 400
        response = client.post(url, json={"number": DID}, headers=headers)
        assert response.status_code == 201 and response.headers["etag"] == '"1"'
        number = response.json()["id"]
        assert (
            client.put(
                f"{url}/{number}/binding", json={"release_id": release}, headers=headers
            ).status_code
            == 428
        )
        assert (
            client.put(
                f"{url}/{number}/binding",
                json={"release_id": release},
                headers={**headers, "If-Match": '"1"'},
            ).json()["error"]
            == "number_not_verified"
        )
        assert client.get(url).json()["numbers"][0]["number"] == DID
        with connection(accounts.dsn) as conn:
            conn.execute("UPDATE workspace_memberships SET role='viewer'")
        assert client.get(url).status_code == 200
        assert client.post(url, json={"number": OTHER_DID}, headers=headers).status_code == 403
        assert (
            client.post(
                f"{url}/{number}/deactivate", json={}, headers={**headers, "If-Match": '"1"'}
            ).status_code
            == 403
        )


@pytest.fixture
def dedicated(accounts):
    roles = []

    def create(purpose):
        name = "test_routing_" + uuid.uuid4().hex
        role = psycopg.sql.Identifier(name)
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
        roles.append((name, role))
        if purpose == "mcp-execution":
            from alojan.mcp_execution_roles import grant_execution

            grant_execution(accounts.dsn, name)
        elif purpose == "mcp":
            from alojan.mcp_roles import grant_discovery

            grant_discovery(accounts.dsn, name)
        elif purpose == "latency":
            from alojan.latency import grant_ingest

            grant_ingest(accounts.dsn, name, NODE)
        elif purpose == "actions":
            grant_actions(accounts.dsn, name)
        elif purpose == "credentials":
            grant_credentials(accounts.dsn, name)
        elif purpose == "readiness":
            grant_readiness(accounts.dsn, name, NODE)
        elif purpose in {"records", "summaries"}:
            grant_call_records(accounts.dsn, name, summaries=purpose == "summaries")
        else:
            (grant_management if purpose == "management" else grant_routing)(accounts.dsn, name)
        options = conninfo_to_dict(accounts.dsn)["options"] + f" -c role={name}"
        return make_conninfo(accounts.dsn, options=options)

    yield create
    with connection(accounts.dsn) as conn:
        for name, role in roles:
            # Dedicated policies depend on the role; remove this schema's generated policies first.
            policies = conn.execute(
                """SELECT tablename,policyname FROM pg_policies
                WHERE schemaname=current_schema() AND %s=ANY(roles)""",
                (name,),
            ).fetchall()
            for table, policy in policies:
                conn.execute(
                    psycopg.sql.SQL("DROP POLICY {} ON {}").format(
                        psycopg.sql.Identifier(policy), psycopg.sql.Identifier(table)
                    )
                )
            conn.execute(psycopg.sql.SQL("DROP OWNED BY {}").format(role))
            conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(role))


def test_restricted_management_can_bind_but_cannot_verify_or_fake_readiness(
    accounts, published, dedicated
):
    token, scope, _, release = published
    dsn = dedicated("management")
    limited = Accounts(dsn)
    number = Numbers(limited).create(token, scope, DID)["id"]
    with pytest.raises(AuthError, match="operator_authority_required"):
        decide(dsn, scope, number, 1, "not-operator", ownership="fake", routing="fake")
    decide(accounts.dsn, scope, number, 1, "operator", ownership="proof", routing="route")
    ready(accounts, scope, release)
    assert Numbers(limited, NODE).bind(token, scope, number, release, 2)["enabled"]
    assert not Numbers(limited).deactivate(token, scope, number, 3)["enabled"]
    for query in (
        "UPDATE phone_numbers SET status='verified'",
        "UPDATE release_readiness SET ready=true",
        "UPDATE release_readiness SET valid_until=now()+interval '1 day'",
        "SELECT * FROM call_route_snapshots",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection(dsn) as conn:
                conn.execute(query)


def test_restricted_router_discovers_scope_without_bypassing_rls(accounts, published, dedicated):
    token, scope, _, _ = published
    bound(accounts, published)
    dsn = dedicated("routing")
    router = CallRouter(dsn, NODE)
    first = asyncio.run(router.initialize("restricted-call", DID, "request_uri"))
    assert first.scope_id == scope
    assert asyncio.run(router.initialize("restricted-call", DID, "request_uri")) == first
    assert asyncio.run(router.cancel_unanswered("restricted-call"))
    with connection(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM agent_releases").fetchone()[0] == 0
        assert not conn.execute(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0]
    for query in (
        "UPDATE phone_numbers SET enabled=true",
        "SELECT * FROM users",
        "INSERT INTO number_bindings SELECT * FROM number_bindings",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection(dsn) as conn:
                conn.execute(query)


def test_locked_route_fails_boundedly_and_cancelled_transaction_leaves_no_snapshot(
    accounts, published
):
    number = bound(accounts, published)
    with connection(accounts.dsn) as blocker:
        blocker.execute("SELECT id FROM phone_numbers WHERE id=%s FOR UPDATE", (number,))
        with pytest.raises(RoutingError, match="routing_temporarily_unavailable"):
            initialize(accounts, "locked-call")

        async def cancelled():
            task = asyncio.create_task(
                CallRouter(accounts.dsn, NODE).initialize("cancelled-task", DID, "request_uri")
            )
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(cancelled())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM call_route_snapshots").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM calls").fetchone()[0] == 0


def test_legacy_unscoped_call_is_not_claimed(accounts, published):
    bound(accounts, published)
    with connection(accounts.dsn) as conn:
        conn.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status) VALUES (%s,'legacy','inbound','active')",
            (call_uuid("legacy"),),
        )
    with pytest.raises(RoutingError, match="unscoped_call_conflict"):
        initialize(accounts, "legacy")


def test_cross_workspace_release_binding_is_rejected_in_api_and_database(accounts, published):
    token, scope, agent, release = published
    second = register(accounts, "second.owner")
    other_scope = accounts.session(second)["workspaces"][0]["id"]
    other_number = verified(accounts, second, other_scope, OTHER_DID)
    ready(accounts, scope, release)
    with pytest.raises(AuthError, match="not_found"):
        Numbers(accounts, NODE).bind(second, other_scope, other_number, release, 2)
    with connection(accounts.dsn) as conn:
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute(
                """INSERT INTO number_bindings(id,scope_id,number_id,revision,profile_id,release_id,node_id,created_by)
                VALUES (%s,%s,%s,3,%s,%s,%s,%s)""",
                (uuid.uuid4(), other_scope, other_number, agent, release, NODE, user),
            )


def test_readiness_cannot_claim_unbounded_freshness_or_wrong_digest(accounts, published):
    _, scope, _, release = published
    ready(accounts, scope, release)
    for statement, error in (
        (
            "UPDATE release_readiness SET valid_until=now()+interval '1 day'",
            psycopg.errors.CheckViolation,
        ),
        (
            "UPDATE release_readiness SET manifest_digest=repeat('0',64)",
            psycopg.errors.ForeignKeyViolation,
        ),
    ):
        with pytest.raises(error):
            with connection(accounts.dsn) as conn:
                conn.execute(statement)


def test_revoked_model_only_blocks_new_admission_and_caller_hint_cannot_select_agent(
    accounts, published
):
    bound(accounts, published)
    first = asyncio.run(
        CallRouter(accounts.dsn, NODE).initialize("caller-hint", DID, "request_uri", OTHER_DID)
    )
    assert first.release_id == published[3]
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE model_catalog_status SET enabled=false")
    with pytest.raises(RoutingError, match="model_not_qualified"):
        initialize(accounts, "revoked")
    assert (
        asyncio.run(
            CallRouter(accounts.dsn, NODE).initialize("caller-hint", DID, "request_uri", OTHER_DID)
        )
        == first
    )


def test_atomic_rebind_during_admission_never_mixes_fields(accounts, published, tmp_path):
    token, scope, agent, release = published
    number = bound(accounts, published)
    old_binding = initialize(accounts, "old").binding_id
    Profiles(accounts).update(token, scope, agent, content("Changed"), 1)
    prepared, _, _ = prepare_assets(accounts, (token, scope, agent), tmp_path, version=2)
    new_release = Releases(accounts).publish(token, scope, agent, prepared["id"], 1)["id"]
    ready(accounts, scope, new_release)
    with ThreadPoolExecutor(max_workers=2) as pool:
        admission = pool.submit(initialize, accounts, "racing")
        publication = pool.submit(
            Numbers(accounts, NODE).bind, token, scope, number, new_release, 3
        )
        result, binding = admission.result(), publication.result()
    assert (result.binding_id, result.release_id) in {
        (old_binding, release),
        (binding["binding_id"], new_release),
    }
    assert initialize(accounts, "racing") == result
