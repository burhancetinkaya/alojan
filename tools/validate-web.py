"""Real HTTPS browser checks against an isolated management schema; no live voice writes."""

from urllib.parse import urlunsplit
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import uuid

import psycopg
from cryptography.fernet import Fernet
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "services/app-api"),
    str(ROOT / "services/agent"),
    str(ROOT / "services/voice-contracts"),
    str(ROOT / "tests"),
    str(ROOT / "tests/support"),
    str(ROOT / "generated/python"),
]
from alojan.auth import Accounts  # noqa: E402
from alojan.connections import Connections  # noqa: E402
from alojan.migrate import migrate  # noqa: E402
from alojan.profiles import Profiles, validate_draft  # noqa: E402
from alojan.releases import Releases  # noqa: E402
from alojan.voice_assets import import_pack  # noqa: E402
from alojan.telegram_connections import TelegramConnections  # noqa: E402
from test_agent_releases import pack  # noqa: E402
from alojan_agent.records import CallRecords, CallSummaries  # noqa: E402
from alojan_agent.action_delivery import ActionDelivery  # noqa: E402
from alojan_agent.telegram_delivery import Result  # noqa: E402
from test_action_delivery import Transport  # noqa: E402
from test_action_grants import action, consent  # noqa: E402
from alojan_agent.models import Note  # noqa: E402
from alojan.numbers import Numbers  # noqa: E402
from test_scoped_call_records import summary  # noqa: E402
import test_number_routing as routing  # noqa: E402
from alojan.latency import ingest, FIELDS  # noqa: E402
from test_call_latency import line  # noqa: E402
from alojan.roles import grant_management  # noqa: E402
from alojan_contracts.configuration import EnginePreset, canonical_digest  # noqa: E402
from alojan_contracts.secrets import SecretBox  # noqa: E402
from web_journey import start_journey_fixture  # noqa: E402
from web_mcp import setup_mcp  # noqa: E402

NODE = "node:22.23.1-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3"
BROWSER = "mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea"
MANAGEMENT = "sha256:03047806993d5f549885e73cba4ad549835e6041df03b120da2d14de26f9ba43"


