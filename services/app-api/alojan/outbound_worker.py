"""Single-node worker for private announcement synthesis and gateway handoff."""

import fcntl
import os
import time
import wave
from pathlib import Path

import grpc
import psycopg
from psycopg.rows import dict_row
from voice.v1 import voice_pb2 as pb, voice_pb2_grpc as rpc

from alojan.voice_generation import render_segments
from alojan_contracts.configuration import AgentDraft
from alojan_contracts.synthesis import SynthesisProfile


ACTIVE = ("preparing", "dialing", "answered")
TERMINAL = ("completed", "busy", "rejected", "no_answer", "interrupted", "failed", "uncertain")


def synthesize(job, path, endpoint):
    manifest = job["manifest"]
    draft = AgentDraft.model_validate(manifest["content"])
    assets = manifest["voice_assets"]
    profile = SynthesisProfile(assets["model"], assets["model_revision"], draft.voice)
    call = "managed-outbound-" + job["id"].hex
    with grpc.insecure_channel(
        endpoint, options=[("grpc.max_receive_message_length", 65536)]
    ) as channel:
        control, synthesizer = rpc.GenerationControlStub(channel), rpc.SynthesisStub(channel)
        lease = control.OpenCall(pb.CallLeaseRequest(call_id=call), timeout=3).lease
        if not lease:
            raise ValueError("TTS lease unavailable")
        metadata = [("x-alojan-lease", lease)]
        try:
            configured = synthesizer.ConfigureCall(
                pb.SynthesisCallConfiguration(
                    call_id=call,
                    release_id=str(job["release_id"]),
                    manifest_digest=job["manifest_digest"],
                    configuration=profile.to_proto(),
                ),
                metadata=metadata,
                timeout=3,
            )
            if not configured.accepted:
                raise ValueError("TTS configuration rejected")
            audio = bytearray()
            render_segments(
                synthesizer,
                call,
                metadata,
                job["message"],
                audio,
                240 * 16000,
                lambda: None,
            )
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                wav.writeframes(audio)
        finally:
            if not control.ReleaseCall(
                pb.CallLeaseRequest(call_id=call, lease=lease), timeout=5
            ).accepted:
                raise ValueError("TTS cleanup unconfirmed")


