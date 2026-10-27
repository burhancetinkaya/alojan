"""Fixed-origin Telegram adapter. No retries of uncertain POSTs, redirects or ambient proxies."""

import asyncio
from dataclasses import dataclass
import ipaddress
import json
import logging
import re
import socket

import httpx2 as httpx

# HTTP request URLs contain the bot credential. This dedicated process never exports HTTP logs.
for name in ("httpx2", "httpcore2"):
    logger = logging.getLogger(name)
    logger.addHandler(logging.NullHandler())
    logger.propagate = False


@dataclass(frozen=True)
class Result:
    status: str
    code: str | None = None
    message_id: int | None = None
    retry_after: int = 0
    http_status: int | None = None


def response(status, data, chat_id):
    unknown = Result("delivery_unknown", "invalid_response")
    if not isinstance(data, dict) or type(data.get("ok")) is not bool:
        return unknown
    if status == 200 and data["ok"]:
        result = data.get("result")
        if isinstance(result, dict) and type(result.get("message_id")) is int:
            chat = result.get("chat")
            if (
                0 < result["message_id"] <= 9223372036854775807
                and isinstance(chat, dict)
                and type(chat.get("id")) is int
            ):
                if str(chat["id"]) == chat_id:
                    return Result("sent", message_id=result["message_id"])
        return unknown
    if data["ok"] is False and type(data.get("error_code")) is int:
        if status == data["error_code"] == 429:
            parameters = data.get("parameters")
            delay = parameters.get("retry_after") if isinstance(parameters, dict) else None
            if type(delay) is int and 1 <= delay <= 86400:
                return Result("pending", "rate_limited", retry_after=delay)
            return Result("failed", "rejected")
        if status == data["error_code"] and 400 <= status < 500:
            # Includes migrated chat IDs: never silently redirect an approved destination.
            return Result("failed", "rejected")
    return unknown


def public_address(address):
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise ValueError("telegram resolution denied")
    return str(ip)


class Telegram:
    async def resolve(self):
        async with asyncio.timeout(3):
            addresses = await asyncio.get_running_loop().getaddrinfo(
                "api.telegram.org", 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
            )
        if not addresses:
            raise ValueError("telegram resolution unavailable")
        for _, _, _, _, addr in addresses:
            public_address(addr[0])
        # Connect to this vetted literal, retaining TLS hostname verification and the fixed Host.
        return addresses[0][4][0]

    async def send(self, address, token, chat_id, text):
        if not re.fullmatch(r"[1-9][0-9]{0,19}:[A-Za-z0-9_-]{20,128}", token):
            return Result("failed", "credential_unavailable")
        address = public_address(address)
        host = f"[{address}]" if ":" in address else address
        try:
            async with asyncio.timeout(12):
                async with httpx.AsyncClient(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(5, connect=3),
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
                ) as client:
                    async with client.stream(
                        "POST",
                        f"https://{host}/bot{token}/sendMessage",
                        headers={"Host": "api.telegram.org", "Accept-Encoding": "identity"},
                        extensions={"sni_hostname": "api.telegram.org"},
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "link_preview_options": {"is_disabled": True},
                        },
                    ) as reply:
                        raw = bytearray()
                        async for chunk in reply.aiter_raw():
                            raw.extend(chunk)
                            if len(raw) > 65536:
                                return Result("delivery_unknown", "invalid_response")
                        return response(reply.status_code, json.loads(raw), chat_id)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return Result("pending", "connect_failed")
        except Exception:
            # Includes write/read timeout, malformed body, dropped response and unexpected 5xx.
            return Result("delivery_unknown", "send_uncertain")
