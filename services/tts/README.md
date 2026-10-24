# Native EMA speech worker (M2-02)

## Current Docker deployment

The owner-selected runtime is [Docker Compose](../../docs/DOCKER.md), under
[ADR 0011](../../docs/ADR/0011-docker-runtime.md). Use that guide for startup,
private configuration, health checks and recovery. Native commands below remain
development and rollback references; do not start a duplicate worker beside the
container using the same port or GPU model.

This worker keeps one pinned EMA instance on CUDA, compiles/warms it once, and
serves `voice.v1.Synthesis` and `GenerationControl` on **127.0.0.1:15072**. Standard
gRPC health for `voice.v1.Synthesis` becomes `SERVING` only after model checksum
verification and successful lightning graph validation. It uses the same voice,
revision and seed as the owner-accepted named greeting. No CPU/model fallback.

This implements requirements §8.2 and §10 on the authorized Linux development
host. The [M2-03 scripted gateway profile](../voice-gateway/README.md) now connects
SIP media. Turn detection and carrier/G3/barge-in acceptance remain separate.

## Run on Linux

From the repository root, with `~/.local/bin` on PATH:

```sh
uv sync --frozen --project services/tts
PYTHONPATH=services/tts:services/voice-contracts:generated/python \
  uv run --frozen --project services/tts python -m alojan_tts.model
scripts/run-tts.sh
```

The explicit model command downloads the pinned revision and verifies all three
files. Normal worker startup uses only that cache, under ignored `.local/ema/`.
The existing offline prompt tool shares the weights and compilation cache; do
not run two EMA instances simultaneously on the development GPU. ASR uses its
separate environment and may stay resident. `--port` changes only the loopback
port. SIGTERM/SIGINT stop readiness and cancel active work.

This is a foreground development worker; keep it running in a supervised session
or redirect it with `nohup`. It survives individual RPCs, not a machine reboot.
Production process supervision, containers and call lifecycle cleanup remain open.

## Streaming and limits

- Each request supplies fresh opaque call/generation IDs, a deadline and a complete
  Turkish phrase. Maximum 512 characters; empty/punctuation-only text and unsafe
  control characters are rejected. The pinned frontend normalizes numbers, dates,
  times, currency and supported foreign names. Normalized output must contain at
  most 2048 model letters across at most 16 pieces. No text is logged by the worker.
- Exactly one stream is admitted. Busy requests fail `RESOURCE_EXHAUSTED` without
  enqueuing another inference. The service rejects used/cancelled IDs and retains
  at most 4096 tombstones until restart, failing closed at capacity. A future call
  release contract must replace this bounded development limitation.
- The fixed transport profile is **8 kHz, mono, PCM16 little endian**, sequence zero
  onward, 160 samples / 20 ms per frame. EMA generates float32 native 48 kHz and
  uses its own stateful low-pass resampler for direct 8 kHz streaming. PCM rounds
  `float * 32767`; chunks must be finite and normalized. Remainders carry across
  model chunks; only the last frame is zero-padded (less than 20 ms).
- At most eight PCM frames wait in the application queue (160 ms), plus one frame
  awaiting write and one bounded model chunk. A write blocked for 200 ms fails
  `RESOURCE_EXHAUSTED`. gRPC/network buffers are separate; slow-reader detection
  starts when transport flow control actually blocks a write.
- EMA 1.1.2 internally uses an unbounded `SimpleQueue`. A version-specific adapter
  replaces each request outbox with one cancellable queue slot and preserves the
  original scheduler, normalization, inference and resampling. At most one decoded
  window waits there, plus the scheduler's in-flight window. Public factory hooks
  should replace this small private-API adapter when upstream provides them.
- Model chunks are capped at five seconds and output at 30 seconds. Exceeding a
  limit fails the stream, even if earlier audio was delivered; it never reports a
  truncated utterance as successful. Full text planning precedes the first chunk;
  this is a short-phrase development profile, not unbounded document synthesis.
- Explicit cancellation, deadline expiry and client disconnect stop delivery and
  close the model iterator. Closing cancels the EMA request and releases blocked
  outbox puts. The admission slot remains occupied until the native stage, CUDA
  synchronization and scheduler cleanup finish. This does **not** preempt a running
  GPU kernel. A fresh request can receive busy until cleanup completes.
- Native/normalizer errors are sanitized. Invalid normalized text is
  `INVALID_ARGUMENT`; malformed model PCM/native failures are `INTERNAL`.
  Successful stream EOF is the completion signal; capture timestamps are zero
  because synthesized samples have no microphone capture time. RTP pacing and
  sent-audio accounting belong to the gateway, not this worker.

Cancellation cannot retract bytes already in gRPC buffers. Consumers must compare
current generation before playout and flush stale audio. The shared ASR/TTS
cancellation helper checks invalidation before scheduling another read/write;
active operations are raced against cancellation.

## Verification

```sh
uv run --frozen pytest -q tests/test_tts.py tests/test_asr.py
# Requires both real loopback workers; creates only synthetic evaluation audio.
PYTHONPATH=services/voice-contracts:generated/python \
  uv run --frozen --project services/tts python tools/validate-speech.py \
  --output .local/speech-evidence-new
# Stop the TTS worker first; this calibration loads one EMA itself. ASR can remain.
PYTHONPATH=services/tts:services/voice-contracts:generated/python \
  uv run --frozen --project services/tts python tools/validate-ema-rates.py \
  --output .local/ema-rates-new.json
```

Contract tests use a fake PCM producer over real gRPC, never simulated model
readiness. The live check runs six synthetic TTS requests alongside real ASR,
then ASR-transcribes each synthesized result, checks active cancellation and
recovery, and samples total GPU memory every 100 ms. RPC overlap proves concurrent
service work, not exact kernel overlap. Recognition text is diagnostic rather than
a pronunciation oracle or normalized WER acceptance test. Review the
[Linux report](../../docs/validation/linux-tts-2026-10-23.md) for measured limits,
normalization findings and remaining listening/quality work.
