# Whisper large-v3 speed study — 2026-10-24

M2-01 / M5-03; requirements §3/8.1, US-02/04/06; ADR 0003 and ADR 0008.
Owner requested ways to accelerate the standard large-v3 candidate.

## Outcome

No tested decoder setting delivered a large speedup while preserving all measured
quality conditions. The fastest combination, INT8 with greedy decoding, reduced
human PCMA median inference from 359 to 288 ms (19.8%), but lost accuracy.
INT8 with beam five is the most conservative measured candidate: 334 ms (7.0%),
unchanged PCMA/quiet pooled WER and improved noisy WER, but worse clean WER.
It is not ready for automatic promotion. Keep live/default Turbo unchanged.

INT8 with beam three reached 320 ms (11.1%), but introduced an extra subtitle-like
phrase in a quiet synthetic closing fixture. Aggregate human WER alone concealed
this regression. Disabling timestamps and reducing FP16 beam size also regressed
quality. FlashAttention failed at startup; its constructor parameter is not proof
of working support. No production code or runtime configuration was changed.

## Paired results

The same 24 public Turkish FLEURS recordings and 16 EMA synthetic utterances,
four conditions and normalized scoring were used in seven sequential profiles:
**1,120 measured decodes**, excluding warm-ups. The reference wrapper reproduced
all 160 transcripts from the previous standard-large-v3 run exactly. Model/runtime
pins and corpus limitations are in the [standard-model report](whisper-large-v3-2026-10-24.md)
and [evaluation guide](../../tools/asr-compare/README.md).

| Profile | Human PCMA P50 / P95 | Speedup in P50 | Clean WER | PCMA WER | Noisy WER | Quiet WER |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FP16, beam 5 (reference) | 359 / 537 ms | 0.0% | 6.14% | 9.65% | 24.12% | 11.40% |
| FP16, beam 3 | 347 / 508 ms | 3.5% | 6.36% | 10.09% | 23.90% | 12.06% |
| FP16, beam 1 | 308 / 449 ms | 14.2% | 7.68% | 10.09% | 23.25% | 12.94% |
| INT8/FP16, beam 5 | 334 / 510 ms | 7.2% | 6.80% | 9.65% | 21.27% | 11.40% |
| INT8/FP16, beam 3 | 320 / 485 ms | 11.1% | 6.80% | 9.65% | 21.27% | 11.40% |
| INT8/FP16, beam 1 | 288 / 426 ms | 19.9% | 7.46% | 11.18% | 23.46% | 15.35% |
| FP16, beam 5, no timestamps | 338 / 514 ms | 6.0% | 6.36% | 10.31% | 24.78% | 14.47% |

Times are warmed full-utterance inference on RTX 4080, not phone response delay.
All successful profiles used CTranslate2 4.6.0 / faster-whisper 1.2.1, pinned
standard large-v3 weights, Turkish, four CPU threads, one worker, temperature zero,
max 440 tokens, no previous-text conditioning/internal VAD/word alignment, and no
private spelling corrections. Each profile changes only the listed options.
INT8 uses `compute_type=int8_float16`. The timestamps experiment changes
`without_timestamps`, which is separate from the already-disabled word alignment.
The shared development GPU was not reserved exclusively; these are diagnostic
single-pass distributions, not statistically established production improvements.

Every profile had two curated product/brand misses in the synthetic PCMA group,
versus one in the previous Turbo comparison. This set has only three entity labels
per condition and no curated human entity labels. Number formatting confounds
synthetic literal WER. No configuration fixes all domain recognition issues.

The INT8 beam-three quiet closing gained “Altyazı M.K.” after its farewell.
This increased that sample from two to four word edits. Three independent
decodes per profile reproduced the extra phrase in all three INT8/beam-three
attempts, and in none of the FP16-reference or plain-INT8 attempts. These nine
follow-up decodes bring the study to **1,169 measured decodes**, excluding warm-ups. Its synthetic quiet WER
was 21.54% versus 20.00% for the FP16 reference. It is additional fabricated
content, not merely punctuation or numeric formatting.

## Where time is spent

A separate instrumented pass over the 40 PCMA utterances timed the existing
`encode` and `generate_with_fallback` methods and consumed all output. The native
encode method synchronizes its CUDA stream before returning; full generation is
also consumed. These are component wall times, not individual kernel profiling.

| Corpus | Mean total | Encode | Decode | Other work |
| --- | ---: | ---: | ---: | ---: |
| 24 human recordings | 380.8 ms | 73.6 ms | 300.7 ms | 6.5 ms |
| 16 synthetic utterances | 201.8 ms | 73.5 ms | 124.7 ms | 3.6 ms |

About 79% of human inference time is decoder generation, 19% encoder and 2% other
work. This suggests prioritizing a more efficient decoder engine over small CPU
wrapper changes. It does not predict a particular speedup from TensorRT or any
other untested engine. This pass adds **40 measured decodes** to the screening.

## Research and implementation constraints

