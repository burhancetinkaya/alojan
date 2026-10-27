# Turkish ASR comparison

M2-01 / M5-03, ADR 0008, requirements §8.1 and US-02/04/06. This is an offline
CUDA comparison, not handset or carrier acceptance. All audio and detailed
transcripts stay in ignored `.local/`; do not commit the downloaded corpus.

## Inputs and attribution

- [Google FLEURS](https://huggingface.co/datasets/google/fleurs), Turkish test
  split; CC BY 4.0. Parquet conversion revision
  `168de341b3db6859a9bac1c50a2ef5e3b47647e0`, file `tr_tr/test/0000.parquet`, SHA-256
  `ced63953ed29a51ae618fffb03125c04bdf2b14ea461ccea503406cc61f94d3d`.
  Select 24 evenly spaced rows before seeing model outputs, accepting 2–20 s mono
  recordings. The selected metadata has only gender category 0; speaker IDs are
  absent. Do not claim a verified count of different speakers or gender balance.
  Public read speech differs from spontaneous telephone speech.
- Existing explicitly synthetic EMA fixtures with references and optional entity
  labels, using the private `synthetic-ema` manifest from the earlier ASR study.
  This voice and these phrases are a separate diagnostic set, not independent
  human quality acceptance.
- Nemotron weights/runtime are pinned in `services/asr/nemotron.json` and
  `services/asr-nemotron/uv.lock`; see the ASR README for explicit download.
  Model license: OpenMDW 1.1; Transformers: Apache 2.0; PyTorch: BSD-style.
  CUDA wheel terms and redistribution remain subject to the project's license
  review. Do not infer blanket redistribution approval.

## Reproduce on the primary Linux host

Download the pinned public Parquet into `.local/nemotron-eval/` and verify its
hash first. Keep existing workers idle during timing and run profiles sequentially.
Use the installed `uv` and the same source on Linux:

```sh
uv run --frozen --project services/asr-nemotron --with pyarrow==19.0.1 \
  python tools/asr-compare/prepare.py \
  --parquet .local/nemotron-eval/fleurs-tr-test.parquet \
  --synthetic .local/asr-quality-probe/fixtures.json \
  --output .local/nemotron-eval/fixtures-new

# Supply the same CTranslate2 CUDA library paths as scripts/run-asr.sh.
OPENBLAS_NUM_THREADS=1 uv run --frozen --project services/asr python \
  tools/asr-compare/run.py --fixtures .local/nemotron-eval/fixtures-new/manifest.json \
  --profile whisper --output .local/nemotron-eval/whisper-new
OPENBLAS_NUM_THREADS=1 uv run --frozen --project services/asr-nemotron python \
  tools/asr-compare/run.py --fixtures .local/nemotron-eval/fixtures-new/manifest.json \
  --profile nemotron --lookahead 3 --output .local/nemotron-eval/nemotron320-new
# Use --lookahead 13 and a fresh output path for the 1120 ms profile.
uv run --frozen --project services/asr-nemotron --with pytest==8.3.5 \
  pytest -q tools/asr-compare/test_compare.py
```

Each fixture runs clean at 16 kHz, through 8 kHz G.711 A-law, with deterministic
10 dB noise after that phone conversion, and with approximately -24 dB gain.
These last two are controlled perturbations, not recordings of an actual handset.
Both backends receive the identical samples without private spelling corrections.
The Turkish case normalization preserves dotted/dotless I. Literal WER includes
number-format differences; review number/entity results separately. FLEURS has
no curated entity labels in this tool, so its entity-miss field is not an entity
accuracy measurement.

One warm-up precedes each profile; timings consume the full result, and Nemotron
synchronizes CUDA. Report the one-pass P50/P95 as diagnostic sample statistics,
not stable production latency. Audio is supplied unpaced. Nemotron uses actual
cache-aware chunks within each utterance; the service still recomputes cumulative
partial hypotheses. Runtime memory, cancellation and service readiness must be
validated separately before promotion. A failed candidate remains optional;
Whisper is the live default.

## Qwen3-ASR-1.7B follow-up

`qwen.py` reuses the same runner with an offline-only Qwen backend. The legacy
`--profile whisper` argument selects the runner slot replaced by this adapter;
its output directory must clearly identify Qwen. This is not a production backend
or a change to `ALOJAN_ASR_BACKEND`.

Create an isolated Python 3.12 uv project under `.local/qwen-eval` with
`qwen-asr==0.0.6`, `torch==2.6.0+cu124` (the explicit PyTorch cu124 index),
`numpy==2.2.6`, `librosa==0.11.0` and `soundfile==0.13.1`. Resolve once and retain
the resulting `uv.lock`; subsequent runs use `--frozen`. Qwen pins Transformers
4.57.6 and Accelerate 1.12.0. Do not modify the resident ASR/TTS environments.
Download `Qwen/Qwen3-ASR-1.7B` revision
`7278e1e70fe206f11671096ffdd38061171dd6e5` into `.local/qwen-eval/model`, then
verify both weight shards against the hashes in the evaluation report.

```sh
OPENBLAS_NUM_THREADS=1 HF_HUB_OFFLINE=1 \
  ALOJAN_QWEN_MODEL="$PWD/.local/qwen-eval/model" \
  uv run --frozen --project .local/qwen-eval python tools/asr-compare/qwen.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --profile whisper --output .local/qwen-eval/qwen-new
uv run --frozen --project services/asr-nemotron --with pytest==8.3.5 \
  pytest -q tools/asr-compare/test_compare.py tools/asr-compare/test_qwen.py
```

The adapter uses BF16, SDPA, batch size one, greedy generation, 440 maximum new
tokens, explicit Turkish, no context hints and no forced aligner. The comparison
supplies full utterances, synchronizes CUDA before timing ends and retains the
same exact-zero silence guard as Whisper. It does not test streaming, generation
cancellation or native telephone integration. Qwen and its toolkit declare
Apache-2.0; runtime dependencies retain their upstream terms. This does not
approve redistribution. See [measured results](../../docs/validation/qwen-asr-2026-10-24.md).
