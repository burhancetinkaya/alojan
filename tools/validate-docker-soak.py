"""Read-only container sampling plus synthetic GPU speech; never places carrier calls."""

import argparse
import asyncio
import audioop
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generated/python"))
import grpc  # noqa: E402
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc  # noqa: E402

SERVICES = {"postgres", "gateway", "asr", "tts", "agent", "api", "telegram"}


def snapshot(project):
    ids = subprocess.check_output(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"],
        text=True,
    ).split()
    assert ids, "no project containers"
    containers = json.loads(subprocess.check_output(["docker", "inspect", *ids]))
    result = {}
    for item in containers:
        name = item["Config"]["Labels"]["com.docker.compose.service"]
        if name not in SERVICES:
            continue
        state = item["State"]
        assert name not in result, "duplicate service"
        assert state["Status"] == "running" and state["Health"]["Status"] == "healthy", name
        assert not state["OOMKilled"], name
        result[name] = {"id": item["Id"][:12], "restarts": item["RestartCount"]}
    assert set(result) == SERVICES, "missing service"
    return result


async def speech_probe():
    key = "synthetic-soak-" + uuid.uuid4().hex
    started = time.monotonic()
    async with (
        grpc.aio.insecure_channel("127.0.0.1:15072") as tts,
        grpc.aio.insecure_channel("127.0.0.1:15173") as asr,
    ):
        frames = rpc.SynthesisStub(tts).StreamSynthesize(
            pb.SynthesisRequest(
                call_id=key, generation_id="tts", text="Bu bir sistem kontrolüdür."
            ),
            timeout=30,
        )
        audio = bytearray()
        async for frame in frames:
            assert frame.sample_rate_hz == 8000 and frame.format == "pcm_s16le"
            audio.extend(frame.audio)
            assert len(audio) <= 16000 * 15
        assert audio and any(audio), "empty synthesis"
        pcm, _ = audioop.ratecv(bytes(audio), 2, 1, 8000, 16000, None)

        async def input_frames():
            for index, offset in enumerate(range(0, len(pcm), 640)):
                yield pb.AudioFrame(
                    call_id=key,
                    generation_id="asr",
                    sequence=index,
                    sample_rate_hz=16000,
                    channels=1,
                    format="pcm_s16le",
                    audio=pcm[offset : offset + 640],
                )

        events = [
            e async for e in rpc.RecognitionStub(asr).StreamRecognize(input_frames(), timeout=30)
        ]
        assert events and events[-1].is_final and events[-1].text.strip(), "missing recognition"
    return round((time.monotonic() - started) * 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="alojan-local")
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 120 or args.output.exists():
        parser.error("use 1..120 minutes and a fresh output file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "container health and synthetic CUDA speech; no carrier acceptance",
        "samples": [],
    }
    started = time.monotonic()
    baseline = snapshot(args.project)
    try:
        while True:
            current = snapshot(args.project)
            assert current == baseline, "container replaced or unexpectedly restarted"
            sample = {"elapsed_seconds": round(time.monotonic() - started), "services": current}
            sample["speech_probe_ms"] = asyncio.run(speech_probe())
            sample["gpu"] = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            ).strip()
            sample["memory"] = subprocess.check_output(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.Name}} {{.MemUsage}}",
                    *[item["id"] for item in current.values()],
                ],
                text=True,
            ).splitlines()
            report["samples"].append(sample)
            report["elapsed_seconds"] = round(time.monotonic() - started)
            print(
                f"samples={len(report['samples'])} elapsed_seconds={report['elapsed_seconds']}",
                flush=True,
            )
            if time.monotonic() - started >= args.minutes * 60:
                report["passed"] = True
                break
            time.sleep(min(30, max(0, args.minutes * 60 - (time.monotonic() - started))))
    except Exception as error:
        report.update(passed=False, failure=type(error).__name__)
        raise
    finally:
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
