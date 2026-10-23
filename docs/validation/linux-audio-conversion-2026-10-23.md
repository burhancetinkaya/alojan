# Linux audio conversion validation — 2026-10-23

Tasks: M1-02 and M1-05 regression coverage; requirements US-01, sections 5–7 and
15.1. Gate: G1-Ubuntu supporting evidence. Tester: Codex under ADR 0003;
2026-10-23, Europe/Istanbul. Source: `codex/audio-conversion`, uncommitted on
baseline `a59675e9806e6fbe09cb4b8c3725ec89a7a27716`, preserving prior M0/M1 work.
Execution: `~/ai/alojan`, Ubuntu 24.04.2 x86_64, GCC 13.3.0, Python 3.12.3,
PJSIP 2.16 and frozen project tools. Mac was used for editing/review only.
No push, PR, merge, release, model inference or new GPU validation occurred.

## Resulting behavior

The per-call receive port now requests mono PCM16 at 16 kHz, with 320 samples per
20 ms frame. The existing PJMEDIA conference bridge resamples negotiated 8 kHz
PCMA/PCMU audio using its large filter; media quality is explicitly set to 8.
The conference and outbound WAV/RTP clocks remain 8 kHz. No new audio dependency,
custom DSP implementation or inference consumer was introduced.

The receive callback counts samples and malformed frames without storing audio or
performing blocking IO. Invalid types/sizes do not enter the sample count. Safe
closure diagnostics include `input_rate_hz`, `input_frames`, `input_samples` and
`input_bad_frames`. The six real SIP transport/impairment scenarios assert 16 kHz,
at least 100 accepted frames, zero malformed frames and exactly 320 samples per
accepted frame, while retaining playback pacing and RTCP impairment assertions.

## Native numerical evidence

The new `audio-conversion` CTest exercises the pinned PJMEDIA implementation:

- 44 fixed encode/decode reference checks, independently obtained from CPython
  3.12.3 `audioop`; 512 codeword roundtrips across both codecs. Mu-law negative
  zero is explicitly canonicalized to positive zero.
- All 65,536 signed PCM16 inputs through both codecs: maximum absolute roundtrip
  error 515 for A-law and 644 for mu-law, in PCM sample units.
- Fifty 20 ms frames in each direction: 8→16 kHz produces 16,000 samples and
  16→8 kHz produces 8,000 samples, each representing one second.
- At a 1 kHz input tone with amplitude 12,000, fitted output amplitude is
  12,000.3 / 12,000.8 and residual RMS is 0.993275 / 0.309547 respectively.
  Thresholds are amplitude 11,800–12,200 and residual RMS below 30 after 40 ms
  startup settling. Phase is fitted to allow the actual filter delay.
- Downsampling a 6 kHz tone at 16 kHz gives RMS 2.5 after settling, below the 85
  anti-alias threshold. Guard samples around output buffers remain intact.
- An impulse on a frame boundary carries its filter tail into the next frame and
  drains to silence. Interleaved silent contexts remain silent; recreated contexts
  reproduce output without inheriting prior-call history.

The initial test used audioop's A-law maximum-error bound of 512 and failed against
PJSIP with 515. Inspection of PJSIP 2.16's table-based codec implementation showed
14-bit lookup indices and different negative encoding boundaries. The test now
records a bound of 515 for this pinned implementation; the independent fixed
vectors all match. This is regression evidence, not a claim of exhaustive bitwise
agreement with audioop or formal ITU conformance. No codec implementation was changed.

## Commands and results

Run from the Linux project root with `~/.local/bin` on PATH:

```sh
uv run --frozen cmake --preset local
uv run --frozen cmake --build --preset local -j 8
build/local/audio-conversion-test
uv run --frozen pytest tests/sip-integration/test_sip.py -q -k two_way_rtp --tb=short
uv run --frozen ctest --preset local
uv run --frozen --env-file .local/dev.env pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen clang-format --dry-run --Werror services/voice-gateway/src/*.cpp services/voice-gateway/src/*.hpp tests/identity/*.cpp tests/audio/*.cpp tests/grpc/contract_probe.cpp tests/gpu/cuda_smoke.cu
```

| Check | Observed result |
|---|---|
| Frozen CMake configure/build | Passed |
| Final CTest | 3/3 passed, 1.05 s; no skips |
| Focused real SIP conversion/impairment | 6 passed, 36 deselected, 1 warning, 28.73 s |
| Full pytest with configured PostgreSQL | 87 passed, 1 warning, 131.72 s; no skips |
| Ruff and clang-format | Passed; 13 Python files already formatted |
| Code graph refresh | 374 nodes / 861 edges; local caches excluded from sync |

The full pytest run includes 33 real SIP cases, 9 admission/identity CLI checks,
12 prompt/startup checks, 4 database tests, 5 protobuf tests and 24 gRPC contract
tests. Closure, isolation, speech and recovery regressions all remained green.

The warning is the existing Python 3.12 `audioop` deprecation in the SIP test
oracle; no runtime dependency was added. CMake shares existing PJPROJECT flags
through an interface target so the audio test does not depend on caller-identity
code. CI formatting includes the new C++ test; hosted CI was not executed.

## Remaining acceptance

The owner answered on 2026-10-23 that the spoken greeting has not yet been listened
to. Human Turkish intelligibility review remains pending; G1 is not marked complete,
and M2–M5 were not started. Real ASR/EMA, streaming model-input finalization,
24/48 kHz TTS conversion, GPU model coexistence and live carrier acceptance remain
separate work. Filter delay/tail tests do not prove end-to-end inference latency or
handset intelligibility. Raw audio recording remains disabled.

Sources and sanitized evidence are synchronized to the authorized Linux workspace;
secrets, virtual environments, compiled binaries and graph caches remain host-local.
