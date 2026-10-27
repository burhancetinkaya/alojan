import uuid

from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.profiles import Profiles
import test_agent_releases
from test_native_auth import ORIGIN, register
from test_agent_releases import prepare_assets

accounts = test_agent_releases.accounts
author = test_agent_releases.author
database = test_agent_releases.database


def test_authenticated_preview_matches_pack_and_rejects_stale_foreign_or_bad_files(
    accounts,
    author,
    tmp_path,
):
    token, scope, agent = author
    _, source, target = prepare_assets(accounts, author, tmp_path)
    client = TestClient(
        create_app(accounts, ORIGIN, voice_asset_root=tmp_path / "store"), base_url=ORIGIN
    )
    url = f"/v1/workspaces/{scope}/agents/{agent}/voice-preview/greeting"
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 401
    client.cookies.set(COOKIE, token)
    response = client.get(url, headers={"If-Match": '"1"'})
    assert response.status_code == 200
    assert response.content == (source / "greeting.wav").read_bytes()
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert client.get(url).status_code == 428
    assert client.get(url, headers={"If-Match": '"2"'}).status_code == 412
    assert (
        client.get(
            url.replace(str(agent), str(uuid.uuid4())), headers={"If-Match": '"1"'}
        ).status_code
        == 404
    )
    other = register(accounts, "other.preview")
    client.cookies.set(COOKIE, other)
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 404
    client.cookies.set(COOKIE, token)
    for clip in ["unavailable", "unknown"]:
        assert client.get(
            url.replace("greeting", clip), headers={"If-Match": '"1"'}
        ).status_code == (200 if clip == "unavailable" else 404)
    (target / "greeting.wav").write_bytes(b"not a WAV")
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 503
    (target / "greeting.wav").unlink()
    (target / "greeting.wav").symlink_to(source / "greeting.wav")
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 503
    (target / "greeting.wav").unlink()
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 503


def test_missing_or_changed_speech_never_plays_old_audio(accounts, author, tmp_path):
    token, scope, agent = author
    client = TestClient(
        create_app(accounts, ORIGIN, voice_asset_root=tmp_path / "store"), base_url=ORIGIN
    )
    client.cookies.set(COOKIE, token)
    url = f"/v1/workspaces/{scope}/agents/{agent}/voice-preview/greeting"
    assert client.get(url, headers={"If-Match": '"1"'}).json() == {"error": "voice_assets_pending"}
    prepare_assets(accounts, author, tmp_path)
    profiles = Profiles(accounts)
    draft = profiles.get(token, scope, agent)["content"]
    profiles.update(token, scope, agent, draft | {"greeting_text": "Yeni karşılama."}, 1)
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 412
    assert client.get(url, headers={"If-Match": '"2"'}).json() == {"error": "voice_assets_pending"}
    disabled = TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN)
    disabled.cookies.set(COOKIE, token)
    assert disabled.get(url, headers={"If-Match": '"2"'}).status_code == 503


def test_waiting_preview_is_release_content_bound_and_requires_preparation(
    accounts, author, tmp_path
):
    token, scope, agent = author
    profiles = Profiles(accounts)
    draft = profiles.get(token, scope, agent)["content"]
    client = TestClient(
        create_app(accounts, ORIGIN, voice_asset_root=tmp_path / "store"), base_url=ORIGIN
    )
    client.cookies.set(COOKIE, token)
    url = f"/v1/workspaces/{scope}/agents/{agent}/voice-preview/waiting"
    assert client.get(url, headers={"If-Match": '"1"'}).status_code == 404
    draft["response_experience"] = {"enabled": True}
    profiles.update(token, scope, agent, draft, 1)
    _, source, _ = prepare_assets(accounts, author, tmp_path, version=2)
    response = client.get(url, headers={"If-Match": '"2"'})
    assert response.status_code == 200
    assert response.content == (source / "waiting.wav").read_bytes()
    draft["response_experience"] = {"enabled": True, "waiting_text": "Kontrol ediyorum."}
    profiles.update(token, scope, agent, draft, 2)
    assert client.get(url, headers={"If-Match": '"3"'}).json() == {"error": "voice_assets_pending"}
