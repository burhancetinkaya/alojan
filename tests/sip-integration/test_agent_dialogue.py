"""Native two-turn SIP/RTP conversation; all inference is explicitly scripted."""

import audioop
import os
import re
import subprocess
import sys
import time

import pytest
from test_sip import ROOT, Peer, connect, run_gateway
import test_speech
from test_speech import tcp_port, drive

speech_services = test_speech.speech_services


@pytest.fixture
def agent_service(tmp_path, request):
    port = tcp_port()
    log = tmp_path / "fake-agent.log"
    mode = getattr(request, "param", "normal")
    env = os.environ | {
        "PYTHONPATH": ":".join(
            str(ROOT / p)
            for p in ["tests", "generated/python", "services/agent", "services/voice-contracts"]
        )
    }
    with log.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "support.agent_server", "--port", str(port), "--mode", mode],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=output,
        )
        try:
            until = time.monotonic() + 5
            while "event=fake_agent_ready" not in log.read_text():
                assert process.poll() is None and time.monotonic() < until, log.read_text()
                time.sleep(0.01)
            yield port, log
        finally:
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture
def agent_gateway(tmp_path, speech_services, agent_service):
    asr, tts, _, _ = speech_services
    agent, _ = agent_service
    yield from run_gateway(
        tmp_path,
        {
            "speech_profile": True,
            "answer_delay_ms": 0,
            "max_call_seconds": 30,
            "speech_options": [
                "--speech-test-ms",
                "1000",
                "--asr-port",
                str(asr),
                "--tts-port",
                str(tts),
                "--agent-port",
                str(agent),
            ],
        },
    )


@pytest.mark.parametrize("codec", [8, 0])
def test_two_turns_complete_audio_before_hangup(agent_gateway, agent_service, codec):
    port, log, _ = agent_gateway
    peer = Peer(port, codec=codec)
    try:
        media_port = connect(peer)
        frames, arrivals, bye = drive(peer, media_port, log, duration=25)
        bye_at = time.monotonic() - 0.05  # drive waits 50 ms after acknowledging BYE.
        assert bye, log.read_text()
        decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
        last_speech_at = max(
            at
            for frame, at in zip(frames, arrivals)
            if audioop.rms(decode(frame[12:], 2), 2) > 1000
        )
        assert 3 <= bye_at - last_speech_at < 3.7
        assert "generation=turn-2" in log.read_text()
        assert "event=speech_fallback" not in log.read_text()
        assert "tts_frames=200" in log.read_text(), log.read_text()
        assert "waiting_music_ms=0" in log.read_text()
        assert len(frames) >= 200
        until = time.monotonic() + 3
        while "event=agent_call_ended" not in agent_service[1].read_text():
            assert time.monotonic() < until, agent_service[1].read_text()
            time.sleep(0.01)
        assert agent_service[1].read_text().count("sent_ms=2000") == 2
        histories = [
            line for line in log.read_text().splitlines() if line.startswith("event=sent_speech")
        ]
        assert len(histories) == 2
        timings = [x for x in log.read_text().splitlines() if x.startswith("event=turn_latency")]
        assert len(timings) == 2
        for line in timings:
            assert "status=completed" in line and "kind=response" in line
            metrics = dict(re.findall(r"(\w+_ms)=(-?\d+)", line))
            assert int(metrics["agent_first_phrase_ms"]) >= 0
            assert int(metrics["endpoint_to_audio_ms"]) >= int(metrics["asr_finalize_ms"]) >= 0
            assert int(metrics["tts_first_chunk_ms"]) >= 0
            assert int(metrics["vad_end_to_audio_estimate_ms"]) == -1  # Fixed capture, no VAD.
        for line in histories:
            assert "kind=response" in line
            metrics = dict(re.findall(r"(\w+_ms)=(-?\d+)", line))
            assert int(metrics["endpoint_to_audio_ms"]) >= int(metrics["asr_finalize_ms"]) >= 0
            assert (
                int(metrics["phrase_ready_to_audio_ms"]) >= int(metrics["tts_first_chunk_ms"]) >= 0
            )
    finally:
        peer.close()


