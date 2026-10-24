"""M5-01: standalone durable post-call notifications, outside the voice process."""

import argparse
import os
import signal
import threading
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Summary
from .store import Store
from .telegram import DeliveryError, Telegram, paired_chat


def clipped(value, limit):
    text = " ".join(str(value or "Belirtilmedi").split())
    if len(text.encode("utf-16-le")) // 2 <= limit:
        return text
    return text.encode("utf-16-le")[: (limit - 1) * 2].decode("utf-16-le", errors="ignore") + "…"


def notification_text(call):
    """No new model request; use the validated finalized summary, never raw dialogue."""
    summary = None
    if call["job_status"] == "done" and call["json_schema_version"] == 1:
        try:
            summary = Summary.model_validate(call["detail_jsonb"])
        except ValueError:
            pass
    ended = call["ended_at"].astimezone(ZoneInfo("Europe/Istanbul"))
    lines = [
        "Alojan · Arama tamamlandı",
        ended.strftime("%d.%m.%Y %H:%M (Türkiye)"),
        "Arayan numara: " + clipped(call["from_number_e164"], 40),
    ]
    if summary:
        lines += [
            "İsim: " + clipped(summary.caller_name, 100),
            "Konu: " + clipped(summary.subject, 180),
            "Özet: " + clipped(summary.summary, 2100),
            "Talep / geri dönüş: " + clipped(summary.requested_action, 600),
            "Öncelik: " + {"low": "Normal", "medium": "Orta", "high": "Yüksek"}[summary.urgency],
        ]
        if summary.caller_number and summary.caller_number != call["from_number_e164"]:
            lines += ["İletişim numarası (beyan): " + clipped(summary.caller_number, 40)]
        if summary.unresolved_questions:
            lines += ["Açık kalan: " + clipped("; ".join(summary.unresolved_questions), 250)]
        lines += ["Otomatik özet; arayanın beyanıdır."]
    else:
        lines += ["Görüşme özeti hazırlanamadı. Varsa konuşma kayıtları veritabanında korunuyor."]
    lines += ["Arama kimliği: " + str(call["id"])]
    return "\n".join(lines)


