"""Explicit real-API evaluation of synthetic dialogues; no carrier calls or durable writes."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
for relative in ("services/agent", "services/voice-contracts", "generated/python", "tests"):
    sys.path.insert(0, str(ROOT / relative))

import grpc  # noqa: E402
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc  # noqa: E402
from alojan_agent.backend import Backend  # noqa: E402
from alojan_agent.models import offers_more_help  # noqa: E402
from alojan_agent.service import AgentService, create_server  # noqa: E402
from test_agent import MemoryStore, request  # noqa: E402


async def evaluate(cases, output):
    backend = Backend()
    service = AgentService(backend, MemoryStore())
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    rows = []
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = rpc.AgentStub(channel)
            for case in cases:
                invitations = 0
                for turn, expected in enumerate(case["turns"], 1):
                    row = {"case": case["id"], "turn": turn, "failures": []}
                    events = []
                    previous = service.calls.get(case["id"])
                    previous_timing = previous.timing if previous else None
                    started = time.monotonic()
                    try:
                        async for event in stub.RunTurn(
                            request(cid=case["id"], gen=f"turn-{turn}", text=expected["text"]),
                            timeout=15,
                        ):
                            if event.type == "text_delta" and "first_phrase_ms" not in row:
                                row["first_phrase_ms"] = round((time.monotonic() - started) * 1000)
                            events.append(event)
                        reply = " ".join(e.text for e in events if e.type == "text_delta")
                        call = service.calls[case["id"]]
                        note = call.note.model_dump() if call.note else None
                        note_text = json.dumps(note, ensure_ascii=False).casefold()
                        row.update(reply=reply, note=note, version=call.version, finish=call.finish)
                        if expected["note"] is not None and bool(note) != expected["note"]:
                            row["failures"].append("note_presence")
                        if call.finish != expected["finish"]:
                            row["failures"].append("completion")
                        if "version" in expected and call.version != expected["version"]:
                            row["failures"].append("note_version")
                        if len(reply) > 400 or reply.count("?") > 1 or not reply:
                            row["failures"].append("speech_bounds")
                        for key, actual in (("reply", reply.casefold()), ("note", note_text)):
                            if any(
                                x.casefold() not in actual for x in expected.get(key + "_all", [])
                            ):
                                row["failures"].append(key + "_missing_detail")
                            if any(x.casefold() in actual for x in expected.get(key + "_none", [])):
                                row["failures"].append(key + "_forbidden_detail")
                            alternatives = expected.get(key + "_any", [])
                            if alternatives and not any(
                                x.casefold() in actual for x in alternatives
                            ):
                                row["failures"].append(key + "_missing_alternative")
                        invitations += int(offers_more_help(reply))
                        if invitations > 1:
                            row["failures"].append("repeated_invitation")
                        for event in events:
                            if event.type == "text_delta":
                                await stub.ReportPlayback(
                                    pb.PlaybackReport(
                                        call_id=case["id"],
                                        generation_id=f"turn-{turn}",
                                        phrase_index=json.loads(event.detail_json)["phrase_index"],
                                        sent_audio_ms=500,
                                        completed=True,
                                    ),
                                    timeout=2,
                                )
                    except Exception as error:
                        row["failures"].append(type(error).__name__)
                    finally:
                        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                        current = service.calls.get(case["id"])
                        if current and current.timing and current.timing is not previous_timing:
                            row["timing"] = current.timing.snapshot()
                    rows.append(row)
                    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
                    print(
                        json.dumps({k: v for k, v in row.items() if k not in {"reply", "note"}}),
                        flush=True,
                    )
                    if row.get("finish") and not expected["finish"]:
                        # An unexpected hangup invalidates the remaining dialogue; never count it as passed.
                        for skipped in range(turn + 1, len(case["turns"]) + 1):
                            rows.append(
                                {"case": case["id"], "turn": skipped, "failures": ["prior_hangup"]}
                            )
                        break
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"passed": sum(not r["failures"] for r in rows), "total": len(rows)}))
        return any(r["failures"] for r in rows)
    finally:
        await server.stop(0)
        await backend.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "tests/fixtures/agent/dialogue-review.json"
    )
    parser.add_argument("--output", type=Path, required=True, help="Private evaluation JSON path")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sys.exit(int(asyncio.run(evaluate(json.loads(args.cases.read_text()), args.output))))
