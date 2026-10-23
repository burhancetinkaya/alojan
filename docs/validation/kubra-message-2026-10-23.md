# Kübra greeting and message closing

Date: 2026-10-23. Tasks M1-03, M4-01/02/03; US-01/02/05/07.
Authorization and scope changes: ADR 0006. Opening text approved before synthesis,
with an explicit subsequent correction to Burhan Bey. Notification remains deferred.

## Changes

Resident EMA generated the approved v5 greeting: 5360 ms including the preserved
400 ms silent lead-in. Real CUDA ASR recognized the full approved sentence,
including Kübra and Burhan Bey. This is synthetic recognition evidence, not
human listening acceptance. The fallback WAV remains byte-identical to v3.

A successful take_note saves confirmed=false and emits exactly the requested
closing, without readback. Attempts to set confirmed=true are refused. Durable
save failure restores in-memory note state and cannot emit the success closing.
Native closure waits three seconds after audio completion plus 150 ms for queued
media. Initial three-second ringing, speech interruption and waiting music remain.

Availability is owner-configured: unavailable, possibly in a meeting. Do not
claim calendar knowledge or a return time. Actual messages/callback requests
have priority over offering to take a message.

## Evidence

- Initial Mac and Linux focused runs exposed a fixture expectation mismatch:
  Agents SDK wraps the synthetic database exception as UserError. The assertion
  was corrected without changing failure behavior. Final results pending below.
- First real API probe correctly answered availability but incorrectly offered
  message collection when a callback message was already present. Prompt scope
  was narrowed and message priority made explicit; the repeated probe passed
  both availability and exact no-confirmation closing with a saved note.
- Linux build and nine CTests passed (2.33 s).
- Focused Linux suite: 78 passed, one fixture failure above, 159.56 s, no skips,
  one known audioop deprecation warning. The final agent/phrase rerun passed all
  40 cases (4.51 s), including the corrected failure case. Unchanged SIP, asset
  and DB cases from the larger run were not needlessly repeated.
- Both PCMA and PCMU measured 3.0–3.7 seconds from last non-silent closing RTP
  to BYE in the local scripted integration assertions. The v5 greeting retained
  opening audio under simulated first-300-ms loss and both ring-delay profiles.
- Real synthetic adaptive CUDA ASR/EMA + OpenRouter + isolated DB call passed
  in one turn: unconfirmed saved note, exact closing and completed post-call
  summary. First response output 3580 ms after ASR half-close, waiting music
  2620 ms. These are not handset timings or latency percentiles.
- Ruff, clang-format, shell syntax and diff whitespace checks passed.
- Idle-line activation completed; gateway PID 1966506, agent launcher 1966398.
  Active v5 prompt path and 3000 ms ring delay verified; all three workers healthy.
  Previous binary, arguments, backend and logs retained in a private rollback
  snapshot. Binary SHA256:
  `bb9d5823635885d38e7df3e96de6cfa0f8d1239278f321d3b6a74c969f7a433e`.

Carrier development profile is deployed; human handset acceptance is pending. Raw audio recording
remains off; all generated/testing speech is synthetic. No external notification
was sent, and stored notes are not mislabeled confirmed or delivered.