class Notifications:
    def __init__(self, dsn, telegram, chat_id):
        if type(chat_id) is not int or chat_id <= 0:
            raise ValueError("invalid owner private chat")
        self.store = Store(dsn)
        self.telegram = telegram
        self.chat_id = chat_id
        self.target = f"telegram:{chat_id}"

    def activate(self):
        self.telegram.private_chat(self.chat_id)
        self.store.transaction(
            lambda c: c.execute(
                "INSERT INTO notification_channels(target) VALUES(%s) ON CONFLICT DO NOTHING",
                (self.target,),
            )
        )

    def enqueue(self):
        def save(conn):
            channel = conn.execute(
                "SELECT enabled_at FROM notification_channels WHERE target=%s", (self.target,)
            ).fetchone()
            if not channel:
                raise ValueError("activate the owner notification channel first")
            with conn.cursor(row_factory=dict_row) as cursor:
                calls = cursor.execute(
                    "SELECT c.id,c.ended_at,c.from_number_e164,j.status AS job_status,"
                    "s.detail_jsonb,s.json_schema_version FROM calls c "
                    "LEFT JOIN summary_jobs j ON j.call_id=c.id "
                    "LEFT JOIN call_summaries s ON s.call_id=c.id "
                    "WHERE c.ended_at >= %s AND c.status='ended' "
                    "AND (j.status IN ('done','failed') OR c.ended_at < now()-interval '2 minutes') "
                    "AND NOT EXISTS (SELECT 1 FROM notification_outbox o "
                    "WHERE o.call_id=c.id AND o.target=%s) ORDER BY c.ended_at,c.id LIMIT 100",
                    (channel[0], self.target),
                ).fetchall()
            for call in calls:
                conn.execute(
                    "INSERT INTO notification_outbox(id,call_id,target,payload_jsonb) "
                    "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        uuid.uuid5(call["id"], self.target),
                        call["id"],
                        self.target,
                        Jsonb({"version": 1, "text": notification_text(call)}),
                    ),
                )
            return len(calls)

        return self.store.transaction(save)

    def deliver_one(self):
        def send(conn):
            row = conn.execute(
                "SELECT id,payload_jsonb,retry_count FROM notification_outbox "
                "WHERE target=%s AND delivered_at IS NULL AND failed_at IS NULL "
                "AND next_attempt_at<=now() ORDER BY next_attempt_at,id "
                "LIMIT 1 FOR UPDATE SKIP LOCKED",
                (self.target,),
            ).fetchone()
            if row is None:
                return "idle"
            identity, payload, retries = row
            try:
                if (
                    not isinstance(payload, dict)
                    or payload.get("version") != 1
                    or not isinstance(payload.get("text"), str)
                    or not payload["text"]
                    or len(payload["text"].encode("utf-16-le")) // 2 > 4096
                ):
                    raise DeliveryError("notification_invalid_payload", permanent=True)
                message_id = self.telegram.send(self.chat_id, payload["text"])
            except DeliveryError as error:
                failed = error.permanent or retries + 1 >= 12
                delay = max(error.retry_after, min(3600, 5 * 2 ** min(retries, 10)))
                conn.execute(
                    "UPDATE notification_outbox SET retry_count=retry_count+1,last_error=%s,"
                    "next_attempt_at=now()+make_interval(secs=>%s),"
                    "failed_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
                    (error.code, delay, failed, identity),
                )
                return "failed" if failed else "retry"
            conn.execute(
                "UPDATE notification_outbox SET delivered_at=now(),provider_message_id=%s,"
                "last_error=NULL WHERE id=%s",
                (message_id, identity),
            )
            return "delivered"

        # Lock only the outbox row. A crash after Telegram accepts but before commit
        # may duplicate delivery: Telegram sendMessage has no idempotency key.
        return self.store.transaction(send)


def pair(telegram, code, destination):
    updates = telegram.request("getUpdates", {"limit": 100, "allowed_updates": ["message"]})
    chat_id = paired_chat(updates, code)
    telegram.private_chat(chat_id)
    # Exclusive creation prevents silently replacing an already paired recipient.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(f"TELEGRAM_CHAT_ID={chat_id}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--activate", action="store_true")
    actions.add_argument("--test-message", action="store_true")
    actions.add_argument("--pair", type=Path, metavar="PRIVATE_OWNER_ENV")
    args = parser.parse_args()
    try:
        telegram = Telegram(os.environ["TELEGRAM_BOT_TOKEN"])
        if args.pair:
            pair(telegram, os.environ["TELEGRAM_PAIR_CODE"], args.pair)
            print("event=telegram_paired", flush=True)
            return
        chat_id = int(os.environ["TELEGRAM_CHAT_ID"])
        telegram.private_chat(chat_id)
        if args.test_message:
            telegram.send(chat_id, "Alojan bildirim testi: Telegram bağlantınız hazır.")
            print("event=telegram_test_delivered", flush=True)
            return
        worker = Notifications(os.environ["ALOJAN_DATABASE_URL"], telegram, chat_id)
        if args.activate:
            worker.activate()
            print("event=telegram_activated historical_calls=excluded", flush=True)
            return
        stopping = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stopping.set())
        worker.enqueue()
        print("event=notification_worker_ready", flush=True)
        while not stopping.is_set():
            try:
                worker.enqueue()
                result = worker.deliver_one()
                if result != "idle":
                    print(f"event=notification_{result}", flush=True)
            except Exception:
                print("event=notification_worker_unavailable", flush=True)
            stopping.wait(2)
    except Exception:
        # Exception strings/tracebacks can contain the bot URL, DSN or caller text.
        print("event=notification_startup_failed", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
