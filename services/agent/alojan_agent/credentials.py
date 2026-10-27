"""Preloaded workspace-bound provider clients. No credential IO in model_for/turns."""

import asyncio
import time
import uuid

import psycopg
from openai import AsyncOpenAI


class ProviderClients:
    def __init__(self, dsn, secrets):
        self.dsn, self.secrets = dsn, secrets
        self.clients = {}
        self.expires = {}
        self.closed = False

    @staticmethod
    def key(runtime):
        if not runtime or not runtime.scope_id or not runtime.model_connection:
            raise ValueError("scoped provider connection required")
        return tuple(str(uuid.UUID(v)) for v in (runtime.scope_id, runtime.model_connection))

    async def prepare(self, runtime):
        key = self.key(runtime)
        try:
            if self.closed or (key not in self.clients and len(self.clients) >= 16):
                raise ValueError("provider client unavailable")
            start = time.monotonic()
            async with asyncio.timeout(1):
                async with await psycopg.AsyncConnection.connect(self.dsn, connect_timeout=1) as c:
                    await c.execute("SET LOCAL statement_timeout=500")
                    await c.execute("SELECT set_config('alojan.scope_id',%s,true)", (key[0],))
                    row = await (
                        await c.execute(
                            """SELECT p.ciphertext FROM provider_connections p
                        JOIN recipient_scopes s ON s.id=p.scope_id AND s.enabled
                        WHERE p.scope_id=%s AND p.id=%s AND p.enabled AND p.provider='openrouter'""",
                            key,
                        )
                    ).fetchone()
                    if not row:
                        raise ValueError("provider connection unavailable")
            # Identity-bound authenticated ciphertext cannot be transplanted across connections.
            secret = self.secrets.open(*key, bytes(row[0]))
            if self.closed:
                raise ValueError("provider client closed")
            if key not in self.clients:
                self.clients[key] = AsyncOpenAI(
                    api_key=secret,
                    base_url=runtime.engine.base_url,
                    timeout=runtime.engine.llm_timeout_seconds,
                    max_retries=runtime.engine.llm_max_retries,
                )
            elif self.clients[key].api_key != secret:
                raise ValueError("provider identity changed")
            self.expires[key] = start + 2
        except BaseException:
            self.expires.pop(key, None)
            raise

    def get(self, runtime):
        key = self.key(runtime)
        if self.closed or self.expires.get(key, 0) <= time.monotonic():
            raise ValueError("provider credential freshness expired")
        client = self.clients[key]
        if client.is_closed():
            raise ValueError("provider client closed")
        return client

    async def retain(self, runtimes):
        keep = {self.key(runtime) for runtime in runtimes}
        removed = []
        for key in list(self.clients):
            if key not in keep:
                self.expires.pop(key, None)
                removed.append(self.clients.pop(key))
        await asyncio.gather(*(client.close() for client in removed))

    async def close(self):
        self.closed = True
        self.expires.clear()
        await asyncio.gather(*(client.close() for client in self.clients.values()))
        self.clients.clear()
