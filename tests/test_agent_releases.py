import hashlib
import io
import json
import math
import struct
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from starlette.testclient import TestClient

import test_native_auth
from alojan.api import create_app
from alojan.auth import AuthError, connection
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan.voice_assets import import_pack
from alojan_contracts.assets import speech_identity
from alojan_contracts.configuration import EnginePreset, canonical_digest
from test_agent_drafts import content
from test_native_auth import ORIGIN, PASSWORD, register

accounts = test_native_auth.accounts
database = test_native_auth.database


def qualify(accounts, *, enabled=True, calibration=None, output=None):
    preset = EnginePreset(calibration=calibration, output=output).model_dump()
    with connection(accounts.dsn) as conn:
        conn.execute(
            "INSERT INTO engine_presets(id,revision,configuration,digest) VALUES ('test-preset',1,%s,%s)",
            (Jsonb(preset), canonical_digest(preset)),
        )
        conn.execute(
            """INSERT INTO model_catalog(id,revision,display_name,preset_id,preset_revision)
            VALUES ('gpt-oss-120b-cerebras',1,'Synthetic qualification','test-preset',1)"""
        )
        conn.execute(
            """INSERT INTO model_catalog_status(model_id,model_revision,enabled,qualification_ref)
            VALUES ('gpt-oss-120b-cerebras',1,%s,'isolated-test-only')""",
            (enabled,),
        )


@pytest.fixture
def author(accounts):
    qualify(accounts)
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    agent = Profiles(accounts).create(token, scope, content())
    return token, scope, agent["id"]


def pack(tmp_path, draft, preset=None):
    """Synthetic tones validate storage/parsing only; never model readiness."""
    preset = preset or EnginePreset()
    path = tmp_path / uuid.uuid4().hex
    path.mkdir()
    manifest = {
        "schema_version": 1,
        "model": "canberkkkkkk/ema-lightning",
        "model_revision": preset.voice_model_revision,
        "speech_digest": speech_identity(draft, preset),
        "sample_rate_hz": 8000,
        "greeting_pad_ms": preset.greeting_pad_ms,
    }
    for name, text in draft.speech_texts().items():
        pad = preset.greeting_pad_ms * 8 if name == "greeting" else 0
        pcm = bytes(pad * 2) + b"".join(
            struct.pack("<h", int(4000 * math.sin(i * 0.2))) for i in range(8000)
        )
        stream = io.BytesIO()
        with wave.open(stream, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(pcm)
        data = stream.getvalue()
        (path / f"{name}.wav").write_bytes(data)
        manifest[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "samples": len(pcm) // 2,
        }
    (path / "manifest.json").write_text(json.dumps(manifest))
    return path


def prepare_assets(accounts, author, tmp_path, version=1):
    token, scope, agent = author
    preparation = Releases(accounts).prepare(token, scope, agent, version)
    draft = validate_draft(Profiles(accounts).get(token, scope, agent)["content"])
    source = pack(tmp_path, draft)
    target = import_pack(accounts.dsn, scope, preparation["id"], source, tmp_path / "store")
    return preparation, source, target


def test_preset_limits_match_consumer_bounds():
    for overrides in (
        {"max_call_seconds": 3600},
        {"answer_delay_ms": 30000},
        {"reply_max_chars": 1000},
        {"llm_timeout_seconds": 20, "turn_timeout_seconds": 10},
        {"raw_recording_enabled": True},
        {"base_url": "http://localhost"},
        {"temperature": float("nan")},
        {"unreviewed_knob": 1},
    ):
        with pytest.raises(ValidationError):
            EnginePreset(**overrides)


def test_speech_identity_changes_only_with_voice_inputs():
    first = validate_draft(content())
    preset = EnginePreset()
    assert speech_identity(first, preset) != speech_identity(
        validate_draft(content("Renamed")), preset
    )
    changed = first.model_copy(update={"instructions": "Another business instruction"})
    assert first.digest() != changed.digest()
    assert speech_identity(first, preset) == speech_identity(changed, preset)
    assert speech_identity(first, preset) != speech_identity(
        first, EnginePreset(greeting_pad_ms=200)
    )


def test_prepare_requires_qualified_model_and_latest_draft(accounts):
    token = register(accounts)
    scope = accounts.session(token)["workspaces"][0]["id"]
    agent = Profiles(accounts).create(token, scope, content())["id"]
    releases = Releases(accounts)
    with pytest.raises(AuthError, match="model_not_qualified"):
        releases.prepare(token, scope, agent, 1)
    qualify(accounts, enabled=False)
    with pytest.raises(AuthError, match="model_not_qualified"):
        releases.prepare(token, scope, agent, 1)
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE model_catalog_status SET enabled=true")
    with pytest.raises(AuthError, match="stale_version"):
        releases.prepare(token, scope, agent, 2)
    one = releases.prepare(token, scope, agent, 1)
    assert one == releases.prepare(token, scope, agent, 1)
    assert one["readiness"] == "voice_assets_pending"
    with pytest.raises(AuthError, match="voice_assets_pending"):
        releases.publish(token, scope, agent, one["id"], 0)
    assert releases.list(token, scope, agent)["releases"] == []


def test_publish_and_rollback_preserve_snapshots_and_current_draft(accounts, author, tmp_path):
    token, scope, agent = author
    releases = Releases(accounts)
    preparation, source, target = prepare_assets(accounts, author, tmp_path)
    assert import_pack(accounts.dsn, scope, preparation["id"], source, tmp_path / "store") == target
    assert releases.prepare(token, scope, agent, 1)["readiness"] == "ready_to_publish"
    first = releases.publish(token, scope, agent, preparation["id"], 0)
    with connection(accounts.dsn) as conn:
        original = conn.execute(
            "SELECT manifest FROM agent_releases WHERE id=%s", (first["id"],)
        ).fetchone()[0]
    Profiles(accounts).update(token, scope, agent, content("Renamed"), 1)
    with pytest.raises(AuthError, match="stale_preparation"):
        releases.publish(token, scope, agent, preparation["id"], 1)
    second, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    assert second["speech_digest"] != preparation["speech_digest"]
    releases.publish(token, scope, agent, second["id"], 1)
    restored = releases.rollback(token, scope, agent, first["id"], 2)
    assert restored["revision"] == 3
    assert Profiles(accounts).get(token, scope, agent)["content"]["agent_name"] == "Renamed"
    assert releases.list(token, scope, agent)["releases"][0]["rollback_of"] == first["id"]
    with connection(accounts.dsn) as conn:
        assert (
            conn.execute(
                "SELECT manifest FROM agent_releases WHERE id=%s", (restored["id"],)
            ).fetchone()[0]
            == original
        )
        assert (
            conn.execute(
                "SELECT manifest FROM agent_releases WHERE id=%s", (first["id"],)
            ).fetchone()[0]
            == original
        )
        assert (
            conn.execute("SELECT enabled FROM assistant_profiles WHERE id=%s", (agent,)).fetchone()[
                0
            ]
            is False
        )
        assert conn.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE agent_releases SET manifest='{}' WHERE id=%s", (first["id"],))


def test_parallel_publish_has_one_winner(accounts, author, tmp_path):
    token, scope, agent = author
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)

    another_session = accounts.login("test.owner", PASSWORD, peer="127.0.0.1")

    def publish(session_token):
        try:
            return Releases(accounts).publish(session_token, scope, agent, preparation["id"], 0)[
                "status"
            ]
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(publish, [token, another_session])) == [
            "published",
            "stale_publication",
        ]
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM agent_releases").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM assistant_profile_revisions").fetchone()[0] == 1


