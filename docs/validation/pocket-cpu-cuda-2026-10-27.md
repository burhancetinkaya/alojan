# Pocket CPU versus CUDA — 2026-10-27

TTS-01 / M2-02 / US-01/05; ADR 0015. Owner requested GPU testing after CPU results.

Follow-up: the timings below remain accurate for the original configuration, but
the CPU preference is superseded by the [cuDNN interaction investigation and
corrected candidate](pocket-cuda-autotuner-2026-10-27.md).

## Method

Actual primary Linux RTX 4080 (16 GiB), serving TTS image
`f70f53561c65d0be3e01f53a0e0e07944ca2bbe0b3b42997335186ec6f22f9fd`.
An isolated loopback RPC container loaded EMA on CUDA and Pocket first on CUDA,
then on CPU. Same image, weights, voices, thread calibration and application
adapter; no CPU quota, 6 GiB container memory limit, one synthesis at a time.
Models and six speaker states were warm before measurement. Upstream explicit
CUDA selection moves the Pocket model to CUDA; the GPU run used real NVIDIA
execution, not a simulated producer.

First-frame time includes local RPC delivery of the first 20 ms PCM frame.
Total time is until the full stream ends, not telephone playout. Each of three
authored Turkish texts was synthesized five times with EMA and Pocket female 2
on each deployment variant: **60 measured syntheses**. Tables report medians.
Pocket uses the adapter's fixed seed; GPU and CPU output durations can still differ.

Before timing, both variants passed the existing actual-model checks for EMA and
all six Pocket voices: valid PCM frames, cancel a longer stream, reuse the call
after native cleanup, release its lease and return to EMA. No call traffic was
generated. Live active-call count was monitored; the candidate would be stopped
if an active/initializing call appeared or monitoring failed. No abort occurred.

## Measurements

| Text | Engine/device | First frame ms | Full generation ms | Audio duration ms |
| --- | --- | ---: | ---: | ---: |
| Short | EMA CUDA, Pocket CPU resident | 7.13 | 28.95 | 2120 |
| Short | EMA CUDA, Pocket CUDA resident | 7.01 | 28.28 | 2120 |
| Short | Pocket CPU | 55.74 | 558.53 | 2560 |
| Short | Pocket CUDA | 126.60 | 283.44 | 2560 |
| Nazli greeting | EMA CUDA, Pocket CPU resident | 8.87 | 35.93 | 5000 |
| Nazli greeting | EMA CUDA, Pocket CUDA resident | 8.51 | 46.40 | 5000 |
| Nazli greeting | Pocket CPU | 66.72 | 1431.01 | 6460 |
| Nazli greeting | Pocket CUDA | 226.36 | 806.85 | 6380 |
| Answer | EMA CUDA, Pocket CPU resident | 9.63 | 50.09 | 6480 |
| Answer | EMA CUDA, Pocket CUDA resident | 8.69 | 47.40 | 6480 |
| Answer | Pocket CPU | 69.02 | 1604.59 | 7040 |
| Answer | Pocket CUDA | 237.88 | 664.23 | 6960 |

Authored fixtures:

- Short: “Merhaba, size nasıl yardımcı olabilirim?”
- Nazli greeting: “Merhaba, ben Nazlı. Burhan Bey'in yapay zekâ asistanıyım.
  Size nasıl yardımcı olabilirim?”
- Answer: “Bugün ekibin geliştirme oturumlarını kontrol ettim. Kullanıcı bazındaki
  sonuçları ve toplam maliyeti sizinle paylaşabilirim.”

Whole-device GPU memory before either candidate: 4090 MiB. At readiness it was
5239 MiB with Pocket CUDA versus 4759 MiB with Pocket CPU (both include the
additional EMA CUDA instance). The difference is approximately 480 MiB at that
sampling point, not peak memory or a per-model allocator measurement. CUDA-run
post-test sample was 5263 MiB. Candidate startup, including EMA compilation and
all voice warm-ups, was 35.94 s CUDA / 35.97 s CPU. After cleanup, memory returned
to 4090 MiB and the live TTS remained healthy; pinned preparer stayed active.

## Interpretation and limits

Pocket CUDA reduced total generation time by 1.77–2.42x, but delayed the first
frame by 2.27–3.45x across these texts. Both devices produced audio faster than
playback. EMA remained substantially faster in this implementation. The measured
CUDA path is the pinned upstream model transfer, not a separately optimized CUDA
graph/compiled Pocket implementation. These results do not establish a universal
GPU disadvantage or identify the exact source of startup overhead.

Keep the current live Pocket CPU configuration for faster conversational onset.
No live device setting, image, agent draft/release, number binding or audio preview
was changed. No subjective quality, carrier call, concurrent load, ASR contention,
long soak, P95 latency or cold-query quality claim follows from five repeats.
No product source changed; application unit/browser suites were not rerun for this
benchmark. Private harness, raw measurements and logs are retained under
`.local/pocket-gpu-benchmark` and `.local/pocket-rollout/gpu-benchmark.py` on Linux.
