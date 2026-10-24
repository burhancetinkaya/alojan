"""Native offline probe validation; explicitly select the built Linux executable."""

import importlib.util
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("denoise", Path(__file__).with_name("run.py"))
denoise = importlib.util.module_from_spec(spec)
spec.loader.exec_module(denoise)


@pytest.fixture
def probe():
    path = os.environ.get("ALOJAN_DENOISE_PROBE")
    if not path:
        pytest.skip("native Linux probe path is required")
    return Path(path).resolve()


@pytest.mark.parametrize("profile", denoise.PROFILES)
def test_frame_tail_and_instance_isolation(probe, profile, tmp_path):
    samples = (np.sin(np.arange(3203) * 0.1) * 0.01).astype(np.float32)
    first, timing = denoise.process(probe, profile, samples, tmp_path)
    denoise.process(probe, profile, -samples, tmp_path)
    again, _ = denoise.process(probe, profile, samples, tmp_path)
    assert np.array_equal(first, again)
    assert timing["frames"] == 21
    assert np.max(np.abs(first)) <= 1
    if profile == "bypass":
        assert np.array_equal(first, samples)


@pytest.mark.parametrize(
    "payload", [b"", b"x", np.array([np.nan], "<f4").tobytes(), np.array([2.0], "<f4").tobytes()]
)
def test_invalid_audio_fails_before_output(probe, payload, tmp_path):
    source, target = tmp_path / "in", tmp_path / "out"
    source.write_bytes(payload)
    result = subprocess.run([str(probe), "bypass", str(source), str(target)], capture_output=True)
    assert result.returncode != 0
    assert not target.exists()


def test_unknown_profile_rejected(probe, tmp_path):
    result = subprocess.run(
        [str(probe), "invalid", str(tmp_path / "in"), str(tmp_path / "out")], capture_output=True
    )
    assert result.returncode != 0 and b"unknown profile" in result.stderr


def test_noise_conditions_repeatable():
    samples = (np.sin(np.arange(16000) * 0.1) * 0.05).astype(np.float32)
    first, second = list(denoise.variants(samples, 42)), list(denoise.variants(samples, 42))
    assert len(first) == 5
    for (name, audio, clipped), (other, repeated, _) in zip(first, second, strict=True):
        assert name == other and np.array_equal(audio, repeated)
        assert 23990 <= len(audio) <= 24000 and clipped == 0
    assert not np.array_equal(first[0][1], first[1][1])