def validate():
    os.umask(0o077)
    manifest = json.loads((ROOT / "services/web/.next/routes-manifest.json").read_text())
    rewrites = manifest["rewrites"]["afterFiles"]
    if len(rewrites) != 1 or rewrites[0].get("destination") != "http://127.0.0.1:18181/v1/:path*":
        raise RuntimeError(
            "Build the test frontend with ALOJAN_MANAGEMENT_URL=http://127.0.0.1:18181 first"
        )
    for port in (18181, 13001, 18443):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
    run = uuid.uuid4().hex
    schema = role = "test_web_" + run
    work = ROOT / ".local" / ("web-validation-" + run)
    work.mkdir()
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    isolated = make_conninfo(dsn, options=f"-c search_path={schema}")
    containers = []
    journey = None

    def start(name, image, arguments, *, mounts=(), env=()):
        container = "alojan-web-test-" + name + "-" + run
        containers.append(container)
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container,
                "--network=host",
                "--cpus=2",
                "--memory=2g",
                "--user=1000:1000",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                *mounts,
                *env,
                image,
                *arguments,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    try:
        with psycopg.connect(dsn) as c:
            c.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        migrate(isolated)
        password = secrets.token_urlsafe(24)
        with psycopg.connect(dsn) as c:
            c.execute(
                psycopg.sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(psycopg.sql.Identifier(role), psycopg.sql.Literal(password))
            )
        grant_management(isolated, role)
        accounts = Accounts(isolated)
        (work / "provider.key").write_bytes(Fernet.generate_key())
        box = SecretBox.from_file(work / "provider.key")
        login = "web.owner@example.test"
        owner_password = "Synthetic browser password 123!"
        token = accounts.register(login, owner_password, "Test Sahibi", peer="fixture")
        scope = accounts.session(token)["workspaces"][0]["id"]
        connection = Connections(accounts, box).create(
            token,
            scope,
            dict(
                provider="openrouter",
                label="Test model bağlantısı",
                api_key="synthetic-provider-key-never-used",
            ),
        )["id"]
        instructions = "Arayanın mesajını eksiksiz not al. " * 480
        note_ack = "Talebinizi {owner_dative} iletmek üzere not aldım."
        content = dict(
            agent_name="Test Asistanı",
            owner_display_name="Test Sahibi",
            owner_address="Test Sahibi",
            owner_dative="Test Sahibine",
            owner_genitive="Test Sahibinin",
            instructions=instructions,
            vocabulary=["Test Terimi"],
            note_ack_template=note_ack,
            model_connection=connection,
        )
        agent = Profiles(accounts).create(token, scope, content)["id"]
        other = accounts.register(
            "other.owner@example.test", owner_password, "Other Owner", peer="fixture"
        )
        other_scope = accounts.session(other)["workspaces"][0]["id"]
        Profiles(accounts).create(
            other,
            other_scope,
            content | dict(agent_name="Other private agent", model_connection=None),
        )
        preset = EnginePreset().model_dump()
        with psycopg.connect(isolated) as c:
            c.execute(
                "INSERT INTO engine_presets(id,revision,configuration,digest) VALUES ('web-test',1,%s,%s)",
                (Jsonb(preset), canonical_digest(preset)),
            )
            c.execute(
                "INSERT INTO model_catalog(id,revision,display_name,preset_id,preset_revision) VALUES ('gpt-oss-120b-cerebras',1,'GPT-OSS 120B','web-test',1)"
            )
            c.execute(
                "INSERT INTO model_catalog_status(model_id,model_revision,enabled,qualification_ref) VALUES ('gpt-oss-120b-cerebras',1,true,'synthetic-browser-test-only')"
            )
        preparation = Releases(accounts).prepare(token, scope, agent, 1)
        draft = validate_draft(Profiles(accounts).get(token, scope, agent)["content"])
        source = pack(work, draft)
        import_pack(isolated, scope, preparation["id"], source, work / "voice-store")
        TelegramConnections(accounts, box).create(
            token,
            scope,
            {
                "label": "Browser Telegram",
                "chat_id": "123456789",
                "bot_token": "123456789:synthetic_token_never_sent_123456",
            },
        )
        # Dedicated synthetic call workspace keeps the builder scenarios independent.
        call_login = "calls.owner@example.test"
        call_token = accounts.register(
            call_login, owner_password, "Call Owner", peer="call-fixture"
        )
        call_scope = accounts.session(call_token)["workspaces"][0]["id"]
        call_connection = TelegramConnections(accounts, box).create(
            call_token,
            call_scope,
            {
                "label": "Call notification",
                "chat_id": "123456789",
                "bot_token": "123456789:synthetic_token_never_sent_123456",
            },
        )["id"]
        call_agent = Profiles(accounts).create(
            call_token,
            call_scope,
            content
            | {
                "agent_name": "Çağrı Asistanı",
                "model_connection": None,
                "post_call_actions": [action(call_connection)],
            },
        )["id"]
        call_author = (call_token, call_scope, call_agent)
        consent(accounts, call_author)
        call_preparation = Releases(accounts).prepare(*call_author, 1)
        call_draft = validate_draft(Profiles(accounts).get(*call_author)["content"])
        import_pack(
            isolated,
            call_scope,
            call_preparation["id"],
            pack(work, call_draft),
            work / "voice-store",
        )
        call_release = Releases(accounts).publish(*call_author, call_preparation["id"], 0)["id"]
        number = routing.verified(accounts, call_token, call_scope)
        routing.ready(accounts, call_scope, call_release)
        Numbers(accounts, routing.NODE).bind(call_token, call_scope, number, call_release, 2)
        Profiles(accounts).update(
            *call_author, call_draft.model_dump() | {"instructions": "İkinci sürüm talimatı."}, 1
        )
        call_second = Releases(accounts).prepare(*call_author, 2)
        Releases(accounts).publish(*call_author, call_second["id"], 1)
        route = routing.initialize(accounts, "browser-history")
        records = CallRecords(isolated, route)

        async def finish_call():
            await records.answered(route.call_id)
            await records.utterance(
                route.call_id,
                "caller-text",
                "caller",
                "<script>window.transcriptInjected=true</script> Sentetik arayan metni.",
            )
            await records.utterance(
                route.call_id, "sent-text", "assistant", "İletilmek üzere not aldım.", sent_ms=800
            )
            await records.utterance(route.call_id, "interrupted-text", "assistant", "", sent_ms=200)
            await records.utterance(route.call_id, "unsent-text", "assistant", "", sent_ms=0)
            for index in range(49):
                await records.utterance(
                    route.call_id, f"continuation-{index}", "caller", f"Sentetik devam {index}."
                )
            await records.note(
                route.call_id,
                Note(
                    subject="Randevu isteği",
                    message='<img src=x onerror="window.callInjected=true"> Sentetik görüşme notu.',
                    confirmed=True,
                ),
                1,
            )
            await records.end(route.call_id, "completed")
            summaries = CallSummaries(isolated)
            claim = await summaries.claim()
            await summaries.finish(claim, summary())
            transport = Transport(Result("delivery_unknown", "send_uncertain"))
            await ActionDelivery(isolated, box).process_one(transport)
            assert len(transport.calls) == 1  # In-memory fake; never sends network requests.

        asyncio.run(finish_call())
        from alojan_agent.store import call_uuid

        ingest(
            isolated,
            routing.NODE,
            [
                line(route.call_id, "timing-1"),
                line(route.call_id, "timing-2", **{key: 300 for key in FIELDS}),
                line(route.call_id, "timing-3", status="interrupted"),
                line(route.call_id, "timing-4", kind="silence_reminder"),
                line(route.call_id, "timing-5", **{key: -1 for key in FIELDS}),
            ],
        )
        call_id = str(call_uuid(route.call_id))
        with psycopg.connect(isolated) as c:
            call_job = str(
                c.execute("SELECT id FROM action_jobs WHERE call_id=%s", (call_id,)).fetchone()[0]
            )
        mcp_fixture = setup_mcp(accounts, owner_password)
        token_login = "mcp.browser@example.test"
        accounts.register(token_login, owner_password, "MCP Browser Owner", peer="token-fixture")
        (work / "fixture.json").write_text(
            json.dumps(
                dict(
                    mcp=mcp_fixture,
                    token_login=token_login,
                    call_job=call_job,
                    call_release=call_release,
                    call_preparation=call_second["id"],
                    call_agent=call_agent,
                    call_login=call_login,
                    call_scope=call_scope,
                    call_id=call_id,
                    login=login,
                    password=owner_password,
                    scope=scope,
                    other_scope=other_scope,
                    agent=agent,
                    instructions=instructions,
                    note_ack=note_ack,
                    connection=connection,
                )
            )
        )
        runtime = make_conninfo(isolated, user=role, password=password)
        (work / "management.env").write_text(
            "ALOJAN_DATABASE_URL="
            + json.dumps(runtime)
            + f"\nALOJAN_PUBLIC_ORIGIN=https://localhost:18443\nALOJAN_MCP_PUBLIC_URL={urlunsplit(('https', 'localhost:18443', '/mcp', '', ''))}\nALOJAN_MANAGEMENT_PORT=18181\nALOJAN_MANAGEMENT_BIND=127.0.0.1\nALOJAN_CREDENTIAL_KEY_FILE=/evidence/provider.key\nALOJAN_VOICE_ASSET_ROOT=/evidence/voice-store\n"
            + f"ALOJAN_VOICE_NODE_ID={routing.NODE}\n"
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(work / "key.pem"),
                "-out",
                str(work / "cert.pem"),
                "-days",
                "2",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mount = ["-v", f"{work}:/evidence"]
        web_mount = [*mount, "-v", f"{ROOT / 'services/web'}:/app", "-w", "/app"]
        start(
            "api",
            os.environ.get("ALOJAN_WEB_MANAGEMENT_IMAGE", MANAGEMENT),
            [
                "uv",
                "run",
                "--frozen",
                "--no-sync",
                "--project",
                "services/app-api",
                "--env-file",
                "/evidence/management.env",
                "python",
                "-m",
                "alojan.api",
            ],
            mounts=mount,
        )
        start(
            "frontend",
            NODE,
            ["npm", "start", "--", "--port", "13001"],
            mounts=web_mount,
            env=["-e", "NEXT_TELEMETRY_DISABLED=1"],
        )
        start("tls", NODE, ["node", "tests/tls-proxy.mjs"], mounts=web_mount)
        for port in (18181, 13001, 18443):
            deadline = time.monotonic() + 25
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Browser validation service failed to start") from None
                    time.sleep(0.2)
        journey = start_journey_fixture(isolated, work)
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=host",
                "--user=1000:1000",
                "--cpus=2",
                "--memory=2g",
                "--shm-size=1g",
                *web_mount,
                "-e",
                "HOME=/tmp",
                "-e",
                "ALOJAN_WEB_TEST_FIXTURE=/evidence/fixture.json",
                BROWSER,
                "npm",
                "test",
            ],
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Browser validation failed; inspect retained synthetic evidence")
        assert not journey[2], "Synthetic fixture failed"
        assert json.loads((work / "journey-stopped.response.json").read_text())["pinned"]
        with psycopg.connect(isolated) as c:
            assert c.execute("SELECT count(*) FROM agent_publications").fetchone()[0] == 3
            assert c.execute("SELECT count(*) FROM number_bindings").fetchone()[0] == 3
            assert c.execute("SELECT count(*) FROM action_jobs").fetchone()[0] == 1
            assert c.execute("SELECT status,attempts FROM action_jobs").fetchone() == (
                "delivery_unknown",
                1,
            )
            assert c.execute("SELECT count(*) FROM action_retry_requests").fetchone()[0] == 1
            assert (
                str(
                    c.execute(
                        "SELECT release_id FROM number_bindings WHERE scope_id=%s", (call_scope,)
                    ).fetchone()[0]
                )
                == call_release
            )
            assert (
                c.execute(
                    "SELECT count(*) FROM agent_releases WHERE profile_id=%s", (call_agent,)
                ).fetchone()[0]
                == 5
            )
            assert (
                c.execute(
                    "SELECT content->>'instructions' FROM agent_drafts WHERE profile_id=%s",
                    (call_agent,),
                ).fetchone()[0]
                == "İkinci sürüm talimatı."
            )
        print(
            json.dumps(
                dict(status="passed", evidence=str(work), production_writes=0, external_sends=0)
            )
        )
    finally:
        if journey:
            journey[0].set()
            journey[1].join(timeout=5)
        for container in reversed(containers):
            subprocess.run(
                ["docker", "rm", "-f", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute(
                psycopg.sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    psycopg.sql.Identifier(schema)
                )
            )
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if exists:
                c.execute(psycopg.sql.SQL("DROP ROLE {}").format(psycopg.sql.Identifier(role)))


if __name__ == "__main__":
    validate()
