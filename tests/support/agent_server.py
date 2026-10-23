"""Explicit test agent: real service protocol, scripted text and no external API or DB."""

import argparse
import asyncio
import signal

from alojan_agent.service import AgentService, create_server
from test_agent import MemoryStore
from voice.v1 import voice_pb2 as pb


class Script:
    def __init__(self, mode):
        self.mode = mode

    async def stream(self, call, save):
        try:
            if self.mode == "wait":
                await asyncio.sleep(60)
            if self.mode == "fail":
                raise RuntimeError("synthetic failure")
            if self.mode == "slow":
                await asyncio.sleep(1.1)
            call.finish = call.turns >= 2
            yield "Sentetik soru." if call.turns == 1 else "Sentetik kapanış."
        finally:
            print("event=fake_agent_stream_closed", flush=True)


class ObservedStore(MemoryStore):
    async def utterance(self, *args):
        await super().utterance(*args)
        if args[2] == "assistant":
            print(
                f"event=agent_receipt text_bytes={len(args[3].encode())} sent_ms={args[4]}",
                flush=True,
            )

    async def end(self, *args):
        print("event=agent_call_ended", flush=True)
        await super().end(*args)


class ObservedAgent(AgentService):
    async def RunTurn(self, request, context):
        if self.backend.mode == "invalid-kind":
            await context.write(
                pb.AgentEvent(
                    call_id=request.call_id,
                    generation_id=request.generation_id,
                    type="text_delta",
                    text="Must not play",
                    detail_json='{"phrase_index":0,"kind":"unknown"}',
                )
            )
            return
        if self.backend.mode == "stale":
            await context.write(
                pb.AgentEvent(
                    call_id="other-call",
                    generation_id=request.generation_id,
                    type="text_delta",
                    text="Must not play",
                    detail_json='{"phrase_index":0}',
                )
            )
            return
        if self.backend.mode == "missing-end":
            return
        await super().RunTurn(request, context)


async def serve(port, mode):
    server = create_server(ObservedAgent(Script(mode), ObservedStore()))
    assert server.add_insecure_port(f"127.0.0.1:{port}")
    await server.start()
    stopped = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stopped.set)
    print("event=fake_agent_ready", flush=True)
    try:
        await stopped.wait()
    finally:
        await server.stop(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", default="normal")
    args = parser.parse_args()
    asyncio.run(serve(args.port, args.mode))
