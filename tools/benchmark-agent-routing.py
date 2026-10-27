"""Compare same-model routing with synthetic conversations and simulated audio receipts."""

import argparse
import asyncio
import json
import math
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
for directory in ("services/agent", "services/voice-contracts", "generated/python"):
    sys.path.insert(0, str(ROOT / directory))

import grpc  # noqa: E402
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc  # noqa: E402
from alojan_agent.backend import Backend, MODEL  # noqa: E402
from alojan_agent.models import normalize  # noqa: E402
from alojan_agent.service import AgentService, create_server  # noqa: E402

PROFILES = ["default", "latency", "sticky", "latency-sticky"]
CASES = {
    "inquiry": [
        "Burhan Bey ile görüşebilir miyim?",
        "Orion ürünüyle ilgili bir soru sormak istiyorum.",
    ],
    "message": [
        "Ben Deniz Test. Burhan Bey'e mesajım: Yarın beni arasın. Telefon numarası vermeyeceğim.",
        "Mesajı düzeltelim, yarın değil cuma beni arasın.",
    ],
    "exit": [
        "Orion ürününün kurulumu hakkında soru sormak istiyorum.",
        "Hayır, vazgeçtim. Ben daha sonra tekrar ararım. İyi günler.",
    ],
}


class SyntheticStore:
    async def start(self, *args):
        pass

    async def utterance(self, *args):
        pass

    async def note(self, cid, note, version):
        return f"synthetic-{version}"

    async def end(self, *args):
        pass


def summarize(rows):
    result = {}
    for profile in PROFILES:
        group = [r for r in rows if r["profile"] == profile]
        good = [r for r in group if r["status"] == "completed"]
        timings = sorted(r["first_phrase_ms"] for r in good)
        models = [m for r in good for m in r["timing"]["model_steps"]]
        usage = [m for m in models if m["cached_tokens"] >= 0]
        result[profile] = {
            "attempts": len(group),
            "completed": len(good),
            "behavior_failures": sum(not r.get("behavior_ok", False) for r in group),
            "median_ms": statistics.median(timings) if timings else None,
            "p95_ms": timings[math.ceil(0.95 * len(timings)) - 1] if timings else None,
            "maximum_ms": max(timings) if timings else None,
            "model_requests": len(models),
            "usage_observed_requests": len(usage),
            "cache_hit_requests": sum(m["cached_tokens"] > 0 for m in usage),
            "cached_tokens": sum(m["cached_tokens"] for m in usage),
        }
    return result


async def conversation(profile, case):
    backend = Backend(routing=profile)
    service = AgentService(backend, SyntheticStore())
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    cid = "routing-" + uuid.uuid4().hex
    rows = []
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = rpc.AgentStub(channel)
            for turn, text in enumerate(CASES[case], 1):
                row = {"profile": profile, "case": case, "turn": turn, "status": "failed"}
                started = time.monotonic()
                first = None
                phrases = []
                try:
                    async for event in stub.RunTurn(
                        pb.AgentRequest(
                            call_id=cid,
                            generation_id=f"turn-{turn}",
                            final_user_text=text,
                            context_json="{}",
                        ),
                        timeout=25,
                    ):
                        if event.type == "text_delta":
                            first = first if first is not None else time.monotonic()
                            phrases.append(event)
                    assert first is not None
                    for event in phrases:
                        await stub.ReportPlayback(
                            pb.PlaybackReport(
                                call_id=cid,
                                generation_id=f"turn-{turn}",
                                phrase_index=json.loads(event.detail_json)["phrase_index"],
                                sent_audio_ms=1000,
                                completed=True,
                            ),
                            timeout=3,
                        )
                    call = service.calls[cid]
                    answer = " ".join(p.text for p in phrases)
                    expected_finish = case == "exit" and turn == 2
                    ok = call.finish == expected_finish and answer.count("?") <= 1
                    if case == "message":
                        ok &= call.note is not None and not call.note.confirmed
                        if turn == 2 and call.note:
                            note = normalize(call.note.message)
                            ok &= "cuma" in note and "yarın" not in note
                    else:
                        ok &= call.note is None
                    row.update(
                        status="completed",
                        first_phrase_ms=round((first - started) * 1000),
                        elapsed_ms=round((time.monotonic() - started) * 1000),
                        timing=call.timing.snapshot(),
                        behavior_ok=bool(ok),
                        answer=answer,
                        note_saved=call.note is not None,
                        finish=call.finish,
                    )
                except Exception as error:
                    row.update(error_type=type(error).__name__, behavior_ok=False)
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "benchmark_progress": {
                                k: v for k, v in row.items() if k not in {"answer", "timing"}
                            }
                        }
                    ),
                    flush=True,
                )
                if row["status"] != "completed":
                    break
    finally:
        await server.stop(0)
        await backend.close()
    return rows


async def run(rounds, output):
    rows = []
    for repetition in range(rounds):
        for case_index, case in enumerate(CASES):
            offset = (repetition + case_index) % len(PROFILES)
            order = PROFILES[offset:] + PROFILES[:offset]
            if repetition % 2:
                order = list(reversed(order))
            for profile in order:
                batch = await conversation(profile, case)
                rows.extend(dict(row, repetition=repetition) for row in batch)
                output.write_text(
                    json.dumps(
                        {
                            "model": MODEL,
                            "scope": "real API; synthetic store and playback receipts; no ASR/TTS/SIP",
                            "cache_note": "Shared provider caches are not flushed; first turns are not guaranteed cold.",
                            "rows": rows,
                            "summary": summarize(rows),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
    print(json.dumps({"benchmark_summary": summarize(rows)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    asyncio.run(run(args.rounds, args.output))