def test_wrong_scope_profile_and_editor_cannot_publish(accounts, author, tmp_path):
    token, scope, agent = author
    releases = Releases(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    other_token = register(accounts, "other.owner")
    other_scope = accounts.session(other_token)["workspaces"][0]["id"]
    other = Profiles(accounts).create(other_token, other_scope, content())["id"]
    other_preparation = releases.prepare(other_token, other_scope, other, 1)
    assert other_preparation["speech_digest"] == preparation["speech_digest"]
    assert other_preparation["readiness"] == "voice_assets_pending"
    with pytest.raises(AuthError, match="voice_assets_pending"):
        releases.publish(other_token, other_scope, other, other_preparation["id"], 0)
    with pytest.raises(AuthError, match="not_found"):
        releases.publish(other_token, other_scope, other, preparation["id"], 0)
    with pytest.raises(AuthError, match="not_found"):
        releases.list(other_token, scope, agent)
    same_workspace = Profiles(accounts).create(token, scope, content())["id"]
    with pytest.raises(AuthError, match="not_found"):
        releases.publish(token, scope, same_workspace, preparation["id"], 0)
    first = releases.publish(token, scope, agent, preparation["id"], 0)
    with pytest.raises(AuthError, match="not_found"):
        releases.rollback(token, scope, same_workspace, first["id"], 0)
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE workspace_memberships SET role='editor' WHERE scope_id=%s", (scope,))
    assert releases.prepare(token, scope, agent, 1)["id"] == preparation["id"]
    with pytest.raises(AuthError, match="forbidden"):
        releases.publish(token, scope, agent, preparation["id"], 1)
    with pytest.raises(AuthError, match="forbidden"):
        releases.rollback(token, scope, agent, first["id"], 1)


def test_revoked_model_blocks_publish_and_rollback(accounts, author, tmp_path):
    token, scope, agent = author
    releases = Releases(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    first = releases.publish(token, scope, agent, preparation["id"], 0)
    with connection(accounts.dsn) as conn:
        conn.execute("UPDATE model_catalog_status SET enabled=false")
    with pytest.raises(AuthError, match="model_not_qualified"):
        releases.publish(token, scope, agent, preparation["id"], 1)
    with pytest.raises(AuthError, match="model_not_qualified"):
        releases.rollback(token, scope, agent, first["id"], 1)
    assert releases.list(token, scope, agent)["current_release"] == first["id"]


@pytest.mark.parametrize("damage", ["bytes", "text", "symlink", "rate", "truncated", "silence"])
def test_invalid_pack_never_marks_ready(accounts, author, tmp_path, damage):
    token, scope, agent = author
    preparation = Releases(accounts).prepare(token, scope, agent, 1)
    source = pack(tmp_path, validate_draft(content()))
    wav = source / "greeting.wav"
    manifest = json.loads((source / "manifest.json").read_text())
    if damage == "symlink":
        wav.rename(source / "other.wav")
        wav.symlink_to(source / "other.wav")
    elif damage == "text":
        manifest["greeting"]["text_sha256"] = "0" * 64
    else:
        data = bytearray(wav.read_bytes())
        if damage == "bytes":
            data[-1] ^= 1
        elif damage == "rate":
            data[24:28] = struct.pack("<I", 16000)
        elif damage == "truncated":
            data = data[:-100]
        else:
            data[44:] = bytes(len(data) - 44)
        wav.write_bytes(data)
        if damage != "bytes":
            manifest["greeting"]["sha256"] = hashlib.sha256(data).hexdigest()
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        import_pack(accounts.dsn, scope, preparation["id"], source, tmp_path / "store")
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT count(*) FROM prepared_voice_assets").fetchone()[0] == 0


def test_release_http_contract(accounts, tmp_path):
    qualify(accounts)
    with TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client:
        response = client.post(
            "/v1/auth/register",
            json={"login": "http.owner", "password": PASSWORD, "display_name": "Synthetic Owner"},
            headers={"Origin": ORIGIN},
        )
        session = response.json()
        scope = session["workspaces"][0]["id"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
        base = f"/v1/workspaces/{scope}"
        models = client.get(base + "/models").json()["models"]
        assert models[0]["id"] == "gpt-oss-120b-cerebras" and "preset" not in models[0]
        agent = client.post(base + "/agents", json=content(), headers=headers).json()["id"]
        url = base + f"/agents/{agent}"
        assert client.post(url + "/prepare", json={}, headers=headers).status_code == 428
        preparation = client.post(
            url + "/prepare", json={}, headers={**headers, "If-Match": '"1"'}
        ).json()
        source = pack(tmp_path, validate_draft(content()))
        import_pack(accounts.dsn, scope, preparation["id"], source, tmp_path / "store")
        assert client.get(url + "/releases").headers["etag"] == '"0"'
        assert (
            client.post(
                url + "/publish",
                json={"preparation_id": preparation["id"]},
                headers={**headers, "If-Match": '"0"'},
            ).status_code
            == 201
        )
        assert (
            client.post(
                url + "/rollback",
                json={"release_id": "bad"},
                headers={**headers, "If-Match": '"1"'},
            ).status_code
            == 400
        )
        assert (
            client.post(
                url + "/prepare", json={"engine": {}}, headers={**headers, "If-Match": '"1"'}
            ).status_code
            == 400
        )


def test_release_tables_enforce_workspace_rls_for_non_owner(accounts, author, tmp_path):
    token, scope, agent = author
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    Releases(accounts).publish(token, scope, agent, preparation["id"], 0)
    role = psycopg.sql.Identifier("test_release_" + uuid.uuid4().hex)
    tables = ("agent_preparations", "prepared_voice_assets", "agent_releases", "agent_publications")
    with connection(accounts.dsn) as conn:
        schema = psycopg.sql.Identifier(conn.execute("SELECT current_schema()").fetchone()[0])
        conn.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
        conn.execute(psycopg.sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, role))
        conn.execute(
            psycopg.sql.SQL("GRANT SELECT,UPDATE ON {} TO {}").format(
                psycopg.sql.SQL(",").join(map(psycopg.sql.Identifier, tables)),
                role,
            )
        )
    try:
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("SET LOCAL ROLE {}").format(role))
            for table in tables:
                query = psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                    psycopg.sql.Identifier(table)
                )
                assert conn.execute(query).fetchone()[0] == 0
            conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (scope,))
            for table in tables:
                query = psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                    psycopg.sql.Identifier(table)
                )
                assert conn.execute(query).fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute("UPDATE agent_publications SET scope_id=%s", (uuid.uuid4(),))
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("SET LOCAL ROLE {}").format(role))
            assert conn.execute("SELECT count(*) FROM agent_releases").fetchone()[0] == 0
    finally:
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("DROP OWNED BY {}").format(role))
            conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(role))


