"""Pinned TTS capability checks over real RPC with explicitly synthetic inference."""

import asyncio
from dataclasses import FrozenInstanceError, asdict, replace

import grpc
import pytest
from voice.v1 import voice_pb2 as pb
from test_call_initialization import lease
from test_tts import SYNTHETIC_PROFILE, Producer, error_code, request, running


def configuration(cid="managed-a", **changes):
    return pb.SynthesisCallConfiguration(
        **(
            dict(
                call_id=cid,
                release_id="00000000-0000-4000-8000-000000000001",
                manifest_digest="a" * 64,
                configuration=SYNTHETIC_PROFILE.to_proto(),
            )
            | changes
        )
    )


def producer(profile=SYNTHETIC_PROFILE):
    backend = Producer()
    backend.synthesis_profile = profile
    return backend


async def rejected(operation, status):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await operation
    assert error.value.code() == status
    assert "Merhaba" not in error.value.details()


def test_two_calls_pin_profiles_and_release_identity_without_model_reload():
    async def run():
        async with running(producer()) as (service, backend, stub, control):
            headers = {}
            for cid, digest in (("managed-a", "a" * 64), ("managed-b", "b" * 64)):
                headers[cid] = await lease(control, cid)
                config = configuration(cid, manifest_digest=digest)
                assert (await stub.ConfigureCall(config, timeout=1, metadata=headers[cid])).accepted
                config.configuration.voice = "modified"
            for turn, cid in enumerate(("managed-a", "managed-b", "managed-a")):
                frames = [
                    f
                    async for f in stub.StreamSynthesize(
                        request(call_id=cid, generation_id=f"g{turn}"),
                        timeout=1,
                        metadata=headers[cid],
                    )
                ]
                assert len(frames) == 3 and all(f.call_id == cid for f in frames)
            assert len(backend.calls) == 3
            assert (
                await stub.ConfigureCall(configuration(), timeout=1, metadata=headers["managed-a"])
            ).accepted
            for changed in (
                configuration(manifest_digest="c" * 64),
                configuration(release_id="00000000-0000-4000-8000-000000000002"),
            ):
                await rejected(
                    stub.ConfigureCall(changed, timeout=1, metadata=headers["managed-a"]),
                    grpc.StatusCode.FAILED_PRECONDITION,
                )
            # Backend declarations cannot mutate the service snapshot after startup.
            backend.synthesis_profile = replace(SYNTHETIC_PROFILE, voice="other")
            assert service.loaded_profile == SYNTHETIC_PROFILE
            with pytest.raises(FrozenInstanceError):
                service.loaded_profile.voice = "other"
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-a", lease=headers["managed-a"][0][1]),
                timeout=1,
            )
            assert set(service.configurations) == {"managed-b"}
            assert all(cid == "managed-b" for cid, _ in service.generations)
            service.release_call("managed-b")  # Same expiry callback as the production timer.
            assert not service.configurations and not service.leases and not service.generations
            fresh = await lease(control, "managed-a")
            await error_code(
                stub.StreamSynthesize(request(call_id="managed-a"), timeout=1, metadata=fresh),
                grpc.StatusCode.FAILED_PRECONDITION,
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"call_id": "legacy"},
        {"call_id": "managed-bad id"},
        {"release_id": "bad"},
        {"manifest_digest": "bad"},
        {"configuration": pb.SynthesisConfiguration()},
        {
            "configuration": pb.SynthesisConfiguration(
                **(asdict(SYNTHETIC_PROFILE) | {"schema_version": 2})
            )
        },
    ],
)
def test_invalid_synthesis_configuration_does_not_pin_or_infer(change):
    async def run():
        async with running(producer()) as (service, backend, stub, control):
            headers = await lease(control, "managed-a")
            await rejected(
                stub.ConfigureCall(configuration(**change), timeout=1, metadata=headers),
                grpc.StatusCode.INVALID_ARGUMENT,
            )
            assert not service.configurations and not backend.calls

    asyncio.run(run())


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "different/model"),
        ("model_revision", "b" * 40),
        ("voice", "another-voice"),
    ],
)
def test_worker_mismatch_fails_without_loading_or_switching_model(field, value):
    async def run():
        async with running(producer()) as (service, backend, stub, control):
            headers = await lease(control, "managed-a")
            config = configuration(
                configuration=replace(SYNTHETIC_PROFILE, **{field: value}).to_proto()
            )
            await rejected(
                stub.ConfigureCall(config, timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            assert not service.configurations and not backend.calls
            assert service.loaded_profile == SYNTHETIC_PROFILE

    asyncio.run(run())


@pytest.mark.parametrize(
    "field,value",
    [
        ("sample_rate_hz", 48000),
        ("channels", 2),
        ("format", "pcm_f32le"),
        ("model_revision", "invalid"),
        ("voice", "x" * 65),
        ("model", "x" * 140),
    ],
)
def test_invalid_voice_transport_and_unbounded_identifiers_rejected(field, value):
    async def run():
        async with running(producer()) as (service, backend, stub, control):
            headers = await lease(control, "managed-a")
            config = configuration()
            setattr(config.configuration, field, value)
            await rejected(
                stub.ConfigureCall(config, timeout=1, metadata=headers),
                grpc.StatusCode.INVALID_ARGUMENT,
            )
            assert not service.configurations and not backend.calls

    asyncio.run(run())


def test_configuration_requires_deadline_exact_live_lease_and_clears_on_reopen():
    async def run():
        async with running(producer(), require_agent_release=True) as (
            service,
            backend,
            stub,
            control,
        ):
            headers = await lease(control, "managed-a")
            for metadata, timeout, status in (
                ((), 1, grpc.StatusCode.FAILED_PRECONDITION),
                ((("x-alojan-lease", "wrong"),), 1, grpc.StatusCode.FAILED_PRECONDITION),
                (headers + headers, 1, grpc.StatusCode.FAILED_PRECONDITION),
                (headers, None, grpc.StatusCode.INVALID_ARGUMENT),
            ):
                await rejected(
                    stub.ConfigureCall(configuration(), timeout=timeout, metadata=metadata), status
                )
            for cid, metadata in (("managed-a", headers), ("legacy", ())):
                await error_code(
                    stub.StreamSynthesize(request(call_id=cid), timeout=1, metadata=metadata),
                    grpc.StatusCode.FAILED_PRECONDITION,
                )
            assert not backend.calls and not service.configurations
            assert (await stub.ConfigureCall(configuration(), timeout=1, metadata=headers)).accepted
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-a", lease=headers[0][1]), timeout=1
            )
            fresh = await lease(control, "managed-a")
            await rejected(
                stub.ConfigureCall(configuration(), timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            assert (await stub.ConfigureCall(configuration(), timeout=1, metadata=fresh)).accepted
            assert (
                await control.CancelGeneration(
                    pb.CancelRequest(call_id="managed-a", generation_id="cancelled"),
                    timeout=1,
                    metadata=fresh,
                )
            ).cancelled
            await error_code(
                stub.StreamSynthesize(
                    request(call_id="managed-a", generation_id="cancelled"),
                    timeout=1,
                    metadata=fresh,
                ),
                grpc.StatusCode.CANCELLED,
            )
            assert not backend.calls

    asyncio.run(run())


def test_undeclared_backend_cannot_claim_release_compatibility():
    async def run():
        async with running() as (service, backend, stub, control):
            headers = await lease(control, "managed-a")
            await rejected(
                stub.ConfigureCall(configuration(), timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            await error_code(
                stub.StreamSynthesize(request(call_id="managed-a"), timeout=1, metadata=headers),
                grpc.StatusCode.FAILED_PRECONDITION,
            )
            assert not service.configurations and not backend.calls
            assert len([f async for f in stub.StreamSynthesize(request(), timeout=1)]) == 3

    asyncio.run(run())


def test_release_cancels_active_synthesis_and_drops_profile_pin():
    async def run():
        backend = producer()
        backend.block = True
        async with running(backend) as (service, _, stub, control):
            headers = await lease(control, "managed-a")
            await stub.ConfigureCall(configuration(), timeout=1, metadata=headers)
            call = stub.StreamSynthesize(request(call_id="managed-a"), timeout=2, metadata=headers)
            reading = asyncio.create_task(call.read())
            assert await asyncio.to_thread(backend.started.wait, 1)
            await control.ReleaseCall(
                pb.CallLeaseRequest(call_id="managed-a", lease=headers[0][1]), timeout=1
            )
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await reading
            assert error.value.code() == grpc.StatusCode.CANCELLED
            assert not service.configurations and not service.generations and not service.leases
            backend.release.set()
            await asyncio.shield(service.inference)
            assert backend.closed.is_set()

    asyncio.run(run())


@pytest.mark.parametrize("failure", [None, "weights", "graphs"])
def test_ema_declares_capability_only_after_verified_load_and_warmup(monkeypatch, failure):
    import sys
    from types import ModuleType, SimpleNamespace
    from alojan_tts import model

    events = []
    paths = {name: "synthetic/" + name for name in model.WEIGHTS}

    def verified_paths():
        events.append("weights")
        if failure == "weights":
            raise RuntimeError("synthetic checksum failure")
        return paths

    api = ModuleType("ema_lightning.api")
    api.hf_hub_download = lambda *args: pytest.fail("unexpected download")

    class FakeEMA:
        def __init__(self, device):
            assert device == "cuda"
            for name, path in paths.items():
                assert api.hf_hub_download(model.MODEL, name) == path
            events.append("loaded")
            self._engine = SimpleNamespace(graphs=None)

        def lightning(self, batch_size):
            assert batch_size == 1
            events.append("warmed")
            self._engine.graphs = None if failure == "graphs" else object()

    ema = ModuleType("ema_lightning")
    ema.EMA, ema.api = FakeEMA, api
    monkeypatch.setitem(sys.modules, "ema_lightning", ema)
    monkeypatch.setitem(sys.modules, "ema_lightning.api", api)
    monkeypatch.setitem(sys.modules, "ema_lightning.engine", SimpleNamespace(WINDOW=1))
    monkeypatch.setitem(sys.modules, "ema_lightning.scheduler", SimpleNamespace(Request=object))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            cuda=SimpleNamespace(
                is_available=lambda: True, synchronize=lambda: events.append("synchronized")
            ),
            set_num_threads=lambda _: None,
        ),
    )
    monkeypatch.setattr(model, "model_paths", verified_paths)
    backend = object.__new__(model.EmaBackend)
    if failure:
        with pytest.raises(RuntimeError):
            backend.__init__()
        assert not hasattr(backend, "synthesis_profile")
    else:
        backend.__init__()
        assert backend.synthesis_profile == SYNTHETIC_PROFILE
        assert events == ["weights", "loaded", "warmed", "synchronized"]
