"""Pinned recognition vocabulary over real loopback RPC; no CUDA/quality claims."""

import asyncio
import json
import uuid
from types import SimpleNamespace

import grpc
import pytest

from alojan_asr.model import WhisperBackend
from alojan_contracts.vocabulary import compile_replacements
from voice.v1 import voice_pb2 as pb
from test_asr import Decoder, error_code, frames, running
from test_call_initialization import lease


class VocabularyDecoder(Decoder):
    def __init__(self):
        super().__init__()
        self.default = compile_replacements('{"Merhaba dünya":"Legacy Brand"}')

    def transcribe(self, audio, sample_format, replacements=None):
        super().transcribe(audio, sample_format)
        pattern, aliases = self.default if replacements is None else replacements
        text = "Merhaba dünya, 1234. Evet."
        return pattern.sub(lambda m: aliases[m.lastgroup], text) if pattern else text


def configuration(cid="managed-a", target="Example Brand", **changes):
    return pb.RecognitionCallConfiguration(
        **(
            dict(
                call_id=cid,
                release_id="00000000-0000-4000-8000-000000000001",
                manifest_digest="a" * 64,
                configuration=pb.RecognitionConfiguration(
                    schema_version=1, replacements={"Merhaba dünya": target} if target else {}
                ),
            )
            | changes
        )
    )


async def configure(stub, control, request):
    headers = await lease(control, request.call_id)
    assert (await stub.ConfigureCall(request, timeout=1, metadata=headers)).accepted
    return headers


async def rejected(operation, status):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await operation
    assert error.value.code() == status
    assert "Merhaba" not in error.value.details()


def test_interleaved_calls_pin_aliases_and_empty_does_not_inherit_legacy():
    async def run():
        async with running(VocabularyDecoder()) as (service, decoder, stub, control):
            requests = [
                configuration(),
                configuration("managed-b", "Other Brand"),
                configuration("managed-empty", None),
            ]
            headers = {r.call_id: await configure(stub, control, r) for r in requests}
            # Configuration is copied, not retained from a mutable request or draft.
            requests[0].configuration.replacements["Merhaba dünya"] = "Changed Brand"
            for index, cid in enumerate(
                ("managed-a", "managed-b", "managed-empty", "legacy", "managed-b", "managed-a")
            ):
                events = [
                    e
                    async for e in stub.StreamRecognize(
                        frames(60, call_id=cid, generation_id=f"g{index}"),
                        timeout=2,
                        metadata=headers.get(cid, ()),
                    )
                ]
                expected = {
                    "managed-a": "Example Brand",
                    "managed-b": "Other Brand",
                    "managed-empty": "Merhaba dünya",
                    "legacy": "Legacy Brand",
                }[cid]
                assert [e.text for e in events] == [expected + ", 1234. Evet."] * 2
                assert [e.is_final for e in events] == [False, True]
                assert [e.processed_audio_ms for e in events] == [1000, 1200]
            assert len(decoder.calls) == 12
            # Identical retry is harmless even after turns; a different release/config fails.
            assert (
                await stub.ConfigureCall(configuration(), timeout=1, metadata=headers["managed-a"])
            ).accepted
            for changed in (
                requests[0],
                configuration(manifest_digest="b" * 64),
                configuration(release_id=str(uuid.uuid4())),
            ):
                await rejected(
                    stub.ConfigureCall(changed, timeout=1, metadata=headers["managed-a"]),
                    grpc.StatusCode.FAILED_PRECONDITION,
                )
            assert len(service.configurations) == 3

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"call_id": "ordinary"},
        {"release_id": "bad"},
        {"manifest_digest": "bad"},
        {"configuration": pb.RecognitionConfiguration()},
        {"configuration": pb.RecognitionConfiguration(schema_version=2)},
        {
            "configuration": pb.RecognitionConfiguration(
                schema_version=1, replacements={"1234 Number": "Other Number"}
            )
        },
        {
            "configuration": pb.RecognitionConfiguration(
                schema_version=1,
                replacements={"Merhaba dünya": "Other Brand", "MERHABA DÜNYA": "Another Brand"},
            )
        },
    ],
)
def test_invalid_configuration_never_reaches_decoder(change):
    async def run():
        async with running(VocabularyDecoder()) as (svc, decoder, stub, control):
            headers = await lease(control, "managed-a")
            await rejected(
                stub.ConfigureCall(configuration(**change), timeout=1, metadata=headers),
                grpc.StatusCode.INVALID_ARGUMENT,
            )
            assert not svc.configurations and not decoder.calls

    asyncio.run(run())