def test_management_role_can_publish_but_not_qualify_models_or_invent_assets(accounts, tmp_path):
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from alojan.auth import Accounts
    from alojan.roles import grant_management

    qualify(accounts)
    role_name = "test_api_" + uuid.uuid4().hex
    role = psycopg.sql.Identifier(role_name)
    with connection(accounts.dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
    try:
        grant_management(accounts.dsn, role_name)
        options = conninfo_to_dict(accounts.dsn)["options"] + f" -c role={role_name}"
        limited = Accounts(make_conninfo(accounts.dsn, options=options))
        assert limited.ready()
        token = register(limited)
        scope = limited.session(token)["workspaces"][0]["id"]
        agent = Profiles(limited).create(token, scope, content())["id"]
        preparation = Releases(limited).prepare(token, scope, agent, 1)
        import_pack(
            accounts.dsn,
            scope,
            preparation["id"],
            pack(tmp_path, validate_draft(content())),
            tmp_path / "store",
        )
        assert (
            Releases(limited).publish(token, scope, agent, preparation["id"], 0)["status"]
            == "published"
        )
        limited.change_password(token, PASSWORD, "another synthetic password", peer="127.0.0.1")
        limited.cleanup()
        for query in (
            "UPDATE model_catalog_status SET enabled=true",
            "UPDATE assistant_profiles SET enabled=true",
            "UPDATE workspace_memberships SET role='owner'",
            "UPDATE users SET enabled=true",
            "INSERT INTO prepared_voice_assets SELECT * FROM prepared_voice_assets",
            "INSERT INTO engine_presets SELECT * FROM engine_presets",
            "SELECT * FROM calls",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connection(limited.dsn) as conn:
                    conn.execute(query)
    finally:
        with connection(accounts.dsn) as conn:
            conn.execute(psycopg.sql.SQL("DROP OWNED BY {}").format(role))
            conn.execute(psycopg.sql.SQL("DROP ROLE {}").format(role))


def test_catalog_example_is_repeatable_disabled_and_integrity_checked(accounts):
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "infra/examples/agent_catalog.sql"
    with connection(accounts.dsn) as conn:
        conn.execute(source.read_text())
        conn.execute(source.read_text())
        row = conn.execute("SELECT configuration,digest FROM engine_presets").fetchone()
        assert canonical_digest(EnginePreset.model_validate(row[0]).model_dump()) == row[1]
        assert conn.execute("SELECT enabled FROM model_catalog_status").fetchone()[0] is False
        assert conn.execute("SELECT count(*) FROM engine_presets").fetchone()[0] == 1
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE engine_presets SET configuration='{}'")


def test_assets_must_leave_room_for_closing(tmp_path):
    from alojan_contracts.assets import validate_manifest

    draft = validate_draft(content())
    preset = EnginePreset(max_call_seconds=10)
    source = pack(tmp_path, draft, preset)
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["greeting"]["samples"] = 56000
    with pytest.raises(ValueError, match="no time for conversation"):
        validate_manifest(manifest, draft, preset)


@pytest.mark.parametrize(
    "example,revision", [("agent_calibration.sql", 2), ("agent_output.sql", 3)]
)
def test_operator_catalog_revision_preserves_historical_preset(accounts, example, revision):
    from pathlib import Path
    from alojan_contracts.configuration import NativeCalibration, OutputBudget

    examples = Path(__file__).resolve().parents[1] / "infra/examples"
    with connection(accounts.dsn) as conn:
        conn.execute((examples / "agent_catalog.sql").read_text())
        original = conn.execute(
            "SELECT configuration,digest FROM engine_presets WHERE revision=1"
        ).fetchone()
        conn.execute((examples / example).read_text())
        conn.execute((examples / example).read_text())
        assert (
            conn.execute(
                "SELECT configuration,digest FROM engine_presets WHERE revision=1"
            ).fetchone()
            == original
        )
        rows = conn.execute(
            "SELECT revision,configuration,digest FROM engine_presets ORDER BY revision"
        ).fetchall()
        assert len(rows) == 2
        for _, configuration, digest in rows:
            engine = EnginePreset.model_validate(configuration)
            assert canonical_digest(engine.model_dump()) == digest
        assert rows[1][0] == revision
        engine = EnginePreset.model_validate(rows[1][1])
        if revision == 2:
            assert engine.calibration == NativeCalibration(partial_hint=True)
        else:
            assert engine.output == OutputBudget(
                phrase_max_chars=120, phrase_max_bytes=480, max_phrases=8
            )
        assert (
            conn.execute("SELECT count(*) FROM model_catalog_status WHERE enabled").fetchone()[0]
            == 0
        )
