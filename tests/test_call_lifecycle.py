"""Managed call reclamation over real loopback gRPC, with synthetic inference."""

import asyncio
from contextlib import AsyncExitStack

import grpc
import pytest
from voice.v1 import voice_pb2 as pb

import test_agent
import test_asr
import test_tts
from test_tts_configuration import configuration, producer


async def open_call(control, cid):
    reply = await control.OpenCall(pb.CallLeaseRequest(call_id=cid), timeout=2)
    return reply.lease, (("x-alojan-lease", reply.lease),)


async def release(control, cid, token):
    assert (
        await control.ReleaseCall(pb.CallLeaseRequest(call_id=cid, lease=token), timeout=2)
    ).accepted


def test_sequential_calls_exceed_old_lifetime_limits_without_retained_state():
    async def check(agent, agent_control, service):
        async with AsyncExitStack() as stack:
            asr, _, recognition, asr_control = await stack.enter_async_context(test_asr.running())
            tts, _, synthesis, tts_control = await stack.enter_async_context(
                test_tts.running(producer())
            )
            for index in range(140):
                cid = f"managed-sequential-{index}"
                opened = []
                for control in (agent_control, asr_control, tts_control):
                    token, metadata = await open_call(control, cid)
                    opened.append((control, token, metadata))
                    # >4096 unique generation tombstones per resident worker in this run.
                    for generation in range(32):
                        await control.CancelGeneration(
                            pb.CancelRequest(call_id=cid, generation_id=f"cancel-{generation}"),
                            timeout=2,
                            metadata=metadata,
                        )
                turn = [
                    e
                    async for e in agent.RunTurn(
                        test_agent.request(cid), timeout=2, metadata=opened[0][2]
                    )
                ]
                assert turn[-1].type == "end"
                assert [
                    e
                    async for e in recognition.StreamRecognize(
                        test_asr.frames(call_id=cid), timeout=2, metadata=opened[1][2]
                    )
                ][-1].is_final
                assert (
                    await synthesis.ConfigureCall(
                        configuration(cid), timeout=2, metadata=opened[2][2]
                    )
                ).accepted
                audio = [
                    e
                    async for e in synthesis.StreamSynthesize(
                        test_tts.request(call_id=cid), timeout=2, metadata=opened[2][2]
                    )
                ]
                assert len(audio) == 3
                await agent.ReportPlayback(
                    pb.PlaybackReport(
                        call_id=cid,
                        generation_id="turn-1",
                        phrase_index=0,
                        sent_audio_ms=100,
                        completed=True,
                    ),
                    timeout=2,
                    metadata=opened[0][2],
                )
                await agent.EndCall(
                    pb.CallEnd(call_id=cid, reason="completed"), timeout=2, metadata=opened[0][2]
                )
                for control, token, _ in opened:
                    await release(control, cid, token)
                assert not service.calls and not service.turn_tasks
                assert not tts.configurations
                for worker in (service, asr, tts):
                    assert not worker.leases and not worker.generations and not worker.active
            assert len(service.store.ended) == 140
            assert len(service.store.utterances) == 280

    asyncio.run(test_agent.scenario(check))


def test_closed_and_reopened_call_rejects_all_old_operations():
    async def check(stub, control, service):
        cid = "managed-reuse"
        old, metadata = await open_call(control, cid)
        events = [
            e async for e in stub.RunTurn(test_agent.request(cid), timeout=2, metadata=metadata)
        ]
        assert events[-1].type == "end"
        await release(control, cid, old)
        await release(control, cid, old)
        for old_metadata in (metadata, ()):
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.RunTurn(test_agent.request(cid), timeout=2, metadata=old_metadata).read()
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
        new, fresh = await open_call(control, cid)
        assert new != old
        operations = [
            control.CancelGeneration(
                pb.CancelRequest(call_id=cid, generation_id="turn-1"), timeout=2, metadata=metadata
            ),
            control.ReleaseCall(pb.CallLeaseRequest(call_id=cid, lease=old), timeout=2),
            stub.ReportPlayback(
                pb.PlaybackReport(call_id=cid, generation_id="turn-1"), timeout=2, metadata=metadata
            ),
            stub.EndCall(pb.CallEnd(call_id=cid, reason="completed"), timeout=2, metadata=metadata),
        ]
        for operation in operations:
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await operation
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
        assert [e async for e in stub.RunTurn(test_agent.request(cid), timeout=2, metadata=fresh)][
            -1
        ].type == "end"
        await release(control, cid, new)
        assert not service.calls and not service.generations and not service.leases

    asyncio.run(test_agent.scenario(check))


