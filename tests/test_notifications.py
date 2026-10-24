"""Synthetic Telegram boundaries and durable outbox tests; no external deliveries."""

import asyncio
import io
import json
import os
import threading
import time
import urllib.error
import uuid
from datetime import datetime, timezone

import psycopg
import pytest
from alojan.migrate import migrate
from alojan_agent.notifications import Notifications, notification_text, pair
from alojan_agent.models import Summary
from alojan_agent.store import Store, call_uuid
from alojan_agent.telegram import DeliveryError, Telegram, paired_chat
import test_database

database = test_database.database
TOKEN = "123456:" + "a" * 30  # Synthetic; never a usable bot credential.
CODE = "synthetic-pairing-challenge-123456"
SUMMARY = {
    "caller_name": "Deneme Kişi",
    "caller_number": None,
    "subject": "Sentetik ürün sorusu",
    "summary": "Ürün hakkında bilgi istedi.",
    "requested_action": "Yarın geri aranmak istiyor.",
    "urgency": "low",
    "promised_action": "none",
    "confirmation_status": "unconfirmed",
    "unresolved_questions": [],
    "confidence": 0.8,
    "privacy_flags": [],
}


class FakeTelegram:
    def __init__(self):
        self.sent = []
        self.failure = None

    def private_chat(self, chat_id):
        assert chat_id == 123

    def send(self, chat_id, text):
        if self.failure:
            raise self.failure
        self.sent.append((chat_id, text))
        return 456


def create_call(database, *, status="done", old=False, ended=True):
    identity = uuid.uuid4()
    with psycopg.connect(database) as conn:
        conn.execute(
            "INSERT INTO calls(id,sip_call_id,direction,status,ended_at) "
            "VALUES(%s,'synthetic','inbound',%s,"
            "CASE WHEN %s THEN now()-make_interval(secs=>%s) ELSE NULL END)",
            (identity, "ended" if ended else "active", ended, 3600 if old else 0),
        )
        if status:
            conn.execute(
                "INSERT INTO summary_jobs(call_id,status) VALUES(%s,%s)", (identity, status)
            )
        if status == "done":
            conn.execute(
                "INSERT INTO call_summaries(call_id,subject,summary,urgency,confirmation_status,"
                "json_schema_version,detail_jsonb) VALUES(%s,'synthetic','synthetic','low',"
                "'unconfirmed',1,%s)",
                (identity, psycopg.types.json.Jsonb(SUMMARY)),
            )
    return identity


def setup(database):
    migrate(database)
    telegram = FakeTelegram()
    worker = Notifications(database, telegram, 123)
    worker.activate()
    return worker, telegram


def due(database):
    with psycopg.connect(database) as conn:
        conn.execute("UPDATE notification_outbox SET next_attempt_at=now()")


def test_outbox_restart_dedup_and_historical_call_exclusion(database):
    worker, telegram = setup(database)
    create_call(database, old=True)
    create_call(database, ended=False)
    create_call(database, status="pending")
    cid = create_call(database)
    assert worker.enqueue() == 1
    assert worker.enqueue() == 0
    # A restarted process finds durable pending work, not just new summary events.
    restarted = Notifications(database, telegram, 123)
    restarted.activate()
    assert restarted.deliver_one() == "delivered"
    assert worker.deliver_one() == "idle"
    assert worker.enqueue() == 0
    assert len(telegram.sent) == 1
    assert str(cid) in telegram.sent[0][1]
    assert "Yarın geri aranmak" in telegram.sent[0][1]
    with psycopg.connect(database) as conn:
        assert conn.execute(
            "SELECT provider_message_id,delivered_at IS NOT NULL FROM notification_outbox"
        ).fetchone() == (456, True)


