# Turkish-adapted Whisper evaluation — 2026-10-24

M2-01 / M5-03; requirements §8.1, US-02/04/06; evaluation under ADR 0003
and ADR 0008. The owner requested a test of the Turkish-adapted model after
research. No live model/configuration change was made.

## Decision

Retain large-v3-turbo on the carrier development line. The candidate improves
aggregate noisy/quiet human speech results, ties ordinary PCMA WER, slightly
regresses clean human speech, and increases product-name misses and inference
latency. This is a useful candidate for further domain adaptation, not a demonstrated
replacement for the current interactive profile.

## Model and execution provenance

- Candidate: [TurkMedSTT general Turkish large-v3](https://huggingface.co/turkmedstt/whisper-large-v3-turkish-general),
  revision `ec03ccfcedc0cc1c553b47a607086f2bd7a386b2`.
- Source `model.safetensors`: SHA-256
  `1942821b3742a39b1e7e9b68d4beaef0b54c3bed9a6bd94cc7850816d07f00c0`,
  verified against the upstream LFS object ID; 3,087,130,976 bytes.
- Converted float16 `model.bin`: SHA-256
  `ec9e51e4fde500a6fb4822e8f0f478ed3950cf1d3da4a24f284fb790de815f35`.
  Tokenizer was generated from the pinned local source, with 51,866 tokens.
- Inference: existing faster-whisper 1.2.1 / CTranslate2 4.6.0, CUDA float16,
  RTX 4080, Ubuntu. Conversion used the frozen Nemotron preparation environment
  (Transformers 5.13.0, PyTorch 2.6.0+cu124) with CTranslate2 4.6.0 in a temporary
  uv overlay. No runtime lockfile or resident service was modified.
- Baseline: pinned `dropbox-dash/faster-whisper-large-v3-turbo`, revision
  `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`; rerun during this experiment.
- Candidate model card declares Apache-2.0; conversion/runtime tools retain their
  upstream licenses. Evaluation does not approve model/data redistribution.
- Source files, converted weights, hashes and detailed outputs remain under
  ignored `.local/turkmed-eval/` on Linux. No private transcripts or audio are
  included in this report.

## Protocol

Reused `tools/asr-compare/run.py` without source changes (SHA-256
`e9b925b49d2ecfa788f5ae40cf1b79a25ed7499a195f49c5cf93c94567515803`).
The exact [previous public/synthetic fixture manifest](../../tools/asr-compare/README.md)
contains 24 FLEURS Turkish human read recordings and 16 EMA synthetic utterances.
Four paired conditions give 160 decodes per model, 320 total. Source WAV hashes
are checked by the runner. Conditions are clean 16 kHz, 8 kHz PCMA round trip,
PCMA with deterministic 10 dB noise, and PCMA attenuated approximately 24 dB.

Both models used Turkish, beam 5, temperature 0, previous-text conditioning off,
internal VAD off, word timestamps off, maximum 440 new tokens, and no private
spelling replacements or hotwords. Default segment timestamp decoding was retained.
Only the offline model-path lookup was substituted for the candidate. Full results
were consumed after warm-up; profiles ran sequentially. Resident services remained
loaded. Timings are unpaced whole-utterance inference, not streaming partials,
turn-end latency, handset performance, or concurrent-load acceptance.

## Human speech results

WER is pooled word edits / reference words; lower is better.

| Condition (24 recordings each) | Turbo WER | Turkish model WER | Candidate better / tied / worse recordings |
| --- | ---: | ---: | --- |
| Clean | 7.24% | 7.89% | 5 / 14 / 5 |
| PCMA | 11.40% | 11.40% | 7 / 13 / 4 |
| PCMA + 10 dB noise | 24.56% | 22.15% | 13 / 4 / 7 |
| Quiet PCMA | 21.93% | 12.28% | 7 / 11 / 6 |

Quiet-speech aggregate improvement is not uniform across recordings. Speaker IDs
are unavailable and the selected gender metadata is uniformly category 0. The
small read-speech set does not establish broad speaker coverage or spontaneous
call-center performance. Training overlap with public corpora is not ruled out.

| PCMA inference | Turbo | Turkish model |
| --- | ---: | ---: |
| Human P50 | 142 ms | 368 ms |
| Human P95 | 179 ms | 550 ms |
| Synthetic P50 | 112 ms | 217 ms |
| Synthetic P95 | 123 ms | 293 ms |

Whole-device GPU memory was 6,626 MiB before evaluation and peaked at 10,373 MiB
in 500 ms samples during the candidate run, an observed increase of 3,747 MiB.
This includes resident services and allocator overhead; it is not a model-only
memory figure or a guarantee for longer/concurrent requests. No OOM occurred.

## Synthetic entities and silence

| Condition (16 synthetic utterances each) | Turbo literal WER | Turkish model literal WER | Turbo / candidate entity misses |
| --- | ---: | ---: | ---: |
| Clean | 19.23% | 2.31% | 1 / 2 |
| PCMA | 19.23% | 3.08% | 1 / 2 |
| Noisy PCMA | 21.54% | 6.92% | 2 / 2 |
| Quiet PCMA | 19.23% | 2.31% | 1 / 2 |

The apparent synthetic WER improvement substantially reflects number formatting:
the reference spells numbers out, the candidate often does likewise, and Turbo
often emits digits. It must not be reported as an equivalent improvement in
semantic accuracy. The candidate phone utterance had zero literal word edits in
all four conditions. Product spelling regressed: the clean/PCMA/quiet entity-miss
count rose from one to two. There are only three curated product/brand entity
labels per condition; FLEURS has none. Name and date examples were inspected,
but this is not a broad entity benchmark or a normalized digit-error-rate study.

An additional direct-backend diagnostic used 1 s / 5 s digital silence and seeded
Gaussian noise (standard deviation 0.003, seed 41). Both returned empty text for
both exact-silence cases through the existing zero-input guard. Turbo emitted
text on both noise cases; the candidate was empty at 1 s but emitted text at 5 s.
Both therefore retain noise-hallucination risk. This diagnostic bypasses the
gateway's external VAD and does not demonstrate a live false activation.

## Reproduction

Use the pinned source revision above with `huggingface_hub.snapshot_download`,
verify the source hash, and convert on CPU in the existing preparation environment:

```python
from ctranslate2.converters import TransformersConverter
from transformers import AutoTokenizer

source = '.local/turkmed-eval/source'
target = '.local/turkmed-eval/ct2'
TransformersConverter(source, copy_files=[
    'tokenizer_config.json', 'preprocessor_config.json'
]).convert(target, quantization='float16')
AutoTokenizer.from_pretrained(source, local_files_only=True).save_pretrained(target)
```

Run the existing comparison CLI with `--profile whisper`, the original
`.local/nemotron-eval/fixtures/manifest.json`, and a new output directory. For
the candidate only, wrap the same runner in this offline process:

```python
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

sys.path.insert(0, 'services/asr')
from alojan_asr import model
with patch.object(model, 'model_path', return_value=Path('.local/turkmed-eval/ct2')):
    runpy.run_path('tools/asr-compare/run.py', run_name='__main__')
```

Use the ASR environment, `OPENBLAS_NUM_THREADS=1`, and the same cuBLAS/cuDNN
library paths as `scripts/run-asr.sh`. This substitution is an evaluation-only
mechanism, not a new production model selection API.

## Checks and remaining gates

Linux comparison checks: **3 passed**, with the existing Python 3.12 `audioop`
deprecation warning. Both 160-decode profiles and eight additional silence/noise
diagnostics completed. Temporary inference processes exited after testing.
After cleanup, whole-device GPU memory returned to 6,626 MiB and health checks
on the resident ASR (15173), EMA (15072), and agent (15073) all returned SERVING.
No application source changed; service lifecycle/cancellation and carrier tests
were not rerun for this candidate. No carrier call, caller recording, deployment,
push or model-default change occurred. Further promotion would require broader
human telephone data, entity regression resolution and service/latency validation.
