"""Real managed process regressions; isolated PostgreSQL and synthetic speech only."""

import asyncio
import json

import grpc
import psycopg
import pytest
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import Accounts, connection, csrf_token
from alojan.connections import Connections
from alojan.numbers import Numbers
from alojan.profiles import Profiles
from alojan.releases import Releases
from alojan_agent.readiness import ReadinessRepository
from alojan_contracts.secrets import SecretBox
from test_agent_drafts import content
from test_agent_releases import prepare_assets
from test_call_initialization import setup, lease
from test_native_auth import ORIGIN
from voice.v1 import voice_pb2_grpc as rpc
import test_managed_startup as launch
import test_number_routing as routing

accounts, database = launch.accounts, launch.database
author, published, dedicated = launch.author, launch.published, launch.dedicated


async def ready(accounts, release):
    async with asyncio.timeout(10):
        while True:
            with connection(accounts.dsn) as c:
                row = c.execute(
                    "SELECT ready FROM release_readiness WHERE release_id=%s AND valid_until>now()",
                    (release,),
                ).fetchone()
            if row == (True,):
                return
            await asyncio.sleep(0.1)


def test_publication_activates_without_restart_and_preserves_old_call(
    accounts, published, tmp_path, dedicated
):
    token, scope, agent, original = published
    number = routing.verified(accounts, token, scope)

    async def run():
        async with launch.deployment(published, tmp_path, dedicated) as (path, env, data, _, __):
            async with (
                launch.process(path, env) as child,
                grpc.aio.insecure_channel(f"127.0.0.1:{data['agent_port']}") as channel,
            ):
                await launch.started(child, channel)
                Numbers(accounts, routing.NODE).bind(token, scope, number, original, 2)
                control, stub = rpc.GenerationControlStub(channel), rpc.AgentStub(channel)
                headers = await lease(control, "managed-before-publication")
                old = await stub.InitializeCall(
                    setup("managed-before-publication"), metadata=headers, timeout=2
                )
                assert old.ready_for_answer
                draft = Profiles(accounts).get(token, scope, agent)
                Profiles(accounts).update(
                    token,
                    scope,
                    agent,
                    draft["content"] | {"instructions": "Updated approved instructions."},
                    draft["version"],
                )
                prepared = Releases(accounts).prepare(token, scope, agent, draft["version"] + 1)
                app = create_app(
                    Accounts(dedicated("management")),
                    ORIGIN,
                    voice_node_id=routing.NODE,
                )
                with TestClient(app, base_url=ORIGIN) as client:
                    client.cookies.set(COOKIE, token)
                    response = client.post(
                        f"/v1/workspaces/{scope}/agents/{agent}/publish",
                        headers={
                            "Origin": ORIGIN,
                            "X-CSRF-Token": csrf_token(token),
                            "If-Match": '"1"',
                        },
                        json={"preparation_id": prepared["id"]},
                    )
                assert response.status_code == 201, response.text
                release = response.json()["id"]
                await ready(accounts, release)
                Numbers(accounts, routing.NODE).bind(token, scope, number, release, 3)
                new_headers = await lease(control, "managed-after-publication")
                new = await stub.InitializeCall(
                    setup("managed-after-publication"), metadata=new_headers, timeout=2
                )
                assert new.ready_for_answer and new.release_id == release
                assert old.release_id == original
                assert child.returncode is None
                with connection(accounts.dsn) as c:
                    assert c.execute(
                        "SELECT release_id::text FROM call_route_snapshots ORDER BY created_at"
                    ).fetchall() == [(original,), (release,)]

    asyncio.run(run())


