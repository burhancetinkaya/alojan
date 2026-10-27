# Call transcript and delivery retry UI — 2026-10-26

AGP-06 / M2,M5, P1 dashboard, US-05/07, requirements §2/7.3/11.2/12/14–16,
ADR 0011. Ponytail full; extends the approved flat Next.js/shadcn design using
existing call storage and owner-reviewed retry APIs. No new runtime dependency,
worker, voice setting, transcript backfill, external message or recording.

## Implemented behavior

`GET /v1/workspaces/{scope}/calls/{call}/transcript` authorizes workspace membership
and immutable call ownership before reading. It returns up to 50 finalized rows,
ordered by `(created_at,id)` ascending, with an exclusive UUID `after` cursor.
Cursors are restricted to visible rows in the same call. Unsent assistant output
and partial ASR are excluded. A positive sent-audio interval with no aligned text
is represented honestly as an unavailable-text segment, not reconstructed speech.
Caller ASR and aligned agent text remain estimates, not proof of what was heard.

Migration 0018 adds a matching partial index. Management receives only the required
utterance SELECT columns; source generation IDs and all transcript mutation remain
denied. RLS excludes other workspaces and unscoped legacy records. Existing request
limits, three-second query timeout and no-store headers apply. No row locks,
media callbacks, per-turn lookups or raw audio are introduced. Pages load on demand
and replace one another, so browser memory stays bounded. Refresh returns to the
first page; active-call pagination is not a frozen whole-conversation snapshot.

Call detail now offers owner-only retry review for failed/paused/uncertain jobs.
The existing server review supplies the exact original message, connection and
chat target, duplicate-delivery warning, digest and current eligibility. Consent
starts unchecked. Cancel/review does not enqueue anything; explicit acceptance
uses the existing audited/idempotent POST. Uncertain HTTP responses retain the same
request UUID, while stale reviews require refreshed information and renewed consent.
Success says queued, never sent. The background worker retains authority/revocation,
retry-generation and delivery-state enforcement; no backend retry policy changed.

## Verification

- **48 Linux tests passed in 49.93s**, no skips: scoped call/transcript API, same-call
  cursor validation, stable equal-timestamp ordering, partial/unsent filtering,
  honest empty segments, HTML-as-data, empty history, authentication/RLS/read-only
  grants plus existing record and delivery retry/consent/fencing regressions.
- TypeScript and production builds passed. Ruff check/format passed.
- **11 HTTPS browser scenarios passed in 20.0s**, no retries/skips. Actual restricted
  API covers 52 transcript entries across 50/2 pages, return-to-start, plain-text
  injection handling, canceled/unchecked retry review, renewed consent after a
  simulated stale response, and a real accepted retry whose HTTP response is
  deliberately dropped. The subsequent click reuses identical request bytes.
  Exactly one durable retry exists; the synthetic delivery remains uncertain with
  one fake transport attempt. No worker consumes that retry and no network send
  occurs. The isolated schema/role/containers are dropped afterward.
- Desktop/mobile review completed; retry dialog fits the 390px viewport with 16px
  margins and scrolling. Final browser evidence:
  `.local/web-validation-44bedb227de649c49c72c7024003a03a`.
- The deployed owner browser check reads existing configuration/audio, call detail,
  transcript and already-sent status, then logs out. All non-read requests except
  login/logout are blocked by the harness; no retry is submitted on the real account.

Earlier attempts are not passes: the expanded fixture initially lacked the generated
protobuf import path; adding it resolved startup. One browser assertion matched both
loading and success status elements (10 passed/1 failed); it now selects the success
notice specifically. An intermediate 11/18.2s run preceded mobile margin refinement;
11/18.9s preceded explicit settled-position checks. Visual capture now waits for
responsive layout rather than photographing a transition.

The first owner smoke incorrectly assumed the newest call had utterances and failed
that assertion. Both the API and a content-free DB check confirmed that record had
none. The UI correctly showed its empty state. The final smoke selects an existing
record with a transcript and sent delivery. No historical text was manufactured,
reassigned, logged or copied to evidence.

## Deployment and limits

Private DB backup preceded additive migration 0018: **0.021s**, 19 applied
migrations, existing utterances preserved. Preflight required no active calls and
an utterance table below 1 MiB; lock/statement timeouts are 200ms/3s. Larger histories
require an online index rollout. Re-applied narrow management grants. Old images
remain compatible with the added index/privileges for application rollback.

Only management and web were recreated; **eight peer container IDs and health
were preserved**. No gateway/agent/ASR/TTS restart, inference or admission setting
change. Private rollback files, backup and receipts:
`.local/transcript-retry-20261026`.

- Management: `sha256:67ff3c43c3e110d8c00cab773e1dbfb606a11026efda27adb0959b7716607413`.
- Web: `sha256:716a805515187a24973ed6e32154cd933a19edbfa96cccd4c04a5ecada272e1e`.

Real Telegram retry delivery, new handset calls, concurrent capacity and matched
latency/load acceptance were not exercised. Retry delivery remains explicitly
at-least-once/uncertain across provider boundaries, not exactly-once. Rollback UI,
latency views, complete AGP-06 workflow acceptance, MCP/HTTP builders and public
recovery/launch remain subsequent steps.