def test_configuration_requires_deadline_and_exact_live_lease():
    async def run():
        async with running(VocabularyDecoder(), require_agent_release=True) as (
            svc,
            decoder,
            stub,
            control,
        ):
            headers = await lease(control, "managed-a")
            for supplied, timeout, expected in (
                ((), 1, grpc.StatusCode.FAILED_PRECONDITION),
                ((("x-alojan-lease", "forged"),), 1, grpc.StatusCode.FAILED_PRECONDITION),
                (headers + headers, 1, grpc.StatusCode.FAILED_PRECONDITION),
                (headers, None, grpc.StatusCode.INVALID_ARGUMENT),
            ):
                await rejected(
                    stub.ConfigureCall(configuration(), timeout=timeout, metadata=supplied),
                    expected,
                )
            for cid, metadata in (("managed-a", headers), ("legacy", ())):
                await error_code(
                    stub.StreamRecognize(frames(call_id=cid), timeout=1, metadata=metadata),
                    grpc.StatusCode.FAILED_PRECONDITION,
                )
            assert not decoder.calls and not svc.configurations
            assert (await stub.ConfigureCall(configuration(), timeout=1, metadata=headers)).accepted
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-a", lease=headers[0][1]), timeout=1
            )
            assert not svc.configurations
            await rejected(
                stub.ConfigureCall(configuration(), timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            fresh = await lease(control, "managed-a")
            await error_code(
                stub.StreamRecognize(frames(call_id="managed-a"), timeout=1, metadata=fresh),
                grpc.StatusCode.FAILED_PRECONDITION,
            )

    asyncio.run(run())


def test_cannot_configure_legacy_call_after_recognition_starts():
    async def run():
        async with running(VocabularyDecoder()) as (_, _, stub, control):
            headers = await lease(control, "managed-a")
            assert [
                e
                async for e in stub.StreamRecognize(
                    frames(call_id="managed-a"), timeout=1, metadata=headers
                )
            ]
            await rejected(
                stub.ConfigureCall(configuration(), timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )

    asyncio.run(run())


def test_release_cancels_decode_and_new_call_cannot_inherit_configuration():
    async def run():
        async with running(VocabularyDecoder(), require_agent_release=True) as (
            svc,
            decoder,
            stub,
            control,
        ):
            headers = await configure(stub, control, configuration())
            decoder.block = True
            stream = stub.StreamRecognize(
                frames(50, call_id="managed-a"), timeout=3, metadata=headers
            )
            assert await asyncio.to_thread(decoder.started.wait, 1)
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-a", lease=headers[0][1]), timeout=1
            )
            await error_code(stream, grpc.StatusCode.CANCELLED)
            assert not svc.configurations and not svc.inference.done()
            fresh = await lease(control, "managed-a")
            await error_code(
                stub.StreamRecognize(frames(call_id="managed-a"), timeout=1, metadata=fresh),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            decoder.release.set()
            await asyncio.shield(svc.inference)
            await stub.ConfigureCall(configuration(target=None), timeout=1, metadata=fresh)
            result = [
                e
                async for e in stub.StreamRecognize(
                    frames(call_id="managed-a", generation_id="fresh"), timeout=1, metadata=fresh
                )
            ]
            assert result[0].text == "Merhaba dünya, 1234. Evet."

    asyncio.run(run())


def test_whisper_request_override_never_mutates_shared_decoder_defaults():
    backend = WhisperBackend.__new__(WhisperBackend)
    backend.model = SimpleNamespace(
        transcribe=lambda *a, **k: (iter([SimpleNamespace(text="Merhaba dünya, 1234.")]), None)
    )
    backend.replacement_pattern, backend.replacements = compile_replacements(
        '{"Merhaba dünya":"Legacy Brand"}'
    )
    for aliases, expected in (
        ({}, "Merhaba dünya"),
        ({"Merhaba dünya": "Other Brand"}, "Other Brand"),
    ):
        assert (
            backend._decode([0.1], compile_replacements(json.dumps(aliases)))
            == expected + ", 1234."
        )
        assert backend._decode([0.1]) == "Legacy Brand, 1234."


def test_hints_preserve_existing_decode_budget_with_call_vocabulary():
    async def run():
        async with running(VocabularyDecoder(), require_agent_release=True) as (
            _,
            decoder,
            stub,
            control,
        ):
            headers = await configure(stub, control, configuration())
            events = [
                e
                async for e in stub.StreamRecognize(
                    frames(100, call_id="managed-a", partial_hint=True), timeout=2, metadata=headers
                )
            ]
            assert [e.processed_audio_ms for e in events] == [600, 1600, 2000]
            assert [e.is_final for e in events] == [False, False, True]
            assert all(e.text == "Example Brand, 1234. Evet." for e in events)
            assert [size for size, _ in decoder.calls] == [19200, 51200, 64000]

    asyncio.run(run())
