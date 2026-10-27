"""Transport pressure and cancellation stay bounded without touching a database."""

from urllib.parse import urlunsplit
import asyncio

import httpx2
import pytest

from alojan_management_mcp import server

ORIGIN = urlunsplit(("https", "mcp.example.test", "", "", ""))
HEADERS = {
    "Authorization": "Bearer alojan_pat_synthetic-never-a-real-token",
    "Accept": "application/json, text/event-stream",
}
BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
IDENTITY = {"id": "synthetic-user", "scope_id": "synthetic-scope", "permissions": []}


def test_overload_rejects_without_waiting_and_cancellation_releases_capacity():
    async def exercise():
        entered = asyncio.Queue()
        release = asyncio.Event()
        active = 0

        async def upstream(request):
            nonlocal active
            assert request.url.path == "/v1/mcp/context"
            active += 1
            entered.put_nowait(True)
            try:
                await release.wait()
                return httpx2.Response(200, json=IDENTITY)
            finally:
                active -= 1

        app = server.create_app(
            "http://management.test", ORIGIN + "/mcp", transport=httpx2.MockTransport(upstream)
        )
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url=ORIGIN, headers=HEADERS
            ) as client:
                tasks = [asyncio.create_task(client.post("/mcp", json=BODY)) for _ in range(4)]
                try:
                    for _ in tasks:
                        await asyncio.wait_for(entered.get(), 2)
                    assert active == 4
                    rejected = await asyncio.wait_for(client.post("/mcp", json=BODY), 1)
                    assert rejected.status_code == 503
                    assert rejected.json() == {"error": "server_busy"}
                    assert rejected.headers["cache-control"] == "no-store"
                    assert entered.empty() and active == 4
                    assert (await client.get("/health/live")).status_code == 200
                    tasks[0].cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await tasks[0]
                    assert active == 3
                    tasks.append(asyncio.create_task(client.post("/mcp", json=BODY)))
                    await asyncio.wait_for(entered.get(), 2)
                    assert active == 4
                    release.set()
                    assert all(r.status_code == 200 for r in await asyncio.gather(*tasks[1:]))
                    assert active == 0
                    assert (await client.post("/mcp", json=BODY)).status_code == 200
                finally:
                    release.set()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(exercise())


def test_deadline_cancels_stalled_upstream_and_releases_capacity(monkeypatch):
    monkeypatch.setattr(server, "REQUEST_TIMEOUT", 0.03)

    async def exercise():
        active = 0

        async def upstream(request):
            nonlocal active
            active += 1
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1

        app = server.create_app(
            "http://management.test", ORIGIN + "/mcp", transport=httpx2.MockTransport(upstream)
        )
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url=ORIGIN, headers=HEADERS
            ) as client:
                for _ in range(6):
                    response = await asyncio.wait_for(client.post("/mcp", json=BODY), 2)
                    assert response.status_code == 504
                    assert response.json() == {"error": "request_timeout"}
                    assert active == 0
                assert (await client.get("/health/live")).status_code == 200

    asyncio.run(exercise())
