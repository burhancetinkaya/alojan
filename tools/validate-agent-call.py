"""Synthetic loopback phone call with real CUDA speech, OpenRouter and isolated DB."""

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
import re
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
for directory in (
    "services/agent",
    "services/app-api",
    "services/voice-contracts",
    "generated/python",
    "tests/sip-integration",
):
    sys.path.insert(0, str(ROOT / directory))

import grpc  # noqa: E402
import psycopg  # noqa: E402
from psycopg.conninfo import make_conninfo  # noqa: E402
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc  # noqa: E402
from alojan.migrate import migrate  # noqa: E402
from alojan_agent.backend import Backend  # noqa: E402
from alojan_agent.service import AgentService, create_server  # noqa: E402
from alojan_agent.store import Store  # noqa: E402
from test_sip import Peer, connect, run_gateway  # noqa: E402
from test_speech import drive  # noqa: E402


async def source(text, run, index):
    async with grpc.aio.insecure_channel("127.0.0.1:15072") as channel:
        stream = rpc.SynthesisStub(channel).StreamSynthesize(
            pb.SynthesisRequest(call_id=run, generation_id=f"fixture-{index}", text=text),
            timeout=30,
        )
        audio = b"".join([f.audio async for f in stream])
        assert 0 < len(audio) <= 8000 * 2 * 9, "synthetic input exceeds fixed test capture"
        return audio


def phone_call(output, agent_port, asr_port, sources, adaptive):
    config = {
        "speech_profile": True,
        "answer_delay_ms": 0,
        "max_call_seconds": 100,
        "speech_options": [
            "--speech-test-ms",
            "10000",
            "--asr-port",
            str(asr_port),
            "--agent-port",
            str(agent_port),
        ],
    }
    if adaptive:
        config["speech_options"] = [
            "--turn-model-dir",
            str(ROOT / ".local/turn-models"),
            "--barge-in",
            "1",
            "--asr-port",
            str(asr_port),
            "--agent-port",
            str(agent_port),
        ]
    with contextmanager(run_gateway)(output, config) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            _, _, ended = drive(
                peer,
                media,
                log,
                source=sources[0],
                duration=55,
                until="event=speech_listening call=1 turn=2" if len(sources) > 1 else None,
            )
            if len(sources) > 1:
                assert not ended and "turn=2" in log.read_text(), "premature message hangup"
                _, _, ended = drive(peer, media, log, source=sources[1], duration=45)
            contents = log.read_text()
            assert ended and "event=speech_fallback" not in contents, "dialogue failed"
            assert "event=speech_test_complete" in contents, "closing did not complete"
            history = [
                line for line in contents.splitlines() if line.startswith("event=sent_speech")
            ]
            music_ms = int(re.search(r"waiting_music_ms=(\d+)", contents)[1])
            return history, music_ms
        finally:
            peer.close()


async def validate(dsn, output, asr_port, adaptive, goodbye=False):
    backend = Backend()
    store = Store(dsn)
    service = AgentService(backend, store)
    server = create_server(service)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    run = "synthetic-" + uuid.uuid4().hex
    try:
        texts = [
            "Aramayı bitir."
            if goodbye
            else "Merhaba, ben Deniz. Burhan Bey'e mesajım: Yarın beni arasın. Numaramı vermek istemiyorum.",
        ]
        if not goodbye:
            texts.append("Hayır, başka bir şey yok. Teşekkür ederim, iyi günler.")
        sources = [await source(text, run, i) for i, text in enumerate(texts)]
        histories, music_ms = await asyncio.to_thread(
            phone_call, output, port, asr_port, sources, adaptive
        )
        assert all("kind=response" in line for line in histories)
        assert len(service.calls) == 1
        call = next(iter(service.calls.values()))
        assert call.finish and call.ended and call.turns == (1 if goodbye else 2)
        assert call.note is None if goodbye else call.note is not None and not call.note.confirmed
        job = await store.pending()
        assert job
        data = await store.summary_input(job[0])
        summary = await backend.summarize(data)
        summary.confirmation_status = (
            "confirmed" if data["last_note"] and data["last_note"][1] else "unconfirmed"
        )
        await store.summary_result(job[0], summary)
        return {
            "scope": "synthetic PCMA loopback, real CUDA ASR/EMA and OpenRouter",
            "adaptive": adaptive,
            "turns": call.turns,
            "confirmed_note": bool(call.note and call.note.confirmed),
            "explicit_goodbye": goodbye,
            "postcall_summary": True,
            "sent_history": histories,
            "waiting_music_ms": music_ms,
        }
    finally:
        await server.stop(0)
        await backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asr-port", type=int, default=15171)
    parser.add_argument("--adaptive", action="store_true")
    parser.add_argument("--goodbye", action="store_true", help="End without leaving a message")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    dsn = os.environ["ALOJAN_DATABASE_URL"]
    schema = "agent_phone_" + uuid.uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
    isolated = make_conninfo(dsn, options=f"-c search_path={schema}")
    try:
        migrate(isolated)
        report = asyncio.run(
            validate(isolated, args.output, args.asr_port, args.adaptive, args.goodbye)
        )
        (args.output / "result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
    except Exception as error:
        print(json.dumps({"passed": False, "kind": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


if __name__ == "__main__":
    main()
