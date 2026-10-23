# Quiet waiting music

Date: 2026-10-23. Branch: `codex/waiting-music`.
Tasks: M4-01 waiting feedback / M5-03 performance follow-up.
Acceptance: US-02/05/06; requirements §7.3–4 and §9.2.
Authorization: owner explicitly requested unobtrusive music instead of the spoken
waiting sentence. No fixed architecture/model decision changed.

## Behavior and provenance

The agent no longer generates `Söylediklerinizi kontrol ediyorum.`. The native
renderer starts a quiet original six-second instrumental loop after 800 ms
waiting for the first response PCM. Prepared PCM uses no model, external service,
file I/O, allocation or locks in the callback. [Score and levels](../../assets/waiting/README.md)
are reproducible from the native source; no third-party recording was introduced.

Response PCM has priority over music on the next 20 ms render callback. Music does
not occupy the speech queue, require an EMA request or return between phrases.
Existing call-state and generation guards stop it on interruption, failure or
hangup. Echo reference includes the actual music output. Speech counters, playback
receipts, transcripts, confirmation and substantive latency exclude music; separate
`waiting_music_ms` accounts for the output. The cursor advances only on rendered
frames, avoiding clock jitter causing repeated/skipped music frames.

## Checks

- Linux native build passed; 9 CTests passed in 2.33 seconds. New music test checks
  bounded level, non-silence, identical looping and the quiet loop seam. Observed
  PCM peak 1156; RMS 419.755, approximately -29/-38 dBFS respectively.
- Linux focused pytest: 44 passed in 119.04 seconds, no skips, one known `audioop`
  deprecation warning. Covers agent/phrase/PostgreSQL and native SIP/RTP dialogue.
  Both G.711 codecs receive quiet non-silent music, keep music out of speech
  history, and start real speech within 500 ms of text arrival under scripted
  inference. Fast scripted responses produce zero music frames.
- Native barge-in test waits until music is playing, injects synthetic caller
  speech, observes generation cancellation and the next recognition/response,
  and verifies at least ten silent RTP frames 100–500 ms after interruption.
  This is cancellation evidence, not a new onset-to-stop target claim.
- Mac unit checks: 34 passed in 4.46 seconds. Ruff check/format, affected C++
  clang-format and `git diff --check` passed separately. Graph refreshed without
  a shared cache artifact.
- Real adaptive PCMA loopback used resident CUDA ASR/EMA, actual OpenRouter Pro
  and isolated PostgreSQL. Two-turn confirmation and post-call summary passed.
  Music played for 3280 ms; all four speech receipts were substantive responses.
  First response PCM reached the output port 15 ms after phrase arrival, with
  no wait for a music loop to finish. Confirmation closing began at 138 ms after
  ASR half-close and did not need music. Initial substantive response still took
  4238 ms after half-close (agent text 4076 ms); music does not accelerate inference.

No real carrier call was made for this change. Human preference, handset loudness
and acoustic echo remain listening/calibration work. The music is deliberately
quiet; the preview is native 8 kHz PCM and does not emulate carrier compression.
Existing broader M3/M5 quality, lifetime/retention and latency gates remain open.

## Development activation

The idle development gateway and agent were restarted after a private rollback
snapshot (`.local/carrier-before-waiting-music`). All three worker health checks
and gateway readiness passed; active profile reports `waiting_music=v1` and
`waiting_phrase=false`. Binary SHA-256:
`331d82d7276aaeb7ae6520ec1cdbe47d968bb2e40afae583a657198b2cfdb8b1`.
Source checksum comparison between Mac and Linux was clean. No secret, private
recording, model cache or environment was synchronized. No commit/push/PR was made.