def test_revoked_unbound_agent_does_not_block_healthy_restart(
    accounts, published, tmp_path, dedicated
):
    token, scope, _, original = published
    reference = Connections(accounts, SecretBox((tmp_path / "provider.key").read_bytes())).create(
        token,
        scope,
        {"provider": "openrouter", "label": "Other agent", "api_key": "unused-secondary-test-key"},
    )["id"]
    other = Profiles(accounts).create(
        token, scope, content("Other Assistant") | {"model_connection": reference}
    )["id"]
    prep, _, __ = prepare_assets(accounts, (token, scope, other), tmp_path)
    second = Releases(accounts).publish(token, scope, other, prep["id"], 0)["id"]
    number = routing.verified(accounts, token, scope)

    async def run():
        async with launch.deployment(published, tmp_path, dedicated) as (path, env, data, _, __):
            data["targets"].append(dict(scope_id=scope, release_id=second))
            path.write_text(json.dumps(data))
            async with (
                launch.process(path, env) as child,
                grpc.aio.insecure_channel(f"127.0.0.1:{data['agent_port']}") as channel,
            ):
                await launch.started(child, channel)
                Numbers(accounts, routing.NODE).bind(token, scope, number, original, 2)
            Connections(accounts).revoke(token, scope, reference)
            async with (
                launch.process(path, env) as child,
                grpc.aio.insecure_channel(f"127.0.0.1:{data['agent_port']}") as channel,
            ):
                await launch.started(child, channel)
                control, stub = rpc.GenerationControlStub(channel), rpc.AgentStub(channel)
                headers = await lease(control, "managed-healthy-after-restart")
                reply = await stub.InitializeCall(
                    setup("managed-healthy-after-restart"), metadata=headers, timeout=2
                )
                assert reply.ready_for_answer and reply.release_id == original
                with connection(accounts.dsn) as c:
                    assert c.execute(
                        "SELECT ready FROM release_readiness WHERE release_id=%s", (second,)
                    ).fetchone() == (False,)

    asyncio.run(run())


def test_empty_node_discovers_publications_and_respects_node_assignment(
    accounts, published, tmp_path, dedicated
):
    token, scope, agent, original = published
    with connection(accounts.dsn) as c:
        c.execute("UPDATE agent_publications SET node_id='other-node'")
    repo = ReadinessRepository(dedicated("readiness"), routing.NODE)
    assert asyncio.run(repo.desired(16)) == []
    with connection(dedicated("readiness")) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("UPDATE agent_publications SET node_id=%s", (routing.NODE,))

    async def run():
        async with launch.deployment(published, tmp_path, dedicated) as (path, env, data, _, __):
            data["targets"] = []
            path.write_text(json.dumps(data))
            async with (
                launch.process(path, env) as child,
                grpc.aio.insecure_channel(f"127.0.0.1:{data['agent_port']}") as channel,
            ):
                await launch.started(child, channel)
                assert await repo.desired(16) == []
                preparation = Releases(accounts).prepare(token, scope, agent, 1)
                release = Releases(accounts, routing.NODE).publish(
                    token, scope, agent, preparation["id"], 1
                )["id"]
                await ready(accounts, release)
                assert await repo.desired(16) == [(scope, release)]
                with connection(accounts.dsn) as c:
                    assert c.execute(
                        "SELECT count(*) FROM release_readiness WHERE release_id=%s", (original,)
                    ).fetchone() == (0,)

    asyncio.run(run())


def test_slow_activation_keeps_warm_release_ready_and_retires_after_last_call(
    accounts, published, tmp_path, dedicated
):
    from test_release_readiness import running_node

    token, scope, agent, original = published
    number = routing.verified(accounts, token, scope)
    preparation = Releases(accounts).prepare(token, scope, agent, 1)
    newer = Releases(accounts, routing.NODE).publish(token, scope, agent, preparation["id"], 1)[
        "id"
    ]

    async def run():
        async with running_node(accounts, tmp_path, dedicated) as node:
            await node.coordinator.activate(scope, original)
            Numbers(accounts, routing.NODE).bind(token, scope, number, original, 2)
            headers = await lease(node.control, "managed-retained")
            old = await node.stub.InitializeCall(
                setup("managed-retained"), metadata=headers, timeout=2
            )
            assert old.ready_for_answer
            route = node.service.routes["managed-retained"]
            preload = node.cache.preload
            entered, release_load = asyncio.Event(), asyncio.Event()

            async def slow(*args):
                entered.set()
                await release_load.wait()
                return await preload(*args)

            node.cache.preload = slow
            cold = asyncio.create_task(node.coordinator.activate(scope, newer))
            await entered.wait()
            try:
                for _ in range(12):
                    await asyncio.sleep(0.2)
                    await node.coordinator.refresh()
                    assert node.coordinator.accepts(route)
            finally:
                release_load.set()
                await cold
                node.cache.preload = preload
            Numbers(accounts, routing.NODE).bind(token, scope, number, newer, 3)
            await node.coordinator.discover()
            assert any(key[1] == original for key in node.coordinator.targets)
            from voice.v1 import voice_pb2 as pb

            await node.control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-retained", lease=headers[0][1]), timeout=2
            )
            await node.coordinator.discover()
            assert {key[1] for key in node.coordinator.targets} == {newer}
            with connection(accounts.dsn) as c:
                assert c.execute(
                    "SELECT ready FROM release_readiness WHERE release_id=%s", (original,)
                ).fetchone() == (False,)

    asyncio.run(run())
