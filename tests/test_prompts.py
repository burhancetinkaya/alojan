"""Versioned, synthetic speech fixtures and startup safety checks (M1-03)."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import wave

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "assets/prompts/tr-v3-ema"


@pytest.mark.parametrize(
    ("directory", "profile"),
    [
        ("tr-v1", "tr-v1-formant-test"),
        ("tr-v2-ema", "tr-v2-ema-cuda"),
        ("tr-v3-ema", "tr-v3-ema-cuda"),
        ("tr-v4-ema", "tr-v4-ema-carrier-pad"),
        ("tr-v5-kubra", "tr-v5-kubra-ema"),
    ],
)
def test_prompt_provenance_and_pcm(directory, profile):
    prompts = ROOT / "assets/prompts" / directory
    manifest = json.loads((prompts / "manifest.json").read_text())
    assert manifest["profile"] == profile
    if directory in {"tr-v2-ema", "tr-v3-ema"}:
        assert manifest["model"] == "canberkkkkkk/ema-lightning"
        assert manifest["model_revision"] == "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"
        assert manifest["packages"]["ema-lightning"] == "1.1.2"
        assert len(manifest["previews"]) == 2
    if directory == "tr-v5-kubra":
        assert (prompts / "greeting.txt").read_text().strip() == (
            "Merhaba, ben Kübra. Burhan Bey’in yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?"
        )
        with wave.open(str(prompts / "greeting.wav")) as f:
            assert f.readframes(3200) == bytes(6400)
    if directory == "tr-v3-ema":
        assert (prompts / "greeting.txt").read_text().strip() == (
            "Merhaba, ben Burhan Çetinkaya’nın yapay zekâ asistanıyım."
        )
    assert "yapay zekâ asistanıyım" in (prompts / "greeting.txt").read_text()
    assert "Şu anda mesaj alamıyorum" in (prompts / "unavailable.txt").read_text()
    assert [entry["file"] for entry in manifest["files"]] == ["greeting.wav", "unavailable.wav"]
    for entry in manifest["files"] + manifest.get("previews", []):
        rate = entry.get("sample_rate_hz", 8000)
        path = prompts / entry["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        assert (
            hashlib.sha256((prompts / entry["text_file"]).read_bytes()).hexdigest()
            == entry["text_sha256"]
        )
        with wave.open(str(path), "rb") as speech:
            assert (speech.getnchannels(), speech.getsampwidth(), speech.getframerate()) == (
                1,
                2,
                rate,
            )
            assert speech.getnframes() == entry["samples"] == entry["duration_ms"] * rate // 1000
            assert speech.getnframes() % (rate // 50) == 0
            assert any(speech.readframes(speech.getnframes()))


def test_carrier_padding_preserves_every_original_greeting_sample():
    padded = ROOT / "assets/prompts/tr-v4-ema"
    with wave.open(str(PROMPTS / "greeting.wav")) as f:
        original = f.readframes(f.getnframes())
    with wave.open(str(padded / "greeting.wav")) as f:
        audio = f.readframes(f.getnframes())
    assert audio[:6400] == bytes(6400)
    assert audio[6400:] == original
    assert (padded / "unavailable.wav").read_bytes() == (PROMPTS / "unavailable.wav").read_bytes()
    manifest = json.loads((padded / "manifest.json").read_text())
    assert (
        manifest["source_manifest_sha256"]
        == hashlib.sha256((PROMPTS / "manifest.json").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "corrupt",
        "truncated",
        "bad-data-length",
        "stereo",
        "rate",
        "bits",
        "empty",
        "too-long",
        "short-call",
    ],
)
def test_invalid_speech_assets_fail_before_ready(tmp_path, problem):
    directory = tmp_path / "prompts"
    shutil.copytree(PROMPTS, directory)
    fallback = directory / "unavailable.wav"
    if problem == "missing":
        fallback.unlink()
    elif problem == "corrupt":
        fallback.write_bytes(b"not a WAV file")
    elif problem == "truncated":
        fallback.write_bytes(fallback.read_bytes()[:-2])
    elif problem == "bad-data-length":
        data = bytearray(fallback.read_bytes())
        data[40:44] = (len(data) + 100).to_bytes(4, "little")
        fallback.write_bytes(data)
    elif problem != "short-call":
        channels = 2 if problem == "stereo" else 1
        width = 1 if problem == "bits" else 2
        rate = 16000 if problem == "rate" else 8000
        frames = 0 if problem == "empty" else 8000 * (31 if problem == "too-long" else 1)
        with wave.open(str(fallback), "wb") as speech:
            speech.setparams((channels, width, rate, 0, "NONE", "not compressed"))
            speech.writeframes(bytes(frames * channels * width))
    command = [str(ROOT / "build/local/voice-gateway"), "--prompt-dir", str(directory)]
    if problem == "short-call":
        command.extend(["--max-call-seconds", "2"])
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 1
    assert "event=ready" not in result.stdout
    assert "gateway_error" in result.stderr
    assert str(directory) not in result.stderr


def test_playback_modes_cannot_be_combined():
    result = subprocess.run(
        [
            str(ROOT / "build/local/voice-gateway"),
            "--wav",
            str(PROMPTS / "greeting.wav"),
            "--prompt-dir",
            str(PROMPTS),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 1
    assert "choose --wav or --prompt-dir" in result.stderr
    assert "event=ready" not in result.stdout
