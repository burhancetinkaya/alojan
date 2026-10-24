"""Offline Qwen3-ASR evaluation using the existing paired comparison protocol."""

import importlib.util
import json
import os
from pathlib import Path

import numpy as np


class QwenBackend:
    def __init__(self):
        import torch
        from qwen_asr import Qwen3ASRModel

        torch.set_num_threads(4)
        self.model = Qwen3ASRModel.from_pretrained(
            os.environ["ALOJAN_QWEN_MODEL"],
            dtype=torch.bfloat16,
            device_map="cuda:0",
            attn_implementation="sdpa",
            max_inference_batch_size=1,
            max_new_tokens=440,
            local_files_only=True,
        )

    def transcribe(self, audio, sample_format):
        import torch

        if sample_format != "pcm_f32le":
            raise ValueError("Offline comparison requires float32 PCM")
        samples = np.frombuffer(audio, dtype="<f4").copy()
        if not np.any(samples):
            return ""
        result = self.model.transcribe(audio=(samples, 16000), language="Turkish")
        torch.cuda.synchronize()
        return result[0].text.strip()


def main():
    spec = importlib.util.spec_from_file_location("comparison", Path(__file__).with_name("run.py"))
    comparison = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison)
    # Reuse identical fixtures, perturbations, metrics and timing boundaries.
    comparison.quality.WhisperBackend = QwenBackend
    comparison.main()
    import torch

    print(json.dumps({"qwen_peak_allocated_bytes": torch.cuda.max_memory_allocated()}))


if __name__ == "__main__":
    main()
