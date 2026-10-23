# Persistent Turkish ASR (M2-01)

The native Linux worker implements `voice.v1.Recognition` and
`voice.v1.GenerationControl` using one persistent faster-whisper large-v3-turbo
model on CUDA float16. It binds only `127.0.0.1:15071`. The [M2-03 scripted
gateway profile](../voice-gateway/README.md) now supplies live loopback media.
Turn detection, caller recording, transcript storage and external APIs remain
outside this service. M3 decides when to end a caller turn.

## Setup and run

From `~/ai/alojan` on the authorized Ubuntu GPU host:

```sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --frozen --project services/asr
PYTHONPATH=services/asr uv run --frozen --project services/asr python -m alojan_asr.model
scripts/run-asr.sh
```

The explicit preparation command downloads only the five files pinned in
`model.json`, then verifies every SHA-256. Model cache and virtual environment
stay under ignored `.local/asr/models` and `services/asr/.venv`. Runtime loading
is offline and verifies the hashes again. CUDA absence, missing/corrupt weights
or warm-up failure prevents readiness; there is no smaller-model or CPU fallback.
The launcher sets process-local CUDA library paths, leaving the driver and EMA
installation unchanged. `--port` selects another unprivileged loopback port.

After real model loading and a decoder warm-up, the process logs `event=asr_ready`.
The standard gRPC health service reports `SERVING` for `voice.v1.Recognition`.
It reports model readiness, not gateway/agent readiness or available admission slots.
SIGINT/SIGTERM marks health non-serving, invalidates active generations and drains
gRPC for up to two seconds. The current native decode may still finish before the
Python process exits; this is not a hard GPU-kernel termination guarantee.

The worker is a foreground process suitable for the current native development
profile. The development instance can remain running between calls; automatic
restart after host reboot and production supervision are separate deployment work.

## Recognition contract

- Supply a deadline and opaque `call_id` / `generation_id` on every stream.
  IDs and frames use the existing shared validator: monotonically increasing
  sequence from zero, finite normalized floats, mono PCM and at most 20 ms/frame.
- This service accepts **16 kHz only**, either `pcm_s16le` or `pcm_f32le`.
  Resample decoded telephony audio before submitting it. This narrows the endpoint's
  accepted input profile without changing the versioned protobuf fields.
- Every additional second of accepted input produces a replacement hypothesis for
  the entire buffered turn. It is application-managed repeated decoding, not native
  incremental Whisper streaming. A partial is revisable text, never an append-only
  delta or permission to start the assistant's answer.
- Half-close explicitly finalizes the turn and returns exactly one `is_final`
  event. If the last partial already covers all samples, its text is reused.
  Empty streams are invalid; exact all-zero PCM returns empty text, including final.
  Quiet nonzero speech is retained. General noise/hallucination detection remains
  unvalidated and belongs with VAD/turn integration, not a guessed RMS threshold.
- Decoding is Turkish transcription, temperature 0, beam size 5, no cross-turn
  text context, no model VAD and at most 440 generated tokens per decode. Names may
  differ in spelling/word boundaries; numbers and dates can be emitted as digits.
  The caller-confirmation policy remains essential in subsequent agent work.

## Bounds, cancellation and errors

One recognition stream owns admission. There is one native inference worker and
no application inference queue. Input is pull-based: reads pause during inference,
so gRPC flow control backpressures the sender. The cumulative turn buffer is capped
at 30 seconds (960,000 PCM16 bytes or 1,920,000 float32 bytes); crossing the bound
returns `RESOURCE_EXHAUSTED`, never a silently truncated final. A caller must not
split a sentence merely to bypass this limit; longer-turn policy needs integration
validation. Copies used for decoding are likewise bounded.

Explicit cancellation is idempotent, including before a stream starts. It wakes
idle reads, waits on inference and output writes. Before emission the generation
is checked again. Transport cancellation/deadline expiration closes the stream and
its generation cannot be reused. CTranslate2's native decode cannot be preempted:
its result is discarded and its capacity remains reserved until it actually
returns. New streams receive `RESOURCE_EXHAUSTED` during that interval, preventing
an unbounded executor queue or overlapping CUDA decodes. Already buffered network
events cannot be retracted; clients must discard cancelled generation IDs.

Application output has no queue and each write has a one-second stall budget;
slow consumers receive `RESOURCE_EXHAUSTED`. Messages are capped at 16 KiB, text
at 8 KiB, transport concurrency at 16 RPCs and generation records at 4096.
Tombstones are not evicted: a full registry rejects new keys until a controlled
restart with fresh client IDs. This temporary bound follows the existing contract;
call-release lifecycle integration is still needed before long-running production.

Invalid streams return `INVALID_ARGUMENT`; explicit cancellation returns
`CANCELLED`; other reused identities return `ALREADY_EXISTS`. Decoder failures
return sanitized `INTERNAL`, without model exception text, caller audio or transcript.
A new generation can retry; no hidden model substitution or automatic request replay
occurs. Do not expose this unauthenticated loopback service publicly.

## Validation

```sh
uv run --frozen pytest tests/test_asr.py -q
PYTHONPATH=generated/python uv run --frozen --project services/asr \
  python tools/validate-asr.py --output .local/asr-evidence-new.json
```

The first command uses real gRPC with an explicitly fake decoder to test lifecycle,
input validation, revisions, cancellation, capacity and failure recovery. It runs
in ordinary CPU CI without model packages. The second requires the running real
CUDA service and uses only repository synthetic speech and digital silence.
Choose a fresh output file. It checks fixture hashes, entity matches, empty silence,
partial/final output, cancellation and recovery, and samples host GPU memory.
Its unpaced upload times are **not** SIP turn-end latency, phone intelligibility,
noise WER, a 50-turn percentile benchmark or concurrent EMA acceptance.

See [Linux evidence](../../docs/validation/linux-asr-2026-10-23.md) and
[dependency inventory](../../docs/DEPENDENCIES.md) for pins, measured limitations
and pending license/distribution review.
