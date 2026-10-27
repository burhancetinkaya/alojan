"""Private local probes; never print connection details or response bodies."""

import os
from pathlib import Path
import socket
import sys
import time
import urllib.request
import uuid


def healthy(service, *, maintenance=False):
    if service in {"asr", "tts", "agent"}:
        import grpc
        from grpc_health.v1 import health_pb2, health_pb2_grpc

        port, name = {
            "asr": ("15173", "Recognition"),
            "tts": ("15072", "Synthesis"),
            "agent": ("15073", "Agent"),
        }[service]
        port = os.environ.get("ALOJAN_SERVICE_PORT", port)
        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            reply = health_pb2_grpc.HealthStub(channel).Check(
                health_pb2.HealthCheckRequest(
                    service="voice.v1.Maintenance" if maintenance else f"voice.v1.{name}"
                ),
                timeout=2,
            )
            return reply.status == health_pb2.HealthCheckResponse.SERVING
    if maintenance:
        raise ValueError("maintenance checks require an inference worker")
    if service == "api":
        port = os.environ.get("ALOJAN_HEALTH_PORT", "18080")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=3) as r:
            return r.status == 200
    if service == "telegram":
        return time.time() - Path("/tmp/alojan-notification-heartbeat").stat().st_mtime < 90
    if service == "gateway":
        # OPTIONS verifies the SIP event loop without creating a call or recording audio.
        host = os.environ["ALOJAN_SIP_BIND"]
        port = int(os.environ.get("ALOJAN_SIP_PORT", "5060"))
        tag = uuid.uuid4().hex
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            local = sock.getsockname()[1]
            message = (
                f"OPTIONS sip:{host}:{port} SIP/2.0\r\n"
                f"Via: SIP/2.0/UDP 127.0.0.1:{local};branch=z9hG4bK{tag};rport\r\n"
                f"From: <sip:health@localhost>;tag={tag}\r\n"
                f"To: <sip:{host}>\r\nCall-ID: health-{tag}\r\n"
                "CSeq: 1 OPTIONS\r\nMax-Forwards: 1\r\nContent-Length: 0\r\n\r\n"
            )
            sock.settimeout(3)
            sock.sendto(message.encode(), (host, port))
            data, _ = sock.recvfrom(8192)
            return data.startswith(b"SIP/2.0 200 ") and tag.encode() in data
    raise ValueError("unknown service")


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--maintenance"):
            raise ValueError("invalid health arguments")
        ok = healthy(sys.argv[1], maintenance=len(sys.argv) == 3)
    except Exception:
        ok = False
    sys.exit(0 if ok else 1)
