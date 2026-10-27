"""Bounded MCP connection/discovery data; discovery never grants execution."""

import ipaddress
import json
import re
from urllib.parse import urlsplit

from alojan_contracts.configuration import canonical_digest

PROTOCOL = "2025-11-25"
SUPPORTED_PROTOCOLS = (PROTOCOL, "2025-06-18")
MAX_MANIFEST_BYTES = 262144


def endpoint(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError("invalid MCP endpoint")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host)
        or "." not in host
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", p) for p in host.split(".")
        )
        or not re.fullmatch(r"/[A-Za-z0-9/_.~-]*", parsed.path)
        or any(p in {".", ".."} for p in parsed.path.split("/"))
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
        or value != f"https://{host}{parsed.path}"
    ):
        raise ValueError("invalid MCP endpoint")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return value
    raise ValueError("MCP endpoint requires a DNS hostname")


def public_address(value):
    ip = ipaddress.ip_address(value)
    if (
        not ip.is_global
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or getattr(ip, "ipv4_mapped", None)
        or getattr(ip, "sixtofour", None)
        or getattr(ip, "teredo", None)
        or "%" in value
    ):
        raise ValueError("MCP address denied")
    return str(ip)


def manifest(tools, *, protocol=PROTOCOL):
    """Keep remote descriptions/schemas as untrusted data, never executable UI."""
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError("Unsupported MCP protocol")
    if not isinstance(tools, list) or len(tools) > 100:
        raise ValueError("MCP tool limit")
    raw = json.dumps(tools, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_MANIFEST_BYTES or b"\\u0000" in raw:
        raise ValueError("MCP manifest limit")
    names, result = set(), []
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name)
            or name in names
        ):
            raise ValueError("invalid MCP tool name")
        names.add(name)
        description = tool.get("description", "")
        if not isinstance(description, str) or len(description) > 4096 or "\x00" in description:
            raise ValueError("invalid MCP description")
        item = {"name": name, "description": description, "inputSchema": tool.get("inputSchema")}
        if tool.get("outputSchema") is not None:
            item["outputSchema"] = tool["outputSchema"]
        for field in ("inputSchema", "outputSchema"):
            if field not in item:
                continue
            schema = item[field]
            if not isinstance(schema, dict) or schema.get("type") != "object":
                raise ValueError("MCP object schema required")
            pending = [(schema, 0)]
            while pending:
                value, depth = pending.pop()
                if depth > 12:
                    raise ValueError("MCP schema depth")
                if isinstance(value, dict):
                    if any(k in value for k in ("$id", "$dynamicRef", "$dynamicAnchor")):
                        raise ValueError("MCP external schema unsupported")
                    if "$ref" in value and (
                        not isinstance(value["$ref"], str) or not value["$ref"].startswith("#/")
                    ):
                        raise ValueError("MCP external schema unsupported")
                    pending.extend((v, depth + 1) for v in value.values())
                elif isinstance(value, list):
                    pending.extend((v, depth + 1) for v in value)
        annotations = tool.get("annotations") or {}
        if not isinstance(annotations, dict):
            raise ValueError("invalid MCP annotation")
        item["read_only_hint"] = annotations.get("readOnlyHint") is True
        item["review_status"] = "unreviewed"
        item["digest"] = canonical_digest(item)
        result.append(item)
    result.sort(key=lambda t: t["name"])
    return {"protocol": protocol, "tools": result, "digest": canonical_digest(result)}
