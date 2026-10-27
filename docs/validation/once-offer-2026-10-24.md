# Once-per-call further-help invitation — 2026-10-24

Scope: M4-01 / M5-03, US-02, requirements §9.2, owner amendment to ADR 0007.

## Finding and behavior

The latest carrier review showed a correct social farewell and one stored note,
but an intermediate response repeated storage and dismissed the caller's request
for a further-help question. The owner now explicitly requires that question once.

The system prompt, tool descriptions and turn state now agree on one invitation
after handling the request and essential details. Known storage acknowledgements
without a question receive the invitation on the normal speech path. Completed
playback sets a call-scoped flag, independent of note versions; interrupted speech
does not consume it. A repeated invitation is rejected for model correction.
Bare thanks cannot skip an outstanding invitation; explicit exits still bypass it.
No model/provider change, new external write or added normal-path API roundtrip.

## Evidence

- Linux focused agent/phrases/database/model/timing/latency tests: **110 passed in
  8.05 seconds**. Includes interrupted invitation playback, thanks before/after an
  invitation, explicit exits, correction without a second invitation, speech bounds,
  tool validation, cancellation, persistence and acknowledgement versioning.
- Linux Ruff check passed; formatting applied; Git whitespace check passed.
- Real GPT-OSS 120B/Cerebras/medium replay through isolated loopback gRPC and an
  in-memory store: **19/19 note/completion state checks**, seven conversations,
  exactly one invitation per conversation. Extra requests and corrections did not
  repeat it. Mean first phrase **998 ms**, maximum **2442 ms**. Completed playback
  receipts were simulated; these are not handset or audio latency measurements.
- Quality limit: in the unknown-product case, the model offered further help before
  asking the product name. The later supplied name was saved. This pre-existing
  essential-detail elicitation gap remains open; state checks are not full quality
  acceptance. A repeat-request answer also restated the message; no universal
  no-readback guarantee is claimed.
- Development agent activated after idle-call checks; agent/ASR/TTS health checked.
  Gateway and resident speech services preserved. Previous agent sources/log kept
  privately under `.local/rollbacks/once-offer-20261024` for rollback.

No new GPU/native-media benchmark was run for this Python conversation change.
New carrier listening, full conversation quality, G3 and soak remain pending.
Private call records, API secrets and raw recordings are excluded from this report.
