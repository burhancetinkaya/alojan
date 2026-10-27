"""Check the offline adapter's silence boundary without loading GPU weights."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "qwen_comparison", Path(__file__).with_name("qwen.py")
)
qwen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qwen)


def test_qwen_keeps_quiet_speech_but_rejects_wrong_format(monkeypatch):
    calls = []
    syncs = []
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: syncs.append(1))),
    )
    backend = qwen.QwenBackend.__new__(qwen.QwenBackend)

    def decode(**kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(text=" Evet. ")]

    backend.model = SimpleNamespace(transcribe=decode)
    assert backend.transcribe(bytes(64000), "pcm_f32le") == ""
    assert not calls and not syncs
    quiet = np.full(320, 1 / 32768, dtype="<f4")
    assert backend.transcribe(quiet.tobytes(), "pcm_f32le") == "Evet."
    assert np.array_equal(calls[0]["audio"][0], quiet)
    assert calls[0]["audio"][1] == 16000
    assert calls[0]["language"] == "Turkish"
    assert syncs == [1]
    with pytest.raises(ValueError, match="float32"):
        backend.transcribe(bytes(640), "pcm_s16le")
