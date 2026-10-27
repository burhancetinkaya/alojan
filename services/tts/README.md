# Native EMA speech worker (M2-02)

## Operator maintenance fence

`ALOJAN_WORKER_ADMISSION_FILE` opts into shared private worker admission control.
The maintenance Health Check requires closed admission, no active requests/leases,
a successful native-future completion and confirmed cleanup. EMA only confirms
quiescence after stream closure, engine-lock synchronization, CUDA synchronization
and closed scheduler/output cleanup. Cleanup failure keeps the receipt unready;
normal service health does not imply an idle GPU. No second EMA instance is started.
See the [operator sequence](../../docs/DEV_SETUP.md#dependent-worker-maintenance-fence).

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
  at most 4096 tombstones, failing closed at capacity. Managed calls clear their
  generations on explicit release/lease expiry; legacy callers retain tombstones
  until restart.
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


## Managed call transport

The shared GenerationControl requires a matching worker lease for `managed-*` calls,
including synthesis and generation cancellation. The isolated gateway setup now opens
this TTS lease before readiness and passes it through every SpeechBridge phrase;
release cancels generations and removes lease state. This uses the existing single
resident model and bounded inference/PCM queues without a per-agent worker or reload.

A lease proves access to this private worker. Managed synthesis additionally requires
Synthesis.ConfigureCall with the pinned release/digest and schema-v1 model, revision,
voice and PCM contract. The service compares this with an immutable backend capability
captured at startup; EMA exposes it only after checksum verification and CUDA graph
warm-up. Missing/unsupported/mismatched profiles fail without switching or loading a
model. Repeating the same configuration is idempotent; changing a pinned release fails.
Release/expiry removes the pin and cancels generations. Each phrase checks the existing
call pin, without DB/HTTP/manifest reads or another model instance.

Legacy calls remain compatible by default. For a future fully routed deployment,
`scripts/run-tts.sh --require-agent-release` rejects unconfigured legacy IDs too; do
not enable it on the live legacy gateway. Managed IDs always require configuration.
Upgrade the native gateway, agent, TTS and both generated bindings together. The v1
profile preserves the existing fixed seed 0 and normalization/chunking; it adds no
user tuning controls. Complete routed readiness and measured performance/quality
acceptance remain pending. Native tests use synthetic PCM, not EMA/CUDA qualification.
