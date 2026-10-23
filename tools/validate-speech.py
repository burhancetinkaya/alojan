"""Synthetic live TTS/ASR coexistence checks; no SIP, carrier or human-quality claim."""

import argparse
import asyncio
import audioop
import json
import re
from pathlib import Path
import subprocess
import time
import uuid
import wave

import grpc
import numpy as np
from alojan_contracts.audio import AudioStreamValidator
from grpc_health.v1 import health_pb2, health_pb2_grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc

ROOT = Path(__file__).resolve().parents[1]


async def recognize(client, audio, key):
    started = time.monotonic()

    async def frames():
        for sequence, offset in enumerate(range(0, len(audio), 640)):
            yield pb.AudioFrame(
                call_id=key,
                generation_id="asr",
                sequence=sequence,
                sample_rate_hz=16000,
                channels=1,
                format="pcm_s16le",
                audio=audio[offset : offset + 640],
            )

    events = [e async for e in client.StreamRecognize(frames(), timeout=30)]
    ended = time.monotonic()
    assert events and events[-1].is_final and sum(e.is_final for e in events) == 1
    assert events[-1].text.strip() and all(
        e.call_id == key and e.generation_id == "asr" for e in events
    )
    return {
        "start": started,
        "end": ended,
        "elapsed_ms": round((ended - started) * 1000, 2),
        "transcript": events[-1].text,
    }


async def synthesize(client, text, key):
    started = time.monotonic()
    first = None
    validator = AudioStreamValidator()
    output = bytearray()
    async for frame in client.StreamSynthesize(
        pb.SynthesisRequest(call_id=key, generation_id="tts", text=text), timeout=30
    ):
        assert validator.accept(frame) == (key, "tts")
        assert (
            frame.sample_rate_hz == 8000 and frame.format == "pcm_s16le" and len(frame.audio) == 320
        )
        first = first or time.monotonic()
        output.extend(frame.audio)
        assert len(output) <= 480000
    ended = time.monotonic()
    values = np.frombuffer(output, dtype="<i2").astype(np.float64) / 32768
    rms = float(np.sqrt(np.mean(values**2)))
    assert 0 < len(output) <= 480000 and rms > 0.001 and np.max(np.abs(values)) < 1
    return bytes(output), {
        "start": started,
        "end": ended,
        "first_ms": round((first - started) * 1000, 2),
        "elapsed_ms": round((ended - started) * 1000, 2),
        "seconds": len(output) / 16000,
        "rms": rms,
    }


async def validate(output):
    run = uuid.uuid4().hex
    with wave.open(str(ROOT / "assets/asr/tr-v1/phone.wav"), "rb") as wav:
        source, _ = audioop.ratecv(
            wav.readframes(wav.getnframes()), 2, 1, wav.getframerate(), 16000, None
        )
    cases = [
        ("greeting", (ROOT / "assets/prompts/tr-v3-ema/greeting.txt").read_text().strip()),
        ("closing", (ROOT / "assets/prompts/tr-v3-ema/unavailable.txt").read_text().strip()),
        ("date-time", "Randevum 12 Kasım Perşembe günü saat 14:30'da."),
        ("phone", "Telefon numaram 0555 000 00 01."),
        ("amount", "Toplam 1.250,50 TL ve yüzde 25 indirim."),
        ("foreign", "Toplantıyı Zoom veya Microsoft Teams üzerinden yapabiliriz."),
    ]
    results = []
    async with (
        grpc.aio.insecure_channel("127.0.0.1:15071") as asr_channel,
        grpc.aio.insecure_channel("127.0.0.1:15072") as tts_channel,
    ):
        for channel, name in [(asr_channel, "Recognition"), (tts_channel, "Synthesis")]:
            health = await health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest(service=f"voice.v1.{name}"), timeout=2
            )
            assert health.status == health_pb2.HealthCheckResponse.SERVING
        asr, tts = rpc.RecognitionStub(asr_channel), rpc.SynthesisStub(tts_channel)
        control = rpc.GenerationControlStub(tts_channel)
        for name, text in cases:
            (audio, speech), recognition = await asyncio.gather(
                synthesize(tts, text, f"{run}-{name}"), recognize(asr, source, f"{run}-{name}")
            )
            overlap = min(speech["end"], recognition["end"]) - max(
                speech["start"], recognition["start"]
            )
            assert overlap > 0
            assert "".join(re.findall(r"\d", recognition["transcript"])) == "05550000001"
            with wave.open(str(output / f"{name}.wav"), "wb") as wav:
                wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                wav.writeframes(audio)
            converted, _ = audioop.ratecv(audio, 2, 1, 8000, 16000, None)
            roundtrip = await recognize(asr, converted, f"{run}-{name}-roundtrip")
            if name == "phone":
                roundtrip["digits_match"] = (
                    "".join(re.findall(r"\d", roundtrip["transcript"])) == "05550000001"
                )
            results.append(
                {
                    "case": name,
                    "tts": speech,
                    "concurrent_asr": recognition,
                    "overlap_ms": round(overlap * 1000, 2),
                    "roundtrip": roundtrip,
                }
            )
        key = pb.CancelRequest(call_id=f"{run}-cancel", generation_id="tts")
        call = tts.StreamSynthesize(
            pb.SynthesisRequest(
                call_id=key.call_id, generation_id=key.generation_id, text=cases[5][1] * 6
            ),
            timeout=20,
        )
        assert (await call.read()).call_id == key.call_id
        began = time.monotonic()
        await control.CancelGeneration(key, timeout=2)
        try:
            while await call.read() is not grpc.aio.EOF:
                pass
            raise AssertionError("cancelled stream completed successfully")
        except grpc.aio.AioRpcError as error:
            assert error.code() == grpc.StatusCode.CANCELLED
        cancel_ms = round((time.monotonic() - began) * 1000, 2)
        for i in range(100):
            try:
                await synthesize(tts, cases[0][1], f"{run}-recovery-{i}")
                break
            except grpc.aio.AioRpcError as error:
                assert error.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
                await asyncio.sleep(0.05)
        else:
            raise AssertionError("native TTS did not recover")
        for _ in range(2):
            assert (await control.CancelGeneration(key, timeout=2)).cancelled
        try:
            await tts.StreamSynthesize(
                pb.SynthesisRequest(
                    call_id=key.call_id, generation_id=key.generation_id, text=cases[0][1]
                ),
                timeout=2,
            ).read()
            raise AssertionError("cancelled identity revived")
        except grpc.aio.AioRpcError as error:
            assert error.code() == grpc.StatusCode.CANCELLED
    return {
        "cases": results,
        "active_cancel_ms": cancel_ms,
        "recovery_attempts": i + 1,
        "scope": "unpaced loopback requests; overlapping RPCs, not a GPU kernel profiler or RTP latency",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "gpu.csv").open("w") as log:
        monitor = subprocess.Popen(
            [
                "nvidia-smi",
                "--query-gpu=timestamp,memory.used",
                "--format=csv,noheader,nounits",
                "-lms",
                "100",
            ],
            stdout=log,
        )
        try:
            result = asyncio.run(validate(args.output))
        finally:
            monitor.terminate()
            monitor.wait(timeout=2)
    usage = [
        int(line.rsplit(",", 1)[1]) for line in (args.output / "gpu.csv").read_text().splitlines()
    ]
    result["sampled_host_peak_mib"] = max(usage)
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "stream_cases_passed": len(result["cases"]),
                "cancel_ms": result["active_cancel_ms"],
                "peak_mib": result["sampled_host_peak_mib"],
            }
        )
    )


if __name__ == "__main__":
    main()
