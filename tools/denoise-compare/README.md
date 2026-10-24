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
