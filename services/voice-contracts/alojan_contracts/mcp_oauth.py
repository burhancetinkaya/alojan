"""Pre-registered public-client OAuth: pinned metadata, PKCE and resource binding."""

import asyncio
import base64
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit

import httpx2 as httpx

from alojan_contracts.mcp import endpoint
from alojan_contracts.mcp_http import PinnedTransport
from alojan_contracts.secrets import SecretBox


class OAuthError(ValueError):
    """Fixed diagnostics only; never propagate remote token responses."""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issuer_url(value):
    if not isinstance(value, str):
        raise ValueError("invalid OAuth issuer")
    endpoint(value if urlsplit(value).path else value + "/")
    return value


def provider(value):
    fields = {
        "id",
        "label",
        "resource",
        "resource_metadata",
        "issuer",
        "server_metadata",
        "authorization_endpoint",
        "token_endpoint",
        "client_id",
        "scopes",
    }
    if not isinstance(value, dict) or value.keys() != fields:
        raise ValueError("invalid OAuth provider")
    if not isinstance(value["id"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", value["id"]):
        raise ValueError("invalid OAuth provider id")
    for field, limit in (("label", 80), ("client_id", 256)):
        if (
            not isinstance(value[field], str)
            or not 1 <= len(value[field]) <= limit
            or not value[field].isprintable()
        ):
            raise ValueError("invalid OAuth provider text")
    for key in (
        "resource",
        "resource_metadata",
        "server_metadata",
        "authorization_endpoint",
        "token_endpoint",
    ):
        endpoint(value[key])
    issuer_url(value["issuer"])
    scopes = value["scopes"]
    if (
        not isinstance(scopes, list)
        or not 1 <= len(scopes) <= 16
        or any(
            not isinstance(s, str) or not re.fullmatch(r"[a-zA-Z0-9:._/-]{1,80}", s) for s in scopes
        )
        or len(set(scopes)) != len(scopes)
    ):
        raise ValueError("invalid OAuth scopes")
    return json.loads(json.dumps(value))


def providers(path):
    if not path:
        return {}
    with Path(path).open("rb") as source:
        raw = source.read(65537)
    values = json.loads(raw)
    if len(raw) > 65536 or not isinstance(values, list) or len(values) > 20:
        raise ValueError("invalid OAuth provider registry")
    checked = [provider(v) for v in values]
    result = {v["id"]: v for v in checked}
    if len(result) != len(checked):
        raise ValueError("duplicate OAuth provider")
    return result


async def request_json(url, fields=None):
    try:
        async with (
            asyncio.timeout(6),
            httpx.AsyncClient(
                transport=PinnedTransport(url),
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(4),
                headers={"Accept": "application/json"},
            ) as client,
        ):
            async with client.stream(
                "POST" if fields is not None else "GET", url, data=fields
            ) as response:
                if response.status_code != 200:
                    raise OAuthError("oauth_remote_rejected")
                if (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                    != "application/json"
                ):
                    raise OAuthError("oauth_invalid_response")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 32768:
                        raise OAuthError("oauth_invalid_response")
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise OAuthError("oauth_invalid_response")
                return value
    except Exception:
        raise OAuthError("oauth_request_failed") from None


async def validate_metadata(config, *, request=request_json):
    # Neither remote document may introduce an unapproved fetch or redirect target.
    resource = await request(config["resource_metadata"])
    server = await request(config["server_metadata"])
    for document, fields in (
        (resource, ("authorization_servers", "scopes_supported")),
        (
            server,
            (
                "code_challenge_methods_supported",
                "response_types_supported",
                "token_endpoint_auth_methods_supported",
            ),
        ),
    ):
        if not isinstance(document, dict):
            raise OAuthError("oauth_metadata_changed")
        for field in fields:
            values = document.get(field)
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 100
                or any(not isinstance(v, str) or len(v) > 2048 for v in values)
            ):
                raise OAuthError("oauth_metadata_changed")
    if (
        resource.get("resource") != config["resource"]
        or config["issuer"] not in resource.get("authorization_servers", [])
        or not set(config["scopes"]) <= set(resource.get("scopes_supported", []))
        or server.get("issuer") != config["issuer"]
        or server.get("authorization_endpoint") != config["authorization_endpoint"]
        or server.get("token_endpoint") != config["token_endpoint"]
        or "S256" not in server.get("code_challenge_methods_supported", [])
        or "code" not in server.get("response_types_supported", [])
        or "none" not in server.get("token_endpoint_auth_methods_supported", [])
        or server.get("authorization_response_iss_parameter_supported") is not True
    ):
        raise OAuthError("oauth_metadata_changed")


def authorization_url(config, redirect, state, verifier):
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return (
        config["authorization_endpoint"]
        + "?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": config["client_id"],
                "redirect_uri": redirect,
                "scope": " ".join(config["scopes"]),
                "resource": config["resource"],
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )


def tokens(value, config, *, previous_refresh=None):
    try:
        access = SecretBox.validate(value["access_token"], purpose="mcp-oauth-access")
        refresh = value.get("refresh_token")
        if refresh is not None:
            SecretBox.validate(refresh, purpose="mcp-oauth-refresh")
        lifetime = value["expires_in"]
        scopes = value.get("scope", " ".join(config["scopes"]))
        if (
            value["token_type"].lower() != "bearer"
            or type(lifetime) is not int
            or not 60 <= lifetime <= 86400
            or not isinstance(scopes, str)
            or set(scopes.split()) != set(config["scopes"])
            or value.get("resource", config["resource"]) != config["resource"]
            or (previous_refresh is not None and (not refresh or refresh == previous_refresh))
        ):
            raise ValueError()
        return access, refresh, lifetime
    except (KeyError, TypeError, ValueError, AttributeError):
        raise OAuthError("oauth_invalid_tokens") from None


async def exchange(
    config, *, code=None, verifier=None, redirect=None, refresh=None, request=request_json
):
    fields = {"client_id": config["client_id"], "resource": config["resource"]}
    if refresh is None:
        fields.update(
            grant_type="authorization_code",
            code=code,
            code_verifier=verifier,
            redirect_uri=redirect,
        )
    else:
        fields.update(
            grant_type="refresh_token", refresh_token=refresh, scope=" ".join(config["scopes"])
        )
    return tokens(await request(config["token_endpoint"], fields), config, previous_refresh=refresh)