def test_real_store_end_and_summary_lifecycle_drives_outbox(database):
    worker, telegram = setup(database)

    async def lifecycle():
        store = Store(database)
        await store.start("synthetic-lifecycle", None)
        assert worker.enqueue() == 0
        await store.end("synthetic-lifecycle", "caller_disconnected")
        assert worker.enqueue() == 0
        await store.summary_result(call_uuid("synthetic-lifecycle"), Summary(**SUMMARY))
        assert worker.enqueue() == 1
        await store.end("synthetic-lifecycle", "duplicate_end_event")
        assert worker.enqueue() == 0

    asyncio.run(lifecycle())
    assert worker.deliver_one() == "delivered"
    assert len(telegram.sent) == 1


def test_retries_rate_limit_permanent_failure_and_exhaustion(database):
    worker, telegram = setup(database)
    create_call(database)
    worker.enqueue()
    telegram.failure = DeliveryError("telegram_rate_limited", retry_after=90)
    assert worker.deliver_one() == "retry"
    assert worker.deliver_one() == "idle"
    with psycopg.connect(database) as conn:
        count, seconds = conn.execute(
            "SELECT retry_count,extract(epoch FROM next_attempt_at-now()) FROM notification_outbox"
        ).fetchone()
        assert count == 1 and seconds > 85
    due(database)
    telegram.failure = DeliveryError("telegram_rejected", permanent=True)
    assert worker.deliver_one() == "failed"
    due(database)
    assert worker.deliver_one() == "idle"
    with psycopg.connect(database) as conn:
        conn.execute("UPDATE notification_outbox SET failed_at=NULL,retry_count=11")
    telegram.failure = DeliveryError("telegram_transport_failed")
    assert worker.deliver_one() == "failed"
    assert not telegram.sent


def test_summary_failure_timeout_and_invalid_summary_are_honest(database):
    worker, telegram = setup(database)
    create_call(database, status="failed")
    pending = create_call(database, status=None)
    invalid = create_call(database)
    with psycopg.connect(database) as conn:
        conn.execute("UPDATE calls SET ended_at=now()-interval '3 minutes' WHERE id=%s", (pending,))
        conn.execute("UPDATE notification_channels SET enabled_at=now()-interval '4 minutes'")
        conn.execute("UPDATE call_summaries SET detail_jsonb='{}' WHERE call_id=%s", (invalid,))
    assert worker.enqueue() == 3
    for _ in range(3):
        assert worker.deliver_one() == "delivered"
    assert all("özet" in text and "hazırlanamadı" in text for _, text in telegram.sent)


def test_two_workers_cannot_send_same_row(database):
    worker, telegram = setup(database)
    create_call(database)
    worker.enqueue()
    entered, release = threading.Event(), threading.Event()
    send = telegram.send

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return send(*args)

    telegram.send = blocked
    outcomes = []
    first = threading.Thread(target=lambda: outcomes.append(worker.deliver_one()))
    first.start()
    try:
        assert entered.wait(3)
        assert Notifications(database, telegram, 123).deliver_one() == "idle"
    finally:
        release.set()
        first.join(5)
    assert outcomes == ["delivered"] and len(telegram.sent) == 1


def test_no_channel_and_other_recipient_cannot_send(database):
    migrate(database)
    telegram = FakeTelegram()
    worker = Notifications(database, telegram, 123)
    with pytest.raises(ValueError, match="activate"):
        worker.enqueue()
    worker.activate()
    create_call(database)
    worker.enqueue()
    assert Notifications(database, telegram, 999).deliver_one() == "idle"


def test_retry_survives_restart_and_invalid_payload_is_quarantined(database):
    worker, telegram = setup(database)
    create_call(database)
    worker.enqueue()
    telegram.failure = DeliveryError("telegram_transport_failed")
    assert worker.deliver_one() == "retry"
    telegram.failure = None
    due(database)
    assert Notifications(database, telegram, 123).deliver_one() == "delivered"
    assert len(telegram.sent) == 1
    create_call(database)
    worker.enqueue()
    with psycopg.connect(database) as conn:
        conn.execute("UPDATE notification_outbox SET payload_jsonb='[]' WHERE delivered_at IS NULL")
    assert worker.deliver_one() == "failed"
    assert len(telegram.sent) == 1


