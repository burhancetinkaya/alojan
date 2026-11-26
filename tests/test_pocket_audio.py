"""Adapter filtering and cancellation with synthetic audio, not model quality evidence."""

import pytest

np = pytest.importorskip("numpy")
soxr = pytest.importorskip("soxr")
from alojan_tts.pocket import PocketBackend  # noqa: E402


class Speech:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False
        self.calls = []

    def prepare(self, text):
        return [text]

    def stream(self, text, **options):
        self.calls.append(options)
        try:
            yield from self.chunks
        finally:
            self.closed = True


def test_streaming_resampling_has_no_chunk_seams_or_state_leakage():
    audio = (np.sin(np.arange(24000) * 0.15) * 0.5).astype(np.float32)
    speech = Speech([audio[:1937], audio[1937:7333], audio[7333:]])
    backend = PocketBackend(speech, "pocket-female_2")
    actual = b"".join(backend.stream("Merhaba"))
    expected = soxr.resample(audio, 24000, 8000, quality="LQ")
    expected = (np.clip(expected, -1, 1) * 32767).round().astype("<i2").tobytes()
    assert actual == expected and len(actual) == 16000
    assert b"".join(backend.stream("Tekrar")) == expected
    assert speech.closed and backend.quiescence_confirmed
    assert all(c == dict(voice="female_2", seed=0) for c in speech.calls)


def test_cancel_closes_upstream_and_next_generation_starts_cleanly():
    speech = Speech([np.ones(1920, dtype=np.float32) * 0.1] * 1000)
    backend = PocketBackend(speech, "pocket-male_1")
    stream = backend.stream("Merhaba")
    first = next(stream)
    assert not backend.quiescence_confirmed
    stream.close()
    assert speech.closed and backend.quiescence_confirmed
    next_stream = backend.stream("Yeni")
    assert next(next_stream) == first
    next_stream.close()


@pytest.mark.parametrize(
    "audio",
    [
        np.array([np.nan], dtype=np.float32),
        np.array([np.inf], dtype=np.float32),
        np.ones((2, 2), dtype=np.float32),
        np.zeros(0, dtype=np.float32),
    ],
)
def test_invalid_model_audio_is_rejected_and_producer_closes(audio):
    speech = Speech([audio])
    backend = PocketBackend(speech, "pocket-female_1")
    with pytest.raises(ValueError, match="Invalid Pocket audio"):
        list(backend.stream("Merhaba"))
    assert speech.closed and backend.quiescence_confirmed


def test_vocoder_full_scale_overshoot_is_clipped_without_aborting_speech():
    audio = np.full(1920, 1.02, dtype=np.float32)
    backend = PocketBackend(Speech([audio]), "pocket-female_2")
    actual = np.frombuffer(b"".join(backend.stream("Merhaba")), dtype="<i2")
    assert len(actual) == 640 and actual.max() == 32767 and actual.min() > 0
    assert backend.quiescence_confirmed


def test_native_producer_budget_rejects_excess_before_worker_threads_start():
    from types import SimpleNamespace
    from alojan_tts.pocket import bound_generation
    from alojan_tts.service import InvalidText

    model = SimpleNamespace(_estimate_max_gen_len=lambda tokens: tokens * 5)
    bound_generation(model)
    assert model._estimate_max_gen_len(75) == 375
    with pytest.raises(InvalidText):
        model._estimate_max_gen_len(76)


@pytest.mark.parametrize("original", [False, True])
@pytest.mark.parametrize("fails", [False, True])
def test_cuda_decoder_restores_ema_tuning_even_on_worker_failure(monkeypatch, original, fails):
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from alojan_tts.pocket import configure_cuda_decoder

    cudnn = SimpleNamespace(benchmark=original, enabled=True, allow_tf32=True)
    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(backends=SimpleNamespace(cudnn=cudnn))
    )
    latent, state = object(), object()

    def decode(actual_latent, actual_state):
        assert actual_latent is latent and actual_state is state
        assert cudnn.benchmark is False and cudnn.enabled and cudnn.allow_tf32
        if fails:
            raise RuntimeError("decoder failed")
        return latent

    model = SimpleNamespace(mimi=SimpleNamespace(decode_from_latent=decode))
    configure_cuda_decoder(model)
    with ThreadPoolExecutor(max_workers=1) as worker:
        future = worker.submit(model.mimi.decode_from_latent, latent, state)
        if fails:
            with pytest.raises(RuntimeError, match="decoder failed"):
                future.result()
        else:
            assert future.result() is latent
    assert cudnn.benchmark is original and cudnn.enabled and cudnn.allow_tf32
