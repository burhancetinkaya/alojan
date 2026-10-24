"""Metric and deterministic degradation checks; these do not exercise ASR models."""

import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("asr_comparison", Path(__file__).with_name("run.py"))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_turkish_words_preserve_dotless_i_and_numeric_tokens():
    assert comparison.words("IŞIK, İZMİR! 12.30") == ["ışık", "izmir", "12", "30"]
    assert comparison.quality.distance(["bir", "iki"], ["bir", "üç"]) == 1
    assert comparison.quality.distance([], ["fazla"]) == 1


def test_degradations_are_paired_and_keep_quiet_speech():
    samples = np.sin(np.arange(16000, dtype=np.float32) * 0.1) * 0.1
    first = dict(comparison.variants(samples, 12))
    second = dict(comparison.variants(samples, 12))
    assert set(first) == {"clean16", "pcma", "pcma-noise10", "pcma-quiet"}
    assert all(np.array_equal(first[key], second[key]) for key in first)
    assert all(np.isfinite(value).all() for value in first.values())
    assert np.max(np.abs(first["pcma-quiet"])) > 0
    assert np.max(np.abs(first["pcma-quiet"])) < np.max(np.abs(first["pcma"]))
    assert not np.array_equal(first["pcma"], first["pcma-noise10"])


def test_nemotron_silence_and_quiet_pcm_do_not_share_decode_state():
    from alojan_asr.nemotron import NemotronBackend

    backend = NemotronBackend.__new__(NemotronBackend)
    backend.replacement_pattern = None
    observed = []

    def decode(samples):
        observed.append(samples.copy())
        return "Evet."

    backend._decode = decode
    assert backend.transcribe(bytes(32000), "pcm_s16le") == ""
    assert backend.transcribe(bytes(64000), "pcm_f32le") == ""
    assert not observed
    assert backend.transcribe(np.ones(320, dtype="<i2").tobytes(), "pcm_s16le") == "Evet."
    assert np.all(observed[0] == np.float32(1 / 32768))
    assert backend.transcribe(np.full(320, 0.25, dtype="<f4").tobytes(), "pcm_f32le") == "Evet."
    assert np.all(observed[1] == 0.25)
