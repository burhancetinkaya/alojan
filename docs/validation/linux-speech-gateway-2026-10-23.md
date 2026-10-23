# Linux native speech gateway — 2026-10-23

Task **M2-03**, requirements §3 and §10, supporting the speech portion of G3
and the §7.4 cancellation boundary. Work ran on `codex/speech-gateway` over the
existing uncommitted foundation (base `a59675e`). Source review ran on Mac;
all builds, tests and inference below ran on the authorized Ubuntu 24.04 host
in `~/ai/alojan`. No publication, schema change or new dependency was introduced.
Validation date: 2026-10-23, Europe/Istanbul (UTC+03:00).

## Result and boundary

The native gateway connects real SIP/RTP to the resident ASR and EMA workers.
An explicit development flag enables a scripted capture window after the approved
AI greeting. ASR receives actual PJMEDIA 16 kHz PCM, emits partials and finalizes
on half-close. EMA then generates the fixed unavailable/closing message, which
is played at 8 kHz through the negotiated G.711 codec before BYE.

This is a synthetic local integration test, not a conversational assistant.
The default WAV fallback remains available and `voice_pipeline_ready=0` remains
accurate. M3 owns turn detection and interruption policy; M4 owns agent responses.
G2/carrier and full G3 acceptance remain open. Native Linux M2-03 completion
permits M3 development under ADR 0003 without claiming those external gates.

## Implementation and checks

- One bridge, bounded PCM queues and cancellable RPC contexts per call/generation.
  Input is 64 × 640 bytes; output is 32 × 320 bytes. PJMEDIA callbacks do no
  network/model work. Background readers consume ASR partials while writing input.
- The native output port reuses PJMEDIA's provided buffer and group-lock teardown
  convention. Ports detach before the bridge is destroyed. Hangup invalidates
  queued delivery immediately; background cancellation reaches both workers.
- ASR has capture duration plus five seconds, capped by the parent call deadline.
  TTS inherits the parent deadline. Two separate 150 ms control cleanup budgets
  do not extend inference time. Output stall beyond 250 ms fails closed.
- IDs, sequence, PCM format/size, final ordering and message/duration bounds are
  checked. Failures stop generated playback and use the approved local fallback.
  Final playout completion also waits for the last consumed frame to be accounted.
- Logs contain local IDs, counts and timings, not recognized text or raw caller
  audio. `output_port_ms` is PCM delivered to the conference bridge, not handset
  playback or production sent-transcript alignment.

The 20 added pytest cases use **explicit fake inference over real native
SIP/RTP/gRPC**. They cover both codecs, exact capture/finalization, paced playout,
ASR failure/empty/premature final, TTS failure/stale ID/sequence/format, BYE during
capture and output with cancellation/reuse, worker disappearance, bounded
shutdown, input option validation, stopped output consumption, ASR deadline,
two-call capacity isolation and the full-audio alignment regression. A fifth
CTest checks queue overflow rejection, FIFO order and 100,000 concurrent
wraparounds. These transport tests are separate from real CUDA evidence below.

| Check | Outcome |
|---|---|
| Final native build | Passed, seven incremental build/link steps |
| CTest | **5/5 passed**, 2.06 s |
| Full pytest with isolated development DB | **151 passed, no skips**, 273.50 s; one known Python 3.12 `audioop` deprecation warning |
| Ruff | Lint passed; 32 Python files formatted |
| clang-format | All six changed native source/header/test files passed after formatting two queue-test lines |
| Review | Task diff reviewed; 20 changed/new files checked for whitespace and local document links, zero issues |
| Graph | Refreshed after code changes: 1,705 nodes / 3,869 edges; no shared graph artifact |

Final gateway executable SHA-256:
`a55970252508c890d9532eeaa0c9a1c41b8a7c19dc45e9d1572b5f95af4205be`.
This identifies the Linux binary tested over the uncommitted source snapshot;
the baseline Git revision alone does not identify these new files.

## Real CUDA SIP/RTP evidence

