"""Bounded synthesis through the resident EMA service, inside an operator-owned window."""

import hashlib
import io
import json
import wave
import uuid

import grpc
from voice.v1 import voice_pb2 as pb
from voice.v1 import voice_pb2_grpc as rpc
from alojan_contracts.assets import speech_identity, validate_manifest, validate_wav
from alojan_contracts.synthesis import EMA_MODEL, SynthesisProfile


def segments(text):
    """Preserve every word while respecting the resident worker's 512-character limit."""
    remaining = text.strip()
    while remaining:
        if len(remaining) <= 512:
            yield remaining
            return
        end = max(remaining.rfind(mark, 0, 512) for mark in (". ", "! ", "? ", "; "))
        end = end + 1 if end >= 0 else remaining.rfind(" ", 0, 513)
        if end <= 0:
            raise ValueError("Speech contains an unsupported long token")
        yield remaining[:end]
        remaining = remaining[end:].lstrip()


def generate_pack(endpoint, preparation, draft, preset, directory, check):
    call = "managed-assets-" + uuid.uuid4().hex
    manifest = dict(
        model=EMA_MODEL,
        model_revision=preset.voice_model_revision,
        speech_digest=speech_identity(draft, preset),
        greeting_pad_ms=preset.greeting_pad_ms,
    )
    profile = SynthesisProfile(EMA_MODEL, preset.voice_model_revision, draft.voice)
    with grpc.insecure_channel(
        endpoint, options=[("grpc.max_receive_message_length", 65536)]
    ) as channel:
        control, synthesis = rpc.GenerationControlStub(channel), rpc.SynthesisStub(channel)
        check()
        lease = control.OpenCall(pb.CallLeaseRequest(call_id=call), timeout=3).lease
        if not lease:
            raise ValueError("Missing synthesis lease")
        metadata = [("x-alojan-lease", lease)]
        try:
            accepted = synthesis.ConfigureCall(
                pb.SynthesisCallConfiguration(
                    call_id=call,
                    release_id=str(preparation),
                    manifest_digest=draft.digest(),
                    configuration=profile.to_proto(),
                ),
                metadata=metadata,
                timeout=3,
            )
            if not accepted.accepted:
                raise ValueError("Synthesis configuration rejected")
            for name, text in draft.speech_texts().items():
                pcm = bytearray(bytes(preset.greeting_pad_ms * 16) if name == "greeting" else b"")
                for part in segments(text):
                    check()
                    generation = uuid.uuid4().hex
                    stream = synthesis.StreamSynthesize(
                        pb.SynthesisRequest(call_id=call, generation_id=generation, text=part),
                        metadata=metadata,
                        timeout=40,
                    )
                    count = 0
                    try:
                        for frame in stream:
                            check()
                            if (
                                frame.call_id != call
                                or frame.generation_id != generation
                                or frame.sequence != count
                                or frame.sample_rate_hz != 8000
                                or frame.channels != 1
                                or frame.format != "pcm_s16le"
                                or len(frame.audio) != 320
                            ):
                                raise ValueError("Invalid synthesis frame")
                            pcm.extend(frame.audio)
                            count += 1
                            if len(pcm) > min(480000, preset.asset_max_duration_ms * 16):
                                raise ValueError("Speech exceeds prepared asset duration")
                    finally:
                        stream.cancel()
                    if not count:
                        raise ValueError("Empty synthesis")
                output = io.BytesIO()
                with wave.open(output, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(8000)
                    wav.writeframes(pcm)
                data = output.getvalue()
                (directory / f"{name}.wav").write_bytes(data)
                manifest[name] = dict(
                    sha256=hashlib.sha256(data).hexdigest(),
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    samples=len(pcm) // 2,
                )
            validated = validate_manifest(manifest, draft, preset)
            for name in draft.speech_texts():
                validate_wav(
                    (directory / f"{name}.wav").read_bytes(),
                    getattr(validated, name),
                    leading_silence_ms=preset.greeting_pad_ms if name == "greeting" else 0,
                )
            (directory / "manifest.json").write_text(json.dumps(validated.model_dump()))
        finally:
            result = control.ReleaseCall(pb.CallLeaseRequest(call_id=call, lease=lease), timeout=5)
            if not result.accepted:
                raise ValueError("Synthesis cleanup unconfirmed")
