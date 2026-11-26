# Pocket CUDA autotuner interaction — 2026-10-27

Follow-up: the reviewed final image was deployed on 2026-10-28; see the
[GPU release record](pocket-gpu-release-2026-10-28.md). The candidate-only statements
below describe this earlier measurement session.

TTS-01 / M2-02 / US-01/05; ADR 0015. The owner challenged the unexpectedly slow
GPU first-frame measurements. This investigation supersedes the previous CPU
preference; it does not invalidate the recorded timings for that older configuration.

## Cause and scope

Pinned EMA 1.1.2 initialization sets `torch.backends.cudnn.benchmark=True`, which
applies process-wide. Pocket inherits it in the shared worker. The Pocket decoder
handles variable frame batches; algorithm selection was delaying the first decoded
audio. Stage timing placed prompt processing near 4 ms and GPU-to-CPU copy near
0.02–0.09 ms, while the first decoded frame waited about 110–130 ms. For multi-sentence
text, the Turkish wrapper's deliberate last-piece holdback further exposed the delay.

Sixty-six instrumented trials compared the baseline, single-frame decoder batching,
TF32, disabling autotuning, disabling cuDNN and a narrowly scoped decoder override.
Neither TF32 nor frame batching alone removed the onset penalty. The final on/off/on
trial measured the same Nazli greeting at 206.36 / 28.07 / 202.76 ms first PCM, and
796.09 / 352.76 / 778.65 ms total generation. Restoring the original setting restored
the delay, supporting the causal explanation rather than merely warm-up effects.

The fix wraps `mimi.decode_from_latent` only when Pocket is loaded on CUDA. It saves
the benchmark flag, disables it for the decode call and restores it in `finally`.
Other cuDNN flags, dtype, model/reference hashes, seed, sampler steps, queues and
CPU path are unchanged. The existing single admitted synthesis remains required.
No compilation or reduced-precision experiment was necessary after identifying the
dominant configuration interaction.

## Final service measurements

Real Linux RTX 4080, identical fixtures and RPC framing to the preceding benchmark.
The corrected candidate image is
`daa4132d0ae828c2c658e724017e60598a0c2726fff50639515424efe8538f17`.
Five repeats of three texts with both EMA and Pocket female 2: **30 timed syntheses**.
All numbers below are medians in milliseconds. CPU and old GPU columns are the
previous run; corrected GPU is the final RPC run without diagnostic instrumentation.

| Text | Pocket CPU first/total | Old Pocket GPU first/total | Corrected Pocket GPU first/total | EMA GPU first/total in corrected worker |
| --- | ---: | ---: | ---: | ---: |
| Short | 55.74 / 558.53 | 126.60 / 283.44 | 26.39 / 177.92 | 6.95 / 23.27 |
| Nazli greeting | 66.72 / 1431.01 | 226.36 / 806.85 | 32.22 / 435.38 | 8.86 / 46.16 |
| Answer | 69.02 / 1604.59 | 237.88 / 664.23 | 33.30 / 466.43 | 9.46 / 44.81 |

For the greeting, corrected GPU onset is about seven times faster than the old GPU
configuration, and total synthesis about 1.85 times faster. Compared with CPU, first
audio arrives about twice as fast and total generation is about 3.29 times faster.
EMA remains faster in this implementation. These are warm single-request results,
not end-to-end telephone latency or concurrent production capacity.

## Validation and deployment status

- **76 tests passed** in 8.65 s: Pocket audio, TTS service/configuration and maintenance.
  The new parameterized test executes the decoder on a worker thread and verifies
  original True/False settings are restored after success and exceptions, other
  flags stay intact, and input/output/error propagation is preserved.
- Actual corrected GPU RPC checks passed for EMA and all six Pocket voices, valid
  PCM framing, cancellation/reuse, lease release and return to EMA.
- Ruff, formatting, candidate container build and `git diff --check` passed.
- Candidate ran isolated with active-call monitoring and was removed afterward.
  Serving TTS image/device and number bindings were not changed. Live TTS remained
  healthy and whole-device GPU memory returned to the 4090 MiB baseline.
- No new carrier call, acoustic quality corpus, ASR contention, multi-call soak or
  P95 claim. UI/database contracts did not change and those suites were not repeated.
  The corrected source and image are ready for a separate serving-device rollout;
  live Pocket still uses CPU.

Private traces and harnesses: `.local/pocket-gpu-investigation`; final RPC measurements:
`.local/pocket-gpu-fixed`. No operational endpoint or conversation recording is stored
in these maintained results.

## Primary sources

- [PyTorch performance tuning guide](https://docs.pytorch.org/tutorials/recipes/recipes/tuning_guide):
  variable convolution shapes can make autotuner overhead counterproductive.
- [PyTorch backend controls](https://docs.pytorch.org/docs/main/backends.html):
  semantics of the cuDNN benchmark flag.
- [Pocket Turkish upstream](https://github.com/witetech/pocket-tts-turkish):
  explicit device selection and streaming interface; its advertised speed is a
  hardware-specific upstream result, not our acceptance evidence.