def test_concurrent_enqueue_creates_only_one_notification(database):
    worker, telegram = setup(database)
    create_call(database)
    errors = []

    def enqueue():
        try:
            worker.enqueue()
        except Exception as error:
            errors.append(type(error).__name__)

    workers = [threading.Thread(target=enqueue) for _ in range(3)]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join(5)
        assert not thread.is_alive()
    assert not errors
    assert worker.deliver_one() == "delivered"
    assert worker.deliver_one() == "idle"
    assert len(telegram.sent) == 1


def test_text_bounds_plain_text_and_no_fabricated_identity():
    summary = dict(SUMMARY, summary="😀" * 3000, requested_action="ş" * 1000)
    summary["caller_name"] = "<a href='https://example.test'>Test</a>"
    summary["unresolved_questions"] = ["😀" * 1000] * 10
    call = dict(
        id=uuid.uuid4(),
        ended_at=datetime.now(timezone.utc),
        from_number_e164=None,
        job_status="done",
        detail_jsonb=summary,
        json_schema_version=1,
    )
    text = notification_text(call)
    assert len(text.encode("utf-16-le")) // 2 <= 4096
    assert "Arayan numara: Belirtilmedi" in text
    assert "https://example.test" in text
    assert text.endswith(str(call["id"]))


def pairing_update(**changes):
    message = dict(
        text="/start " + CODE,
        date=int(time.time()),
        chat={"type": "private", "id": 123},
        **{"from": {"id": 123, "is_bot": False}},
    )
    message.update(changes)
    return {"message": message}


@pytest.mark.parametrize(
    "change",
    [
        {"text": "/start"},
        {"date": 0},
        {"chat": {"type": "group", "id": -123}},
        {"from": {"id": 999, "is_bot": False}},
        {"forward_origin": {"type": "user"}},
    ],
)
def test_pairing_rejects_unrelated_or_unsafe_updates(change):
    with pytest.raises(ValueError, match="fresh matching"):
        paired_chat([pairing_update(**change)], CODE)


def test_pairing_writes_private_file_and_never_replaces_recipient(tmp_path):
    telegram = FakeTelegram()
    telegram.request = lambda *_: [pairing_update()]
    target = tmp_path / "owner.env"
    pair(telegram, CODE, target)
    assert target.read_text() == "TELEGRAM_CHAT_ID=123\n"
    assert os.stat(target).st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        pair(telegram, CODE, target)


class Response(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(json.dumps(data).encode())
        self.code = status


def test_transport_never_sends_formatting_or_leaks_provider_error(monkeypatch):
    telegram = Telegram(TOKEN)
    captured = []

    def response(request, **kwargs):
        captured.append(json.loads(request.data))
        return Response({"ok": True, "result": {"message_id": 7, "chat": {"id": 123}}})

    monkeypatch.setattr(telegram._http, "open", response)
    assert telegram.send(123, "<b>caller text</b>") == 7
    assert "parse_mode" not in captured[0]
    assert captured[0]["link_preview_options"] == {"is_disabled": True}

    def rejected(*args, **kwargs):
        return Response({"ok": False, "error_code": 403, "description": TOKEN}, 403)

    monkeypatch.setattr(telegram._http, "open", rejected)
    with pytest.raises(DeliveryError) as error:
        telegram.send(123, "test")
    assert error.value.permanent and TOKEN not in str(error.value)


def test_transport_timeout_and_http_429(monkeypatch):
    telegram = Telegram(TOKEN)

    def timeout(*args, **kwargs):
        raise TimeoutError(TOKEN)

    monkeypatch.setattr(telegram._http, "open", timeout)
    with pytest.raises(DeliveryError, match="^telegram_transport_failed$"):
        telegram.send(123, "test")

    def limited(*args, **kwargs):
        body = Response({"ok": False, "error_code": 429, "parameters": {"retry_after": 34}})
        raise urllib.error.HTTPError("private-url", 429, "private", {}, body)

    monkeypatch.setattr(telegram._http, "open", limited)
    with pytest.raises(DeliveryError) as error:
        telegram.send(123, "test")
    assert error.value.retry_after == 34 and not error.value.permanent