- [CTranslate2 quantization](https://opennmt.net/CTranslate2/quantization.html)
  supports loading the existing FP16 weights with `compute_type=int8_float16`.
  Hardware support was queried on the RTX 4080 before execution. No weight
  download, conversion, runtime upgrade or dependency change was needed.
- [CTranslate2 Whisper decoding options](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html)
  expose beam size one for greedy search. Fewer hypotheses can reduce work but
  change recognition; measurements below evaluate that tradeoff directly.
- [Pinned faster-whisper source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
  distinguishes word alignment from decoder timestamp tokens. We already disable
  word timestamps; `without_timestamps=True` is a different decoding change.
  Shortening `chunk_length` is not a demonstrated shortcut: this version's
  `generate_segments` still calls default `pad_or_trim(segment)` before encoding.
- FlashAttention is accepted as a constructor argument, but the installed
  CTranslate2 4.6.0 Whisper configuration fails at runtime with
  `RuntimeError: Flash attention 2 is not supported`. No successful inference or
  speedup is claimed for that profile. Merely installing a similarly named Python
  package is not a demonstrated fix.
- [faster-whisper batching benchmarks](https://github.com/SYSTRAN/faster-whisper)
  show throughput benefits on long audio, not guaranteed low-latency phone turns.
  Our service has a single inference executor and a single active-stream admission
  flag; setting a batch-size value alone does not implement five-call batching.
- [NVIDIA's supported-model list](https://nvidia.github.io/TensorRT-LLM/models/supported-models.html)
  includes standard Whisper large-v3. A separate TensorRT-LLM evaluation is a
  plausible next engine experiment, not a measured improvement on this host.
  It requires pinned conversion/build/runtime and a repeat of quality, memory,
  cancellation and concurrent-call checks. No TensorRT engine was installed here.

Inspection of `RecognitionService.StreamRecognize` confirms a cumulative decode
approximately every additional second of audio, plus a final decode only if audio
changed since the last partial. It already reuses an unchanged final transcript.
Native inference is not preemptible; cancellation invalidates results and retains
admission until the running call returns. Any reduction/coalescing of partial
work must preserve final audio coverage, current partial age, turn decisions and
bounded cancellation. Do not simply cache encoder features across growing audio:
the existing model is not an incremental causal encoder.

## Prioritized next steps

1. Evaluate a pinned TensorRT-LLM Whisper engine in isolation on the same data and
   RTX 4080; retain full decoding coverage and test paired quality before speed.
   Validate conversion provenance, licensing, memory coexistence and worker
   cancellation/admission before any promotion. No promised two/threefold gain.
2. Measure cumulative partial workload in the real gRPC/gateway path. Explore
   coalescing pending partial snapshots or adaptive partial intervals, with final
   audio coverage and maximum partial age explicit. Check pause/turn-end,
   backchannel, barge-in and cancellation regressions. Do not assume removing
   partials preserves current phone behavior.
3. For five-call capacity, evaluate bounded cross-call batching with a short
   maximum wait and per-call cancellation/isolation. The current single-stream
   service needs admission/scheduling work first. A batch throughput result is
   not single-caller latency or five-call acceptance.
4. Keep plain INT8/beam-five as a modest memory/latency candidate for a larger,
   unseen human telephone set. Its clean-speech regression still needs review.
   Greedy decoding, timestamp suppression and INT8/beam-three should not be
   enabled from the current results.

## Reproduction

On Linux, retain the existing frozen ASR environment and pinned weights from the
standard-model report. Set `OPENBLAS_NUM_THREADS=1` and the CUDA library paths in
`scripts/run-asr.sh`. The experiment scripts are preserved under ignored `.local/large-v3-speed/`
on both workspaces. Detailed outputs remain on Linux; summary metrics are also
copied to Mac. Audio/transcripts are not committed. `profile.py` wraps the unchanged production Whisper backend:


```python
"""Isolated decoder experiment; no service/configuration mutations."""
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
import faster_whisper

sys.path.insert(0, 'services/asr')
from alojan_asr import model
profile=json.loads(os.environ['ALOJAN_EXPERIMENT'])
assert set(profile) <= {'load','decode'}
assert set(profile.get('load',{})) <= {'compute_type','flash_attention'}
assert set(profile.get('decode',{})) <= {'beam_size','without_timestamps'}
original=faster_whisper.WhisperModel

def factory(*args,**kwargs):
    kwargs.update(profile.get('load',{}))
    instance=original(*args,**kwargs)
    original_transcribe=instance.transcribe
    def transcribe(*a,**k):
        k.update(profile.get('decode',{}))
        return original_transcribe(*a,**k)
    instance.transcribe=transcribe
    return instance

with patch.object(model,'model_path',return_value=Path('.local/large-v3-eval/model')), patch.object(faster_whisper,'WhisperModel',factory):
    runpy.run_path('tools/asr-compare/run.py',run_name='__main__')
```

Pass `--profile whisper --fixtures .local/nemotron-eval/fixtures/manifest.json`
and a fresh `--output` path to that wrapper using `uv run --frozen --project
services/asr python`. `ALOJAN_EXPERIMENT` is `{}` for the reference,
`{"decode":{"beam_size":1}}` or beam 3, `{"load":{"compute_type":"int8_float16"}}`,
the combinations of those dictionaries, or `{"decode":{"without_timestamps":true}}`.
`{"load":{"flash_attention":true}}` reproduces the unsupported profile.
The wrapper is an evaluation-only process substitution, not a production API.

## Checks and limits

Linux evaluator tests: **3 passed in 0.11 s**, with the existing Python 3.12
audioop deprecation warning. The untouched-profile reproduction matched all 160
prior transcripts. Seven CUDA profiles and the component timing pass completed;
the FlashAttention startup failed and is not counted as a successful run.
No native build or production application regression run was needed because no
application source changed. Broad unseen-data quality, live partial latency,
SIP/carrier, concurrency and soak validation remain open. No service restart,
model-default change, carrier call, push or publication occurred.

Final resident ASR (15173), EMA (15072) and agent (15073) health checks all
returned SERVING; device memory returned to 6,626 MiB and no evaluation process
remained. Relative documentation links and diff whitespace checks passed.
