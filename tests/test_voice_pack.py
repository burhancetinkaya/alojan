"""Verify reuse of the retained EMA artifacts, without inference or database writes."""

import hashlib
import json
from pathlib import Path
import shutil
import uuid

import pytest

from alojan.voice_pack import prepare_existing_pack
from alojan_contracts.assets import validate_manifest, validate_wav
from alojan_contracts.configuration import AgentDraft, EnginePreset

SOURCE = Path(__file__).resolve().parents[1] / "assets/prompts/tr-v5-kubra"


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    draft = AgentDraft(
        agent_name="Kübra",
        owner_display_name="Burhan",
        owner_address="Burhan Bey",
        owner_dative="Burhan Bey'e",
        owner_genitive="Burhan Bey’in",
        instructions="Take confirmed messages.",
    )
    return draft, EnginePreset(), source, tmp_path / "store", str(uuid.uuid4())


def test_existing_audio_is_byte_identical_and_repeatable(case):
    draft, preset, source, store, scope = case
    target = prepare_existing_pack(*case)
    assert prepare_existing_pack(*case) == target
    manifest = validate_manifest(json.loads((target / "manifest.json").read_text()), draft, preset)
    for name in ("greeting", "unavailable"):
        data = (target / f"{name}.wav").read_bytes()
        assert data == (source / f"{name}.wav").read_bytes()
        validate_wav(
            data, getattr(manifest, name), leading_silence_ms=400 if name == "greeting" else 0
        )
    other = prepare_existing_pack(draft, preset, source, store, uuid.uuid4())
    assert other != target and other.name == target.name


@pytest.mark.parametrize(
    "mutation",
    ["text", "audio", "revision", "samples", "padding", "rate", "duplicate", "path", "symlink"],
)
def test_mismatch_never_installs_pack(case, mutation):
    _, _, source, store, _ = case
    manifest_path = source / "manifest.json"
    value = json.loads(manifest_path.read_text())
    entry = value["files"][0]
    if mutation == "text":
        raw = (source / "greeting.txt").read_text().replace("Kübra", "Berkcan").encode()
        (source / "greeting.txt").write_bytes(raw)
        entry["text_sha256"] = hashlib.sha256(raw).hexdigest()
    elif mutation == "audio":
        path = source / "greeting.wav"
        path.write_bytes(path.read_bytes()[:-2])
    elif mutation == "revision":
        value["model_revision"] = "0" * 40
    elif mutation == "samples":
        entry["samples"] += 160
    elif mutation == "padding":
        value["greeting_pad_ms"] = 0
    elif mutation == "rate":
        entry["sample_rate_hz"] = 48000
    elif mutation == "duplicate":
        value["files"][1] = entry.copy()
    elif mutation == "path":
        entry["text_file"] = "../greeting.txt"
    elif mutation == "symlink":
        path = source / "greeting.wav"
        path.unlink()
        path.symlink_to(SOURCE / "greeting.wav")
    manifest_path.write_text(json.dumps(value))
    with pytest.raises((ValueError, OSError)):
        prepare_existing_pack(*case)
    assert not store.exists()


def test_other_identity_requires_new_audio(case):
    draft, preset, source, store, scope = case
    changed = draft.model_copy(update={"owner_genitive": "Serkan Bey’in"})
    with pytest.raises(ValueError, match="differs"):
        prepare_existing_pack(changed, preset, source, store, scope)
    assert not store.exists()
