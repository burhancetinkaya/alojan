"""Independent management HTTP service; no inference or live media processing."""

import hmac
import ipaddress
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import anyio
import psycopg
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from alojan.auth import Accounts, AuthError, csrf_token
from alojan.connections import Connections
from alojan.action_grants import ActionGrants
from alojan.deliveries import Deliveries
from alojan.calls import Calls
from alojan.latency import Latency
from alojan.telegram_connections import TelegramConnections
from alojan.mcp_connections import MCPConnections
from alojan.mcp_tools import MCPTools
from alojan.mcp_grants import MCPGrants
from alojan_contracts.secrets import SecretBox
from alojan.catalog import available_models
from alojan.releases import Releases
from alojan.numbers import Numbers
from alojan.profiles import AgentDraft, Profiles
from alojan.voice_preview import VoicePreview
from alojan.voice_jobs import VoiceJobs

COOKIE = "__Host-alojan"
BODY_LIMIT = 65536


def create_app(
    accounts,
    origin,
    *,
    trusted_proxy_ips=(),
    voice_node_id=None,
    secrets=None,
    voice_asset_root=None,
    oauth_registry=None,
    mcp_public_url=None,
):
    if mcp_public_url:
        mcp_address = urlsplit(mcp_public_url)
        if (
            mcp_address.scheme != "https"
            or not mcp_address.netloc
            or mcp_address.username
            or mcp_address.password
            or mcp_address.query
            or mcp_address.fragment
        ):
            raise ValueError("Use a public HTTPS MCP URL without credentials or query")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Configure one HTTPS management origin without a path")
    limiter = anyio.CapacityLimiter(2)
    bearer_limiter = anyio.CapacityLimiter(1)
    from alojan.personal_tokens import BearerCredential, PersonalTokens, request_budget
    from alojan.management_permissions import required_permissions

    personal_tokens = PersonalTokens(accounts)
    connections = Connections(accounts, secrets)
    action_grants = ActionGrants(accounts)
    deliveries = Deliveries(accounts)
    calls = Calls(accounts)
    latency = Latency(accounts)
    telegram = TelegramConnections(accounts, secrets)
    from alojan.mcp_oauth import MCPOAuth

    oauth = MCPOAuth(accounts, secrets, oauth_registry or {}, origin)
    from alojan.http_connections import HTTPConnections

    http_connections = HTTPConnections(accounts, secrets)
    mcp = MCPConnections(accounts, secrets)
    from alojan.connection_setups import ConnectionSetups

    connection_setups = ConnectionSetups(
        accounts,
        {"provider": connections, "telegram": telegram, "http": http_connections, "mcp": mcp},
        origin,
    )
    mcp_tools = MCPTools(accounts)
    mcp_grants = MCPGrants(accounts)
    profiles = Profiles(accounts)
    releases = Releases(accounts, voice_node_id)
    voice_preview = VoicePreview(accounts, voice_asset_root)
    voice_jobs = VoiceJobs(accounts)
    numbers = Numbers(accounts, voice_node_id)
    trusted_proxies = {str(ipaddress.ip_address(value)) for value in trusted_proxy_ips}

    async def cleanup():
        while True:
            await anyio.sleep(300)
            try:
                await anyio.to_thread.run_sync(accounts.cleanup, limiter=limiter)
            except psycopg.Error:
                # Expiry is enforced on reads even while cleanup is unavailable.
                pass

    @asynccontextmanager
    async def lifespan(app):
        async with anyio.create_task_group() as group:
            group.start_soon(cleanup)
            yield
            group.cancel_scope.cancel()

    async def endpoint(request):
        try:
            action = request.path_params.get("action")
            token = request.cookies.get(COOKIE, "")
            authorization = request.headers.get("authorization")
            bearer = authorization is not None
            if bearer:
                if token or len(request.headers.getlist("authorization")) != 1:
                    raise AuthError("ambiguous_authentication", 400)
                if not authorization.startswith("Bearer ") or len(authorization) > 160:
                    raise AuthError("authentication_required")
                if action == "mcp-context":
                    required = frozenset()
                elif "scope" in request.path_params:
                    required = required_permissions(
                        request.path_params.get("resource"), action, request.method
                    )
                else:
                    raise AuthError("browser_session_required", 403)
                token = BearerCredential(
                    authorization[7:],
                    str(request.path_params["scope"]) if "scope" in request.path_params else None,
                    required,
                )
                if request.headers.get("origin") not in (None, origin):
                    raise AuthError("origin_rejected", 403)
            body = {}
            if request.method in ("POST", "PUT", "DELETE"):
                if not bearer and request.headers.get("origin") != origin:
                    raise AuthError("origin_rejected", 403)
                if request.headers.get("content-type", "").split(";")[0] != "application/json":
                    raise AuthError("json_required", 415)
                if not bearer and action not in ("register", "login"):
                    expected = csrf_token(token)
                    if not hmac.compare_digest(
                        request.headers.get("x-csrf-token", "").encode(),
                        expected.encode(),
                    ):
                        raise AuthError("csrf_rejected", 403)
                chunks, size = [], 0
                with anyio.fail_after(5):
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > BODY_LIMIT:
                            raise AuthError("body_too_large", 413)
                        chunks.append(chunk)
                try:
                    body = json.loads(b"".join(chunks))
                    json.dumps(body, allow_nan=False).encode("utf-8")
                except (ValueError, RecursionError, UnicodeError):
                    raise AuthError("invalid_json", 400) from None
                if not isinstance(body, dict):
                    raise AuthError("invalid_json", 400)
            peer = request.client.host if request.client else "unknown"
            if peer in trusted_proxies and "cf-connecting-ip" in request.headers:
                try:
                    peer = str(ipaddress.ip_address(request.headers["cf-connecting-ip"]))
                except ValueError:
                    raise AuthError("invalid_client_address", 400) from None

            def handle():
                if action == "mcp-context":
                    if not bearer:
                        raise AuthError("authentication_required")
                    from alojan.auth import connection

                    with connection(accounts.dsn) as conn:
                        user = accounts.authenticate(conn, token)
                    return user | {"management_origin": origin}, None, 200
                if action == "session":
                    return accounts.session(token), None, 200
                if action in ("register", "login"):
                    required = {"login", "password"}
                    if action == "register":
                        required.add("display_name")
                    if body.keys() != required:
                        raise AuthError("invalid_fields", 400)
                    if action == "register":
                        new_token = accounts.register(
                            body["login"],
                            body["password"],
                            body["display_name"],
                            peer=peer,
                        )
                    else:
                        new_token = accounts.login(body["login"], body["password"], peer=peer)
                    return (
                        accounts.session(new_token),
                        new_token,
                        201 if action == "register" else 200,
                    )
                if action == "logout":
                    if body:
                        raise AuthError("invalid_fields", 400)
                    accounts.logout(token)
                    return {"status": "signed_out"}, "", 200
                if action == "password":
                    if body.keys() != {"current_password", "new_password"}:
                        raise AuthError("invalid_fields", 400)
                    accounts.change_password(
                        token,
                        body["current_password"],
                        body["new_password"],
                        peer=peer,
                    )
                    return {"status": "sign_in_required"}, "", 200
                if "scope" in request.path_params:
                    scope = request.path_params["scope"]
                    profile = request.path_params.get("profile")
                    resource = request.path_params.get("resource")
                    if resource == "connection-setups":
                        if request.query_params:
                            raise AuthError("invalid_fields", 400)
                        reference = request.path_params.get("setup")
                        if action == "complete":
                            return (
                                connection_setups.complete(token, scope, reference, body),
                                None,
                                200,
                            )
                        if reference:
                            return connection_setups.get(token, scope, reference), None, 200
                        return connection_setups.create(token, scope, body), None, 201
                    if resource == "personal-tokens":
                        if request.query_params:
                            raise AuthError("invalid_fields", 400)
                        if action == "revoke":
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return (
                                personal_tokens.revoke(
                                    token, scope, request.path_params["personal_token"]
                                ),
                                None,
                                200,
                            )
                        if request.method == "GET":
                            return (
                                {
                                    "tokens": personal_tokens.list(token, scope),
                                    "mcp_url": mcp_public_url,
                                },
                                None,
                                200,
                            )
                        return personal_tokens.create(token, scope, body), None, 201
                    if resource == "performance":
                        pairs = list(request.query_params.multi_items())
                        if any(k not in {"agent", "call"} for k, _ in pairs) or len(pairs) != len(
                            dict(pairs)
                        ):
                            raise AuthError("invalid_call_filter", 400)
                        return latency.get(token, scope, **dict(pairs)), None, 200
                    if resource == "calls":
                        pairs = list(request.query_params.multi_items())
                        allowed = (
                            {
                                "agent",
                                "after",
                                "from_time",
                                "to_time",
                                "caller",
                                "called",
                                "status",
                                "summary_status",
                                "query",
                                "search_in",
                            }
                            if action is None
                            else {"after"}
                            if action == "transcript"
                            else set()
                        )
                        if any(k not in allowed for k, _ in pairs) or len(pairs) != len(
                            dict(pairs)
                        ):
                            raise AuthError("invalid_call_filter", 400)
                        if action == "call":
                            return calls.get(token, scope, request.path_params["call"]), None, 200
                        if action == "transcript":
                            return (
                                calls.transcript(
                                    token, scope, request.path_params["call"], **dict(pairs)
                                ),
                                None,
                                200,
                            )
                        return calls.list(token, scope, **dict(pairs)), None, 200
                    if resource == "http-connections":
                        if request.query_params:
                            raise AuthError("invalid_fields", 400)
                        if request.method == "GET":
                            return {"connections": http_connections.list(token, scope)}, None, 200
                        if action == "revoke":
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return (
                                http_connections.revoke(
                                    token, scope, request.path_params["connection"]
                                ),
                                None,
                                200,
                            )
                        return http_connections.create(token, scope, body), None, 201
                    if resource == "mcp-oauth":
                        if request.query_params:
                            raise AuthError("invalid_fields", 400)
                        if request.method == "GET":
                            return {"providers": oauth.list(token, scope)}, None, 200
                        method = oauth.complete if action == "complete" else oauth.start
                        return method(token, scope, body), None, 200
                    if resource == "mcp-connections":
                        if action == "tools":
                            if request.query_params:
                                raise AuthError("invalid_fields", 400)
                            return (
                                mcp_tools.list(token, scope, request.path_params["connection"]),
                                None,
                                200,
                            )
                        reference = request.path_params.get("connection")
                        if request.query_params:
                            raise AuthError("invalid_fields", 400)
                        if reference is not None:
                            if body:
                                raise AuthError("invalid_fields", 400)
                            if action == "discovery":
                                requested = request.method == "POST"
                                return (
                                    mcp.discover(token, scope, reference, request=requested),
                                    None,
                                    202 if requested else 200,
                                )
                            return mcp.revoke(token, scope, reference), None, 200
                        if request.method == "GET":
                            return {"connections": mcp.list(token, scope)}, None, 200
                        return mcp.create(token, scope, body), None, 201
                    if resource in {"provider-connections", "telegram-connections"}:
                        store = connections if resource == "provider-connections" else telegram
                        reference = request.path_params.get("connection")
                        if reference is not None:
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return store.revoke(token, scope, reference), None, 200
                        if request.method == "GET":
                            return {"connections": store.list(token, scope)}, None, 200
                        return store.create(token, scope, body), None, 201
                    if resource == "numbers":
                        number = request.path_params.get("number")
                        if number is None:
                            if request.method == "GET":
                                return {"numbers": numbers.list(token, scope)}, None, 200
                            if body.keys() != {"number"}:
                                raise AuthError("invalid_fields", 400)
                            return numbers.create(token, scope, body["number"]), None, 201
                        match = request.headers.get("if-match", "")
                        if not re.fullmatch(r'"[1-9][0-9]{0,8}"', match):
                            raise AuthError("version_required", 428)
                        version = int(match[1:-1])
                        if action == "deactivate":
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return numbers.deactivate(token, scope, number, version), None, 200
                        if body.keys() != {"release_id"} or not isinstance(body["release_id"], str):
                            raise AuthError("invalid_fields", 400)
                        try:
                            release = uuid.UUID(body["release_id"])
                        except ValueError:
                            raise AuthError("invalid_fields", 400) from None
                        return numbers.bind(token, scope, number, release, version), None, 200
                    if resource == "agents":
                        if action == "voice-preparation":
                            match = request.headers.get("if-match", "")
                            if not re.fullmatch(r'"[1-9][0-9]{0,8}"', match):
                                raise AuthError("version_required", 428)
                            if body:
                                raise AuthError("invalid_fields", 400)
                            operation = (
                                voice_jobs.request
                                if request.method == "POST"
                                else voice_jobs.status
                            )
                            return operation(token, scope, profile, int(match[1:-1])), None, 200
                        if action == "voice-preview":
                            match = request.headers.get("if-match", "")
                            if not re.fullmatch(r'"[1-9][0-9]{0,8}"', match):
                                raise AuthError("version_required", 428)
                            return (
                                voice_preview.read(
                                    token,
                                    scope,
                                    profile,
                                    int(match[1:-1]),
                                    request.path_params["clip"],
                                ),
                                None,
                                200,
                            )
                        if profile is None:
                            if request.method == "POST":
                                return profiles.create(token, scope, body), None, 201
                            return {"agents": profiles.list(token, scope)}, None, 200
                        if action == "deliveries":
                            pairs = list(request.query_params.multi_items())
                            if any(k not in {"status", "after"} for k, _ in pairs) or len(
                                pairs
                            ) != len(dict(pairs)):
                                raise AuthError("invalid_delivery_filter", 400)
                            return deliveries.list(token, scope, profile, **dict(pairs)), None, 200
                        if action in {"delivery", "retry-review", "retry-delivery"}:
                            if request.query_params:
                                raise AuthError("invalid_delivery_filter", 400)
                            job = request.path_params["job"]
                            if action == "retry-delivery":
                                return deliveries.retry(token, scope, profile, job, body), None, 202
                            method = (
                                deliveries.review if action == "retry-review" else deliveries.get
                            )
                            return method(token, scope, profile, job), None, 200
                        if action in ("mcp-review", "mcp-grants", "revoke-mcp-grant"):
                            if request.query_params:
                                raise AuthError("invalid_fields", 400)
                            if action == "mcp-review":
                                return mcp_grants.review(token, scope, profile), None, 200
                            if action == "mcp-grants":
                                if request.method == "GET":
                                    return (
                                        {"grants": mcp_grants.list(token, scope, profile)},
                                        None,
                                        200,
                                    )
                                return mcp_grants.authorize(token, scope, profile, body), None, 201
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return (
                                mcp_grants.revoke(
                                    token, scope, profile, request.path_params["grant"]
                                ),
                                None,
                                200,
                            )
                        if action == "action-review":
                            return action_grants.review(token, scope, profile), None, 200
                        if action == "action-grants":
                            if request.method == "GET":
                                return (
                                    {"grants": action_grants.list(token, scope, profile)},
                                    None,
                                    200,
                                )
                            return action_grants.authorize(token, scope, profile, body), None, 201
                        if action == "revoke-action-grant":
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return (
                                action_grants.revoke(
                                    token, scope, profile, request.path_params["grant"]
                                ),
                                None,
                                200,
                            )
                        if action == "releases":
                            return releases.list(token, scope, profile), None, 200
                        if action == "release-status":
                            if request.query_params:
                                raise AuthError("invalid_fields", 400)
                            return (
                                releases.status(
                                    token, scope, profile, request.path_params["release"]
                                ),
                                None,
                                200,
                            )
                        if action in ("prepare", "publish", "rollback"):
                            match = request.headers.get("if-match", "")
                            pattern = (
                                r'"[1-9][0-9]{0,8}"'
                                if action == "prepare"
                                else r'"(0|[1-9][0-9]{0,8})"'
                            )
                            if not re.fullmatch(pattern, match):
                                raise AuthError("version_required", 428)
                            version = int(match[1:-1])
                            if action == "prepare":
                                if body:
                                    raise AuthError("invalid_fields", 400)
                                return releases.prepare(token, scope, profile, version), None, 200
                            key = "preparation_id" if action == "publish" else "release_id"
                            if body.keys() != {key} or not isinstance(body[key], str):
                                raise AuthError("invalid_fields", 400)
                            try:
                                identifier = uuid.UUID(body[key])
                            except ValueError:
                                raise AuthError("invalid_fields", 400) from None
                            method = releases.publish if action == "publish" else releases.rollback
                            return method(token, scope, profile, identifier, version), None, 201
                        if action == "preview":
                            if body:
                                raise AuthError("invalid_fields", 400)
                            return profiles.preview(token, scope, profile), None, 200
                        if request.method == "PUT":
                            match = request.headers.get("if-match", "")
                            if not re.fullmatch(r'"[1-9][0-9]{0,8}"', match):
                                raise AuthError("version_required", 428)
                            return (
                                profiles.update(token, scope, profile, body, int(match[1:-1])),
                                None,
                                200,
                            )
                        return profiles.get(token, scope, profile), None, 200
                    if resource == "models":
                        return {"models": available_models(accounts, token, scope)}, None, 200
                    if resource == "agent-schema":
                        with accounts.workspace(token, scope):
                            return AgentDraft.model_json_schema(), None, 200
                    with accounts.workspace(token, request.path_params["scope"]) as (conn, user):
                        row = conn.execute(
                            "SELECT id,display_name FROM recipient_scopes WHERE id=%s",
                            (request.path_params["scope"],),
                        ).fetchone()
                        return {"id": str(row[0]), "name": row[1]}, None, 200
                raise AuthError("not_found", 404)

            def execute():
                if bearer:
                    from alojan.auth import connection

                    with connection(accounts.dsn) as conn:
                        bearer_user = accounts.authenticate(conn, token)
                    request_budget(accounts.dsn, bearer_user)
                if bearer and request.method in {"POST", "PUT", "DELETE"}:
                    from alojan.management_operations import execute as mutate

                    return mutate(accounts, token, request, body, handle)
                return handle()

            payload, cookie, status = await anyio.to_thread.run_sync(
                execute, limiter=bearer_limiter if bearer else limiter
            )
            response = (
                Response(payload, media_type="audio/wav", status_code=status)
                if isinstance(payload, bytes)
                else JSONResponse(payload, status_code=status)
            )
            if isinstance(payload, dict) and "version" in payload:
                response.headers["ETag"] = f'"{payload["version"]}"'
            if cookie:
                response.set_cookie(
                    COOKIE,
                    cookie,
                    secure=True,
                    httponly=True,
                    samesite="strict",
                    path="/",
                )
            elif cookie == "":
                response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="strict")
        except AuthError as exc:
            response = JSONResponse({"error": exc.code}, status_code=exc.status)
            if exc.status == 429:
                response.headers["Retry-After"] = "300"
        except TimeoutError:
            response = JSONResponse({"error": "request_timeout"}, status_code=408)
        except psycopg.Error:
            response = JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    async def health(request):
        if request.url.path.endswith("/ready"):
            ready = await anyio.to_thread.run_sync(accounts.ready, limiter=limiter)
            return JSONResponse(
                {"service": "management-api", "status": "ready" if ready else "not_ready"},
                status_code=200 if ready else 503,
            )
        return JSONResponse({"service": "management-api", "status": "live"})

    routes = [Route("/health/live", health), Route("/health/ready", health)]
    for action, method in [
        ("session", "GET"),
        ("register", "POST"),
        ("login", "POST"),
        ("logout", "POST"),
        ("password", "POST"),
    ]:

        async def bound(request, action=action):
            request.path_params["action"] = action
            return await endpoint(request)

        routes.append(Route(f"/v1/auth/{action}", bound, methods=[method]))

    async def mcp_context(request):
        request.path_params["action"] = "mcp-context"
        return await endpoint(request)

    routes.append(Route("/v1/mcp/context", mcp_context, methods=["GET"]))
    routes.append(Route("/v1/workspaces/{scope}", endpoint, methods=["GET"]))
    for suffix, methods, action in [
        ("connection-setups", ["POST"], None),
        ("connection-setups/{setup:uuid}", ["GET"], None),
        ("connection-setups/{setup:uuid}/complete", ["POST"], "complete"),
        ("personal-tokens", ["GET", "POST"], None),
        ("personal-tokens/{personal_token:uuid}/revoke", ["POST"], "revoke"),
        ("agents", ["GET", "POST"], None),
        ("calls", ["GET"], None),
        ("performance", ["GET"], None),
        ("calls/{call:uuid}", ["GET"], "call"),
        ("calls/{call:uuid}/transcript", ["GET"], "transcript"),
        ("agents/{profile:uuid}", ["GET", "PUT"], None),
        ("agents/{profile:uuid}/preview", ["POST"], "preview"),
        ("agents/{profile:uuid}/voice-preparation", ["GET", "POST"], "voice-preparation"),
        ("agents/{profile:uuid}/voice-preview/{clip}", ["GET"], "voice-preview"),
        ("agents/{profile:uuid}/releases/{release:uuid}/status", ["GET"], "release-status"),
        ("agents/{profile:uuid}/action-review", ["GET"], "action-review"),
        ("agents/{profile:uuid}/deliveries", ["GET"], "deliveries"),
        ("agents/{profile:uuid}/deliveries/{job:uuid}", ["GET"], "delivery"),
        ("agents/{profile:uuid}/deliveries/{job:uuid}/retry-review", ["GET"], "retry-review"),
        ("agents/{profile:uuid}/deliveries/{job:uuid}/retry", ["POST"], "retry-delivery"),
        ("agents/{profile:uuid}/action-grants", ["GET", "POST"], "action-grants"),
        (
            "agents/{profile:uuid}/action-grants/{grant:uuid}/revoke",
            ["POST"],
            "revoke-action-grant",
        ),
        ("agents/{profile:uuid}/mcp-review", ["GET"], "mcp-review"),
        ("agents/{profile:uuid}/mcp-grants", ["GET", "POST"], "mcp-grants"),
        ("agents/{profile:uuid}/mcp-grants/{grant:uuid}/revoke", ["POST"], "revoke-mcp-grant"),
        ("mcp-connections/{connection:uuid}/tools", ["GET"], "tools"),
        ("agent-schema", ["GET"], None),
        ("models", ["GET"], None),
        ("numbers", ["GET", "POST"], None),
        ("provider-connections", ["GET", "POST"], None),
        ("provider-connections/{connection:uuid}/revoke", ["POST"], "revoke"),
        ("telegram-connections", ["GET", "POST"], None),
        ("telegram-connections/{connection:uuid}/revoke", ["POST"], "revoke"),
        ("http-connections", ["GET", "POST"], None),
        ("http-connections/{connection:uuid}/revoke", ["POST"], "revoke"),
        ("mcp-oauth", ["GET", "POST"], None),
        ("mcp-oauth/complete", ["POST"], "complete"),
        ("mcp-connections", ["GET", "POST"], None),
        ("mcp-connections/{connection:uuid}/revoke", ["POST"], "revoke"),
        ("mcp-connections/{connection:uuid}/discovery", ["GET", "POST"], "discovery"),
        ("numbers/{number:uuid}/binding", ["PUT"], "binding"),
        ("numbers/{number:uuid}/deactivate", ["POST"], "deactivate"),
        ("agents/{profile:uuid}/prepare", ["POST"], "prepare"),
        ("agents/{profile:uuid}/releases", ["GET"], "releases"),
        ("agents/{profile:uuid}/publish", ["POST"], "publish"),
        ("agents/{profile:uuid}/rollback", ["POST"], "rollback"),
    ]:

        async def scoped(request, resource=suffix.split("/")[0], action=action):
            request.path_params["resource"] = resource
            request.path_params["action"] = action
            return await endpoint(request)

        routes.append(Route(f"/v1/workspaces/{{scope:uuid}}/{suffix}", scoped, methods=methods))
    return Starlette(routes=routes, lifespan=lifespan)


