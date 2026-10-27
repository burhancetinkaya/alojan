"""M3-01 real SIP/CPU detection with synthetic speech services and no external API."""

import audioop
from contextlib import contextmanager
import time
import wave

import pytest

import test_agent_dialogue
import test_speech
from test_sip import ROOT, Peer, connect, run_gateway
from test_speech import drive
from test_turn import MODELS, phone, profile

speech_services = test_speech.speech_services
agent_service = test_agent_dialogue.agent_service
pytestmark = pytest.mark.skipif(not MODELS.is_dir(), reason="native CPU models required")


def configuration(speech_services, agent_service):
    config = profile(speech_services)
    config["max_call_seconds"] = 60
    config["speech_options"] += ["--barge-in", "1", "--agent-port", str(agent_service[0])]
    return config


def wait_for_capture(peer, media, log):
    drive(peer, media, log, source=b"", duration=15, until="event=speech_test_capture")
    assert "event=speech_test_capture" in log.read_text()


@pytest.mark.parametrize("codec", [8, 0])
def test_silence_reminds_once_then_closes_politely(tmp_path, speech_services, agent_service, codec):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        peer = Peer(port, codec)
        try:
            media = connect(peer)
            wait_for_capture(peer, media, log)
            began = time.monotonic()
            frames, arrivals, ended = drive(
                peer,
                media,
                log,
                source=b"",
                duration=12,
                until="event=speech_listening call=1 turn=2",
            )
            assert not ended and "turn=2" in log.read_text(), log.read_text()
            decode = audioop.alaw2lin if codec == 8 else audioop.ulaw2lin
            first_audio = next(
                at
                for pcm, at in zip(frames, arrivals)
                if audioop.rms(decode(pcm[12:], 2), 2) > 1000
            )
            assert 6.7 <= first_audio - began < 8.2
            assert log.read_text().count("event=silence_reminder") == 1
            _, _, ended = drive(peer, media, log, source=b"", duration=32)
            assert ended and "event=speech_test_complete" in log.read_text(), log.read_text()
            assert log.read_text().count("event=silence_reminder") == 1
            assert "event=speech_fallback" not in log.read_text()
            assert "event=fake_agent_stream_closed" not in agent_service[1].read_text()
            assert "waiting_music_ms=0" in log.read_text()
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["barge-backchannel"], indirect=True)
def test_unconfirmed_activity_at_timeout_farewell_does_not_reopen_call(
    tmp_path, speech_services, agent_service
):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=b"",
                duration=38,
                until="event=speech_speaking call=1 generation=turn-2",
            )
            assert "event=speech_speaking call=1 generation=turn-2" in log.read_text()
            # Three two-second farewell phrases. A late backchannel creates pre-roll
            # but must not veto finish_call without a confirmed interruption.
            drive(peer, media, log, source=b"", duration=5.2)
            with wave.open(str(ROOT / "assets/interruption/tr-v1/acknowledgment.wav")) as wav:
                source = wav.readframes(wav.getnframes())
            _, _, ended = drive(peer, media, log, source=source, duration=8)
            contents = log.read_text()
            assert ended and "event=speech_test_complete" in contents, contents
            assert "event=speech_listening call=1 turn=3" not in contents
            assert "interruptions=0" in contents
            assert "backchannels=1" in contents
            assert "event=speech_fallback" not in contents
            assert "event=fake_agent_stream_closed" not in agent_service[1].read_text()
        finally:
            peer.close()


def test_confirmed_interruption_of_timeout_farewell_still_resumes(
    tmp_path, speech_services, agent_service
):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=b"",
                duration=38,
                until="event=speech_speaking call=1 generation=turn-2",
            )
            assert "event=speech_speaking call=1 generation=turn-2" in log.read_text()
            _, _, ended = drive(peer, media, log, source=phone(), duration=20)
            contents = log.read_text()
            assert ended and "event=speech_test_complete" in contents, contents
            assert "event=speech_interrupted call=1 cancelled_generation=turn-2" in contents
            assert "event=speech_listening call=1 turn=3" in contents
            assert "event=speech_fallback" not in contents
            assert agent_service[1].read_text().count("event=fake_agent_stream_closed") == 1
        finally:
            peer.close()


@pytest.mark.parametrize("delay", [0.2, 1.7])
def test_speech_during_reminder_survives_interruption_or_late_handoff(
    tmp_path, speech_services, agent_service, delay
):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        peer = Peer(port)
        try:
            media = connect(peer)
            drive(
                peer,
                media,
                log,
                source=b"",
                duration=20,
                until="event=speech_speaking call=1 generation=turn-1",
            )
            assert "event=silence_reminder" in log.read_text()
            drive(peer, media, log, source=b"", duration=delay)
            _, _, ended = drive(peer, media, log, source=phone(), duration=25)
            assert ended and "event=speech_test_complete" in log.read_text(), log.read_text()
            assert "event=speech_fallback" not in log.read_text()
            assert log.read_text().count("event=silence_reminder") == 1
            assert agent_service[1].read_text().count("event=fake_agent_stream_closed") == 1
            if delay < 1:
                assert "event=speech_interrupted" in log.read_text()
        finally:
            peer.close()


@pytest.mark.parametrize("speech_services", ["asr-incomplete"], indirect=True)
def test_incomplete_input_clarifies_and_listens_without_using_model(
    tmp_path, speech_services, agent_service
):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        peer = Peer(port)
        try:
            media = connect(peer)
            _, _, ended = drive(
                peer,
                media,
                log,
                source=phone(),
                duration=25,
                until="event=speech_listening call=1 turn=2",
            )
            assert not ended and "turn=2" in log.read_text(), log.read_text()
            assert "event=clarification_requested" in log.read_text()
            assert "event=silence_reminder" not in log.read_text()
            assert "event=speech_fallback" not in log.read_text()
            assert "event=fake_agent_stream_closed" not in agent_service[1].read_text()
            peer.send("BYE", 2, branch="z9hG4bKclarification")
            peer.response(200, "BYE")
        finally:
            peer.close()


def test_hangup_during_reminder_releases_next_call(tmp_path, speech_services, agent_service):
    with contextmanager(run_gateway)(tmp_path, configuration(speech_services, agent_service)) as (
        port,
        log,
        _,
    ):
        for index in (1, 2):
            peer = Peer(port)
            try:
                media = connect(peer)
                _, _, ended = drive(
                    peer,
                    media,
                    log,
                    source=b"",
                    duration=20,
                    until=f"event=speech_speaking call={index} generation=turn-1",
                )
                assert not ended and f"event=silence_reminder call={index}" in log.read_text()
                peer.send("BYE", 2, branch=f"z9hG4bKreminder{index}")
                peer.response(200, "BYE")
                time.sleep(0.4)
                assert f"event=call_closed call={index} " in log.read_text()
            finally:
                peer.close()
        assert log.read_text().count("event=silence_reminder") == 2
