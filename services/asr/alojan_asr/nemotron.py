"""Optional pinned Nemotron decoder; each call owns fresh streaming caches."""

import hashlib
import json
from pathlib import Path

from .model import ROOT, compile_replacements

PIN = json.loads((Path(__file__).resolve().parents[1] / "nemotron.json").read_text())


def model_path():
    directory = ROOT / ".local/nemotron-model"
    for name, expected in PIN["sha256"].items():
        with (directory / name).open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                raise RuntimeError("Nemotron model checksum mismatch")
    return directory


class NemotronBackend:
    pin = PIN

    def __init__(self, replacements="{}", lookahead=3):
        if lookahead not in (0, 3, 6, 13):
            raise ValueError("unsupported Nemotron lookahead")
        self.replacement_pattern, self.replacements = compile_replacements(replacements)
        import numpy as np
        import torch
        from transformers import AutoModelForRNNT, AutoProcessor

        if not torch.cuda.is_available():
            raise RuntimeError("ASR requires CUDA; no CPU/model substitution")
        torch.set_num_threads(4)
        directory = model_path()
        self.lookahead = lookahead
        self.processor = AutoProcessor.from_pretrained(directory, local_files_only=True)
        self.processor.set_num_lookahead_tokens(lookahead)
        self.model = (
            AutoModelForRNNT.from_pretrained(directory, local_files_only=True).to("cuda").eval()
        )
        self._decode(np.zeros(16000, dtype=np.float32))

    def transcribe(self, audio, sample_format):
        import numpy as np

        samples = np.frombuffer(
            audio, dtype="<i2" if sample_format == "pcm_s16le" else "<f4"
        ).astype(np.float32)
        if sample_format == "pcm_s16le":
            samples /= 32768.0
        if not np.any(samples):
            return ""
        text = self._decode(samples)
        if self.replacement_pattern:
            text = self.replacement_pattern.sub(
                lambda match: self.replacements[match.lastgroup], text
            )
        return text

    def _decode(self, samples):
        import numpy as np
        import torch

        processor = self.processor
        hop = processor.feature_extractor.hop_length
        nfft = processor.feature_extractor.n_fft
        first_size = processor.num_samples_first_audio_chunk
        chunk_size = processor.num_samples_per_audio_chunk
        original_length = len(samples)
        samples = np.pad(samples, (0, first_size + chunk_size))
        first = processor(
            samples[:first_size],
            sampling_rate=16000,
            language="tr-TR",
            is_streaming=True,
            is_first_audio_chunk=True,
            return_tensors="pt",
        ).to("cuda")

        def chunks():
            yield first.input_features[:, : processor.num_mel_frames_first_audio_chunk, :]
            mel = processor.num_mel_frames_first_audio_chunk
            start = mel * hop - nfft // 2
            # Include the last partial chunk; discarding it can lose the final word.
            while start < original_length:
                part = processor(
                    samples[start : start + chunk_size],
                    sampling_rate=16000,
                    language="tr-TR",
                    is_streaming=True,
                    is_first_audio_chunk=False,
                    return_tensors="pt",
                ).to("cuda")
                yield part.input_features
                mel += processor.num_mel_frames_per_audio_chunk
                start = mel * hop - nfft // 2

        # shortcut: gRPC partials re-decode cumulative audio; add persistent per-generation
        # caches only after quality and cancellation/latency evidence justifies live use.
        with torch.inference_mode():
            result = self.model.generate(
                **{**first, "input_features": chunks(), "num_lookahead_tokens": self.lookahead},
                return_dict_in_generate=True,
                max_new_tokens=4096,
            )
        torch.cuda.synchronize()
        texts = processor.decode(result.sequences, skip_special_tokens=True)
        if not isinstance(texts, list) or len(texts) != 1 or not isinstance(texts[0], str):
            raise RuntimeError("invalid Nemotron batch output")
        return texts[0].strip()
