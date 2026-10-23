"""Measure a real loopback ASR worker using only repository-owned synthetic audio."""

import argparse
import asyncio
import audioop
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
import wave

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

ROOT = Path(__file__).resolve().parents[1]


def words(text):
    return re.findall(r"\w+", text.casefold().replace("i\u0307", "i"))


def edit_distance(reference, hypothesis):
    row = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        following = [i]
        for j, actual in enumerate(hypothesis, 1):
            following.append(min(row[j] + 1, following[-1] + 1, row[j - 1] + (expected != actual)))
        row = following
    return row[-1]


def fixture(directory, name):
    manifest = json.loads((directory / "manifest.json").read_text())
    entries = manifest.get("previews", []) or manifest["files"]
    entry = next(e for e in entries if e["text_file"] == f"{name}.txt")
    path = directory / entry["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    text = directory / entry["text_file"]
    assert hashlib.sha256(text.read_bytes()).hexdigest() == entry["text_sha256"]
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        audio = wav.readframes(wav.getnframes())
        audio, _ = audioop.ratecv(audio, 2, 1, wav.getframerate(), 16000, None)
    return audio, text.read_text().strip()


async def validate(address):
    results = []
    run = uuid.uuid4().hex
    async with grpc.aio.insecure_channel(address) as channel:
        health = health_pb2_grpc.HealthStub(channel)
        status = await health.Check(
            health_pb2.HealthCheckRequest(service="voice.v1.Recognition"), timeout=2
        )
        assert status.status == health_pb2.HealthCheckResponse.SERVING
        client = rpc.RecognitionStub(channel)
        cases = [
            ("greeting", *fixture(ROOT / "assets/prompts/tr-v3-ema", "greeting")),
            ("closing", *fixture(ROOT / "assets/prompts/tr-v3-ema", "unavailable")),
            ("date-time", *fixture(ROOT / "assets/asr/tr-v1", "date-time")),
            ("phone", *fixture(ROOT / "assets/asr/tr-v1", "phone")),
            ("silence", bytes(32000), ""),
        ]
        import numpy as np

        cases = [(name, audio, reference, "pcm_s16le") for name, audio, reference in cases]
        floating = (np.frombuffer(cases[0][1], dtype="<i2").astype("<f4") / 32768.0).tobytes()
        cases.append(("float-greeting", floating, cases[0][2], "pcm_f32le"))
        cases.append(("float-silence", bytes(64000), "", "pcm_f32le"))
        for name, audio, reference, sample_format in cases:
            frame_bytes = 640 if sample_format == "pcm_s16le" else 1280
            started = time.monotonic()
            half_closed = None

            async def frames():
                nonlocal half_closed
                for index, offset in enumerate(range(0, len(audio), frame_bytes)):
                    yield pb.AudioFrame(
                        call_id=f"eval-{run}",
                        generation_id=name,
                        sequence=index,
                        sample_rate_hz=16000,
                        channels=1,
                        format=sample_format,
                        audio=audio[offset : offset + frame_bytes],
                    )
                half_closed = time.monotonic()

            events, elapsed = [], []
            async for event in client.StreamRecognize(frames(), timeout=60):
                assert event.call_id == f"eval-{run}" and event.generation_id == name
                events.append(event)
                elapsed.append(time.monotonic() - started)
            assert events and events[-1].is_final and sum(e.is_final for e in events) == 1
            actual = events[-1].text
            ref_words, actual_words = words(reference), words(actual)
            result = {
                "fixture": name,
                "audio_seconds": len(audio) / (frame_bytes * 50),
                "sample_format": sample_format,
                "partial_count": len(events) - 1,
                "first_event_ms": round(elapsed[0] * 1000, 2),
                "total_ms": round(elapsed[-1] * 1000, 2),
                "final_after_half_close_ms": round((started + elapsed[-1] - half_closed) * 1000, 2),
                "reference": reference,
                "transcript": actual,
                "word_errors": edit_distance(ref_words, actual_words),
                "reference_words": len(ref_words),
            }
            result["passed"] = (
                (actual == "") if name.endswith("silence") else bool(actual and len(events) > 1)
            )
            normalized = " ".join(words(actual)).replace("â", "a")
            if name in {"greeting", "float-greeting"}:
                result["entity_match"] = "burhançetinkaya" in normalized.replace(" ", "")
            elif name == "date-time":
                result["entity_match"] = (
                    "deniz yılmaz" in normalized
                    and ("12 kasım" in normalized or "on iki kasım" in normalized)
                    and ("14 30" in normalized or "on dört otuz" in normalized)
                )
            elif name == "phone":
                result["entity_match"] = "".join(re.findall(r"\d", actual)) == "05550000001"
            results.append(result)
        # Cancellation before start must not run inference or revive the identity.
        key = pb.CancelRequest(call_id=f"eval-{run}", generation_id="cancel")
        control = rpc.GenerationControlStub(channel)
        assert (await control.CancelGeneration(key, timeout=2)).cancelled
        call = client.StreamRecognize(timeout=2)
        await call.write(
            pb.AudioFrame(
                call_id=key.call_id,
                generation_id=key.generation_id,
                sample_rate_hz=16000,
                channels=1,
                format="pcm_s16le",
                audio=bytes(640),
            )
        )
        try:
            await call.read()
        except grpc.aio.AioRpcError as error:
            assert error.code() == grpc.StatusCode.CANCELLED
        else:
            raise AssertionError("cancelled generation produced output")
        # Cancel an active real-model stream after its first partial; queued output is stale.
        active_id = f"active-{run}"
        active_audio = cases[0][1] * 3

        async def active_frames():
            for index, offset in enumerate(range(0, len(active_audio), 640)):
                yield pb.AudioFrame(
                    call_id=active_id,
                    generation_id="g",
                    sequence=index,
                    sample_rate_hz=16000,
                    channels=1,
                    format="pcm_s16le",
                    audio=active_audio[offset : offset + 640],
                )

        active = client.StreamRecognize(active_frames(), timeout=10)
        assert not (await active.read()).is_final
        cancel_started = time.monotonic()
        await control.CancelGeneration(
            pb.CancelRequest(call_id=active_id, generation_id="g"), timeout=2
        )
        stale_events = 0
        try:
            while True:
                event = await active.read()
                assert event is not grpc.aio.EOF and not event.is_final
                stale_events += 1
        except grpc.aio.AioRpcError as error:
            assert error.code() == grpc.StatusCode.CANCELLED
        cancel_ms = (time.monotonic() - cancel_started) * 1000
        assert cancel_ms < 1000, "active RPC cancellation exceeded test bound"
        # A native decode may still own the slot. Retry with a fresh identity after backoff.
        for attempt in range(20):
            recovery = client.StreamRecognize(timeout=2)
            await recovery.write(
                pb.AudioFrame(
                    call_id=f"recover-{run}-{attempt}",
                    generation_id="g",
                    sample_rate_hz=16000,
                    channels=1,
                    format="pcm_s16le",
                    audio=bytes(640),
                )
            )
            await recovery.done_writing()
            try:
                final = await recovery.read()
                assert final.is_final and not final.text
                break
            except grpc.aio.AioRpcError as error:
                assert error.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
                await asyncio.sleep(0.1)
        else:
            raise AssertionError("decoder did not release capacity after cancellation")
        gpu = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
        return {
            "quality_all_entities_match": all(row.get("entity_match", True) for row in results),
            "profile": "real-cuda-asr-unpaced-synthetic",
            "gpu_after": gpu,
            "cancellation_before_start": "passed",
            "active_cancellation_ms": round(cancel_ms, 2),
            "stale_buffered_events": stale_events,
            "recovery_attempts": attempt + 1,
            "results": results,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=15071)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a fresh evidence output path")
    monitor = subprocess.Popen(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-lms", "100"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        evidence = asyncio.run(validate(f"127.0.0.1:{args.port}"))
    finally:
        monitor.terminate()
        usage, _ = monitor.communicate(timeout=5)
    samples = [int(line) for line in usage.splitlines() if line.isdigit()]
    assert samples, "GPU memory sampling failed"
    evidence["host_gpu_sampled_peak_mib"] = max(samples)
    evidence["gpu_sample_interval_ms"] = 100
    evidence["gpu_sample_count"] = len(samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if (
        not all(row["passed"] for row in evidence["results"])
        or not evidence["quality_all_entities_match"]
    ):
        raise SystemExit("ASR validation failed; see recorded evidence")


if __name__ == "__main__":
    main()
