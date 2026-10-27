"""Real local files and bounded preloading; synthetic tones, never EMA evidence."""

import asyncio
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
import shutil
import threading
from types import SimpleNamespace
import uuid
import wave

import pytest

from alojan_agent import prepared as module
from alojan_agent.prepared import PreloadError, PreparedReleases
from alojan_contracts.assets import VoiceFile, validate_wav
from alojan_contracts.configuration import AgentDraft, EnginePreset, canonical_digest
from test_agent_releases import pack


def release(tmp_path, *, scope=None, name="Synthetic", owner="Example Owner"):
    scope, rid = scope or str(uuid.uuid4()), str(uuid.uuid4())
    draft = AgentDraft(
        agent_name=name,
        owner_display_name=owner,
        owner_address=owner,
        owner_dative=owner,
        owner_genitive=owner,
        instructions="Collect messages.",
    )
    preset = EnginePreset()
    source = pack(tmp_path, draft)
    voice = json.loads((source / "manifest.json").read_text())
    # Different synthetic identities have distinct PCM, so wrong-pack selection is observable.
    marker = int.from_bytes(hashlib.sha256((name + owner).encode()).digest()[:2], "little") % 16000
    for kind in ("greeting", "unavailable"):
        path = source / (kind + ".wav")
        with wave.open(str(path), "rb") as wav:
            params, pcm = wav.getparams(), bytearray(wav.readframes(wav.getnframes()))
        start = preset.greeting_pad_ms * 16 if kind == "greeting" else 0
        pcm[start : start + 2] = marker.to_bytes(2, "little")
        with wave.open(str(path), "wb") as wav:
            wav.setparams(params)
            wav.writeframes(pcm)
        voice[kind]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (source / "manifest.json").write_text(json.dumps(voice))
    manifest = {
        "schema_version": 1,
        "content": draft.model_dump(),
        "model": {
            "id": draft.model,
            "revision": 1,
            "display_name": "Synthetic model",
            "preset_id": "test",
            "preset_revision": 1,
            "preset": preset.model_dump(),
            "preset_digest": canonical_digest(preset.model_dump()),
        },
        "voice_assets": voice,
    }
    target = tmp_path / "store" / scope / voice["speech_digest"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    route = SimpleNamespace(
        scope_id=scope, release_id=rid, manifest_digest=canonical_digest(manifest)
    )
    return route, json.dumps(manifest), target


async def preload(cache, fixture):
    route, manifest, _ = fixture
    return await cache.preload(route.scope_id, route.release_id, manifest, route.manifest_digest)


def test_exact_pcm_identity_and_call_pinning_survive_disk_change(tmp_path):
    first = release(tmp_path, name="First", owner="First Owner")
    second = release(tmp_path, name="Second", owner="Second Owner")

    async def run():
        cache = PreparedReleases(tmp_path / "store", max_entries=1)
        saved = await preload(cache, first)
        call = cache.pin(first[0])
        assert saved is call and call.runtime.name == "First"
        assert "Second Owner" not in call.runtime.instructions
        assert len(call.greeting_pcm) == 22400 and len(call.unavailable_pcm) == 16000
        assert call.greeting_pcm[:6400] == bytes(6400) and any(call.greeting_pcm[6400:])
        with pytest.raises(FrozenInstanceError):
            call.greeting_pcm = b""
        (first[2] / "greeting.wav").write_bytes(b"corrupt")
        assert await preload(cache, first) is call
        with pytest.raises(PreloadError, match="capacity"):
            await preload(cache, second)
        assert cache.pin(first[0]) is call and len(cache.entries) == 1
        cache.unpin(call)
        cache.unpin(call)
        assert not cache.pins
        next_release = await preload(cache, second)
        assert next_release.greeting_pcm != call.greeting_pcm
        assert next_release.unavailable_pcm != call.unavailable_pcm
        with pytest.raises(PreloadError, match="not_preloaded"):
            cache.pin(first[0])
        assert call.greeting_pcm == saved.greeting_pcm
        assert cache.payload_bytes <= cache.max_bytes
        await cache.close()
        assert not cache.entries and not cache.pending and cache.payload_bytes == 0

    asyncio.run(run())


def test_equal_text_in_different_workspaces_never_shares_or_falls_back(tmp_path):
    one, two = release(tmp_path), release(tmp_path)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        a, b = await asyncio.gather(preload(cache, one), preload(cache, two))
        assert a is not b and a.key[0] != b.key[0]
        assert a.greeting_pcm is not b.greeting_pcm
        unknown = SimpleNamespace(**vars(one[0]))
        unknown.scope_id = str(uuid.uuid4())
        with pytest.raises(PreloadError, match="not_preloaded"):
            cache.pin(unknown)
        unknown.scope_id = "../../etc"
        with pytest.raises(PreloadError, match="identity"):
            cache.pin(unknown)
        await cache.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "bytes",
        "manifest",
        "scope_symlink",
        "pack_symlink",
        "file_symlink",
        "fifo",
        "oversize",
    ],
)
def test_untrusted_or_incomplete_pack_never_enters_cache(tmp_path, damage):
    fixture = release(tmp_path)
    target = fixture[2]
    wav = target / "greeting.wav"
    if damage == "missing":
        wav.unlink()
    elif damage == "bytes":
        wav.write_bytes(b"corrupt")
    elif damage == "manifest":
        value = json.loads((target / "manifest.json").read_text())
        value["greeting"]["sha256"] = "0" * 64
        (target / "manifest.json").write_text(json.dumps(value))
    elif damage == "oversize":
        wav.write_bytes(b"x" * 500001)
    elif damage == "fifo":
        wav.unlink()
        os.mkfifo(wav)
    else:
        path = (
            target.parent
            if damage == "scope_symlink"
            else target
            if damage == "pack_symlink"
            else wav
        )
        moved = tmp_path / "outside"
        path.rename(moved)
        path.symlink_to(moved, target_is_directory=moved.is_dir())

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with pytest.raises(PreloadError, match="^prepared_release_invalid$"):
            await preload(cache, fixture)
        assert not cache.entries and not cache.pending and cache.payload_bytes == 0
        await cache.close()

    asyncio.run(run())


