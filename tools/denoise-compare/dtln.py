"""Offline DTLN CPU probe; original 16 kHz model, without LiveKit post-filters.

Algorithm follows breizhn/DTLN's MIT-licensed real_time_processing_onnx.py.
See README.md for the pinned source, attribution and latency limitations.
"""

import argparse
import hashlib
from pathlib import Path
import time
import urllib.request

import numpy as np

REVISION = "1de1f15a8b5b7e1c44905618ff2ef70ca8277fbc"
HASHES = {
    "model_1.onnx": "22b91cae3855e5a0620e66a917ca6c82c58db0e842c770f58d86751c5e8d4ae3",
    "model_2.onnx": "e20c92f9233fccf29cddf86970d0d0161a03aebccc26d6f4d5639c4d5ec2e639",
}


def verify(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"DTLN checksum mismatch: {path.name}")


def download(directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, checksum in HASHES.items():
        path = directory / name
        if not path.exists():
            url = (
                f"https://raw.githubusercontent.com/breizhn/DTLN/{REVISION}/pretrained_model/{name}"
            )
            data = urllib.request.urlopen(url, timeout=30).read()
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError(f"DTLN download checksum mismatch: {name}")
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
        verify(path, checksum)


class DTLN:
    """Reuse CPU sessions, but reset recurrent state between offline utterances."""

    def __init__(self, directory):
        import onnxruntime as ort

        if ort.__version__ != "1.31.0":
            raise RuntimeError("evaluation requires existing ONNX Runtime 1.31.0")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.sessions = []
        for name, checksum in HASHES.items():
            path = directory / name
            verify(path, checksum)
            self.sessions.append(
                ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
            )
        self.names = [[x.name for x in s.get_inputs()] for s in self.sessions]
        for session, width in zip(self.sessions, (257, 512), strict=True):
            shapes = [x.shape for x in session.get_inputs()]
            if shapes != [[1, 1, width], [1, 2, 128, 2]]:
                raise ValueError(f"unexpected DTLN input shapes: {shapes}")
        self.process(np.zeros(1600, dtype=np.float32))

    def process(self, samples, strength=1.0):
        samples = np.asarray(samples, dtype=np.float32)
        if (
            samples.ndim != 1
            or not 0 < samples.size <= 16000 * 30
            or not np.isfinite(samples).all()
            or np.max(np.abs(samples)) > 1
        ):
            raise ValueError("expected finite normalized mono audio, 0-30 seconds")
        if not 0 <= strength <= 1:
            raise ValueError("strength must be between zero and one")
        original_size = len(samples)
        samples = np.pad(samples, (0, (-original_size) % 128))
        states = [np.zeros((1, 2, 128, 2), np.float32) for _ in range(2)]
        incoming = np.zeros(512, np.float32)
        outgoing = np.zeros(512, np.float32)
        result = np.zeros_like(samples)
        timings = []
        cpu_start = time.process_time()
        for offset in range(0, len(samples), 128):
            start = time.perf_counter_ns()
            incoming[:-128] = incoming[128:]
            incoming[-128:] = samples[offset : offset + 128]
            spectrum = np.fft.rfft(incoming)
            magnitude = np.abs(spectrum).astype(np.float32).reshape(1, 1, 257)
            mask, states[0] = self.sessions[0].run(
                None, dict(zip(self.names[0], (magnitude, states[0]), strict=True))
            )
            block = np.fft.irfft(spectrum * mask.reshape(257), n=512)
            block, states[1] = self.sessions[1].run(
                None,
                dict(
                    zip(
                        self.names[1],
                        (block.astype(np.float32).reshape(1, 1, 512), states[1]),
                        strict=True,
                    )
                ),
            )
            outgoing[:-128] = outgoing[128:]
            outgoing[-128:] = 0
            outgoing += block.reshape(512)
            result[offset : offset + 128] = outgoing[:128]
            timings.append((time.perf_counter_ns() - start) / 1000)
        cpu_ms = (time.process_time() - cpu_start) * 1000
        if not np.isfinite(result).all():
            raise ValueError("nonfinite DTLN output")
        # Align dry speech with the 24 ms overlap-add delay, avoiding comb filtering.
        if strength != 1:
            dry = np.pad(samples, (384, 0))[: len(samples)]
            result = strength * result + (1 - strength) * dry
        clipped = int(np.count_nonzero(np.abs(result) > 1))
        return np.clip(result[:original_size], -1, 1).astype("<f4"), {
            "frames": len(timings),
            "frame_ms": 8,
            "mean_us": float(np.mean(timings)),
            "p95_us": float(np.percentile(timings, 95)),
            "max_us": max(timings),
            "cpu_ms": cpu_ms,
            "clipped_samples": clipped,
            "implementation": "python-numpy-native-onnx-cpu",
            "overlap_add_delay_ms": 24,
            "strength": strength,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and verify pinned DTLN models")
    parser.add_argument("--models", type=Path, required=True)
    download(parser.parse_args().models)
    print("Both pinned DTLN model hashes verified")
