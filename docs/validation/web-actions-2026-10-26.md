# Prepared voice playback and Telegram builder — 2026-10-26

AGP-05/06, M2/M5, ADR 0011, requirements §1/12/14–16. Continues the approved
flat Next.js/shadcn UI. Ponytail full; no new dependency, database migration,
GPU process, media callback or live-turn lookup.

## Behavior and boundaries

Authenticated members can play the current draft's already prepared greeting or
unavailable-message WAV. The new GET route requires an exact draft-version
precondition, checks workspace/profile membership and qualified model/manifest,
then releases its DB transaction before bounded file validation. UUID/digest-derived
paths, rejected symlink directories/files, a 500,000-byte limit, exact hashes and
PCM structure prevent arbitrary file serving. No recording/transcript is exposed.
Missing, changed, corrupt or unavailable audio fails closed. The management
container mounts the same trusted asset store read-only; it cannot generate/import
assets or invoke EMA through this endpoint.

The browser loads a private blob on explicit request, provides native audio controls,
and aborts/releases playback when the draft changes or the component unmounts.
No signed URL, token query parameter or persistent browser cache is added.

The Telegram panel supports zero to four actions and derives allowed output paths
from the existing agent schema. Summary status and number provenance are included
with dependent fields. Adding/removing/editing an action is a draft change only.
The owner explicitly opens a server-generated review showing the exact destination,
operation and selected fields before granting consent. Saving/opening the review
does not authorize delivery. Publication and number binding remain separate.
Existing matching grants can be explicitly revoked after a second consequence
review; original server authority, version/digest and dispatch checks are unchanged.
Revocation can affect serving releases and cannot retract an already-started send.

## Verification

- Linux Ruff format/check and TypeScript/production build passed.
- **30 Python tests passed in 16.83s**: prepared preview access, integrity, stale
  versions, missing audio, plus release and action-grant regressions.
- **9 real HTTPS browser scenarios passed in 12.3s**, no retries/skips. Added playable
  synthetic WAV/dirty-draft invalidation and Telegram create/select/review/authorize/
  publish/revoke. The isolated restricted-role schema ended with one test publication,
  no number bindings and no action jobs. It was then dropped. No external sends.
- Visual review of the Telegram destination/field consent dialog completed.
- Deployed read-only owner browser smoke passed: existing Kübra EMA audio loaded and
  decoded with positive duration, all navigation remained usable, no browser errors,
  no agent/release/binding/grant mutation and logout completed. This is browser decode
  of previously accepted speech, not a fresh human listening or synthesis test.
- Web and management alone were recreated. **Eight peer container IDs and health
  stayed unchanged**; web, TLS and management are healthy and the private URL returns 200.

The first Python invocation stopped at lint/import setup: corrected fixture import
placement and included the management project's already-pinned `httpx==0.28.1` in
the root test invocation (`uv run --frozen --with httpx==0.28.1 --env-file
.local/dev.env pytest ...`). These were not test passes. Browser fixtures contain
synthetic tones and unused credentials, not evidence of new-model readiness.

Images:

- Management `sha256:0fdc0898392d6499e1409d2ea53cf327c28e394cc43d35d71e583b0e2b5208d1`.
- Web `sha256:f59cd506e0e44867ad4635cbc4cf48d58683a0a7ea7da78bd2f8df51e5bf3359`.

Private rollback configuration and sanitized rollout receipt:
`.local/web-actions-20261026`. Synthetic browser evidence:
`.local/web-validation-8c39c8f0d8ab46c989c6536f9193bc0f`. Credentials, full phone
numbers and personal transcripts are excluded from maintained evidence.

## Next acceptance

Automatic generation of new speech remains open: changed names/text cannot become
ready merely by pressing Preview or Publish. Complete the existing planned durable
preparation queue and acknowledged drained GPU window, using resident EMA and the
trusted atomic asset importer. A pending preparation must be honest in the UI;
never bypass missing-asset checks or infer GPU availability from an idle snapshot.

Full call-detail UI, general HTTP/MCP builders and public account recovery also remain
open. No handset call, external Telegram message, GPU benchmark, concurrent-call test
or matched latency/load acceptance was run in this HTTP-only step.
