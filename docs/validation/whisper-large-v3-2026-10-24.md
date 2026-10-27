# Standard Whisper large-v3 evaluation — 2026-10-24

M2-01 / M5-03; requirements §8.1, US-02/04/06; ADR 0003 and ADR 0008.
Owner requested a test of standard large-v3 against the current large-v3-turbo.

## Result and decision

Standard large-v3 improved pooled human-speech WER in all four tested conditions,
especially quiet speech. It is a stronger accuracy candidate than the previously
tested Qwen profile on this small corpus. It is not an unqualified replacement:
PCMA human inference P50 increased from 142 to 360 ms, and one additional curated
product name was missed. Retain the current live/default Turbo profile for this
evaluation. No production source/configuration or service was changed.

## Protocol

Reused the [existing paired corpus and evaluator](../../tools/asr-compare/README.md):
24 public FLEURS Turkish human read recordings and 16 EMA synthetic utterances.
Clean 16 kHz, 8 kHz PCMA round trip, PCMA with deterministic 10 dB noise and quiet
PCMA at approximately -24 dB give 160 decodes per model, **320 total**. Source
WAV hashes are checked by the runner. Both models were warmed and run sequentially
with the same settings and resident services loaded. All decodes completed.
Eight additional exact-silence/noise controls completed separately. A subsequent
160-decode Turbo repeat checked the shared-host timing change described below,
for **480 speech decodes plus eight controls** overall.

Human speaker IDs are unavailable and selected gender metadata is uniformly
category 0. Public read speech is not spontaneous handset speech; corpus training
overlap is not ruled out. These are diagnostic samples, not broad acceptance.
WER uses pooled edits/reference words with Turkish case normalization. Synthetic
number-format differences must not be confused with semantic errors.

## Human results

| Condition, 24 recordings each | Turbo WER | Standard large-v3 WER | Large-v3 better / tied / worse |
| --- | ---: | ---: | --- |
| Clean | 7.24% | 6.14% | 5 / 17 / 2 |
| PCMA | 11.40% | 9.65% | 8 / 11 / 5 |
| Noisy PCMA | 24.56% | 24.12% | 12 / 7 / 5 |
| Quiet PCMA | 21.93% | 11.40% | 8 / 12 / 4 |

PCMA pooled word errors fall by approximately 15.4% relative; quiet pooled errors
fall by 48.0%. Improvement is not uniform across recordings, and no statistical
significance or deployment-wide accuracy claim is made.

| PCMA whole-utterance inference | Turbo | Standard large-v3 |
| --- | ---: | ---: |
| Human P50 | 142 ms | 360 ms |
| Human P95 | 179 ms | 540 ms |
| Synthetic P50 | 112 ms | 216 ms |
| Synthetic P95 | 122 ms | 260 ms |

The human median cost is about 2.54 times Turbo, an additional 219 ms. These are
single-pass, unpaced full-utterance measurements, not streaming partials,
endpoint-to-RTP latency or concurrency capacity. The current service recomputes
cumulative partial audio; this benchmark does not measure that extra work.

Whole-device memory observed during candidate inference was 12,231 MiB versus
6,626 MiB at task start and 8,613 MiB after the candidate exited. An independent
endpoint-latency experiment started an additional 1,984 MiB ASR worker during
the download. It was preserved. These totals include resident models, that
additional worker, allocator/runtime overhead and the temporary candidate.
This is a spot observation, not a sampled peak or a model-only measurement. No OOM occurred. Five-call readiness is not established.

A Turbo repeat after the extra worker was loaded reproduced all 160 transcripts
exactly and measured human PCMA P50/P95 of 142/182 ms (original 142/179 ms).
The speed tradeoff therefore persists in that host state. The table retains
the original run; the shared host was not reserved exclusively, and per-process
GPU activity was not continuously recorded. Treat timings as diagnostic.

## Synthetic entities and controls

