"""Discovery-only MCP transport with fixed approved endpoint and bounded egress."""

import asyncio
import json

import httpx2 as httpx
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from jsonschema import Draft202012Validator

from alojan_contracts.mcp import manifest, SUPPORTED_PROTOCOLS
from alojan_contracts.secrets import SecretBox
from alojan_contracts.mcp_http import BoundedStream, PinnedTransport  # noqa: F401


async def discover(url, token=None):
    if token is not None:
        SecretBox.validate(token, purpose="mcp-oauth-access")
    async with asyncio.timeout(15):
        async with httpx.AsyncClient(
            transport=PinnedTransport(url),
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(5, connect=3),
            headers={"Authorization": f"Bearer {token}"} if token else {},
        ) as client:
            async with streamable_http_client(
                url, http_client=client, max_sse_event_size=65536
            ) as streams:
                async with ClientSession(*streams, read_timeout_seconds=5) as session:
                    initialized = await session.initialize()
                    if (
                        initialized.protocol_version not in SUPPORTED_PROTOCOLS
                        or initialized.capabilities.tools is None
                    ):
                        raise ValueError("MCP protocol or tools unavailable")
                    tools, seen, cursor = [], set(), None
                    for _ in range(10):
                        page = await session.list_tools(
                            params=types.PaginatedRequestParams(cursor=cursor) if cursor else None
                        )
                        tools.extend(
                            t.model_dump(mode="json", by_alias=True, exclude_none=True)
                            for t in page.tools
                        )
                        snapshot = manifest(tools, protocol=initialized.protocol_version)
                        if token and json.dumps(token)[1:-1] in json.dumps(
                            snapshot, ensure_ascii=False
                        ):
                            raise ValueError("MCP credential echo denied")
                        for item in snapshot["tools"]:
                            Draft202012Validator.check_schema(item["inputSchema"])
                            if "outputSchema" in item:
                                Draft202012Validator.check_schema(item["outputSchema"])
                        cursor = page.next_cursor
                        if cursor is None:
                            return snapshot
                        if len(cursor) > 2048 or cursor in seen:
                            raise ValueError("MCP pagination cycle")
                        seen.add(cursor)
                    raise ValueError("MCP pagination limit")
