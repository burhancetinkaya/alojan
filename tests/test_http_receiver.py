"""Real loopback TLS receiver and scoped delivery; synthetic DNS/routing only."""

import asyncio
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import ssl
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import httpx2 as httpx
import pytest

from alojan.auth import connection
from alojan_agent.http_delivery import Webhook
from test_action_delivery import Transport, due
from test_http_actions import TOKEN, URL, config, source
import test_http_actions as actions

accounts, database, dedicated, prepared = (
    actions.accounts,
    actions.database,
    actions.dedicated,
    actions.prepared,
)


@pytest.fixture
def receiver(tmp_path, monkeypatch, request):
    wrong_host = getattr(request, "param", False)
    host = "wrong.example.test" if wrong_host else urlsplit(URL).hostname
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "receiver.pem", tmp_path / "receiver.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    seen, server_names = [], []
    response = {"status": 204, "disconnect": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def receive(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            seen.append((self.command, self.path, self.headers, json.loads(body)))
            if response["disconnect"]:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(response["status"])
            self.send_header("Location", "/must-not-follow")
            self.end_headers()

        do_POST = do_PUT = do_PATCH = receive

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    context.set_servername_callback(lambda sock, name, ctx: server_names.append(name))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    trusted = ssl.create_default_context(cafile=str(cert_path))

    class LoopbackClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
            super().__init__(**kwargs, verify=trusted)

        def stream(self, method, url, **kwargs):
            assert url.host == "93.184.216.34"
            assert kwargs["extensions"]["sni_hostname"] == urlsplit(URL).hostname
            # Only socket routing/trust is synthetic; the real client performs TLS and HTTP.
            return super().stream(
                method, url.copy_with(host="127.0.0.1", port=server.server_port), **kwargs
            )

    class LocalWebhook(Webhook):
        async def resolve(self, url):
            assert url == URL
            return "93.184.216.34"

    monkeypatch.setattr("alojan_agent.http_delivery.httpx.AsyncClient", LoopbackClient)
    try:
        yield LocalWebhook(), seen, server_names, response
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
def test_real_tls_delivery_preserves_typed_payload_and_does_not_repeat(
    prepared, accounts, receiver, method
):
    create, worker, _, _, ref, _ = prepared
    create(
        [
            config(
                ref,
                method=method,
                body={
                    "call": source("call_id", "fail"),
                    "status": source("summary_status"),
                    "count": {"kind": "literal", "value": 7.25},
                    "enabled": {"kind": "literal", "value": False},
                    "unknown": {"kind": "literal", "value": None},
                },
            )
        ]
    )
    http, seen, names, _ = receiver
    telegram = Transport()
    assert asyncio.run(worker.process_one(telegram, http_transport=http))
    with connection(accounts.dsn) as conn:
        job, status, code, attempts = conn.execute(
            "SELECT id,status,http_status,attempts FROM action_jobs"
        ).fetchone()
        call_id = conn.execute("SELECT call_id FROM call_finalizations").fetchone()[0]
    assert (status, code, attempts) == ("sent", 204, 1)
    assert len(seen) == 1 and not telegram.calls
    actual_method, path, headers, body = seen[0]
    assert actual_method == method and urlsplit(path).path == "/calls"
    assert parse_qs(urlsplit(path).query).keys() == {"agent"}
    assert headers["Host"] == "hooks.example.test"
    assert headers["Authorization"] == "Bearer " + TOKEN
    assert headers["Idempotency-Key"] == str(job)
    assert headers["X-Data-Team"] == "support"
    assert body == dict(call=str(call_id), status="done", count=7.25, enabled=False, unknown=None)
    assert names == ["hooks.example.test"]
    due(accounts)
    assert not asyncio.run(worker.process_one(telegram, http_transport=http))
    assert len(seen) == 1


@pytest.mark.parametrize(
    "status,disconnect,expected",
    [
        (302, False, "failed"),
        (401, False, "failed"),
        (503, False, "delivery_unknown"),
        (204, True, "delivery_unknown"),
    ],
)
def test_real_receiver_rejection_or_lost_reply_is_not_automatically_replayed(
    prepared, accounts, receiver, status, disconnect, expected
):
    create, worker, *_ = prepared
    create()
    http, seen, _, response = receiver
    response.update(status=status, disconnect=disconnect)
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT status,attempts FROM action_jobs").fetchone() == (expected, 1)
    due(accounts)
    assert not asyncio.run(worker.process_one(Transport(), http_transport=http))
    assert len(seen) == 1


@pytest.mark.parametrize("receiver", [True], indirect=True)
def test_wrong_tls_hostname_sends_no_credentials_or_payload(prepared, accounts, receiver):
    create, worker, *_ = prepared
    create()
    http, seen, names, _ = receiver
    assert asyncio.run(worker.process_one(Transport(), http_transport=http))
    with connection(accounts.dsn) as conn:
        assert conn.execute("SELECT status,failure_code FROM action_jobs").fetchone() == (
            "pending",
            "connect_failed",
        )
    assert seen == [] and names == ["hooks.example.test"]
