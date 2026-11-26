"""Multi-voice publication and call isolation; PCM producers are deliberately synthetic."""

import asyncio
from dataclasses import replace
import json

import grpc
import pytest

from alojan.auth import AuthError, connection
from alojan.profiles import Profiles, validate_draft
from alojan.releases import Releases
from alojan_contracts.assets import speech_identity, validate_manifest
from alojan_contracts.configuration import EnginePreset, canonical_digest
from alojan_contracts.runtime import compile_agent
from alojan_contracts.routing import validated_release
from alojan_contracts.synthesis import POCKET_MODEL, POCKET_REVISION, POCKET_VOICES, voice_profile
from test_agent_drafts import content
import test_agent_releases
from test_agent_releases import prepare_assets, pack

from test_tts import Producer, SYNTHETIC_PROFILE, running, request
from test_tts_configuration import configuration, rejected
from test_call_initialization import lease
from voice.v1 import voice_pb2 as pb

accounts = test_agent_releases.accounts
database = test_agent_releases.database
author = test_agent_releases.author


def test_voice_identity_preserves_ema_and_invalidates_other_assets(tmp_path):
    preset = EnginePreset()
    original = validate_draft(content())
    historical = canonical_digest(
        dict(
            schema_version=1,
            texts=original.speech_texts(),
            voice="ema-default",
            model_revision=preset.voice_model_revision,
            sample_rate_hz=preset.asset_sample_rate_hz,
            greeting_pad_ms=preset.greeting_pad_ms,
        )
    )
    assert speech_identity(original, preset) == historical
    digests = {historical}
    for voice in POCKET_VOICES:
        draft = validate_draft(content() | {"voice": voice})
        profile = compile_agent(draft, preset).synthesis
        assert (profile.model, profile.model_revision, profile.voice) == (
            POCKET_MODEL,
            POCKET_REVISION,
            voice,
        )
        digest = speech_identity(draft, preset)
        assert digest not in digests
        digests.add(digest)
        manifest = json.loads((pack(tmp_path, draft) / "manifest.json").read_text())
        validate_manifest(manifest, draft, preset)
        with pytest.raises(ValueError):
            validate_manifest(manifest, original, preset)
        manifest["model"] = SYNTHETIC_PROFILE.model
        with pytest.raises(ValueError):
            validate_manifest(manifest, draft, preset)
    with pytest.raises(AuthError, match="invalid_agent_configuration"):
        validate_draft(content() | {"voice": "../custom.wav"})


def test_pocket_release_roundtrip_and_ema_rollback(accounts, author, tmp_path):
    token, scope, agent = author
    releases = Releases(accounts)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path)
    ema = releases.publish(token, scope, agent, preparation["id"], 0)
    # Use the same optimistic update boundary as UI and MCP.
    Profiles(accounts).update(token, scope, agent, content() | {"voice": "pocket-female_2"}, 1)
    preparation, _, _ = prepare_assets(accounts, author, tmp_path, version=2)
    pocket = releases.publish(token, scope, agent, preparation["id"], 1)
    with connection(accounts.dsn) as conn:
        manifest, digest = conn.execute(
            "SELECT manifest,manifest_digest FROM agent_releases WHERE id=%s", (pocket["id"],)
        ).fetchone()
        voice = conn.execute(
            "SELECT voice_ref FROM assistant_profile_revisions WHERE profile_id=%s ORDER BY revision DESC LIMIT 1",
            (agent,),
        ).fetchone()[0]
    assert voice == "pocket-female_2" and manifest["schema_version"] == 11
    validated_release(manifest, digest)
    manifest["schema_version"] = 10
    with pytest.raises(ValueError, match="version mismatch"):
        validated_release(manifest, canonical_digest(manifest))
    restored = releases.rollback(token, scope, agent, ema["id"], 2)
    assert restored["id"] != pocket["id"]


