-- M5-01: additive, independent of the live agent and media processes.
CREATE TABLE notification_channels (
    target text PRIMARY KEY,
    enabled_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE notification_outbox ADD COLUMN failed_at timestamptz;
ALTER TABLE notification_outbox ADD COLUMN provider_message_id bigint;
CREATE UNIQUE INDEX telegram_call_target ON notification_outbox(call_id, target)
    WHERE target LIKE 'telegram:%';
