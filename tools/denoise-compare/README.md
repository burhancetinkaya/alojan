# Native noise suppression comparison

M2-01 / M5-03, requirements §8.1 and US-02/06. Offline evaluation authorized by
the owner; this does not enable denoising in the carrier gateway. No new runtime
dependency, audio recording or service restart is required.

## Candidates and provenance

- [WebRTC AudioProcessing 2.1](https://freedesktop.org/software/pulseaudio/webrtc-audio-processing/):
  C++, BSD-style license and upstream PATENTS notice. The standalone package uses
  the WebRTC processing code; GitHub mirror stars are not an adoption measure.
  Evaluate low and moderate suppression, with AEC, AGC and high-pass disabled.
- [RNNoise v0.2](https://github.com/xiph/rnnoise/tree/v0.2): C callable from C++,
  BSD-3-Clause. Model `0b50c45`; native CPU build. The 48 kHz processor uses
  Speex quality-5 resampling from/to our 16 kHz stream. No VAD gating or retrospective
  buffer is enabled. This is v0.2, not a claim about every newer model or plugin.
- [SpeexDSP 1.2.1](https://github.com/xiph/speexdsp/tree/SpeexDSP-1.2.1): C callable
  from C++, BSD-style notices. Ubuntu amd64 package `1.2.1-1ubuntu3`, extracted
  privately rather than installed. Test -15 dB suppression with AGC/VAD disabled;
  the same library supplies RNNoise resampling.
- Build tools: existing GCC 13.3.0; isolated Meson 1.7.0 (Apache-2.0), Ninja
  1.11.1.3 (Apache-2.0); upstream pinned Abseil 20240722.0 (Apache-2.0).
  Archive/package hashes are in `build.sh`; the WebRTC upstream wrap verifies its
  Abseil archive and patch. Retain upstream notices for any future distribution;
  this experiment does not grant redistribution approval or add a project license.

The [C++ werman plugin](https://github.com/werman/noise-suppression-for-voice)
uses RNNoise (GPL-3.0 wrapper); importing the entire desktop plugin is unnecessary
for a server. [OBS documents RNNoise and Speex](https://obsproject.com/kb/noise-suppression-filter)
as supported suppression engines. [EasyEffects](https://github.com/wwmm/easyeffects)
is a desktop effects application, not an independent denoising algorithm.
[DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) was researched but not
benchmarked: its Rust/Python stack falls outside this native C/C++ comparison.

## Reproduce on Ubuntu

Use the existing public/synthetic manifest described in
[ASR comparison](../asr-compare/README.md), with no private caller recordings.
The manifest SHA-256 used in this study is
`dad31c9e7753ae3b0fae450ca872b99852464f02594809ba7bb5b019ef3e7955`.
The runner verifies each source WAV hash through the existing loader.

```sh
export PATH="$HOME/.local/bin:$PATH"
sh tools/denoise-compare/build.sh
ALOJAN_DENOISE_PROBE=.local/denoise-eval/probe \
  uv run --frozen --project services/asr --with pytest==8.3.5 \
  pytest -q tools/denoise-compare/test_probe.py

# Set LD_LIBRARY_PATH to the CTranslate2 CUDA directories as in scripts/run-asr.sh.
OPENBLAS_NUM_THREADS=1 uv run --frozen --project services/asr python \
  tools/denoise-compare/run.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --probe .local/denoise-eval/probe --output .local/denoise-eval/results-new
```

All libraries, binaries, source archives and detailed outputs remain in ignored
`.local/denoise-eval/`. Do not rebuild its shared libraries while an evaluation
is running. No system package installation is performed. The RNNoise benchmark
binary uses `-march=native` and must not be copied to other CPUs.

## Protocol and limits

Forty recordings (24 public FLEURS Turkish read speech; 16 synthetic EMA) are
tested under five conditions: ordinary PCMA, white noise, low-frequency fan-like
noise, sparse click-like noise, and quiet speech (-24 dB). Noise is deterministic,
nominally 10 dB against the source utterance RMS, added at 8 kHz before G.711 A-law
encoding/decoding and 16 kHz conversion. It is synthetic noise, not a real fan or
keyboard recording. Peak clipping is counted. The same 300 ms lead-in and 200 ms
tail are supplied to all profiles to retain filter startup and delayed speech;
these are offline fixture padding, not proposed live buffering. Three nonspeech
controls give 203 inputs × five profiles = 1015 decodes.

The C++ probe handles 160-sample (10 ms) frames with per-instance state, including
native RNNoise rate conversion. Its output retains causal filter delay; no offline
alignment improves the ASR score. The last partial frame is zero-padded internally
and output length is preserved. Input is bounded, normalized finite float32 LE.
No files from private calls may be supplied to this evaluation without consent.

The actual pinned Whisper backend is warmed once, with no spelling replacements,
decoder changes, extra VAD or second ASR pass. Profiles rotate order per fixture.
Literal WER includes written-number formatting differences; curated product-name
labels are sparse. Inspect names/dates/phone digits separately. FLEURS speaker
coverage limitations in the earlier study still apply; this reused set is not
an unseen or spontaneous-call benchmark.

Native timing excludes process startup, initialization, disk I/O and model
inference. The intended future integration would retain one processor per call,
not spawn the executable per frame. CPU milliseconds / audio duration estimate
one CPU core's streaming cost. Wall-clock frame outliers are also recorded;
means and per-file P95 are not hard real-time guarantees. Filter signal delay is
separate from processing cost. Whole-utterance Whisper timing is not phone latency.

Promote only with noise improvements and preserved clean/quiet/entity accuracy,
then validate streaming cancellation, barge-in and carrier listening separately.
Neither aggregate improvement nor fewer audible noises is sufficient on its own.
See [results and decision](../../docs/validation/denoise-2026-10-24.md).

## DTLN follow-up

The owner separately authorized trying DTLN. `dtln.py` evaluates the original
[breizhn/DTLN](https://github.com/breizhn/DTLN/tree/1de1f15a8b5b7e1c44905618ff2ef70ca8277fbc)
two-stage pretrained ONNX model, pinned to commit
`1de1f15a8b5b7e1c44905618ff2ef70ca8277fbc`. Both model SHA-256 values are checked
before loading; corrupted existing files are rejected. The model and reference
algorithm are under upstream MIT terms; see [the notice](DTLN-NOTICE.txt).
This is an evaluation, not redistribution approval or a new project license.

Use the existing ONNX Runtime 1.31.0 CPU provider with one intra/inter-op thread,
NumPy 2.5.4 and Python 3.12.3. The runtime inference is native, but the probe's
FFT/buffering loop is Python/NumPy: timings include that loop and **are not a
standalone C++ gateway benchmark**. No LiveKit dependency, resampler, high-frequency
rolloff, VAD, AGC or second ASR pass is added. Sessions stay loaded; each offline
utterance resets its recurrent state. A live integration would need per-call
state and bounded media-worker scheduling, not `process()` on the media callback.

```sh
uv run --no-sync --project services/asr --with onnxruntime==1.31.0 python \
  tools/denoise-compare/dtln.py --models .local/dtln-eval/models
ALOJAN_DTLN_MODELS=.local/dtln-eval/models \
ALOJAN_DENOISE_PROBE=.local/denoise-eval/probe \
  uv run --no-sync --project services/asr --with onnxruntime==1.31.0 \
  --with pytest==8.3.5 pytest -q tools/denoise-compare/test_dtln.py \
  tools/denoise-compare/test_probe.py

# Set CUDA library paths as in scripts/run-asr.sh; do not load private agent secrets.
OPENBLAS_NUM_THREADS=1 uv run --no-sync --project services/asr \
  --with onnxruntime==1.31.0 python tools/denoise-compare/run.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --probe .local/denoise-eval/probe --profiles bypass dtln \
  --dtln-models .local/dtln-eval/models --output .local/dtln-eval/results-new
```

`--profiles bypass dtln-half` selects a separate exploratory 50% wet/dry blend.
The dry path is delayed by 384 samples (24 ms) before mixing to avoid comb filtering.
This does not reproduce the entire LiveKit plugin, which has additional filtering
and buffering. Each full comparison has 406 decodes. The half-strength follow-up
was selected after seeing full-strength regressions; it is not an independent
held-out confirmation. Existing default profiles remain unchanged.

DTLN uses a 512-sample (32 ms) window and a 128-sample (8 ms) hop. The 24 ms
overlap-add signal lag is retained, with no retrospective alignment for ASR.
Input-frame accumulation and scheduler delays are additional; an 8 ms hop is not
an 8 ms end-to-end latency claim. The shared JSON timing container is named
`native` for compatibility, but DTLN records its actual implementation and 8 ms
frame duration. Do not compare its per-frame values to the older 10 ms values
without normalization. Whole-utterance ASR time is not caller response latency.

The upstream demonstration leaves its final blocks unprocessed. This probe
processes all input including the existing 200 ms fixture tail, zero-pads the
final partial hop and preserves input length. No extra speech is cut to match
that example's file-loop limitation. See [results](../../docs/validation/dtln-2026-10-24.md).

## Free voice isolation: VoxLock

`voxlock_trial.py` is an isolated CPU screening experiment, followed by
`voxlock_score.py` using the existing CUDA Whisper backend. This does not install
VoxLock into any serving application. Source and model declare Apache-2.0;
retain their LICENSE/NOTICE files, including WeSep/REAL-TSE attribution. No paid
SDK or key is required. [Decision and limitations](../../docs/validation/voxlock-2026-10-27.md)
record the wrong-speaker failure; do not enable automatic enrollment on the line.

On the primary Linux host, use Python 3.12 and the existing public/synthetic
fixture manifest. Keep downloads and outputs ignored. For a fresh evaluation folder:

```sh
mkdir -p .local/voxlock-eval
git clone https://github.com/arbazsiddiqui/voxlock.git .local/voxlock-eval/upstream
git -C .local/voxlock-eval/upstream checkout 1348686e7bbb74573daadcd7c33ea654977a501f
uv venv --python 3.12 .local/voxlock-eval/venv
uv pip sync --python .local/voxlock-eval/venv/bin/python --require-hashes \
  tools/denoise-compare/voxlock-requirements.lock
export PYTHONPATH="$PWD/.local/voxlock-eval/upstream"
model_dir=$(.local/voxlock-eval/venv/bin/python -c 'from voxlock import download; print(download("int8"))')
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 .local/voxlock-eval/venv/bin/python \
  tools/denoise-compare/voxlock_trial.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --models "$model_dir" --output .local/voxlock-eval/results

# Set the CUDA library paths as in scripts/run-asr.sh (no private environment needed).
OPENBLAS_NUM_THREADS=1 uv run --no-sync --project services/asr --with soundfile==0.13.1 \
  python tools/denoise-compare/voxlock_score.py .local/voxlock-eval/results
```

Upstream downloads are revision-pinned; the trial verifies both model hashes before
loading. It uses only the CPU ONNX backend, fresh state for each continuous stream,
80 ms chunks and two threads. The self-check verifies fixture-window separation and
both codec round-trips before inference. Detailed results are not a proof of native
real-time deadlines, caller identity, voice enrollment safety or carrier acceptance.

## Free foreground VAD: neovad

`neovad_trial.py` compares the bundled pretrained GRU primary-speech probability
with the pinned serving Silero model on identical telephone fixtures. It reuses
the codec/fixture helpers above without importing VoxLock inference. This is
an offline screening tool, not a gateway integration or denoising processor.
The Apache-2.0 upstream source includes the GRU weights; retain its attribution.
[Results and limits](../../docs/validation/neovad-2026-10-27.md).

Use Python 3.12 on the primary Linux CPU host. The lock selects CPU PyTorch;
do not install these development dependencies into any serving environment.

```sh
mkdir -p .local/neovad-eval
git clone https://github.com/NeovisionSAS/neovad.git .local/neovad-eval/upstream
git -C .local/neovad-eval/upstream checkout 3d82cbb5b787e195d437cd2047dda4c73fce7f0b
uv venv --python 3.12 .local/neovad-eval/venv
uv pip sync --python .local/neovad-eval/venv/bin/python --torch-backend cpu \
  --require-hashes tools/denoise-compare/neovad-requirements.lock
PYTHONPATH="$PWD/.local/neovad-eval/upstream/src" .local/neovad-eval/venv/bin/python \
  tools/denoise-compare/neovad_trial.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --checkpoint .local/neovad-eval/upstream/src/neovad/weights/gru.pt \
  --silero .local/turn-models/silero-v6.2.onnx \
  --output .local/neovad-eval/results-v2.json
```

The current driver contains follow-up initial-background and isolated short-phrase
controls in addition to the first 30-stream run. It refuses to overwrite an
existing output: choose a new filename for another run. It verifies hashes,
loads weights with restricted `weights_only=True`, resets each stream, and runs
codec/policy/state/streaming-parity self-checks before writing measurements.
No audio is saved by this driver. Sustained-threshold scoring deliberately omits
ASR/echo/native scheduling, so it cannot stand in for handset acceptance.

## Hush input cleaning before Silero

`hush_trial.py` keeps Silero unchanged and compares bypass with Hush's unlimited
and 20 dB attenuation settings. Shared `voice_trial.py` fixtures/scoring match the
neovad follow-up exactly. `voxlock_score.py` retains its original defaults and
can explicitly score Hush's three output profiles. The tested upstream native
binary/model bundle is pinned and hash checked; it is not a local source build.
Hush declares Apache-2.0, its native wrapper MIT and vendored DeepFilterNet dual
MIT/Apache licensing. Preserve their notices. [Evidence](../../docs/validation/hush-2026-10-27.md).

```sh
mkdir -p .local/hush-eval
git clone https://github.com/pulp-vision/Hush.git .local/hush-eval/upstream
git -C .local/hush-eval/upstream checkout 9f6414e91461a8f4bdf9840c0cdcdcb7da986339
uv venv --python 3.12 .local/hush-eval/venv
uv pip sync --python .local/hush-eval/venv/bin/python --require-hashes \
  tools/denoise-compare/hush-requirements.lock
PYTHONPATH="$PWD/.local/hush-eval/upstream/deployment/examples/python" \
  .local/hush-eval/venv/bin/python tools/denoise-compare/hush_trial.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --library .local/hush-eval/upstream/deployment/lib/libweya_nc.so \
  --model .local/hush-eval/upstream/deployment/models/advanced_dfnet16k_model_best_onnx.tar.gz \
  --silero .local/turn-models/silero-v6.2.onnx --output .local/hush-eval/results-v2

# Set the CUDA library paths as in scripts/run-asr.sh; do not load private secrets.
OPENBLAS_NUM_THREADS=1 uv run --no-sync --project services/asr --with soundfile==0.13.1 \
  python tools/denoise-compare/voxlock_score.py .local/hush-eval/results-v2 \
  --profiles bypass hush100 hush20 --expected-cases 34 --windows target_repeat
```

Use a fresh output directory; the runner refuses to overwrite results. Calibration
uses 0.001 dB because exactly 0 dB selects a separate DSP bypass. Native errors
are checked before accepting output, and reset/two-session equivalence are tested.
The filter's fixed 10 ms signal delay is removed only for paired quality scoring;
it remains a real deployment cost. The default filter failed quiet-caller retention
in this set; do not infer readiness from its fast processing or improved overlap ASR.

## Silero interruption threshold sweep (offline)

Use the existing isolated Hush evaluation environment; this script only runs
Silero and does not load the Hush native library. Reuse the hash-verified public
fixtures and preceding bypass results to enforce exact 0.50 baseline reproduction.
It evaluates 0.50/0.60/0.70 with fixed 640/160 ms timing, not ASR-assisted interruption.
Choose a new output directory for each run. No live settings are changed.

```sh
.local/hush-eval/venv/bin/python tools/denoise-compare/silero_threshold_trial.py \
  --fixtures .local/nemotron-eval/fixtures/manifest.json \
  --silero .local/turn-models/silero-v6.2.onnx \
  --baseline .local/hush-eval/results-v2/results.json \
  --output .local/silero-threshold-eval/results
```

[Results and limitations](../../docs/validation/silero-threshold-2026-10-27.md).