@pytest.mark.parametrize(
    "agent_service", ["fail", "stale", "missing-end", "invalid-kind"], indirect=True
)
def test_agent_failure_uses_spoken_fallback(agent_gateway, agent_service):
    port, log, _ = agent_gateway
    peer = Peer(port)
    try:
        media_port = connect(peer)
        _, _, bye = drive(peer, media_port, log, duration=20)
        assert bye and "event=speech_fallback" in log.read_text()
        line = next(x for x in log.read_text().splitlines() if x.startswith("event=turn_latency"))
        assert "status=failed" in line
    finally:
        peer.close()


@pytest.mark.parametrize("agent_service", ["slow"], indirect=True)
@pytest.mark.parametrize("codec", [8, 0])
def test_waiting_music_does_not_delay_speech_or_enter_history(agent_gateway, agent_service, codec):
    port, log, _ = agent_gateway
    peer = Peer(port, codec=codec)
    try:
        media_port = connect(peer)
        frames, _, bye = drive(peer, media_port, log, duration=25)
        assert bye and "event=speech_fallback" not in log.read_text()
        histories = [
            line for line in log.read_text().splitlines() if line.startswith("event=sent_speech")
        ]
        assert len(histories) == 2 and all("kind=response" in line for line in histories)
        for response in histories:
            assert int(re.search(r"phrase_ready_to_audio_ms=(\d+)", response)[1]) < 500
        music_ms = int(re.search(r"waiting_music_ms=(\d+)", log.read_text())[1])
        assert 400 <= music_ms <= 1200
        assert "tts_frames=200" in log.read_text()
        assert agent_service[1].read_text().count("sent_ms=2000") == 2
        decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
        quiet_audio = [decode(frame[12:], 2) for frame in frames]
        assert (
            sum(
                30 < audioop.rms(pcm, 2) < 1000 and audioop.max(pcm, 2) < 1500
                for pcm in quiet_audio
            )
            >= 5
        )
    finally:
        peer.close()


@pytest.mark.parametrize("agent_service", ["wait"], indirect=True)
@pytest.mark.parametrize("speech_services", ["barge-normal"], indirect=True)
def test_barge_in_cancels_pending_model_and_starts_next_generation(
    tmp_path,
    speech_services,
    agent_service,
):
    from contextlib import contextmanager
    from test_turn import MODELS, phone, profile

    if not MODELS.is_dir():
        pytest.skip("native CPU models required")
    config = profile(speech_services)
    config["speech_options"] += ["--barge-in", "1", "--agent-port", str(agent_service[0])]
    config["max_call_seconds"] = 60
    with contextmanager(run_gateway)(tmp_path, config) as (port, log, _):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=phone(),
                duration=20,
                until="event=speech_speaking call=1 generation=turn-1",
            )
            drive(
                peer,
                media,
                log,
                source=b"",
                duration=1.5,
            )
            frames, arrivals, _ = drive(
                peer,
                media,
                log,
                source=phone(),
                duration=15,
                until="event=speech_speaking call=1 generation=turn-2",
            )
            assert "event=speech_interrupted" in log.read_text()
            assert (
                int(
                    re.search(
                        r"event=speech_interrupted .*waiting_music_ms=(\d+)", log.read_text()
                    )[1]
                )
                > 0
            )
            assert "event=speech_speaking call=1 generation=turn-2" in log.read_text()
            assert "event=speech_fallback" not in log.read_text()
            assert "event=fake_agent_stream_closed" in agent_service[1].read_text()
            decision = int(re.search(r"decision_ms=(\d+)", log.read_text())[1]) / 1000
            quiet = [frame for frame, at in zip(frames, arrivals) if 0.1 < at - decision < 0.5]
            assert len(quiet) >= 10
            assert all(audioop.rms(audioop.alaw2lin(frame[12:], 2), 2) < 30 for frame in quiet)
            peer.send("BYE", 2, branch="z9hG4bKagent-stop")
            peer.response(200, "BYE")
            until = time.monotonic() + 2
            while "generation=turn-2 status=cancelled" not in log.read_text():
                assert time.monotonic() < until, log.read_text()
                time.sleep(0.01)
            line = next(
                x
                for x in log.read_text().splitlines()
                if x.startswith("event=turn_latency") and "generation=turn-1 " in x
            )
            assert "status=interrupted" in line and "endpoint_to_audio_ms=-1" in line
        finally:
            peer.close()
