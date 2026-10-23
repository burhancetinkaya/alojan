# Linux spoken fallback validation — 2026-10-23

Tasks: M1-03 and M1-05 regression coverage; requirements US-01, sections 6/8.2/14.
Gate: G1-Ubuntu supporting evidence. Tester: Codex under ADR 0003; date/timezone:
2026-10-23, Europe/Istanbul. Source: `codex/spoken-fallback`, uncommitted on baseline
`a59675e9806e6fbe09cb4b8c3725ec89a7a27716`, retaining the existing M0/M1 work.
No push, PR, merge or release. Execution: `~/ai/alojan`, Ubuntu 24.04.2 x86_64,
GCC 13.3.0, Python 3.12.3, PJSIP 2.16 and the frozen project toolchain. Mac was used
for editing/source review only. GPU and production speech models were not exercised.

## Resulting behavior

Without `--wav`, the native loopback gateway now plays the versioned Turkish AI
introduction followed by an unavailable-service/closing announcement, because no
speech/agent pipeline is implemented yet. It reports `voice_pipeline_ready=0` and
ends with `dependencies_unavailable` only after playlist EOF and the 150 ms drain.
No request to leave a message or false message-storage promise is made. `--wav`
retains the explicit transport-test profile; `--prompt-dir` selects the two named
prompt files. The two modes cannot be combined.

PJSIP's existing playlist handles sequence/pacing. Playback waits for confirmed ACK;
PJMEDIA may still send pre-ACK keepalive or silence. Remote BYE, RTP inactivity,
maximum duration and shutdown take priority. Failure to open the files for a call
ends that call with `playback_error`, without taking down the gateway. The runtime
expects immutable prompt assets; do not modify files while serving calls.

Startup validates the complete RIFF/chunk envelope, then uses PJSIP to check mono
PCM16/8 kHz format and duration. This extra completeness check is necessary because
PJSIP 2.16 intentionally tolerates truncated payloads. Invalid/missing files and an
insufficient call-duration budget fail before SIP binding/readiness.

## Speech provenance

Original Turkish text and synthetic WAVs are in
[assets/prompts/tr-v1](../../assets/prompts/tr-v1/README.md). Introduction: 38240
samples / 4780 ms; unavailable/closing: 52640 samples / 6580 ms; total 11360 ms.
These are formant test fixtures, not neural EMA output or a human recording.
Human Turkish listening/intelligibility review remains unperformed.

The Ubuntu eSpeak NG package `1.51+dfsg-12build1` was downloaded using the host's
APT metadata and extracted per-project, with its SHA-256 matching the recorded
pin. Existing library/data packages were reused. No system package, service,
firewall or Docker setting changed. The generator checks executable checksum and
library/data versions. Two independent generations produced byte-identical WAVs
and manifests. Upstream license/source and release limitations are recorded with
the fixtures; no project license or redistribution clearance is asserted.

## Tests and commands

Run from the Linux project root with `~/.local/bin` on PATH:

```sh
uv run --frozen cmake --build --preset local -j 8
uv run --frozen ctest --preset local
uv run --frozen pytest tests/test_prompts.py tests/sip-integration/test_sip.py -q \
  -k 'speech or spoken or prompt or playback_modes or remote_bye_stops' --tb=short
uv run --frozen pytest tests/test_prompts.py -q --tb=short
uv run --frozen --env-file .local/dev.env pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen clang-format --dry-run --Werror services/voice-gateway/src/*.cpp services/voice-gateway/src/*.hpp tests/identity/*.cpp tests/grpc/contract_probe.cpp tests/gpu/cuda_smoke.cu
```

| Check | Observed result |
|---|---|
| Frozen native build | Passed |
| Final CTest | 2/2 passed, 1.03 s; no skips |
| Focused speech/SIP run before the two truncation regressions were added | 16 passed, 36 deselected, 1 warning, 49.58 s |
| Final fixture/configuration/truncation tests | 12 passed, 9.20 s |
| Full pytest with configured PostgreSQL | 87 passed, 1 warning, 131.82 s; no skips |
| Ruff lint / format | Passed; 13 Python files formatted |
| clang-format | Passed for all configured C++/CUDA sources |
| Fixture reproduction | Both WAVs and manifest byte-identical to a second generation |

The full suite comprises 33 real loopback SIP/media/lifecycle/identity/speech cases,
9 admission/identity CLI cases, 12 fixture/startup cases, 4 DB tests, 5 protobuf tests
and 24 gRPC tests. The known warning is Python 3.12's `audioop` deprecation; both the
test decoder and offline fixture resampler must change before Python 3.13.

Speech checks decode actual PCMA/PCMU RTP and compare every sample of both prompts
with the source after startup alignment. Each prompt's RMS error must be below 4%
of reference RMS; both codecs passed. They also check 160-sample timestamp steps,
full expected sample coverage and a playback duration between 11.36 and 13.36 s.
This is transport fidelity, not human recognition or naturalness scoring.

Remote BYE is tested during introduction (0.4 s) and fallback (5.4 s), allowing at
most one in-flight frame after acknowledgement/queue drain, followed by successful
slot reuse. A disappearing fallback file produces bounded teardown while keeping
the process alive; restoring it permits the next call. Delayed ACK emits no prompt
speech. Startup tests cover missing/corrupt/truncated files, inconsistent chunk
length, stereo, wrong rate/bit depth, empty/overlong audio and an insufficient call
budget, plus mutually exclusive configuration and provenance hashes.

## Failures investigated

The first focused run had 13 passes and one failed assertion expecting no pre-ACK
RTP. PJMEDIA sends silence/keepalive independently of prompt playback. The test now
checks absence of speech samples and `media_started` until ACK, and passes.

Two added regressions initially failed by timeout: a truncated file and a declared
data length beyond the file were accepted by PJSIP. Source inspection confirmed its
intentional truncation tolerance. The new RIFF/chunk bounds check rejects both;
the final fixture suite and full suite pass. Sanitized full-suite output is retained
at `.local/logs/spoken-fallback-full.log`; focused output is under the same ignored
logs directory. No private capture or caller recording was saved.

## Remaining acceptance

M1-03 automated playback/failure behavior is implemented. Human listening review,
EMA-generated replacement prompts and distribution approval remain separate. G1
is still partial: explicit codec known vectors and runtime resampling checks remain
before M2–M5. Persistent caller identity/DB correlation, carrier/NAT calls, ASR/TTS,
API integration, Mac revalidation, hosted CI and clang-tidy were not validated in
this task. None of the tone/formant/contract results count as live model readiness.
