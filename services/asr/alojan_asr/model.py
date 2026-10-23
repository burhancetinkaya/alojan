"""Pinned, offline-at-runtime CUDA transcription backend."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PIN = json.loads((Path(__file__).resolve().parents[1] / "model.json").read_text())


def model_path(download=False):
    from huggingface_hub import snapshot_download

    directory = Path(
        snapshot_download(
            PIN["repository"],
            revision=PIN["revision"],
            allow_patterns=list(PIN["sha256"]),
            cache_dir=ROOT / ".local/asr/models",
            local_files_only=not download,
        )
    )
    for name, expected in PIN["sha256"].items():
        with (directory / name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise RuntimeError("ASR model checksum mismatch")
    return directory


class WhisperBackend:
    def __init__(self):
        import ctranslate2
        import numpy as np
        from faster_whisper import WhisperModel

        if not ctranslate2.get_cuda_device_count():
            raise RuntimeError("ASR requires CUDA; no CPU/model substitution")
        self.model = WhisperModel(
            str(model_path()),
            device="cuda",
            device_index=0,
            compute_type="float16",
            cpu_threads=4,
            num_workers=1,
            local_files_only=True,
        )
        # Readiness requires a real decode, not just allocated model weights.
        self._decode(np.zeros(16000, dtype=np.float32))

    def transcribe(self, audio, sample_format):
        import numpy as np

        samples = np.frombuffer(audio, dtype="<i2" if sample_format == "pcm_s16le" else "<f4")
        samples = samples.astype(np.float32)
        if sample_format == "pcm_s16le":
            samples /= 32768.0
        # Whisper can hallucinate even on exact digital silence; do not suppress quiet speech.
        if not np.any(samples):
            return ""
        return self._decode(samples)

    def _decode(self, samples):
        segments, _ = self.model.transcribe(
            samples,
            language="tr",
            task="transcribe",
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            word_timestamps=False,
            max_new_tokens=440,
        )
        return "".join(segment.text for segment in segments).strip()


if __name__ == "__main__":
    model_path(download=True)
    print("ASR pinned model downloaded and checksums verified", flush=True)