| Condition, 16 utterances each | Turbo literal WER | Large-v3 literal WER | Turbo / large-v3 entity misses |
| --- | ---: | ---: | ---: |
| Clean | 19.23% | 20.00% | 1 / 2 |
| PCMA | 19.23% | 20.00% | 1 / 2 |
| Noisy PCMA | 21.54% | 20.77% | 2 / 2 |
| Quiet PCMA | 19.23% | 20.00% | 1 / 2 |

For ordinary PCMA, large-v3 changed the curated product spelling from the correct
“Lena Accredit” to “Lena Agredit”; another product phrase was misspelled by both.
The short interruption phrase and date/name examples matched Turbo. The synthetic
phone case has the same literal edit count for both models; references spell
numbers out while model outputs use digits. This is not a normalized digit-error
benchmark. Only three curated brand/product labels exist per condition, and
human FLEURS entity accuracy is unmeasured. No private spelling aliases were used.

Both models returned empty for one- and five-second digital silence through the
existing exact-zero guard. Both emitted text for one- and five-second seeded
Gaussian noise (seed 41, standard deviation 0.003). This bypasses external gateway
VAD and does not establish a carrier false activation. No caller recordings were used.

## Provenance and reproduction

Candidate: [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3),
the CTranslate2 conversion of standard OpenAI Whisper large-v3, not the previously
tested TurkMedSTT fine-tune. Revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`;
`model.bin` is 3,087,284,237 bytes, SHA-256
`69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1`.
The model card declares MIT; runtime dependencies retain their upstream terms.
Evaluation does not approve redistribution.

Baseline: `dropbox-dash/faster-whisper-large-v3-turbo`, revision
`0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`, rerun during this experiment.
Both run on Ubuntu / RTX 4080 with the existing frozen faster-whisper 1.2.1 /
CTranslate2 4.6.0 environment, CUDA FP16, four CPU threads, one worker, Turkish,
beam five, temperature zero, no previous-text conditioning, no internal VAD,
no word timestamps, max 440 new tokens, no private aliases or hotwords.

The existing runner was reused unchanged (SHA-256
`e9b925b49d2ecfa788f5ae40cf1b79a25ed7499a195f49c5cf93c94567515803`).
For the candidate, an evaluation-only wrapper substitutes its local model path:

```python
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

sys.path.insert(0, 'services/asr')
from alojan_asr import model
with patch.object(model, 'model_path', return_value=Path('.local/large-v3-eval/model')):
    runpy.run_path('tools/asr-compare/run.py', run_name='__main__')
```

Use the frozen `services/asr` environment, `OPENBLAS_NUM_THREADS=1`, and cuBLAS/
cuDNN paths from `scripts/run-asr.sh`. Pass `--profile whisper`,
`--fixtures .local/nemotron-eval/fixtures/manifest.json` and a fresh `--output`
directory to both the unchanged baseline CLI and candidate wrapper. Pin the
candidate download revision above and verify its hash before execution.
Detailed results, controls, weights and wrapper remain under ignored
`.local/large-v3-eval/`; no production model selection API was added.

## Checks and remaining gates

Linux evaluator checks: **3 passed in 0.09 s**, with the existing Python 3.12
`audioop` deprecation warning. No application source changed, so no new native
build or application regression suite was needed. Real GPU evidence is the
480 completed decodes including the baseline repeat, plus eight controls,
separate from those tests. Diff whitespace and relative documentation links passed.

Model weights were downloaded and verified on Mac. SCP proved slow and was
stopped; a direct HTTPS download on Linux completed and its full size/SHA-256
were verified before inference. Partial downloads were not used as model weights.
The runtime remained the existing frozen ASR environment.

Temporary inference exited; ASR (15173), EMA (15072) and agent (15073) health
checks all returned SERVING, including the final delivery check. Device memory
was initially 8,613 MiB after the candidate exited with the independent worker
still loaded; the final delivery check measured 6,626 MiB. No inference process
from this evaluation remained, and no independent worker was stopped by this task.
No service restart, live model switch, carrier call, push or publication occurred. Broader
human speech, proper-name coverage, partial-transcription latency, cancellation,
SIP/handset and concurrent-load validation remain required before promotion.
