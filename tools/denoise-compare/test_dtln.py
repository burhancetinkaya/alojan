"""Real CPU-model boundaries and state isolation; models must be explicitly provided."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("dtln", Path(__file__).with_name("dtln.py"))
dtln = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dtln)


@pytest.fixture(scope="module")
def processor():
    path = os.environ.get("ALOJAN_DTLN_MODELS")
    if not path:
        pytest.skip("explicit DTLN model directory required")
    return dtln.DTLN(Path(path))


def test_tail_silence_and_no_cross_utterance_state(processor):
    silence = np.zeros(3203, dtype=np.float32)
    quiet, timing = processor.process(silence)
    assert np.max(np.abs(quiet)) < 1e-6
    assert len(quiet) == len(silence) and timing["frames"] == 26
    samples = np.random.default_rng(42).normal(0, 0.03, 3203).astype(np.float32)
    first, _ = processor.process(samples)
    processor.process(-samples)
    repeated, _ = processor.process(samples)
    assert np.array_equal(first, repeated)
    assert np.isfinite(first).all() and np.max(np.abs(first)) <= 1
    quiet_after, _ = processor.process(silence)
    assert np.array_equal(quiet, quiet_after)


@pytest.mark.parametrize("samples", [[], [np.nan], [np.inf], [1.1], [[0]], np.zeros(480001)])
def test_invalid_audio(processor, samples):
    with pytest.raises(ValueError, match="finite normalized mono"):
        processor.process(samples)


def test_corrupt_model_is_rejected_before_runtime_load(tmp_path):
    (tmp_path / "model_1.onnx").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        dtln.DTLN(tmp_path)


@pytest.mark.parametrize("strength", [0.5, 1.0])
def test_unity_models_preserve_audio_with_exact_causal_delay(strength):
    class UnitySession:
        def __init__(self, spectral):
            self.spectral = spectral

        def run(self, _, inputs):
            audio = inputs["audio"]
            output = np.ones_like(audio) if self.spectral else audio / 4
            return output, inputs["state"]

    processor = dtln.DTLN.__new__(dtln.DTLN)
    processor.sessions = [UnitySession(True), UnitySession(False)]
    processor.names = [["audio", "state"], ["audio", "state"]]
    source = np.random.default_rng(71).normal(0, 0.05, 3203).astype(np.float32)
    result, _ = processor.process(source, strength)
    assert np.allclose(result[:384], 0, atol=1e-7)
    assert np.allclose(result[384:], source[:-384], atol=1e-7)