def main():
    import uvicorn
    from alojan_contracts.mcp_oauth import providers

    app = create_app(
        Accounts(os.environ["ALOJAN_DATABASE_URL"]),
        os.environ["ALOJAN_PUBLIC_ORIGIN"],
        trusted_proxy_ips=filter(None, os.environ.get("ALOJAN_TRUSTED_PROXY_IPS", "").split(",")),
        voice_node_id=os.environ.get("ALOJAN_VOICE_NODE_ID"),
        voice_asset_root=os.environ.get("ALOJAN_VOICE_ASSET_ROOT"),
        mcp_public_url=os.environ.get("ALOJAN_MCP_PUBLIC_URL"),
        oauth_registry=providers(os.environ.get("ALOJAN_MCP_OAUTH_PROVIDERS_FILE")),
        secrets=(
            SecretBox.from_file(os.environ["ALOJAN_CREDENTIAL_KEY_FILE"])
            if os.environ.get("ALOJAN_CREDENTIAL_KEY_FILE")
            else None
        ),
    )
    uvicorn.run(
        app,
        host=os.environ.get("ALOJAN_MANAGEMENT_BIND", "127.0.0.1"),
        port=int(os.environ.get("ALOJAN_MANAGEMENT_PORT", "18081")),
        proxy_headers=False,
        access_log=False,
        limit_concurrency=32,
        timeout_keep_alive=5,
    )


if __name__ == "__main__":
    main()