The existing pinned faster-whisper float16 and EMA workers remained resident on
the RTX 4080 (16,376 MiB; driver 550.120/CUDA 12.4). Their models/revisions did not
change; see the [ASR](linux-asr-2026-10-23.md) and
[TTS](linux-tts-2026-10-23.md) reports. Two calls use the checksum-verified synthetic
phone fixture and the accepted named greeting/closing reference. No real caller
recording or transcript is stored.

Each call captures seven seconds: 350 PCM frames, seven ASR partials and a
nonempty final. EMA returns 200 frames/four seconds of closing audio. Received
RTP is checked for 160-sample timestamp steps, mean 20 ms pacing and complete
reference audio within 4% relative RMS error after G.711 quantization. The full
waveform comparison detects missing internal audio, independently of counters.

Final run, `.local/gateway-speech-final/`:

| Codec | ASR frames / partials | EMA frames / output-port duration | Half-close → first PCM | Half-close → first output-port PCM | RTP packets / mean spacing | Closing relative RMS error |
|---|---:|---:|---:|---:|---:|---:|
| PCMA | 350 / 7 | 200 / 4,000 ms | 148 ms | 159 ms | 720 / 20.0008 ms | 1.3384% |
| PCMU | 350 / 7 | 200 / 4,000 ms | 140 ms | 159 ms | 720 / 20.0003 ms | 1.4022% |

Both cases passed without fallback or input framing errors. The measured host
GPU peak was **3,008 MiB**. Final ASR and EMA health checks reported `SERVING`;
both existing workers were left running. The models were already warm, so this
run does not repeat or supersede the earlier warm-up memory measurement.

The latency starts at scripted ASR half-close and ends at first returned PCM or
first PCM handed to the PJMEDIA port. It excludes the seven-second capture,
turn detection and GPT; it is not caller-turn-end-to-handset latency or a P95.
GPU memory is sampled host-wide every 100 ms, not a guaranteed maximum or soak.

## Failures found and corrected

1. The first real-model run failed reference alignment: short-window matching
   selected preceding silence. Independent direct EMA output matched the approved
   PCM exactly. Matching the complete reference at RTP frame boundaries corrected
   the measurement. A regression also removes one internal frame and requires
   large error, so missing audio is still rejected. The earlier failed result is
   retained under ignored `.local/gateway-speech-01/`.
2. A hostile test ASR sent a final before client half-close. The regression failed
   before the guard (the client incorrectly synthesized a response), then passed
   after rejecting early finals. The initial 15 integration cases had passed;
   this additional case exposed a distinct protocol ordering gap.
3. An initial full run reported **145 passed / 6 failed** in 273.24 s. The six
   existing receive-counter tests matched `input_frames` inside the new
   `speech_input_frames` field. A word boundary corrected the parser; no PCM
   assertion, packet threshold or runtime input accounting was weakened.

## Reproduction and remaining work

See [gateway setup](../../services/voice-gateway/README.md). From the Linux root:

```sh
uv run --frozen cmake --build --preset local -j 4
uv run --frozen ctest --preset local
uv run --frozen --env-file .local/dev.env pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python tools/validate-gateway-speech.py \
  --output .local/gateway-speech-new
```

The real validator requires both warmed workers on their standard loopback ports.
Raw test evidence remains ignored: `.local/gateway-speech-01/`,
`.local/gateway-speech-02/` and `.local/gateway-speech-final/`. The validation
tool writes only repository-derived synthetic received audio.

The next task is **M3-01**, Silero/Smart Turn and adaptive turn-end decisions.
GPT responses, production sent-audio/transcript alignment, barge-in policy,
carrier audio, broader Turkish/noisy-speech quality, reboot supervision,
production containers, long-duration soak, remote CI and clang-tidy remain open.
The previous number/punctuation quality limitations are unchanged. One admitted
call is still the default; two-call isolation does not establish production
two-call inference capacity. Mac build/runtime was not revalidated.
