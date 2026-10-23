# Linux EMA prompt validation — 2026-10-23

Tasks: M1-03 and the offline generation portion of M2-02; requirements DEC-09,
US-01 and section 8.2. Tester: Codex on the owner-authorized Ubuntu GPU server,
2026-10-23 (Europe/Istanbul), under ADR 0003 and the explicit request recorded in
[ADR 0004](../ADR/0004-ema-prompt-validation.md). Branch `codex/ema-prompts`,
uncommitted on `a59675e9806e6fbe09cb4b8c3725ec89a7a27716`, preserving prior M0/M1
work. No publication, merge, host driver change or shared service restart.

## Human feedback and scope

The owner listened to v1 and reported it unintelligible. The previous formant
fixtures therefore failed human acceptance despite passing transport fidelity.
The owner explicitly requested EMA installation on the GPU server and regeneration
of both texts. This report covers that limited real-model task; it does not mark
G1, G3 or the full M2-02 service complete. New human listening is pending.

## Installation and execution

Ubuntu 24.04.2, Python 3.12.3, NVIDIA RTX 4080 / 16,376 MiB, driver 550.120.
The initial GPU memory usage was 24 MiB. The isolated `tools/ema-prompts/.venv`
contains EMA Lightning 1.1.2, PyTorch 2.6.0+cu124, normalizer-tr 0.8.0, NumPy 2.5.4
and huggingface-hub 2.3.0. All resolved dependencies and hashes are in its own
`uv.lock`; the root development environment was not changed. Frozen installation
completed with 39 packages, after 4 minutes 30 seconds of package preparation.

Model revision `e7c96f2fc0ba843cd0f86e02786655bb56f50df8` was downloaded from the
official repository. Both checkpoint checksums match the pinned values in the
generator and manifest. EMA 1.1.2 has no public revision parameter, so a scoped
download shim passes only those verified local files to its existing CUDA loader.
Upstream checkpoint loading uses `weights_only=True`; no inference code is replaced.

One `EMA(device="cuda")` instance ran `lightning(batch_size=1)` before synthesis.
Ten CUDA graphs were compiled/recorded in 43.7 seconds; the complete warm-up took
44.073 seconds. Upstream compared the accelerated path with the plain model and
retained the graphs. The only recorded warm-up warning recommends enabling TF32
for speed; precision settings were left unchanged. No compile-fallback warning
occurred. Four CPU/compile workers limit impact on the shared host.

The GPU run's PyTorch peak allocated memory was 8,471.5 MiB and peak reserved
memory was 8,876.0 MiB, **including warm-up/compilation/autotuning**. These are not
steady-state service footprint or total driver memory measurements. After process
exit, `nvidia-smi` showed 27 MiB used. ASR coexistence has not been measured.

## Generated audio

All four files use real EMA `stream()` output at seed 0, speed 1.0. The two exact
project-authored texts are unchanged. There is no reference speaker, voice cloning,
microphone input or external inference API. EMA's own resampler handles 8 kHz
output. Final samples are PCM16 mono, padded only to 20 ms boundaries.

| File | Rate | Samples | Duration | Chunks | First chunk | Total generation |
|---|---:|---:|---:|---:|---:|---:|
| greeting-48000.wav | 48 kHz | 155,520 | 3.24 s | 2 | 5.117 ms | 7.924 ms |
| greeting.wav | 8 kHz | 25,920 | 3.24 s | 3 | 13.651 ms | 26.025 ms |
| unavailable-48000.wav | 48 kHz | 192,000 | 4.00 s | 2 | 4.289 ms | 7.181 ms |
| unavailable.wav | 8 kHz | 32,000 | 4.00 s | 3 | 6.879 ms | 17.343 ms |

Timings are four individual warm-process observations, including frontend and
chunk transfer; not latency percentiles, network timing or a service SLA. The third
8 kHz chunk includes resampler flushing. Generation checks finite values,
non-silence, no clipping and bounded duration. Hashes, RMS/peak amplitude and exact
pins accompany [the versioned assets](../../assets/prompts/tr-v2-ema/README.md).

