"""Pinned, offline Pocket voices with streaming conversion to the telephone contract."""

import hashlib
import os
from pathlib import Path

from alojan_contracts.synthesis import POCKET_MODEL, POCKET_REVISION, POCKET_VOICES, voice_profile

from .service import InvalidText

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = {
    "config.yaml": "fa60a7799ac09778360ce1aa5c2216fa2ce6f1be06aabb2e0dd4f6ea63a6d3d7",
    "model.safetensors": "c43b72ed336b64c66adceba8fbbb059e869f753b60de086e3f32bf1b118d5a77",
    "tokenizer.model": "a6c3a7ca48ecf3c9254bf72dff58e3f09f2798f49effcbd7debcf6f7a87f3568",
    "voices/female_1.wav": "82be41762735f5004cec992badc67813a02206fe53888ba7342a589197850225",
    "voices/female_2.wav": "98cd697c9dd6f77f253bd1233675496b6d4882cd9c0ef72434b6a12e06564aa7",
    "voices/female_3.wav": "555eab5c0640649c1323e6e51c2fae10a334ac3988e6ba0052822147fd9bc40c",
    "voices/male_1.wav": "e6538a1f0ce60d08994c3a733946589d327cf9256b35b77e4155c0baefadc81a",
    "voices/male_2.wav": "d5585323c634900b054ea20d1c8c9e39d35516b89dba693eaabf8587143dd6d8",
    "voices/male_3.wav": "b5bbbca120837cca1b93c3b8d740e70bcc3f32f53c557af04b207fc69a31545e",
}


def model_directory(download=False):
    from huggingface_hub import snapshot_download

    folder = Path(
        snapshot_download(
            POCKET_MODEL,
            revision=POCKET_REVISION,
            allow_patterns=list(WEIGHTS),
            cache_dir=os.environ.get(
                "ALOJAN_POCKET_CACHE", str(ROOT / ".local/pocket/huggingface/hub")
            ),
            local_files_only=not download,
        )
    )
    for name, digest in WEIGHTS.items():
        with (folder / name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != digest:
                raise RuntimeError("Pocket model checksum mismatch")
    return folder


class PocketBackend:
    def __init__(self, tts, voice):
        self.tts = tts
        self.synthesis_profile = voice_profile(voice, "")
        self.voice = voice.removeprefix("pocket-")
        self.quiescence_confirmed = True

    def stream(self, text):
        import numpy as np
        import soxr

        sentences = self.tts.prepare(text)
        if not sentences or len(sentences) > 16 or sum(map(len, sentences)) > 2048:
            raise InvalidText("invalid normalized text")
        # A fresh stateful filter per generation avoids chunk seams and cross-call audio leakage.
        resampler = soxr.ResampleStream(24000, 8000, 1, dtype="float32", quality="LQ")
        stream = self.tts.stream(text, voice=self.voice, seed=0)
        self.quiescence_confirmed = False
        total = 0
        try:
            for chunk in stream:
                if (
                    chunk.ndim != 1
                    or not 0 < len(chunk) <= 5 * 24000
                    or not np.isfinite(chunk).all()
                ):
                    raise ValueError("Invalid Pocket audio")
                total += len(chunk)
                if total > 30 * 24000:
                    raise ValueError("Pocket audio exceeds duration limit")
                # The vocoder can slightly exceed full scale (observed 1.02); match
                # upstream WAV export clipping instead of aborting a valid utterance.
                pcm = resampler.resample_chunk(np.clip(chunk, -1, 1))
                if len(pcm):
                    yield (np.clip(pcm, -1, 1) * 32767).round().astype("<i2").tobytes()
            pcm = resampler.resample_chunk(np.empty(0, dtype=np.float32), last=True)
            if len(pcm):
                yield (np.clip(pcm, -1, 1) * 32767).round().astype("<i2").tobytes()
        finally:
            # Pinned pocket-tts 3.3 propagates stop and joins its producer on generator close.
            stream.close()
            self.quiescence_confirmed = True


def bound_generation(model):
    # shortcut: Pocket 3.3 has no queue budget. Bound each producer to 30 seconds
    # (375 codec frames), at most 2.9 MB of queued PCM; use upstream budgets when available.
    original = model._estimate_max_gen_len

    def estimate(token_count):
        frames = original(token_count)
        if not 0 < frames <= 375:
            raise InvalidText("Pocket generation exceeds frame budget")
        return frames

    model._estimate_max_gen_len = estimate


def configure_cuda_decoder(model):
    import torch

    decode = model.mimi.decode_from_latent

    def without_autotuning(*args, **kwargs):
        # EMA enables process-wide autotuning; Pocket's variable decoder shapes
        # repeatedly pay that cost. Scope the override to this admitted decode only.
        benchmark = torch.backends.cudnn.benchmark
        try:
            torch.backends.cudnn.benchmark = False
            return decode(*args, **kwargs)
        finally:
            torch.backends.cudnn.benchmark = benchmark

    model.mimi.decode_from_latent = without_autotuning


def load_backends(device="cpu"):
    import torch
    from pocket_tts_turkish import TurkishTTS

    previous_threads = torch.get_num_threads()
    try:
        tts = TurkishTTS.from_pretrained(model_directory(), device=device)
    finally:
        # The upstream import changes a process-wide PyTorch setting; retain EMA calibration.
        torch.set_num_threads(previous_threads)
    if tts.sample_rate != 24000 or not tts._can_stop:
        raise RuntimeError("Unsupported Pocket streaming runtime")
    bound_generation(tts._model)
    if device == "cuda":
        configure_cuda_decoder(tts._model)
    backends = [PocketBackend(tts, voice) for voice in POCKET_VOICES]
    for backend in backends:
        # Warm every voice once before advertising readiness; never encode references mid-call.
        if not sum(len(chunk) for chunk in backend.stream("Merhaba.")):
            raise RuntimeError("Pocket voice warm-up failed")
    return backends


if __name__ == "__main__":
    model_directory(download=True)
    print("Pocket weights and bundled voices verified")
