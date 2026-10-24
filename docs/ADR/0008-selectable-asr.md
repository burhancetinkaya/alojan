# ADR 0008: Evaluate and select Turkish ASR backends

Date: 2026-10-23 (Europe/Istanbul).
Status: Owner authorized evaluation and configuration-based support in the chat;
activation of Nemotron is conditional on better measured results.
Amends DEC-08 only; maps to M2-01 / M5-03, requirements §8.1 and US-02/04/06.

## Decision

Compare the pinned faster-whisper large-v3-turbo with NVIDIA
`nemotron-3.5-asr-streaming-0.6b` on identical Turkish audio. Separate public
human read speech from synthetic entity/short-answer fixtures. Measure clean,
telephone-band, noisy and quiet speech, word edits, entity preservation and
inference time. Vendor benchmarks do not establish quality for this application.

Keep Whisper as the default unless the local comparison and service validation
justify switching. Keep independent model environments and select one resident
backend through configuration; never load both just to route an individual turn.
Retain the existing gRPC contract, cancellation, generation isolation and bounded
admission. Do not replace the active carrier worker before the candidate passes
these checks; do not infer handset acceptance from an offline benchmark.

The existing service produces rolling partial hypotheses from cumulative audio.
A model's native streaming capability alone does not establish incremental caching
across these gRPC partials or lower end-to-end phone latency. Report these
measurement boundaries explicitly. Record source/runtime pins and license terms;
model redistribution approval is separate from this evaluation.

## Qwen3-ASR follow-up (2026-10-24)

The owner explicitly requested evaluation of `Qwen/Qwen3-ASR-1.7B` and a switch
only if it outperforms Whisper. This authorizes the isolated M2-01/M5-03 GPU
comparison and conditional promotion, subject to the same quality, latency,
resource and service-lifecycle gates above. Keep the current default until those
gates pass; an upstream benchmark alone is not promotion evidence.


## Standard Whisper large-v3 activation (2026-10-24)

The owner explicitly requested replacing the live ASR with standard Whisper
large-v3. This amends DEC-08's default from large-v3-turbo to the pinned
`Systran/faster-whisper-large-v3` conversion at
`edaa852ec7e145841d8ffdb056a99866b5f0a478`. Keep CUDA FP16, beam five and the
existing service contract, cancellation, vocabulary and offline hash checks.
The [paired evaluation](../validation/whisper-large-v3-2026-10-24.md) found better
pooled human PCMA/quiet accuracy with additional inference time; the
[speed study](../validation/whisper-large-v3-speed-2026-10-24.md) does not justify
greedy decoding or other accuracy tradeoffs. Validate real gRPC recognition and
lifecycle before switching the carrier worker; retain the previous pin/cache for
rollback. Handset response latency and conversational quality remain separate
from synthetic GPU validation. No license or model redistribution is approved.
