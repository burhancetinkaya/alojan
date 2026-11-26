"""Release compatibility and outbound timing boundaries."""

import pytest
from pydantic import ValidationError

from alojan_contracts.configuration import AgentDraft, OutboundSettings


def draft(**values):
    return AgentDraft(
        agent_name="Örnek",
        owner_display_name="Örnek",
        owner_address="Örnek",
        owner_dative="Örneğe",
        owner_genitive="Örneğin",
        instructions="Test.",
        **values,
    )


def test_existing_release_keeps_its_serialized_form_and_hash():
    old = draft()
    assert not old.outbound.enabled
    assert "outbound" not in old.model_dump()
    assert draft(outbound={}).digest() == old.digest()
    assert old.greeting() == old.ai_introduction() + " " + old.greeting_text


def test_enabled_configuration_round_trips_in_published_content():
    enabled = draft(outbound={"enabled": True})
    assert enabled.outbound.ring_timeout_seconds == 30
    assert enabled.outbound.post_playback_seconds == 2
    assert AgentDraft.model_validate(enabled.model_dump()) == enabled
    assert enabled.digest() != draft().digest()
    assert draft(outbound={"post_playback_seconds": 0}).model_dump()["outbound"]["enabled"] is False


@pytest.mark.parametrize(
    "options",
    [
        {"ring_timeout_seconds": 0},
        {"ring_timeout_seconds": 121},
        {"post_playback_seconds": -1},
        {"post_playback_seconds": 31},
        {"post_playback_seconds": True},
        {"enabled": "true"},
        {"caller_id": "unverified"},
    ],
)
def test_invalid_policy_is_rejected(options):
    with pytest.raises(ValidationError):
        OutboundSettings.model_validate(options)


def test_synthesis_uses_release_voice_and_preserves_message(tmp_path):
    import asyncio
    import uuid
    import wave
    from test_tts_configuration import producer
    from alojan_tts.service import SynthesisService, create_server
    from alojan.outbound_worker import synthesize

    async def scenario():
        d = draft()
        backend = producer()
        service = SynthesisService(backend, require_agent_release=True)
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        message = "Randevunuz saat üçte. #123."
        job = {
            "id": uuid.uuid4(),
            "release_id": uuid.uuid4(),
            "manifest_digest": "c" * 64,
            "message": message,
            "manifest": {
                "content": d.model_dump(),
                "voice_assets": {
                    "model": backend.synthesis_profile.model,
                    "model_revision": backend.synthesis_profile.model_revision,
                },
            },
        }
        try:
            path = tmp_path / "test.wav"
            await asyncio.to_thread(synthesize, job, path, f"127.0.0.1:{port}")
            assert backend.calls == [d.ai_introduction() + " " + message]
            with wave.open(str(path)) as wav:
                assert wav.getframerate() == 8000 and wav.getnframes() > 0
            assert not service.leases
        finally:
            service.close()
            await server.stop(0)

    asyncio.run(scenario())
