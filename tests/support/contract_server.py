"""Explicit test-only gRPC peer. Hex echo and synthetic PCM are NOT inference."""

import asyncio
from dataclasses import dataclass, field

import grpc
from alojan_contracts.audio import MAX_MESSAGE_BYTES, AudioStreamValidator, generation_key
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc


@dataclass
class Generation:
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    claimed: set[str] = field(default_factory=set)


class ContractPeer(rpc.RecognitionServicer, rpc.SynthesisServicer, rpc.GenerationControlServicer):
    def __init__(self):
        self.generations = {}
        self.produced = 0
        self.queue_peak = 0
        self.active_producers = 0
        self.stopped = asyncio.Event()

    async def state(self, request, context, claim=None):
        try:
            key = generation_key(request)
        except ValueError as error:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
        if key not in self.generations:
            # Fail closed: evicting tombstones would allow cancelled generations to revive.
            if len(self.generations) >= 4096:
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "generation capacity")
            self.generations[key] = Generation()
        state = self.generations[key]
        if claim:
            if context.time_remaining() is None:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "deadline required")
            if state.cancelled.is_set():
                await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
            if claim in state.claimed:
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, "generation already used")
            state.claimed.add(claim)
        return state

    async def CancelGeneration(self, request, context):
        state = await self.state(request, context)
        state.cancelled.set()
        return pb.CancelReply(cancelled=True)

    async def StreamRecognize(self, request_iterator, context):
        validator = AudioStreamValidator()
        state = None
        while True:
            read = asyncio.create_task(anext(request_iterator))
            cancelled = asyncio.create_task(state.cancelled.wait()) if state else None
            try:
                if cancelled:
                    await asyncio.wait((read, cancelled), return_when=asyncio.FIRST_COMPLETED)
                    if state.cancelled.is_set():
                        await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
                try:
                    frame = await read
                except StopAsyncIteration:
                    break
            finally:
                tasks = [read] + ([cancelled] if cancelled else [])
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            try:
                validator.accept(frame)
            except ValueError as error:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(error))
            if state is None:
                state = await self.state(frame, context, claim="recognition")
            # Test-only deadline injection, never enabled in a production service.
            if dict(context.invocation_metadata()).get("x-test-delay") == "yes":
                await asyncio.sleep(0.5)
            if state.cancelled.is_set():
                await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
            yield pb.RecognitionEvent(
                call_id=frame.call_id, generation_id=frame.generation_id, text=frame.audio.hex()
            )
        if state is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "empty audio stream")
        if state.cancelled.is_set():
            await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
        yield pb.RecognitionEvent(
            call_id=frame.call_id, generation_id=frame.generation_id, is_final=True
        )

    async def StreamSynthesize(self, request, context):
        state = await self.state(request, context, claim="synthesis")
        if request.text not in ("one", "flood"):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "expected test fixture name")
        queue = asyncio.Queue(maxsize=8)

        async def produce():
            self.active_producers += 1
            try:
                for sequence in range(1 if request.text == "one" else 100000):
                    await queue.put(
                        pb.AudioFrame(
                            call_id=request.call_id,
                            generation_id=request.generation_id,
                            sequence=sequence,
                            sample_rate_hz=8000,
                            channels=1,
                            format="pcm_s16le",
                            audio=bytes(range(160)) * 2,
                        )
                    )
                    self.produced += 1
                    self.queue_peak = max(self.queue_peak, queue.qsize())
                await queue.put(None)
            finally:
                self.active_producers -= 1

        producer = asyncio.create_task(produce())
        cancelled = asyncio.create_task(state.cancelled.wait())
        try:
            while True:
                frame = await queue.get()
                if state.cancelled.is_set():
                    await context.abort(grpc.StatusCode.CANCELLED, "generation cancelled")
                if frame is None:
                    break
                write = asyncio.create_task(context.write(frame))
                try:
                    done, _ = await asyncio.wait(
                        (write, cancelled), timeout=0.2, return_when=asyncio.FIRST_COMPLETED
                    )
                    if write in done:
                        await write
                finally:
                    write.cancel()
                    await asyncio.gather(write, return_exceptions=True)
                if state.cancelled.is_set() or write not in done:
                    producer.cancel()
                    await asyncio.gather(producer, return_exceptions=True)
                    self.stopped.set()
                    code = (
                        grpc.StatusCode.CANCELLED
                        if state.cancelled.is_set()
                        else grpc.StatusCode.RESOURCE_EXHAUSTED
                    )
                    await context.abort(code, "generation cancelled or slow consumer")
        finally:
            producer.cancel()
            cancelled.cancel()
            await asyncio.gather(producer, cancelled, return_exceptions=True)
            self.stopped.set()


async def start_peer():
    peer = ContractPeer()
    server = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
            ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
        ],
        maximum_concurrent_rpcs=32,
    )
    rpc.add_RecognitionServicer_to_server(peer, server)
    rpc.add_SynthesisServicer_to_server(peer, server)
    rpc.add_GenerationControlServicer_to_server(peer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    if not port:
        raise RuntimeError("cannot bind loopback contract peer")
    await server.start()
    return server, peer, f"127.0.0.1:{port}"
