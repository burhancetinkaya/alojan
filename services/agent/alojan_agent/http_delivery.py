"""Fixed-destination HTTP writes; DNS pinned, bounded, no ambiguous replay."""

import asyncio
import socket
from urllib.parse import urlsplit

import httpx2 as httpx
from alojan_contracts.mcp import endpoint, public_address
from .telegram_delivery import Result


class Webhook:
    async def resolve(self, url):
        host = urlsplit(endpoint(url)).hostname
        async with asyncio.timeout(3):
            answers = await asyncio.get_running_loop().getaddrinfo(
                host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
            )
        if not answers:
            raise ValueError("HTTP destination unavailable")
        addresses = [public_address(answer[4][0]) for answer in answers]
        return addresses[0]

    async def send(self, address, token, request, key):
        address = public_address(address)
        url = httpx.URL(request["url"])
        host = url.host
        headers = request["headers"] | {
            "Host": host,
            "Accept-Encoding": "identity",
            "Content-Type": "application/json",
            "Idempotency-Key": str(key),
        }
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        try:
            async with asyncio.timeout(12):
                async with httpx.AsyncClient(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(5, connect=3),
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
                ) as client:
                    async with client.stream(
                        request["method"],
                        url.copy_with(host=address),
                        headers=headers,
                        extensions={"sni_hostname": host},
                        content=request["body"].encode(),
                    ) as reply:
                        # Acceptance is the HTTP status, never an untrusted response instruction/body.
                        if 200 <= reply.status_code <= 299:
                            return Result("sent", http_status=reply.status_code)
                        if 300 <= reply.status_code < 500:
                            return Result("failed", "rejected")
                        return Result("delivery_unknown", "send_uncertain")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Result("pending", "connect_failed")
        except Exception:
            return Result("delivery_unknown", "send_uncertain")