The gateway default now selects v2's two 8 kHz WAVs. It still plays prerecorded
files and reports `voice_pipeline_ready=0`. The two 48 kHz files are optional
listening previews. V1 remains for historical provenance; its integrity test is
retained. The remote-hangup regression now derives fallback timing from the
actual greeting duration rather than assuming the old 4.78-second prompt.

The first full regression run exposed an existing playlist EOF bug: 2 speech
cases failed and 86 passed (121.53 s). The received closing audio was 80–100 ms
short. PJSIP 2.16's `wav_playlist.c` publishes EOF while filling its 4,000-byte
read-ahead buffer and can return EOF before delivering that final frame. A focused
experiment increasing the drain to 400 ms retained enough duration but still
failed both codecs' sample-fidelity checks (2 failed, 18.07 s); it was discarded.

The final implementation uses two existing single-file `AudioMediaPlayer`s, whose
EOF follows PCM consumption. The main event loop hands off to the next player;
media callbacks still only update atomic flags. The final 150 ms drain remains.
The regression compares every sample of each prompt at the same 4% RMS-error
threshold, requires a handoff gap no greater than 100 ms and rejects truncated
closing speech. Startup validation, interruption and missing-file recovery remain
in force. No upstream library patch or custom audio engine was introduced.

## Verification

Run from the Linux project root with `~/.local/bin` on PATH:

```sh
uv sync --frozen --project tools/ema-prompts
uv run --frozen --project tools/ema-prompts python tools/ema-prompts/generate.py
uv run --frozen cmake --build --preset local -j 8
uv run --frozen ctest --preset local
uv run --frozen --env-file .local/dev.env pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen clang-format --dry-run --Werror services/voice-gateway/src/*.cpp services/voice-gateway/src/*.hpp tests/identity/*.cpp tests/audio/*.cpp tests/grpc/contract_probe.cpp tests/gpu/cuda_smoke.cu
```

The default generator destination must not already exist; use `--output-dir` with
a fresh path to reproduce. Raw setup logs stay in ignored `.local/logs` on Linux.

| Check | Result |
|---|---|
| CUDA generation and waveform self-checks | Passed for both texts at both rates |
| Native build | Passed |
| CTest | 3 passed, 1.05 s |
| Focused speech / BYE / ACK / recovery regression | 6 passed, 36 deselected, 1 warning, 32.78 s |
| Full pytest with PostgreSQL | 88 passed, 1 warning, 121.87 s; no skips |
| Ruff / clang-format | Passed; 14 Python files already formatted |
| Code graph refresh | 376 nodes / 865 edges; local graph caches remain excluded |

The final suite covers 33 real SIP cases, 9 admission/identity CLI checks,
13 asset/startup checks (including both fixture generations), 4 database tests,
5 protobuf tests and 24 gRPC contract tests. Local/remote source checksum comparison
was clean after synchronization. Mac was used for editing, review and playback
file delivery; model generation, native builds and tests ran on Linux.

The HF download client emitted an unauthenticated public-download notice; no
credential was required. GPU inference itself runs locally. The current test
oracle still uses Python 3.12 `audioop`, with its known deprecation warning.

Full ASR, real-time TTS service integration, bounded cancellation/backpressure,
broader Turkish quality evaluation, carrier calls and ASR/TTS memory coexistence
remain untested. New listening feedback must be recorded separately before human
intelligibility acceptance passes. Upstream license observations and release
limitations are in [DEPENDENCIES](../DEPENDENCIES.md).

## Subsequent owner listening — 2026-10-23

After delivery, the owner accepted v2 as clearly intelligible and requested that
the introduction name Burhan Çetinkaya. This closes the pending v2 listening
review recorded above. The v2 WAV/text hashes are unchanged; its manifest now
records this acceptance. The personalized v3 generation and subsequent tests are
recorded separately in [named greeting evidence](linux-named-greeting-2026-10-23.md).
This feedback is not a carrier-call result.
