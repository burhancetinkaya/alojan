"""Repackage an operator-trusted legacy EMA pack without synthesis or publication."""

import argparse
import hashlib
import json
from pathlib import Path
import uuid

from alojan.profiles import validate_draft
from alojan.auth import AuthError
from alojan.voice_assets import install_pack, read_regular
from alojan_contracts.assets import speech_identity, validate_manifest, validate_wav
from alojan_contracts.configuration import EnginePreset


def prepare_existing_pack(draft, preset, source, store, scope):
    if "waiting" in draft.speech_texts():
        raise ValueError("Legacy pack has no waiting clip; prepare new EMA audio")
    source = Path(source)
    scope = str(uuid.UUID(str(scope)))
    legacy = json.loads(read_regular(source / "manifest.json", 8192))
    try:
        manifest = {
            "model": legacy["model"],
            "model_revision": legacy["model_revision"],
            "speech_digest": speech_identity(draft, preset),
            "greeting_pad_ms": legacy.get("greeting_pad_ms", 0),
        }
        entries = legacy["files"]
        if len(entries) != 2 or {item["file"] for item in entries} != {
            "greeting.wav",
            "unavailable.wav",
        }:
            raise ValueError("Expected exactly two telephone assets")
        files = {}
        for name, text in draft.speech_texts().items():
            entry = next(item for item in entries if item["file"] == f"{name}.wav")
            if entry["text_file"] != f"{name}.txt" or entry["sample_rate_hz"] != 8000:
                raise ValueError("Unexpected legacy asset format")
            original = read_regular(source / f"{name}.txt", 8192)
            if (
                hashlib.sha256(original).hexdigest() != entry["text_sha256"]
                or original.decode("utf-8").strip() != text
            ):
                raise ValueError("Legacy text differs; prepare new EMA audio")
            manifest[name] = {
                "sha256": entry["sha256"],
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "samples": entry["samples"],
            }
            files[f"{name}.wav"] = read_regular(source / f"{name}.wav", 500000)
    except (KeyError, TypeError, StopIteration) as exc:
        raise ValueError("Invalid legacy pack") from exc
    manifest = validate_manifest(manifest, draft, preset)
    for name in draft.speech_texts():
        validate_wav(
            files[f"{name}.wav"],
            getattr(manifest, name),
            leading_silence_ms=preset.greeting_pad_ms if name == "greeting" else 0,
        )
    # Hashes establish integrity, not provenance; only operators select this source.
    return install_pack(store, scope, manifest, files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--preset", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--scope", type=uuid.UUID, required=True)
    args = parser.parse_args()
    try:
        draft = validate_draft(json.loads(read_regular(args.draft, 60000)))
        preset = EnginePreset.model_validate_json(read_regular(args.preset, 16384))
        target = prepare_existing_pack(draft, preset, args.source, args.store, args.scope)
    except (AuthError, ValueError, OSError):
        raise SystemExit(
            "Pack preparation failed; verify trusted source, draft and preset"
        ) from None
    print(f"Voice pack verified: {target}; qualification and publication remain separate.")


if __name__ == "__main__":
    main()
