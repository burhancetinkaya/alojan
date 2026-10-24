# Standard Whisper large-v3 activation — 2026-10-24

M2-01 / M5-03; requirements DEC-08, §8.1, US-02/04/06; ADR 0003 and the
owner-authorized activation amendment to ADR 0008.

## Change

The default model manifest now pins `Systran/faster-whisper-large-v3`, revision
`edaa852ec7e145841d8ffdb056a99866b5f0a478`, with SHA-256 checks for all five files.
The previously evaluated weights were verified and copied into the existing
Hugging Face snapshot cache. Runtime loading remained offline and repeated all
hash checks. No Python/C++ logic, dependencies, decoder settings, private spelling
aliases, LLM prompts or media controls changed. CUDA FP16, beam five, Turkish and
bounded cumulative transcription remain in place.

The preceding [quality comparison](whisper-large-v3-2026-10-24.md) measured better
pooled human PCMA and quiet-speech WER, with human PCMA whole-utterance P50 of
360 ms versus 142 ms for Turbo. This is a measured tradeoff on a small corpus,
not a promise of better recognition for every phone utterance.

## Linux and GPU checks

- Existing ASR regression suite: **45 passed in 3.11 seconds**, no skips/failures.
- Candidate at loopback port 15174: seven real-CUDA gRPC synthetic cases passed,
  including PCM16/float speech, digital silence, names, dates/times and numeric
  phone matching. Cancellation before start passed; active cancellation 0.55 ms,
  zero stale buffered events, admission recovered on the first attempt.
- After activation, the same seven cases passed on the carrier ASR port 15173.
  All entity checks passed. Active cancellation was 0.71 ms, no stale buffered
  events, and recovery succeeded on the first attempt. The test distinguishes
  RPC cancellation from native GPU-kernel completion.
- Post-switch sampled whole-device memory peaked at 8,386 MiB; final observation
  was 8,034 MiB of 16,376 MiB. The shared GPU includes other resident workers;
  these are not model-only memory or concurrency-capacity measurements.
- Recognition, Synthesis and Agent health all reported SERVING; the existing
  gateway remained running. The temporary candidate process exited.

Fixtures were delivered unpaced through gRPC; these checks establish contract
and curated entity behavior, not real phone latency or perfect literal transcripts.
Numeric formatting and word edits remain in private detailed evidence. No caller
recordings were used. No native build was needed for this manifest-only change.

## Activation and rollback

Verified zero active persisted calls before stopping the old port-15173 ASR worker.
Restarted only that worker with its previous arguments/environment and existing
private vocabulary. The new readiness log identifies the exact large-v3 revision.
The gateway, TTS and agent were not restarted. Independent older development ASR
processes were preserved; only the carrier worker was promoted.

The previous manifest is retained privately at
`.local/large-v3-eval/before-live-model.json`; the original Turbo cache is intact.
To roll back, wait for no active calls, restore that manifest and restart only the
carrier ASR worker on its existing port, then check readiness. New source checkouts
use the standard pinned-model preparation command from the ASR README.

Real handset accuracy, turn/response latency, noisy conversations, concurrency
and soak acceptance remain pending. No new model redistribution approval follows
from this activation.
