"""Private disposable-schema browser fixture bridge; never loaded by the application."""

import asyncio
import json
import threading
import uuid

import psycopg

from alojan.auth import Accounts
from alojan.number_verification import decide
from alojan.voice_worker import run_one
from alojan_agent.routing import CallRouter, RoutingError
from test_voice_jobs import Window, synthetic
from test_number_routing import ready, NODE


def start_journey_fixture(dsn, work):
    stop = threading.Event()
    failures = []

    def serve():
        for stage in ("audio", "verify", "ready", "pin", "stopped"):
            request = work / f"journey-{stage}.request.json"
            while not stop.wait(0.1):
                if request.exists():
                    break
            else:
                return
            try:
                data = json.loads(request.read_text())
                scope, agent = uuid.UUID(data["scope"]), uuid.UUID(data["agent"])
                with psycopg.connect(dsn) as conn:
                    assert (
                        conn.execute("SELECT current_schema()")
                        .fetchone()[0]
                        .startswith("test_web_")
                    )
                    assert conn.execute(
                        """SELECT 1 FROM assistant_profiles p
                        JOIN workspace_memberships m ON m.scope_id=p.scope_id
                        JOIN users u ON u.id=m.user_id
                        WHERE p.scope_id=%s AND p.id=%s AND m.role='owner'
                        AND u.login='journey.owner@example.test'""",
                        (scope, agent),
                    ).fetchone()
                result = {"stage": stage, "synthetic": True}
                if stage == "audio":
                    with psycopg.connect(dsn) as conn:
                        jobs = conn.execute(
                            "SELECT scope_id,profile_id FROM voice_preparation_jobs WHERE status='queued'"
                        ).fetchall()
                        assert jobs == [(scope, agent)]
                    window = Window()
                    assert run_one(dsn, work / "voice-store", window, "unused", generator=synthetic)
                    assert window.entered == 1
                    with psycopg.connect(dsn) as conn:
                        assert (
                            conn.execute(
                                "SELECT status FROM voice_preparation_jobs WHERE scope_id=%s AND profile_id=%s",
                                (scope, agent),
                            ).fetchone()[0]
                            == "ready"
                        )
                elif stage == "verify":
                    with psycopg.connect(dsn) as conn:
                        number = conn.execute(
                            "SELECT id,version,status,enabled FROM phone_numbers WHERE scope_id=%s",
                            (scope,),
                        ).fetchone()
                    assert number and number[2:] == ("pending", False)
                    decide(
                        dsn,
                        scope,
                        number[0],
                        number[1],
                        "synthetic-browser-operator",
                        ownership="synthetic-account-proof",
                        routing="synthetic-routing-proof",
                    )
                else:
                    release = uuid.UUID(data["release"])
                    with psycopg.connect(dsn) as conn:
                        assert conn.execute(
                            "SELECT 1 FROM agent_releases WHERE scope_id=%s AND profile_id=%s AND id=%s",
                            (scope, agent, release),
                        ).fetchone()
                    if stage == "ready":
                        # Synthetic readiness only, never a GPU/carrier acceptance claim.
                        ready(Accounts(dsn), scope, release)
                    else:
                        with psycopg.connect(dsn) as conn:
                            did = conn.execute(
                                "SELECT e164 FROM phone_numbers WHERE scope_id=%s",
                                (scope,),
                            ).fetchone()[0]
                        route = asyncio.run(
                            CallRouter(dsn, NODE).initialize(
                                "synthetic-browser-journey", did, "request_uri"
                            )
                        )
                        assert (route.scope_id, route.profile_id, route.release_id) == (
                            str(scope),
                            str(agent),
                            str(release),
                        )
                        result["pinned"] = True
                        if stage == "stopped":
                            assert (
                                "Sonraki sürüm için değiştirilen talimat" not in route.manifest_json
                            )
                            try:
                                asyncio.run(
                                    CallRouter(dsn, NODE).initialize(
                                        "synthetic-browser-after-stop", did, "request_uri"
                                    )
                                )
                            except RoutingError as exc:
                                assert exc.code == "number_not_routed"
                            else:
                                raise AssertionError("Stopped number admitted a new call")
                (work / f"journey-{stage}.response.json").write_text(json.dumps(result))
            except Exception as exc:
                failures.append(type(exc).__name__)
                (work / f"journey-{stage}.response.json").write_text(
                    json.dumps({"error": type(exc).__name__})
                )
                return

    thread = threading.Thread(target=serve, name="synthetic-browser-journey", daemon=True)
    thread.start()
    return stop, thread, failures
