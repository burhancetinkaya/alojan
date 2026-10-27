# ADR 0010: Include recorded dialogue in owner Telegram notifications

Date: 2026-10-24, Europe/Istanbul.
Status: Accepted by the owner's explicit request that Telegram include the calling
number, call time, summary and conversation dialogue. Refines M5-01 / US-07 content;
DEC-01–15 and the approved private recipient remain unchanged.

## Decision

Send the persisted calling number, stored start/end timestamps in Europe/Istanbul,
validated summary and the complete available final dialogue to the paired owner.
Use Arayan and Alojan as speaker labels. Caller text comes from final ASR records.
Assistant text is included only with positive sent-audio accounting. An interrupted
assistant record with sent audio but no aligned text receives an explicit missing
text marker; never reconstruct unheard output or invent absent greeting text.
These records do not prove the caller heard every sent audio packet.

Render existing records without an extra LLM request or changes to the live voice
prompt. Missing/failed summaries do not suppress available dialogue. Missing numbers
or dialogue are labeled as unavailable. This extends owner-authorized data sharing
to private transcripts; it does not authorize public/group delivery, raw recordings,
historical backfill or storing private examples in Git.

Telegram sendMessage limits require long dialogue to be split into numbered parts.
Use conservative UTF-16 lengths, preserve every recorded character and correlate
parts by call UUID. Outbox payload version 2 freezes the parts and records each
successful receipt plus the next part to send. Commit each part independently,
pace successive sends, and mark the call notification delivered only after all parts.
Version 1 payloads remain readable. A failure after Telegram accepts a part but
before the database commit can still duplicate that part; exactly-once is not claimed.

## Alternatives and consequences

Summary-only messages do not meet the owner's new request. Truncating the dialogue
silently loses content. Attachments need an additional API upload path and hide the
conversation behind a file; numbered text messages reuse the tested transport.

Previously delivered messages are not resent. Undelivered legacy notifications may
be upgraded during the controlled release switch. No SQL schema change is needed.
Once version 2 rows exist, rollback requires a version-2-capable worker; otherwise
stop notifications and preserve the queue until repaired. Do not start the older
version-1-only worker on new payloads. Transcript accuracy and late/missing persisted
call events remain separate limitations of the voice recording pipeline.
