"""Explicit synthetic OpenRouter/Agents SDK acceptance; not a phone/audio test."""

import asyncio
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
for directory in (
    "services/agent",
    "services/app-api",
    "services/voice-contracts",
    "generated/python",
):
    sys.path.insert(0, str(ROOT / directory))

import grpc  # noqa: E402
import psycopg  # noqa: E402
from psycopg.conninfo import make_conninfo  # noqa: E402
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc  # noqa: E402
from alojan.migrate import migrate  # noqa: E402
from alojan_agent.backend import Backend, MODEL  # noqa: E402
from alojan_agent.service import AgentService, create_server  # noqa: E402
from alojan_agent.store import Store, call_uuid  # noqa: E402


async def validate(dsn):
    backend = Backend()
    store = Store(dsn)
    service = AgentService(backend, store)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    cid = "synthetic-" + uuid.uuid4().hex
    timings = []
    try:
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = rpc.AgentStub(channel)
            texts = [
                "Merhaba, ben Deniz Test. Burhan Bey için mesajım: Yarın beni arasın. "
                "Geri dönüş numaramı vermek istemiyorum.",
                "Hayır, başka bir şey yok. Teşekkür ederim, iyi günler.",
            ]
            for index, text in enumerate(texts, 1):
                gen = f"turn-{index}"
                start = time.monotonic()
                first = None
                phrases = []
                async for event in stub.RunTurn(
                    pb.AgentRequest(
                        call_id=cid, generation_id=gen, final_user_text=text, context_json="{}"
                    ),
                    timeout=25,
                ):
                    if event.type == "text_delta":
                        if first is None:
                            first = time.monotonic()
                        phrases.append(event)
                # Deliberately simulated audio receipts; do not label these audio acceptance.
                for event in phrases:
                    await stub.ReportPlayback(
                        pb.PlaybackReport(
                            call_id=cid,
                            generation_id=gen,
                            phrase_index=json.loads(event.detail_json)["phrase_index"],
                            sent_audio_ms=1000,
                            completed=True,
                        ),
                        timeout=3,
                    )
                call = service.calls[cid]
                timings.append(
                    {
                        "turn": index,
                        "first_phrase_ms": round((first - start) * 1000),
                        "total_ms": round((time.monotonic() - start) * 1000),
                        "phrases": len(phrases),
                        "note_saved": bool(call.note_id),
                        "confirmed": bool(call.note and call.note.confirmed),
                        "finish": call.finish,
                    }
                )
                print(json.dumps({"progress": timings[-1]}), flush=True)
                if call.finish:
                    break
            assert call.note and not call.note.confirmed and call.finish
            assert len(timings) == 2 and not timings[0]["finish"]
            await stub.EndCall(pb.CallEnd(call_id=cid, reason="completed"), timeout=4)
            data = await store.summary_input(call_uuid(cid))
            summary = await backend.summarize(data)
            summary.confirmation_status = "confirmed" if data["last_note"][1] else "unconfirmed"
            await store.summary_result(call_uuid(cid), summary)
            assert await store.pending() is None
            return {
                "model": MODEL,
                "scope": "real API and isolated PostgreSQL; simulated audio receipts",
                "turns": timings,
                "summary_valid": True,
                "promised_action": summary.promised_action,
            }
    finally:
        await server.stop(0)
        await backend.close()


def main():
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    schema = "agent_validation_" + uuid.uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
    isolated = make_conninfo(dsn, options=f"-c search_path={schema}")
    try:
        migrate(isolated)
        print(json.dumps(asyncio.run(validate(isolated)), ensure_ascii=False), flush=True)
    except Exception as error:
        # Provider errors may contain credential or prompt material.
        print(
            json.dumps(
                {
                    "passed": False,
                    "kind": type(error).__name__,
                    "code": str(error.code()) if isinstance(error, grpc.RpcError) else "none",
                    "detail": error.details() if isinstance(error, grpc.RpcError) else "none",
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


if __name__ == "__main__":
    main()
