"""Bounded, DNS-pinned HTTPS transport shared by MCP tools and OAuth endpoints."""

import asyncio
import socket
from urllib.parse import urlsplit

import httpx2 as httpx

from alojan_contracts.mcp import endpoint, public_address


class BoundedStream(httpx.AsyncByteStream):
    def __init__(self, source):
        self.source = source

    async def __aiter__(self):
        size = 0
        async for chunk in self.source:
            size += len(chunk)
            if size > 262144:
                raise ValueError("MCP response limit")
            yield chunk

    async def aclose(self):
        await self.source.aclose()


class PinnedTransport(httpx.AsyncBaseTransport):
    def __init__(self, url):
        self.url = endpoint(url)
        self.host = urlsplit(url).hostname
        self.transport = httpx.AsyncHTTPTransport(
            retries=0,
            trust_env=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=0),
        )

    async def handle_async_request(self, request):
        if str(request.url) != self.url or request.method not in {"POST", "GET", "DELETE"}:
            raise ValueError("MCP request target denied")
        async with asyncio.timeout(3):
            answers = await asyncio.get_running_loop().getaddrinfo(
                self.host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
            )
        if not answers:
            raise ValueError("MCP DNS unavailable")
        addresses = [public_address(a[4][0]) for a in answers]
        # The socket connects to a vetted literal, while TLS verifies the original hostname.
        headers = dict(request.headers)
        headers["host"] = self.host
        headers["accept-encoding"] = "identity"
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=addresses[0]),
            headers=headers,
            stream=request.stream,
            extensions=request.extensions | {"sni_hostname": self.host},
        )
        response = await self.transport.handle_async_request(pinned)
        if (
            300 <= response.status_code < 400
            or response.headers.get("content-encoding", "identity") != "identity"
        ):
            await response.aclose()
            raise ValueError("MCP redirect or encoding denied")
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=BoundedStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self.transport.aclose()