def test_cancelled_preload_stays_bounded_and_coalesces_until_worker_finishes(tmp_path, monkeypatch):
    one, two, three = (release(tmp_path, name=n) for n in ("First", "Second", "Third"))
    started, finish = threading.Event(), threading.Event()
    original = module.load_prepared
    count = 0
    lock = threading.Lock()

    def blocked(*args):
        nonlocal count
        with lock:
            count += 1
            if count == 2:
                started.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(module, "load_prepared", blocked)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        a = asyncio.create_task(preload(cache, one))
        b = asyncio.create_task(preload(cache, two))
        duplicate = asyncio.create_task(preload(cache, one))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            a.cancel()
            with pytest.raises(asyncio.CancelledError):
                await a
            assert len(cache.pending) == 2 and count == 2
            with pytest.raises(PreloadError, match="busy"):
                await preload(cache, three)
            assert not cache.entries
            finish.set()
            first, second = await asyncio.gather(duplicate, b)
            assert first.key != second.key and count == 2
            assert not cache.pending
        finally:
            finish.set()
            await cache.close()

    asyncio.run(run())


def test_single_entry_over_payload_budget_is_rejected(tmp_path):
    one = release(tmp_path)

    async def run():
        cache = PreparedReleases(tmp_path / "store", max_bytes=1)
        with pytest.raises(PreloadError, match="capacity"):
            await preload(cache, one)
        assert not cache.entries and cache.payload_bytes == 0
        await cache.close()

    asyncio.run(run())


@pytest.mark.parametrize("damage", ["riff_size", "trailing", "chunk_size"])
def test_matching_digest_does_not_hide_malformed_wav_container(tmp_path, damage):
    fixture = release(tmp_path)
    data = bytearray((fixture[2] / "greeting.wav").read_bytes())
    if damage == "riff_size":
        data[4:8] = (len(data) + 100).to_bytes(4, "little")
    elif damage == "trailing":
        data += b"extra"
        data[4:8] = (len(data) - 8).to_bytes(4, "little")
    else:
        data[16:20] = (len(data) + 100).to_bytes(4, "little")
    expected = VoiceFile(
        sha256=hashlib.sha256(data).hexdigest(), text_sha256="0" * 64, samples=11200
    )
    with pytest.raises(ValueError, match="WAV"):
        validate_wav(bytes(data), expected, leading_silence_ms=400)


def test_failed_larger_load_preserves_existing_unpinned_entry(tmp_path):
    one = release(tmp_path, name="Small")
    two = release(tmp_path, name="Much Larger Assistant Name")

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        saved = await preload(cache, one)
        cache.max_bytes = saved.payload_bytes
        with pytest.raises(PreloadError, match="capacity"):
            await preload(cache, two)
        assert list(cache.entries) == [saved.key]
        assert cache.payload_bytes == saved.payload_bytes
        assert cache.pin(one[0]) is saved
        cache.unpin(saved)
        await cache.close()

    asyncio.run(run())


def test_shutdown_during_load_prevents_late_installation(tmp_path, monkeypatch):
    fixture = release(tmp_path)
    started, finish = threading.Event(), threading.Event()
    original = module.load_prepared

    def blocked(*args):
        started.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(module, "load_prepared", blocked)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        waiting = asyncio.create_task(preload(cache, fixture))
        closing = None
        try:
            assert await asyncio.to_thread(started.wait, 2)
            closing = asyncio.create_task(cache.close())
            await asyncio.sleep(0)
            assert cache.closed and not closing.done()
            finish.set()
            with pytest.raises(PreloadError, match="closed"):
                await waiting
            await closing
            assert not cache.entries and not cache.pending and cache.payload_bytes == 0
            with pytest.raises(PreloadError, match="closed"):
                await preload(cache, fixture)
        finally:
            finish.set()
            await asyncio.gather(waiting, *([closing] if closing else []), return_exceptions=True)

    asyncio.run(run())


def test_corrupt_release_digest_never_opens_asset_files(tmp_path, monkeypatch):
    fixture = release(tmp_path)
    fixture[0].manifest_digest = "0" * 64

    def forbidden(*args, **kwargs):
        raise AssertionError("An invalid release must fail before opening files")

    monkeypatch.setattr(module.os, "open", forbidden)

    async def run():
        cache = PreparedReleases(tmp_path / "store")
        with pytest.raises(PreloadError, match="prepared_release_invalid"):
            await preload(cache, fixture)
        assert not cache.entries
        await cache.close()

    asyncio.run(run())
