"""Durable queue boundaries and recovery without GPU or external sends."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import shutil
import uuid

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from starlette.testclient import TestClient

import test_agent_releases
from test_agent_releases import pack, prepare_assets
from test_native_auth import register, ORIGIN
from alojan.auth import Accounts, AuthError, connection, csrf_token
from alojan.api import create_app, COOKIE
from alojan.profiles import Profiles
from alojan.roles import grant_management
from alojan.voice_jobs import VoiceJobs
from alojan.voice_worker import run_one, grant_worker, LOCK_ID
from alojan.voice_window import DockerWindow, WindowError
from alojan.voice_generation import segments

accounts = test_agent_releases.accounts
author = test_agent_releases.author
database = test_agent_releases.database


class Window:
    entered = 0

    @contextmanager
    def reserve(self):
        self.entered += 1
        yield lambda: None


def synthetic(endpoint, preparation, draft, preset, directory, check):
    check()
    source = pack(directory, draft, preset)
    for path in source.iterdir():
        shutil.copyfile(path, directory / path.name)


def test_duplicate_requests_are_one_job_and_ready_pack_never_resynthesizes(
    accounts, author, tmp_path
):
    jobs = VoiceJobs(accounts)
    assert jobs.status(*author, 1)["status"] == "missing"
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda _: jobs.request(*author, 1), range(3)))
    assert all(r["status"] == "queued" for r in results)
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM voice_preparation_jobs").fetchone()[0] == 1
    window = Window()
    assert run_one(accounts.dsn, tmp_path, window, "unused", generator=synthetic)
    assert window.entered == 1
    assert jobs.status(*author, 1)["status"] == "ready"
    assert jobs.request(*author, 1)["status"] == "ready"
    assert not run_one(accounts.dsn, tmp_path, window, "unused", generator=synthetic)
    assert window.entered == 1


def test_stale_foreign_csrf_and_superseded_requests_never_infer(accounts, author, tmp_path):
    token, scope, agent = author
    client = TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN)
    url = f"/v1/workspaces/{scope}/agents/{agent}/voice-preparation"
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 401
    client.cookies.set(COOKIE, register(accounts, "other.audio"))
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 404
    client.cookies.set(COOKIE, token)
    assert client.get(url).status_code == 428
    assert client.get(url, headers={"If-Match": '"2"'}).status_code == 412
    assert (
        client.post(url, json={}, headers={"Origin": ORIGIN, "If-Match": '"1"'}).status_code == 403
    )
    headers = {"Origin": ORIGIN, "If-Match": '"1"', "X-CSRF-Token": csrf_token(token)}
    assert client.post(url, json={}, headers=headers).json()["status"] == "queued"
    draft = Profiles(accounts).get(*author)["content"]
    Profiles(accounts).update(*author, draft | {"agent_name": "Changed"}, 1)
    window = Window()
    assert run_one(accounts.dsn, tmp_path, window, "unused", generator=synthetic)
    assert window.entered == 0
    with connection(accounts.dsn) as conn:
        assert conn.execute(
            "SELECT status,failure_code FROM voice_preparation_jobs"
        ).fetchone() == ("failed", "superseded")
    assert VoiceJobs(accounts).status(*author, 2)["status"] == "missing"


def test_failed_jobs_retry_bounded_and_abandoned_claims_are_not_reclaimed(
    accounts, author, tmp_path
):
    jobs = VoiceJobs(accounts)

    def failure(*args):
        raise ValueError("synthetic generation failure")

    for attempt in range(1, 4):
        assert jobs.request(*author, 1)["attempt"] == attempt
        assert run_one(accounts.dsn, tmp_path, Window(), "unused", generator=failure)
        assert jobs.status(*author, 1)["status"] == "failed"
    with pytest.raises(AuthError, match="voice_preparation_limit"):
        jobs.request(*author, 1)
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE voice_preparation_jobs SET status='preparing' WHERE attempt=3")
    window = Window()
    with pytest.raises(WindowError, match="operator recovery"):
        run_one(accounts.dsn, tmp_path, window, "unused", generator=synthetic)
    assert window.entered == 0


def test_session_lock_excludes_another_worker(accounts, author, tmp_path):
    VoiceJobs(accounts).request(*author, 1)
    with connection(accounts.dsn) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        assert not run_one(accounts.dsn, tmp_path, Window(), "unused", generator=synthetic)


def test_management_cannot_forge_readiness_and_worker_cannot_publish(accounts, author, tmp_path):
    roles = ["test_audio_" + uuid.uuid4().hex for _ in range(2)]
    try:
        with connection(accounts.dsn) as conn:
            for role in roles:
                conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        grant_management(accounts.dsn, roles[0])
        grant_worker(accounts.dsn, roles[1])
        options = conninfo_to_dict(accounts.dsn).get("options", "")
        limited = [
            make_conninfo(accounts.dsn, options=options + " -c role=" + role) for role in roles
        ]
        VoiceJobs(Accounts(limited[0])).request(*author, 1)
        with connection(limited[0]) as conn:
            assert not conn.execute(
                "SELECT has_column_privilege(current_user,'voice_preparation_jobs','status','UPDATE')"
            ).fetchone()[0]
            assert not conn.execute(
                "SELECT has_column_privilege(current_user,'voice_preparation_jobs','status','INSERT')"
            ).fetchone()[0]
        assert run_one(limited[1], tmp_path, Window(), "unused", generator=synthetic)
        assert VoiceJobs(Accounts(limited[0])).status(*author, 1)["status"] == "ready"
        with connection(limited[1]) as conn:
            assert not conn.execute(
                "SELECT has_table_privilege(current_user,'agent_releases','INSERT')"
            ).fetchone()[0]
            assert not conn.execute(
                "SELECT has_column_privilege(current_user,'provider_connections','ciphertext','SELECT')"
            ).fetchone()[0]
    finally:
        with connection(accounts.dsn) as conn:
            for role in roles:
                conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_existing_audio_does_not_create_job(accounts, author, tmp_path):
    prepare_assets(accounts, author, tmp_path)
    assert VoiceJobs(accounts).request(*author, 1)["status"] == "ready"
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM voice_preparation_jobs").fetchone()[0] == 0


def test_segments_preserve_words_and_bound_requests():
    text = "Merhaba. " + ("Uzun bir karşılama metni. " * 40)
    parts = list(segments(text))
    assert len(parts) > 1 and all(0 < len(p) <= 512 for p in parts)
    assert " ".join(parts).split() == text.split()
    with pytest.raises(ValueError):
        list(segments("a" * 513))


def test_interrupted_window_fences_without_reopening(tmp_path):
    paths = {name: tmp_path / name for name in ("gateway", "tts", "asr", "agent")}
    for path in paths.values():
        path.write_bytes(b"open\n")
    window = DockerWindow(
        {
            "control_directory": str(tmp_path / "control"),
            "state_files": {k: str(v) for k, v in paths.items()},
        }
    )
    (tmp_path / "control/active.json").write_text("{}")
    with pytest.raises(WindowError, match="operator recovery"):
        with window.reserve():
            pytest.fail("Interrupted reservation was reused")
    assert all(path.read_bytes() == b"closed\n" for path in paths.values())


class SimulatedWindow(DockerWindow):
    """Exercise orchestration with acknowledged fake processes, never model readiness."""

    restarted = False
    clean = True

    def identity(self, name):
        return (name, 2 if self.restarted else 1)

    def gateway_log(self, since, text):
        return True

    def command(self, *args):
        name = args[-1]
        mode = "open" if self.paths[name].read_bytes() == b"open\n" else "quiescent"
        return "event=worker_maintenance instance=abc mode=" + mode

    def healthy(self, name, maintenance=False):
        return self.clean

    def wait(self, predicate, seconds=150):
        self.check(force=True)
        if not predicate():
            raise WindowError("Missing fresh receipt")
        self.check(force=True)


def window_fixture(tmp_path):
    paths = {name: tmp_path / name for name in ("gateway", "tts", "asr", "agent")}
    for path in paths.values():
        path.write_bytes(b"open\n")
    return SimulatedWindow(
        {
            "control_directory": str(tmp_path / "control"),
            "state_files": {k: str(v) for k, v in paths.items()},
            "containers": {k: k for k in paths},
        }
    )


@pytest.mark.parametrize(
    "failure", ["none", "generation", "restart", "cleanup", "fence", "readiness"]
)
def test_window_opens_only_tts_and_never_reopens_after_lost_receipts(tmp_path, failure):
    window = window_fixture(tmp_path)

    def operation():
        with window.reserve() as check:
            assert {k: p.read_bytes() for k, p in window.paths.items()} == {
                "gateway": b"closed\n",
                "asr": b"closed\n",
                "agent": b"closed\n",
                "tts": b"open\n",
            }
            check(force=True)
            if failure == "generation":
                raise ValueError("synthetic invalid audio")
            if failure == "fence":
                window.paths["agent"].write_bytes(b"open\n")
                check(force=True)
            if failure == "readiness":
                window.resume_ready = lambda: False
            window.restarted = failure == "restart"
            window.clean = failure != "cleanup"

    if failure == "none":
        operation()
    else:
        with pytest.raises(ValueError if failure == "generation" else WindowError):
            operation()
    safe = failure in ("none", "generation")
    assert all(
        p.read_bytes() == (b"open\n" if safe else b"closed\n") for p in window.paths.values()
    )
    assert (window.root / "active.json").exists() != safe


def test_real_grpc_synthetic_generation_releases_lease_and_validates_wav(tmp_path):
    import asyncio
    import json
    from alojan_tts.service import SynthesisService, create_server
    from test_tts import Producer, SYNTHETIC_PROFILE
    from test_agent_drafts import content
    from alojan.profiles import validate_draft
    from alojan_contracts.configuration import EnginePreset
    from alojan_contracts.assets import validate_manifest, validate_wav
    from alojan.voice_generation import generate_pack

    async def run():
        backend = Producer()
        backend.synthesis_profile = SYNTHETIC_PROFILE
        backend.chunks = [b"\xe8\x03" * 8000]
        service = SynthesisService(backend, require_agent_release=True)
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        draft = validate_draft(content())
        preset = EnginePreset()
        try:
            await asyncio.to_thread(
                generate_pack,
                f"127.0.0.1:{port}",
                uuid.uuid4(),
                draft,
                preset,
                tmp_path,
                lambda: None,
            )
            manifest = validate_manifest(
                json.loads((tmp_path / "manifest.json").read_text()), draft, preset
            )
            for name in draft.speech_texts():
                validate_wav(
                    (tmp_path / f"{name}.wav").read_bytes(),
                    getattr(manifest, name),
                    leading_silence_ms=preset.greeting_pad_ms if name == "greeting" else 0,
                )
            assert len(backend.calls) == 2
            assert not service.leases and not service.configurations and not service.active
        finally:
            service.close()
            await server.stop(0)

    asyncio.run(run())


def test_pack_installed_before_failed_database_commit_is_recovered_without_gpu(
    accounts, author, tmp_path
):
    import json
    from alojan.voice_assets import install_pack
    from alojan.profiles import validate_draft
    from alojan_contracts.assets import VoiceManifest

    jobs = VoiceJobs(accounts)
    jobs.request(*author, 1)
    draft = validate_draft(Profiles(accounts).get(*author)["content"])
    source = pack(tmp_path, draft)
    manifest = VoiceManifest.model_validate_json((source / "manifest.json").read_bytes())
    store = tmp_path / "store"
    installed = install_pack(
        store,
        author[1],
        manifest,
        {name + ".wav": (source / (name + ".wav")).read_bytes() for name in draft.speech_texts()},
    )
    before = json.loads((installed / "manifest.json").read_text())
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM prepared_voice_assets").fetchone()[0] == 0
    window = Window()

    def unexpected(*args):
        pytest.fail("Previously installed speech was synthesized again")

    assert run_one(accounts.dsn, store, window, "unused", generator=unexpected)
    assert window.entered == 0
    assert jobs.status(*author, 1)["status"] == "ready"
    assert json.loads((installed / "manifest.json").read_text()) == before