def test_calls_pin_distinct_backends_and_do_not_fallback():
    async def run():
        ema = Producer()
        ema.synthesis_profile = SYNTHETIC_PROFILE
        pocket = Producer()
        pocket.synthesis_profile = voice_profile("pocket-female_2", "")
        pocket.chunks = [b"\x03\x00" * 160]
        async with running(ema, additional_backends=[pocket]) as (service, _, stub, control):
            for call_id, profile, expected in [
                ("managed-a", SYNTHETIC_PROFILE, 1),
                ("managed-b", pocket.synthesis_profile, 3),
            ]:
                headers = await lease(control, call_id)
                await stub.ConfigureCall(
                    configuration(call_id=call_id, configuration=profile.to_proto()),
                    timeout=1,
                    metadata=headers,
                )
                frames = [
                    f
                    async for f in stub.StreamSynthesize(
                        request(call_id=call_id), timeout=2, metadata=headers
                    )
                ]
                assert frames[0].audio[:2] == bytes([expected, 0])
                await rejected(
                    stub.ConfigureCall(
                        configuration(
                            call_id=call_id,
                            configuration=replace(profile, voice="unknown").to_proto(),
                        ),
                        timeout=1,
                        metadata=headers,
                    ),
                    grpc.StatusCode.FAILED_PRECONDITION,
                )
                assert service.configurations[call_id][2] == profile
                await control.ReleaseCall(
                    pb.CallLeaseRequest(call_id=call_id, lease=headers[0][1]), timeout=1
                )
            assert len(ema.calls) == len(pocket.calls) == 1
            assert not service.configurations

    asyncio.run(run())


@pytest.mark.parametrize("failed_cleanup", [False, True])
def test_failed_pocket_cleanup_cannot_admit_ema_but_clean_errors_can_recover(failed_cleanup):
    from test_tts import error_code

    class FailedPocket(Producer):
        quiescence_confirmed = True

        def stream(self, text):
            self.quiescence_confirmed = False
            try:
                yield b"\x01\x00" * 160
                raise RuntimeError("synthetic inference failure")
            finally:
                if failed_cleanup:
                    raise RuntimeError("synthetic native cleanup failure")
                self.quiescence_confirmed = True

    async def run():
        ema = Producer()
        ema.synthesis_profile = SYNTHETIC_PROFILE
        pocket = FailedPocket()
        pocket.synthesis_profile = voice_profile("pocket-female_2", "")
        async with running(ema, additional_backends=[pocket]) as (service, _, stub, control):
            a, b = await lease(control, "managed-a"), await lease(control, "managed-b")
            await stub.ConfigureCall(
                configuration(configuration=pocket.synthesis_profile.to_proto()),
                timeout=1,
                metadata=a,
            )
            await stub.ConfigureCall(configuration(call_id="managed-b"), timeout=1, metadata=b)
            await error_code(
                stub.StreamSynthesize(request(call_id="managed-a"), timeout=2, metadata=a),
                grpc.StatusCode.INTERNAL,
            )
            await asyncio.shield(service.inference)
            assert service.cleanup_failed is failed_cleanup
            call = stub.StreamSynthesize(request(call_id="managed-b"), timeout=1, metadata=b)
            if failed_cleanup:
                await error_code(call, grpc.StatusCode.UNAVAILABLE)
                assert not ema.calls
            else:
                assert [frame async for frame in call]
                assert len(ema.calls) == 1

    asyncio.run(run())


def test_cancelled_pocket_keeps_slot_until_cleanup_before_ema():
    from test_tts import error_code

    async def run():
        ema = Producer()
        ema.synthesis_profile = SYNTHETIC_PROFILE
        pocket = Producer()
        pocket.synthesis_profile = voice_profile("pocket-female_2", "")
        pocket.block = True
        async with running(ema, additional_backends=[pocket]) as (service, _, stub, control):
            a, b = await lease(control, "managed-a"), await lease(control, "managed-b")
            await stub.ConfigureCall(
                configuration(configuration=pocket.synthesis_profile.to_proto()),
                timeout=1,
                metadata=a,
            )
            await stub.ConfigureCall(configuration(call_id="managed-b"), timeout=1, metadata=b)
            call = stub.StreamSynthesize(request(call_id="managed-a"), timeout=3, metadata=a)
            pending = asyncio.ensure_future(call.read())
            try:
                assert await asyncio.to_thread(pocket.started.wait, 1)
                call.cancel()
                await asyncio.gather(pending, return_exceptions=True)
                await error_code(
                    stub.StreamSynthesize(request(call_id="managed-b"), timeout=1, metadata=b),
                    grpc.StatusCode.RESOURCE_EXHAUSTED,
                )
                assert not ema.calls
            finally:
                pocket.release.set()
                if service.inference:
                    await asyncio.shield(service.inference)
            assert pocket.closed.is_set()
            frames = [
                f
                async for f in stub.StreamSynthesize(
                    request(call_id="managed-b", generation_id="after-cleanup"),
                    timeout=1,
                    metadata=b,
                )
            ]
            assert frames[0].audio[:2] == b"\x01\x00"

    asyncio.run(run())
