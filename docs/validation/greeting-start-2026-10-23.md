# Carrier greeting opening-word protection

Date: 2026-10-23. Branch: `codex/greeting-start`.
Tasks: M1-03 / M1-06 carrier follow-up. Acceptance: US-01, requirements §6, §8.2.
Owner report: the opening `Merhaba` was not audible on the phone.

The stored v3 greeting matches its manifest checksum. On the primary Linux host,
resident CUDA ASR decoded its first second as `Merhaba ben Burhan`; the full file
also begins with that greeting. First PCM amplitude above 500 occurs at 32 ms.
Thus the word exists in the recording. Startup clipping on the carrier/handset
path is plausible, but no new carrier recording proves the exact clipping point.

V4 prepends 400 ms of digital silence to the exact approved greeting. Paced RTP
begins after ACK as before, giving the receive path time to open before the word.
Netgsm's launcher selects v4; generic gateway fixtures remain v3. No word, voice,
model, waiting music or dialogue policy changed. The fallback is byte-identical.
See [asset provenance and reproduction](../../assets/prompts/tr-v4-ema/README.md).

Linux build completed with no native rebuild required. Final focused checks:
26 passed in 16.26 seconds, no skips, one known `audioop` deprecation warning.
Tests cover asset hashes/format, exact source sample preservation, startup safety,
carrier configuration and both G.711 codecs. Both-codec tests emulate discarding
300 ms of initial audio, then compare the first 800 ms of original speech with
less than 4% RMS error. First audible greeting remains below one second after
ACK, while SIP answer remains immediate.

The initial run had 25 passes and one test-alignment failure: `audioop.findfit`
considered zero-valued mu-law silence a perfect zero-gain match. The test now uses
onset-bounded, unscaled sample comparison; playback files did not change in that
repair. Ruff check/format, shell syntax and diff whitespace checks passed.

This is a bounded startup-padding mitigation. Device paths clipping longer than
the pad need additional calibration. Real phone listening acceptance is pending;
local waveform and RTP checks do not establish what this handset heard.

The idle development gateway was restarted with v4 and readiness verified. Resident
ASR, EMA and agent workers were health-checked and left running. Previous gateway,
arguments, profile and logs are preserved in `.local/carrier-before-greeting-pad`.
The actual running process selects `tr-v4-ema`; source synchronization excludes
secrets and private logs. No commit, push, PR or carrier call was made.
