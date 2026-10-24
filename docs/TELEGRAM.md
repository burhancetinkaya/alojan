# Private post-call Telegram notifications

M5-01, US-07/08, requirements §9.4/11/12. The owner requested this channel on
2026-10-24, superseding the earlier notification deferral and generic-webhook
selection. Telegram was already an allowed baseline option; DEC-01–15 are unchanged.
The authorization covers the owner's paired private chat only. This is outbound
notification delivery, not a Telegram conversation agent or an externally exposed API.

## Behavior and boundaries

Telegram notifications use the product name **Alojan**, including the call title
and setup test message (owner preference, 2026-10-24).

A separate process polls ended calls every two seconds. It uses the existing
finalized, schema-validated summary without another LLM request. The notification
contains the available caller name, carrier-supplied number (a hint, not verified
identity), stored start/end times in Europe/Istanbul, subject, summary, requested
callback/action and unresolved questions. The owner additionally requested the
complete available final dialogue ([ADR 0010](ADR/0010-telegram-dialogue.md)),
labeled Arayan/Alojan and ordered by persisted timestamp and row ID. Assistant
text requires positive sent-audio accounting; interrupted records without complete
text are marked explicitly. Unpersisted speech is never reconstructed.
A separately supplied contact number is labeled as the caller's declaration.
Plain text and disabled link previews prevent caller text becoming HTML or fetching
caller-provided links. Long dialogue is preserved in numbered messages below the
Telegram limit, each correlated with the call UUID. Final ASR may contain recognition
errors; recorded call times reflect the stored agent lifecycle, not independently
measured carrier ringing timestamps.

Summary failure, invalid stored summary, or two minutes without a final summary
labels the summary as unavailable and still includes available dialogue. No text
is invented. There is one logical notification per call, possibly comprising
several numbered messages, and no later second summary update.
Calls without a persisted end event cannot yet be detected as completed here.
Summary quality and durable end-event reconciliation remain separate agent work.

The PostgreSQL outbox stores the frozen payload and provider receipts. Version 2
contains numbered messages, the next part and completed message IDs. Each part is
committed independently, with at least two seconds before the next attempt; restart
resumes at the first uncommitted part. The notification is marked delivered only
when every part has a receipt. Legacy version 1 messages remain readable. Activation
persists a cutoff; calls ending before it are not backfilled. Restart preserves
the cutoff and queued deliveries. Atomic enqueue and a unique call/target index
prevent duplicate queue rows. Row locks with `SKIP LOCKED` prevent concurrent workers
sending the same part; only outbox rows are locked during network IO. There is no
work on the media callbacks and no voice-service restart is required.

Transport errors, server errors and rate limiting retry with exponential delay,
respecting Telegram's `retry_after`. After 12 failed attempts the row is retained
with `failed_at`; 400/401/403/404 are terminal immediately. Operators repair the
configuration before deliberately resetting a specific failed row. The deferred
owner retry API is not implemented by this task. A network/DB failure after
Telegram accepts a message can cause a duplicate on retry: `sendMessage` provides
no idempotency key. Exactly-once external delivery is not claimed.

## Owner bot setup

1. In Telegram, open the official [BotFather](https://t.me/BotFather), use `/newbot`,
   choose a display name and an available username ending in `bot`.
2. Put `TELEGRAM_BOT_TOKEN=...` in the server's ignored `.local/telegram.env`, mode
   `0600`. Do not paste it into chat, tracked files, shell arguments or logs.
3. Open your new bot and press Start. Pair it using a fresh random challenge:
   generate `secrets.token_urlsafe(24)` locally, put it in the process environment
   as `TELEGRAM_PAIR_CODE`, and send `/start <challenge>` to the bot yourself.
   The challenge must be less than 15 minutes old when pairing is checked.
4. Run the pairing command below. It accepts only the matching message from a
   non-bot user in a private chat whose sender ID matches the chat ID. It never
   chooses an arbitrary first update, group or forwarded message. The output env
   file is created with `0600`, exclusively; existing recipient files are not replaced.

Use a dedicated bot with no existing webhook. Pairing reads up to the first 100
pending message updates; if the matching challenge is absent, pairing fails closed.
An operator can inspect/advance the update offset privately for a reused busy bot;
this feature does not silently delete a bot's webhook or unrelated updates.

## Linux installation and operation

Prepare an isolated source release under `~/ai/alojan/.local/telegram-<revision>`
and run `uv sync --frozen` there. Include the root lockfile, `services/agent`,
`services/app-api`, and `infra/migrations`. Do not copy credentials into the release.
Keep the live voice service source intact. From the release directory:

```sh
PYTHONPATH=services/app-api uv run --frozen \
  --env-file "$HOME/ai/alojan/.local/dev.env" python -m alojan.migrate
```

The migration is additive and checksum checked. Run pairing without a DB connection:

```sh
PYTHONPATH=services/agent uv run --frozen \
  --env-file "$HOME/ai/alojan/.local/telegram.env" \
  python -m alojan_agent.notifications --pair "$HOME/ai/alojan/.local/telegram-owner.env"
```

`TELEGRAM_PAIR_CODE` must already be present in that command's environment. Then run
the following separately with `--test-message` and `--activate` as the final argument:

```sh
PYTHONPATH=services/agent uv run --frozen \
  --env-file "$HOME/ai/alojan/.local/dev.env" \
  --env-file "$HOME/ai/alojan/.local/telegram.env" \
  --env-file "$HOME/ai/alojan/.local/telegram-owner.env" \
  python -m alojan_agent.notifications --test-message
```

The test sends a clearly labeled synthetic message only to the paired chat.
Activation verifies that chat is private and stores the initial cutoff; repeated
activation does not reset it. All subsequent calls ending after activation are
eligible, including calls ending while the worker is stopped.

Point `.local/telegram-current` at the tested release, copy
`infra/systemd/alojan-telegram.service` to `~/.config/systemd/user/`, then use
`systemctl --user daemon-reload` and `systemctl --user enable --now alojan-telegram`.
The service uses the release's frozen environment with no dependency synchronization
at startup. Verify the user manager survives logout (`loginctl show-user "$USER"
-p Linger`); enabling linger is needed if it does not. Stop with
`systemctl --user stop alojan-telegram`; queued rows remain durable. Revert the
release symlink and restart this unit to roll back code without restarting voice.
After version 2 payloads exist, only roll back to another version-2-capable release.
For an older release, stop the notification worker and preserve the queue instead
of letting the version-1-only worker reject the new payloads.

Inspect `journalctl --user -u alojan-telegram` for fixed event names only.
Do not add HTTP debug logging: Telegram authenticates via a token in the URL.
Outbox payloads and recipient IDs are private DB data, never diagnostic fixtures.
Retry exhausted rows require explicit operator review; do not bulk reset delivered rows.

## Acceptance

Run `tests/test_notifications.py`, `tests/test_database.py` and
`tests/test_agent_database.py` on Linux with `ALOJAN_DATABASE_URL`; fixtures create
disposable schemas and never truncate live tables. Mock HTTP tests are not proof
of Telegram delivery. Real acceptance needs the owner's paired bot, successful
synthetic delivery, then a completed phone call with matching outbox receipt and
owner confirmation. Verify one logical notification, all numbered parts with complete dialogue, and no
notification before hangup.

Official references: [bot creation](https://core.telegram.org/bots/tutorial),
[Bot API](https://core.telegram.org/bots/api) (`getUpdates`, `getChat`, `sendMessage`,
`ResponseParameters.retry_after`) and [per-chat pacing](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this). Accessed 2026-10-24. No new SDK/dependency added.