def test_release_cancels_pending_agent_before_reclaiming_context():
    async def check(stub, control, service):
        cid = "managed-blocked"
        token, metadata = await open_call(control, cid)
        stream = stub.RunTurn(test_agent.request(cid), timeout=3, metadata=metadata)
        pending = asyncio.create_task(stream.read())
        for _ in range(100):
            if service.active:
                break
            await asyncio.sleep(0.01)
        assert service.active == 1
        await release(control, cid, token)
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await pending
        assert error.value.code() == grpc.StatusCode.CANCELLED
        for _ in range(100):
            if not service.active:
                break
            await asyncio.sleep(0.01)
        assert not service.active and not service.calls and not service.generations
        service.backend.mode = "normal"
        token, metadata = await open_call(control, "managed-next")
        assert [
            e
            async for e in stub.RunTurn(
                test_agent.request("managed-next"), timeout=2, metadata=metadata
            )
        ][-1].type == "end"
        await release(control, "managed-next", token)

    asyncio.run(test_agent.scenario(check, "wait"))


def test_lease_capacity_validation_and_expiry_cleanup():
    async def check(stub, control, service):
        for cid in ("legacy", "managed-" + "x" * 64):
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await open_call(control, cid)
            assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        for n in range(128):
            await open_call(control, f"managed-{n}")
        with pytest.raises(grpc.aio.AioRpcError) as error:
            await open_call(control, "managed-overflow")
        assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
        token = service.leases["managed-0"][0]
        metadata = (("x-alojan-lease", token),)
        assert [
            e
            async for e in stub.RunTurn(
                test_agent.request("managed-0"), timeout=2, metadata=metadata
            )
        ][-1].type == "end"
        # Exercise the actual expiry callback without a five-minute unit-test sleep.
        timer = service.leases["managed-0"][1]
        assert 298 < timer.when() - asyncio.get_running_loop().time() <= 300
        timer._run()
        assert "managed-0" not in service.leases and "managed-0" not in service.calls
        assert not service.generations
        await open_call(control, "managed-replacement")
        service.close_leases()
        assert not service.leases

    asyncio.run(test_agent.scenario(check))


@pytest.mark.parametrize("kind", ["asr", "tts"])
def test_release_discards_native_output_without_reusing_busy_gpu_slot(kind):
    async def run():
        context = test_asr.running() if kind == "asr" else test_tts.running(producer())
        async with context as (service, backend, speech, control):

            def stream(cid, metadata):
                if kind == "asr":
                    return speech.StreamRecognize(
                        test_asr.frames(call_id=cid), timeout=3, metadata=metadata
                    )
                return speech.StreamSynthesize(
                    test_tts.request(call_id=cid), timeout=3, metadata=metadata
                )

            backend.block = True
            old, metadata = await open_call(control, "managed-native")
            if kind == "tts":
                assert (
                    await speech.ConfigureCall(
                        configuration("managed-native"), timeout=2, metadata=metadata
                    )
                ).accepted
            active = stream("managed-native", metadata)
            pending = asyncio.create_task(active.read())
            assert await asyncio.to_thread(backend.started.wait, 2)
            await release(control, "managed-native", old)
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await pending
            assert error.value.code() == grpc.StatusCode.CANCELLED
            for _ in range(100):
                if not service.active:
                    break
                await asyncio.sleep(0.01)
            assert not service.generations and not service.leases
            new, fresh = await open_call(control, "managed-native-next")
            if kind == "tts":
                assert not service.configurations
                assert (
                    await speech.ConfigureCall(
                        configuration("managed-native-next"), timeout=2, metadata=fresh
                    )
                ).accepted
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stream("managed-native-next", fresh).read()
            assert error.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
            backend.release.set()
            await asyncio.wait_for(asyncio.shield(service.inference), 2)
            assert [e async for e in stream("managed-native-next", fresh)]
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stream("managed-native", metadata).read()
            assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
            await release(control, "managed-native-next", new)
            assert not service.generations and not service.leases

    asyncio.run(run())
