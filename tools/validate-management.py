"""Exercise the real isolated management container without changing live schemas/services."""

from urllib.parse import urlunsplit
import argparse
import json
import os
import secrets
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

import psycopg
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/app-api"))
from alojan.migrate import migrate  # noqa: E402
from alojan.roles import grant_management  # noqa: E402


def validate(image, *, network=None, database_host=None):
    if bool(network) != bool(database_host):
        raise ValueError("Specify network and database host together")
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    run_id = uuid.uuid4().hex
    schema = "test_management_" + run_id
    container = "alojan-management-test-" + run_id
    role = "test_management_" + run_id
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with psycopg.connect(dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
    isolated = make_conninfo(dsn, options=f"-c search_path={schema}")
    origin = "https://management.example.test"
    opener = build_opener(ProxyHandler({}))
    cookie = ""

    def request(path, body=None, headers=None, method=None):
        outgoing = {"Origin": origin, "Cookie": cookie, **(headers or {})}
        data = None
        if body is not None:
            outgoing["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        try:
            response = opener.open(
                Request(
                    f"http://127.0.0.1:{port}{path}", data=data, headers=outgoing, method=method
                ),
                timeout=5,
            )
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, json.load(response)

    try:
        migrate(isolated)
        password = secrets.token_urlsafe(32)
        with psycopg.connect(dsn) as conn:
            conn.execute(
                psycopg.sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(
                    psycopg.sql.Identifier(role),
                    psycopg.sql.Literal(password),
                )
            )
        grant_management(isolated, role)
        runtime = make_conninfo(isolated, user=role, password=password)
        if network:
            runtime = make_conninfo(runtime, host=database_host, port=5432)
        with tempfile.TemporaryDirectory(
            prefix="alojan-management-", dir=ROOT / ".local"
        ) as directory:
            env_path = Path(directory) / "management.env"
            env_path.write_text(
                "ALOJAN_DATABASE_URL="
                + json.dumps(runtime)
                + "\n"
                + f"ALOJAN_PUBLIC_ORIGIN={origin}\nALOJAN_MANAGEMENT_PORT={port}\n"
                + f"ALOJAN_MANAGEMENT_BIND={'0.0.0.0' if network else '127.0.0.1'}\n"
            )
            env_path.chmod(0o600)
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container,
                    "--network",
                    network or "host",
                    *(["-p", f"127.0.0.1:{port}:{port}"] if network else []),
                    "--read-only",
                    "--cpus",
                    "0.5",
                    "--memory",
                    "512m",
                    "--pids-limit",
                    "64",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--tmpfs",
                    "/tmp:size=64m,mode=1777",
                    "--mount",
                    f"type=bind,source={env_path},target=/run/secrets/management_env,readonly",
                    image,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(50):
                try:
                    if request("/health/ready")[0] == 200:
                        break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                time.sleep(0.2)
            else:
                raise AssertionError("Container readiness failed")
            status, headers, session = request(
                "/v1/auth/register",
                {
                    "login": "synthetic.owner@example.test",
                    "password": "synthetic container test password",
                    "display_name": "Synthetic Owner",
                },
            )
            assert status == 201, "Registration failed"
            cookie = headers["set-cookie"].split(";", 1)[0]
            assert "Secure" in headers["set-cookie"] and "HttpOnly" in headers["set-cookie"]
            csrf = {"X-CSRF-Token": session["csrf_token"]}
            scope = session["workspaces"][0]["id"]
            status, _, agent = request(
                f"/v1/workspaces/{scope}/agents",
                {
                    "agent_name": "Synthetic Assistant",
                    "owner_display_name": "Synthetic Owner",
                    "owner_address": "Synthetic Owner",
                    "owner_dative": "Synthetic Owner",
                    "owner_genitive": "Synthetic Owner",
                    "instructions": "Collect caller messages.",
                },
                csrf,
            )
            assert status == 201, "Agent authoring failed"
            status, _, preview = request(
                f"/v1/workspaces/{scope}/agents/{agent['id']}/preview", {}, csrf
            )
            assert status == 200 and "yapay zekâ" in preview["greeting"]
            assert preview["can_receive_calls"] is False
            assert request(f"/v1/workspaces/{scope}/models")[2]["models"] == []
            status, _, result = request(
                f"/v1/workspaces/{scope}/agents/{agent['id']}/prepare",
                {},
                {**csrf, "If-Match": '"1"'},
            )
            assert status == 409 and result["error"] == "model_not_qualified"
            assert (
                request(f"/v1/workspaces/{scope}/agents/{agent['id']}/releases")[2]["version"] == 0
            )
            status, _, number = request(
                f"/v1/workspaces/{scope}/numbers", {"number": "+90850" + "1234567"}, csrf
            )
            assert status == 201 and number["status"] == "pending" and not number["enabled"]
            status, _, rejected = request(
                f"/v1/workspaces/{scope}/numbers/{number['id']}/binding",
                {"release_id": str(uuid.uuid4())},
                {**csrf, "If-Match": '"1"'},
                method="PUT",
            )
            assert status == 409 and rejected["error"] == "number_not_verified"
            base = f"/v1/workspaces/{scope}/mcp-connections"
            status, _, mcp = request(
                base,
                {
                    "label": "Synthetic MCP",
                    "endpoint": urlunsplit(("https", "mcp.example.test", "/tools", "", "")),
                    "auth_type": "none",
                    "token": None,
                },
                csrf,
            )
            assert status == 201 and mcp["enabled"]
            assert request(base)[2]["connections"] == [mcp]
            discovery = base + "/" + mcp["id"] + "/discovery"
            assert request(discovery)[2]["status"] == "missing"
            status, _, queued = request(discovery, {}, csrf)
            assert status == 202 and queued["status"] == "queued" and queued["manifest"] is None
            assert request(discovery, {}, csrf)[2] == queued
            assert request(base + "/" + mcp["id"] + "/revoke", {}, csrf)[0] == 200
            assert request(discovery, {}, csrf)[0] == 409
            assert request("/v1/auth/logout", {}, csrf)[0] == 200
            assert request("/v1/auth/session")[0] == 401
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        with psycopg.connect(dsn) as conn:
            conn.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )
            if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                conn.execute(
                    psycopg.sql.SQL("DROP OWNED BY {}").format(psycopg.sql.Identifier(role))
                )
                conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(psycopg.sql.Identifier(role)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--network")
    parser.add_argument("--database-host")
    args = parser.parse_args()
    try:
        validate(args.image, network=args.network, database_host=args.database_host)
    except Exception as exc:
        raise SystemExit(
            f"Management validation failed ({type(exc).__name__}); no credentials printed"
        ) from None
    print(
        "PASS: isolated container, restricted DB role, email registration, scoped draft, "
        "qualification/number-verification guards, MCP discovery queue without network, and session revocation"
    )