class Worker:
    def __init__(self, conn, root, node, endpoint):
        self.conn, self.root, self.node, self.endpoint = conn, root, node, endpoint

    def scope(self, scope):
        self.conn.execute("SELECT set_config('alojan.scope_id',%s,true)", (str(scope),))

    def expire(self):
        with self.conn.transaction():
            for (scope,) in self.conn.execute("SELECT id FROM recipient_scopes"):
                self.scope(scope)
                self.conn.execute(
                    """UPDATE outbound_calls SET message=NULL WHERE scope_id=%s AND node_id=%s
                    AND message IS NOT NULL AND ended_at < now()-make_interval(days=>%s)""",
                    (scope, self.node, int(os.getenv("ALOJAN_OUTBOUND_TEXT_DAYS", "30"))),
                )
                self.conn.execute(
                    """WITH expired AS (
                        DELETE FROM outbound_calls WHERE scope_id=%s AND node_id=%s
                        AND ended_at < now()-make_interval(days=>%s)
                        RETURNING scope_id,operation_key,id,request_digest)
                    INSERT INTO outbound_receipts(scope_id,operation_key,id,request_digest)
                    SELECT scope_id,operation_key,id,request_digest FROM expired""",
                    (scope, self.node, int(os.getenv("ALOJAN_OUTBOUND_HISTORY_DAYS", "90"))),
                )

    def claim(self):
        # Each workspace is read under its normal RLS policy. A single node lock
        # serializes decisions across scopes without a BYPASSRLS account.
        with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
            candidates = []
            for (scope,) in self.conn.execute("SELECT id FROM recipient_scopes"):
                self.scope(scope)
                row = cur.execute(
                    """SELECT o.*,r.manifest,r.manifest_digest,n.enabled AND
                    n.status='verified' AND n.active_binding_id=o.binding_id AS line_valid
                    FROM outbound_calls o JOIN agent_releases r ON (r.scope_id,r.id)=(o.scope_id,o.release_id)
                    JOIN phone_numbers n ON (n.scope_id,n.id)=(o.scope_id,o.number_id)
                    WHERE o.scope_id=%s AND o.node_id=%s AND o.ended_at IS NULL
                    ORDER BY (o.status<>'queued') DESC,o.queued_at,o.id LIMIT 1""",
                    (scope, self.node),
                ).fetchone()
                if row:
                    candidates.append(row)
            if not candidates:
                return None
            job = min(
                candidates, key=lambda row: (row["status"] == "queued", row["queued_at"], row["id"])
            )
            self.scope(job["scope_id"])
            if job["status"] == "queued":
                cur.execute(
                    "UPDATE outbound_calls SET status='preparing' WHERE scope_id=%s AND id=%s",
                    (job["scope_id"], job["id"]),
                )
            return job

    def update(self, job, status, failure=None, answered=None):
        with self.conn.transaction():
            self.scope(job["scope_id"])
            self.conn.execute(
                """UPDATE outbound_calls SET status=%s,failure_code=%s,
                answered_at=COALESCE(answered_at,to_timestamp(%s)),
                ended_at=CASE WHEN %s THEN now() ELSE NULL END WHERE scope_id=%s AND id=%s""",
                (status, failure, answered, status in TERMINAL, job["scope_id"], job["id"]),
            )

    def step(self):
        job = self.claim()
        if not job:
            return False
        key = job["id"].hex
        wav = self.root / (key + ".wav")
        pending, running = self.root / "pending", self.root / "running"
        statusfile = self.root / (key + ".status")
        ack = self.root / (key + ".answered")
        if job["status"] == "queued":
            if not job["line_valid"]:
                self.update(job, "failed", "line_inactive")
                return True
            try:
                synthesize(job, wav, self.endpoint)
            except (ValueError, OSError, grpc.RpcError):
                wav.unlink(missing_ok=True)
                self.update(job, "failed", "synthesis_failed")
                return True
            temp = self.root / (key + ".request")
            temp.write_text(
                f"{key} {job['caller_e164']} {job['destination']} {job['ring_timeout_seconds']} {job['post_playback_seconds']}\n"
            )
            if pending.exists() or running.exists():
                raise RuntimeError("Outbound spool already occupied")
            temp.replace(pending)
            return True
        status = statusfile.read_text().strip() if statusfile.exists() else None
        if status is None and (pending.exists() or running.exists()):
            return False
        if status not in (*TERMINAL, "answered", "dialing"):
            status = "uncertain"
        if status in TERMINAL and running.exists():
            return False
        if status != job["status"]:
            answered = ack.stat().st_mtime if ack.exists() else None
            self.update(
                job, status, status if status in ("failed", "uncertain") else None, answered
            )
        if status in TERMINAL:
            for path in (statusfile, wav, ack, self.root / (key + ".request")):
                path.unlink(missing_ok=True)
        return False


def main():
    os.umask(0o077)
    root = Path(os.environ["ALOJAN_OUTBOUND_DIR"])
    node = os.environ["ALOJAN_VOICE_NODE_ID"]
    with (
        (root / "worker.lock").open("a") as lock,
        psycopg.connect(os.environ["ALOJAN_DATABASE_URL"], autocommit=True) as conn,
    ):
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,8417))", (node,)
        ).fetchone()[0]:
            raise SystemExit("Outbound node already owned")
        worker = Worker(conn, root, node, os.getenv("ALOJAN_TTS_ENDPOINT", "127.0.0.1:15072"))
        next_expiry = 0.0
        while True:
            if time.monotonic() >= next_expiry:
                worker.expire()
                next_expiry = time.monotonic() + 3600
            if not worker.step():
                time.sleep(0.5)


if __name__ == "__main__":
    main()
