"""Explicit fake inference for native gateway tests; real gRPC, no model readiness."""

import argparse
import audioop
import wave
import asyncio
import math
import signal
import struct
import time

from alojan_asr.service import RecognitionService, create_server as asr_server
from alojan_tts.service import SynthesisService, create_server as tts_server
from voice.v1 import voice_pb2 as pb


class Decoder:
    def __init__(self, mode):
        self.mode = mode

    def transcribe(self, audio, sample_format):
        if self.mode == "asr-fail":
            raise RuntimeError("private failed inference")
        if self.mode == "asr-stall":
            time.sleep(8)
        assert sample_format == "pcm_s16le" and len(audio) % 640 == 0
        print(f"event=fake_asr samples={len(audio) // 2}", flush=True)
        if self.mode.startswith("asr-pause-"):
            pause = int(self.mode.rsplit("-", 1)[1])
            return "Çünkü" if len(audio) < (6100 + pause) * 32 else "Yarın arayın."
        if self.mode == "asr-incomplete":
            return "Çünkü"
        return "" if self.mode == "asr-empty" else "Synthetic speech test"


class Producer:
    def __init__(self, mode):
        self.mode = mode

    def stream(self, text):
        if self.mode == "tts-fail":
            raise RuntimeError("private failed synthesis")
        if self.mode == "tts-stall":
            time.sleep(8)
        samples = b"".join(
            struct.pack("<h", round(10000 * math.sin(i * math.tau * 880 / 8000)))
            for i in range(16000)
        )
        try:
            # The output differs from the 440 Hz incoming fixture and the greeting.
            yield samples[:1000]
            yield samples[1000:]
        finally:
            print("event=fake_tts_closed", flush=True)


class ObservedRecognition(RecognitionService):
    async def StreamRecognize(self, request_iterator, context):
        if self.backend.mode in {"barge-backchannel", "barge-invalid-monitor"}:
            first = await anext(request_iterator)

            async def frames():
                yield first
                async for item in request_iterator:
                    yield item

            if first.generation_id.endswith("-monitor"):
                async for frame in frames():
                    if frame.sequence % 10 == 9:
                        await context.write(
                            pb.RecognitionEvent(
                                call_id=frame.call_id,
                                generation_id=frame.generation_id,
                                text="Evet.",
                                processed_audio_ms=(
                                    300000
                                    if self.backend.mode == "barge-invalid-monitor"
                                    else (frame.sequence + 1) * 20
                                ),
                            )
                        )
                return
            await super().StreamRecognize(frames(), context)
            return
        if self.backend.mode == "asr-invalid-coverage":
            async for frame in request_iterator:
                await context.write(
                    pb.RecognitionEvent(
                        call_id=frame.call_id,
                        generation_id=frame.generation_id,
                        text="Synthetic invalid coverage",
                        processed_audio_ms=300000,
                    )
                )
                return
        if self.backend.mode == "asr-early-final":
            first = True
            async for frame in request_iterator:
                if first:
                    first = False
                    await context.write(
                        pb.RecognitionEvent(
                            call_id=frame.call_id,
                            generation_id=frame.generation_id,
                            text="Premature synthetic result",
                            is_final=True,
                        )
                    )
            return
        await super().StreamRecognize(request_iterator, context)

    async def CancelGeneration(self, request, context):
        result = await super().CancelGeneration(request, context)
        print("event=fake_cancel service=asr", flush=True)
        return result


class FaultySynthesis(SynthesisService):
    async def CancelGeneration(self, request, context):
        result = await super().CancelGeneration(request, context)
        print("event=fake_cancel service=tts", flush=True)
        return result

    async def StreamSynthesize(self, request, context):
        if self.backend.mode.startswith("barge-"):
            frequency = 880 if request.generation_id == "turn-1" else 660
            count = 400 if request.generation_id == "turn-1" else 100
            print(f"event=fake_generation generation={request.generation_id}", flush=True)
            reference = None
            if self.backend.mode == "barge-echo":
                with wave.open("assets/asr/tr-v1/phone.wav") as source:
                    reference = audioop.ratecv(
                        source.readframes(source.getnframes()),
                        2,
                        1,
                        source.getframerate(),
                        8000,
                        None,
                    )[0]
                count = (len(reference) + 319) // 320
            for index in range(count):
                pcm = b"".join(
                    struct.pack("<h", round(10000 * math.sin(i * math.tau * frequency / 8000)))
                    for i in range(index * 160, (index + 1) * 160)
                )
                if reference is not None:
                    pcm = reference[index * 320 : (index + 1) * 320].ljust(320, b"\0")
                await context.write(
                    pb.AudioFrame(
                        call_id=request.call_id,
                        generation_id=request.generation_id,
                        sequence=index,
                        sample_rate_hz=8000,
                        channels=1,
                        format="pcm_s16le",
                        audio=pcm,
                    )
                )
                await asyncio.sleep(0.005)
            return
        if self.backend.mode in {"tts-stale", "tts-sequence", "tts-format"}:
            await context.write(
                pb.AudioFrame(
                    call_id="other" if self.backend.mode == "tts-stale" else request.call_id,
                    generation_id=request.generation_id,
                    sequence=1 if self.backend.mode == "tts-sequence" else 0,
                    sample_rate_hz=16000 if self.backend.mode == "tts-format" else 8000,
                    channels=1,
                    format="pcm_s16le",
                    audio=b"\0" * 320,
                )
            )
            return
        await super().StreamSynthesize(request, context)


async def serve(args):
    recognition = ObservedRecognition(Decoder(args.mode))
    synthesis = FaultySynthesis(Producer(args.mode))
    servers = [asr_server(recognition), tts_server(synthesis)]
    for server, port in zip(servers, (args.asr_port, args.tts_port)):
        assert server.add_insecure_port(f"127.0.0.1:{port}")
        await server.start()
    stopped = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stopped.set)
    print("event=fake_speech_ready", flush=True)
    try:
        await stopped.wait()
    finally:
        recognition.close()
        synthesis.close()
        for server in servers:
            await server.stop(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asr-port", type=int, required=True)
    parser.add_argument("--tts-port", type=int, required=True)
    parser.add_argument("--mode", default="normal")
    asyncio.run(serve(parser.parse_args()))
