"""API to database to real SIP/RTP, using only synthetic loopback speech and peers."""

import asyncio
import time
import uuid
from contextlib import contextmanager

import psycopg
from starlette.testclient import TestClient

from alojan.api import COOKIE, create_app
from alojan.auth import csrf_token
from alojan.outbound_worker import Worker
from alojan_tts.service import SynthesisService, create_server
import test_outbound_api as api_tests
from test_native_auth import ORIGIN
from test_outbound_announcement import response
from test_sip import run_gateway, udp
from test_tts_configuration import producer

accounts, database, line, author = (
    api_tests.accounts,
    api_tests.database,
    api_tests.line,
    api_tests.author,
)


def test_submit_prepare_dial_and_finalize(accounts, line, tmp_path):
    session, scope, agent = line
    spool = tmp_path / "outbound"
    spool.mkdir(mode=0o700)
    sip, rtp = udp(), udp()
    cfg = {
        "env": {
            "ALOJAN_OUTBOUND_DIR": str(spool),
            "ALOJAN_OUTBOUND_SIP_USER": api_tests.numbers.DID[3:],
            "ALOJAN_OUTBOUND_SIP_PASSWORD": "synthetic",
            "ALOJAN_OUTBOUND_SIP_DOMAIN": f"127.0.0.1:{sip.getsockname()[1]}",
        }
    }

    async def run():
        backend = producer()
        service = SynthesisService(backend, require_agent_release=True)
        server = create_server(service)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            with (
                contextmanager(run_gateway)(tmp_path, cfg),
                psycopg.connect(accounts.dsn, autocommit=True) as conn,
                TestClient(create_app(accounts, ORIGIN), base_url=ORIGIN) as client,
            ):
                client.cookies.set(COOKIE, session)
                path = f"/v1/workspaces/{scope}/outbound-calls"
                submitted = client.post(
                    path,
                    json={
                        "agent_id": agent,
                        "to": "05320000000",
                        "text": "Deneme.",
                        "post_playback_seconds": 0,
                    },
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": csrf_token(session),
                        "Idempotency-Key": str(uuid.uuid4()),
                    },
                )
                assert submitted.status_code == 202
                worker = Worker(conn, spool, api_tests.numbers.NODE, f"127.0.0.1:{port}")
                assert await asyncio.to_thread(worker.step)
                assert backend.calls[0].endswith("Deneme.")
                req, target = sip.recvfrom(4096)
                body = f"v=0\r\no=test 1 1 IN IP4 127.0.0.1\r\ns=test\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio {rtp.getsockname()[1]} RTP/AVP 8\r\na=rtpmap:8 PCMA/8000\r\n"
                response(sip, target, req.decode(), 200, body)
                assert len(rtp.recv(2048)) >= 172
                while True:
                    msg = sip.recv(4096).decode()
                    if msg.startswith("BYE "):
                        response(sip, target, msg, 200)
                        break
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    worker.step()
                    detail = client.get(path + "/" + submitted.json()["id"]).json()
                    if detail["status"] == "completed":
                        break
                    await asyncio.sleep(0.03)
                assert (
                    detail["status"] == "completed" and detail["ended_at"] and detail["answered_at"]
                )
                assert not list(spool.glob("*.wav"))
        finally:
            service.close()
            await server.stop(0)
            sip.close()
            rtp.close()

    asyncio.run(run())
