# Nemotron 3.5 versus Whisper — 2026-10-23

Scope: M2-01 / M5-03, ADR 0008, requirements §8.1 and US-02/04/06.
Owner requested Turkish comparison on different audio and configuration-based
support for both models, with promotion conditional on improvement.

## Decision

Keep the active worker on faster-whisper large-v3-turbo. Neither tested Nemotron
profile improved Turkish accuracy in this sample. The optional backend is usable
through configuration for development evaluation, but is not promoted to the
carrier line. This result applies to these pins, this adapter, RTX 4080 and this
sample; it is not a universal ranking of the models or optimized NIM/NeMo engines.

## Protocol and provenance

The paired dataset contains 24 public Turkish FLEURS test recordings selected at
evenly spaced indices before examining outputs, plus 16 existing synthetic EMA
utterances. Four transformations per utterance: clean 16 kHz, PCMA roundtrip,
PCMA plus 10 dB white noise, and PCMA at approximately -24 dB gain. Each profile
performed 160 decodes, giving 480 total across Whisper and two Nemotron profiles.
The public set contains 456 reference words and the synthetic set 130 per condition.
Detailed audio/transcripts remain ignored on the primary Linux host.

FLEURS provides no speaker IDs here, and selected gender metadata is uniformly
category 0. These are different human recordings, not proof of 24 distinct voices
or balanced genders. No private caller audio was recorded or uploaded. Public
read speech and a single synthetic voice cannot establish general handset quality.
Sources, corpus hash, revisions and reproduction commands are in
[the evaluation guide](../../tools/asr-compare/README.md).

Whisper uses the existing pinned CUDA float16 beam-5 decoder; Nemotron uses pinned
Transformers 5.13.0/PyTorch 2.6.0+cu124, float32 CUDA, explicit Turkish, and native
cache-aware chunks with 320 or 1120 ms lookahead profiles. Both receive identical
PCM without the private spelling map. The Nemotron final partial chunk is padded
rather than dropped. All six model hashes were checked, including the 2.55 GB
safetensors artifact. Each profile is warmed up, then run sequentially once.
No competing evaluation process ran on the GPU; resident development workers
remained loaded. Incoming carrier traffic was not instrumented for this benchmark.

Word errors use the same Unicode/Turkish case and punctuation normalization for
both models. No semantic or spoken-number normalization is applied. Literal WER
can count equivalent written/spoken number formats as errors. Entity labels are
available only for the synthetic set, not FLEURS.

## Human-recording word error rate

Lower is better. Each cell uses the same 24 recordings / 456 reference words.

| Condition | Whisper | Nemotron 320 ms | Nemotron 1120 ms |
|---|---:|---:|---:|
| Clean 16 kHz | 7.24% | 15.79% | 15.79% |
| G.711 A-law | 11.40% | 23.03% | 23.46% |
| Phone + 10 dB noise | 24.56% | 46.05% | 41.01% |
| Quiet phone | 21.93% | 35.75% | 33.11% |

## Synthetic diagnostic word error rate

Each cell uses 16 utterances / 130 reference words. This set includes formatting
sensitivity and previously inspected phrases; it is not held-out acceptance.

| Condition | Whisper | Nemotron 320 ms | Nemotron 1120 ms |
|---|---:|---:|---:|
| Clean 16 kHz | 19.23% | 26.15% | 20.77% |
| G.711 A-law | 19.23% | 30.77% | 20.77% |
| Phone + 10 dB noise | 21.54% | 65.38% | 42.31% |
| Quiet phone | 19.23% | 33.08% | 23.85% |

Required entity misses across all four synthetic conditions: 5 / 12 / 9,
respectively. This diagnostic checks normalized phrase inclusion, not a general
named-entity or semantic correctness model.

## Timing boundaries

Unpaced complete-utterance inference P50/P95, milliseconds:

| Input | Whisper | Nemotron 320 ms | Nemotron 1120 ms |
|---|---:|---:|---:|
| Human PCMA | 142 / 181 | 510 / 734 | 220 / 304 |
| Synthetic PCMA | 112 / 122 | 146 / 251 | 63 / 105 |

The 1120 ms profile processes short synthetic utterances faster computationally,
but requires more future audio. These times omit real-time audio arrival and
lookahead waiting; they are not turn-end-to-speech, P95 service SLO or handset
latency. The shared gRPC service still repeats cumulative decoding for partials;
there is no persistent Nemotron cache across gRPC partial requests. That shortcut
is documented in the adapter; live incremental optimization remains unvalidated.

## Configuration and real-service validation

`ALOJAN_ASR_BACKEND=whisper|nemotron` selects one backend at worker startup.
Private `.local/asr.env` is parsed by uv, never sourced as shell. Each backend has
its own frozen environment; the gRPC contract, bounded executor, generation
cancellation, output limits and spelling policy remain shared. Invalid names fail
closed, with no silent CPU/model substitution. Readiness requires real CUDA warm-up.
Nemotron's service profile uses 320 ms chunks; the 1120 ms run was an offline
comparison only. No live configuration or running carrier process was changed.

Two temporary workers were tested sequentially on loopback port 15174, then
stopped. Each produced correct partial/final transport for all seven synthetic
PCM16/float/silence cases. Pre-start cancellation, active cancellation, no stale
buffered events, and immediate capacity recovery passed for both. Active RPC
cancellation was 0.45 ms for Nemotron and 0.61 ms for Whisper; this does not mean
the GPU kernel was preempted or satisfy the handset barge-in target.

Whisper's existing entity validator passed all cases. Nemotron's validator exited
with failure for the date/name and phone formatting checks: it joined the synthetic
name's words and returned the phone number in spoken words instead of digits.
The reference and result contain the same count of spoken zeros. These checks
must **not** be reported as proven incorrect phone digits or as an overall pass.
No permissive normalization was added merely to pass them. The broader paired WER
also favors Whisper independently of these formatting checks.

Sampled aggregate host GPU peaks with the candidate plus existing resident
workers were 9451 MiB for Nemotron and 8965 MiB for temporary Whisper, against
6626 MiB before testing. These are host totals, not isolated model allocation or
production capacity evidence.

## Checks and limitations

- Linux shared ASR tests: 45 passed, 3.07 s, no skips.
- Evaluation checks: 3 passed, 0.05 s; expected Python 3.12 audioop deprecation.
- Linux Ruff lint/format passed for nine Python files; launcher syntax, invalid
  backend exit-2 check, diff whitespace and new documentation links passed.
- After temporary-worker cleanup, ASR/EMA/agent health remained SERVING, port
  15174 had no listener and aggregate GPU use returned to 6626 MiB.
- Real model comparison: all three profiles completed 160 speech decodes each.
- Real service lifecycle: both backends passed transport/cancellation; Nemotron
  failed two existing exact entity/format checks, as recorded above.
- Initial integration probes exposed a duplicate lookahead keyword and a batched
  decode return type; both were corrected before the paired runs. An initial
  root-test import failed because NumPy is intentionally absent there; evaluation
  tests now run separately in the model environment.

No carrier call, new native gateway behavior, automatic failover, deployment,
model fine-tuning, notifications or recording was introduced. Full human/noisy
handset acceptance, distinct-speaker coverage, persistent streaming performance,
long-turn calibration and G3/G4 remain open. Do not switch the live default based
on the model name or vendor throughput claims. No push, PR or merge was performed.
