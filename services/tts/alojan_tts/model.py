"""Pinned CUDA EMA adapter with bounded upstream work and verified offline weights."""

import hashlib
import os
from pathlib import Path
import threading
from unittest.mock import patch

from alojan_contracts.synthesis import EMA_MODEL, EMA_VOICE, SynthesisProfile

from .outbox import CancellableOutbox
from .service import InvalidText

ROOT = Path(__file__).resolve().parents[3]
MODEL = EMA_MODEL
REVISION = "e7c96f2fc0ba843cd0f86e02786655bb56f50df8"
WEIGHTS = {
    "config.json": "27546c470dd4e86d9ab8172fd1c85c45a4bffdf52d9ccb3f511c4b0c3ae38241",
    "ema.pt": "95aec03dafbe0e1d69bca774ab597c779464729a14bc99bfcb52480090c7dfe6",
    "decoder.pt": "9595819b173f411340f63d11332695121a97f8bf1f6d8b6fef0b21cf99c7ad67",
}
for key, value in {
    "HF_HOME": str(ROOT / ".local/ema/huggingface"),
    "XDG_CACHE_HOME": str(ROOT / ".local/ema/cache"),
    "TORCHINDUCTOR_CACHE_DIR": str(ROOT / ".local/ema/inductor"),
    "TRITON_CACHE_DIR": str(ROOT / ".local/ema/triton"),
    "TORCHINDUCTOR_COMPILE_THREADS": "4",
    "OMP_NUM_THREADS": "4",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}.items():
    os.environ[key] = value


def model_paths(download=False):
    from huggingface_hub import hf_hub_download

    paths = {}
    for name in WEIGHTS:
        path = Path(hf_hub_download(MODEL, name, revision=REVISION, local_files_only=not download))
        if name in WEIGHTS:
            with path.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != WEIGHTS[name]:
                    raise RuntimeError("EMA model checksum mismatch")
        paths[name] = str(path)
    return paths


class EmaBackend:
    def __init__(self):
        import numpy as np
        import torch
        from ema_lightning import EMA
        from ema_lightning.engine import WINDOW
        from ema_lightning.scheduler import Request

        class BoundedRequest(Request):
            def __init__(self, pieces, speed, first):
                super().__init__(pieces, speed, first)
                self.outbox = CancellableOutbox()

            def cancel(self):
                super().cancel()
                self.outbox.stop()

        class BoundedEMA(EMA):
            # shortcut: pinned 1.1.2 has no outbox factory; remove when upstream exposes one.
            def _submit(self, text, speed, seed, first=None):
                pieces = self._pieces(text, speed, seed)
                if not pieces or len(pieces) > 16 or sum(p.letters for p in pieces) > 2048:
                    raise InvalidText("invalid normalized text")
                request = BoundedRequest(pieces, speed, WINDOW if first is None else first)
                self.request = request
                playhead = self._playhead
                with playhead.cond:
                    playhead.inbox.append(request)
                    if playhead.thread is None:
                        playhead.thread = threading.Thread(
                            target=playhead._loop, name="ema-playhead", daemon=True
                        )
                        playhead.thread.start()
                    playhead.cond.notify()
                return request

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA required")
        torch.set_num_threads(4)
        paths = model_paths()

        def pinned_download(repo, filename):
            if repo != MODEL or filename not in paths:
                raise ValueError("unexpected model file")
            return paths[filename]

        # shortcut: EMA 1.1.2 lacks a revision argument; remove when upstream supports it.
        with patch("ema_lightning.api.hf_hub_download", pinned_download):
            self.tts = BoundedEMA(device="cuda")
        self.tts.lightning(batch_size=1)
        torch.cuda.synchronize()
        if self.tts._engine.graphs is None:
            raise RuntimeError("EMA lightning validation failed")
        self.np, self.torch = np, torch
        # Expose capability only after verified weights and successful CUDA graph warm-up.
        self.synthesis_profile = SynthesisProfile(MODEL, REVISION, EMA_VOICE)
        self.quiescence_confirmed = True

    def stream(self, text):
        self.quiescence_confirmed = False
        stream = self.tts.stream(text, seed=0, sample_rate=self.synthesis_profile.sample_rate_hz)
        try:
            for chunk in stream:
                if (
                    chunk.ndim != 1
                    or not 0 < len(chunk) <= 5 * 8000
                    or not self.np.isfinite(chunk).all()
                    or self.np.max(self.np.abs(chunk)) > 1
                ):
                    raise ValueError("invalid EMA audio")
                yield (chunk * 32767).round().astype("<i2").tobytes()
        finally:
            stream.close()
            # Keep admission occupied until the native stage and cancelled scheduler work drain.
            with self.tts._engine.lock:
                self.torch.cuda.synchronize()
                self.tts._playhead._drop_closed()
            request = getattr(self.tts, "request", None)
            if request is not None:
                while not request.outbox.empty():
                    request.outbox.get_nowait()
                self.tts.request = None
            self.quiescence_confirmed = True


if __name__ == "__main__":
    model_paths(download=True)
    print("EMA weights verified")
