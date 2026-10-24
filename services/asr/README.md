# Persistent Turkish ASR (M2-01)

The native Linux worker implements `voice.v1.Recognition` and
`voice.v1.GenerationControl` using one persistent faster-whisper standard large-v3
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

The standard large-v3 pin is `Systran/faster-whisper-large-v3` at
`edaa852ec7e145841d8ffdb056a99866b5f0a478`; CUDA FP16 and beam five remain unchanged.
This model improved paired human-speech accuracy but took longer than Turbo;
see [evaluation](../../docs/validation/whisper-large-v3-2026-10-24.md).

The explicit preparation command downloads only the five files pinned in
`model.json`, then verifies every SHA-256. Model cache and virtual environment
stay under ignored `.local/asr/models` and `services/asr/.venv`. Runtime loading
is offline and verifies the hashes again. CUDA absence, missing/corrupt weights
or warm-up failure prevents readiness; there is no smaller-model or CPU fallback.
The launcher sets process-local CUDA library paths and `OPENBLAS_NUM_THREADS=1`
to avoid oversized CPU thread pools for mel features. Driver and EMA settings stay
unchanged. `--port` selects another unprivileged loopback port.

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
  The current agent follows ADR 0007: no blanket readback confirmation; clarify
  unclear content in context. ASR output alone never authenticates a caller.

## Optional exact vocabulary spelling

The launcher loads ignored `.local/asr.env` if present. Set
`ALOJAN_ASR_REPLACEMENTS` to a JSON object mapping observed misspellings to the
owner-approved spelling, for example:

```dotenv
ALOJAN_ASR_REPLACEMENTS='{"Orion akredit":"Orion Accredit"}'
```

Keep this file private (`chmod 600`); do not commit customer-specific vocabulary.
The default `{}` disables replacements. At most eight aliases fit in 2048 UTF-8
bytes; each source/target contains two to four alphabetic words separated by single
spaces, up to 80 characters. Invalid configuration prevents readiness without
logging its content. Numbers and single-word acknowledgments cannot be mapped.
Case-insensitive, whole-phrase matching preserves surrounding punctuation and
apostrophe suffixes. It does not fuzzy-match, expand partial words or cascade
replacements. Longest matching aliases take precedence. This corrects spelling
in partial/final text; it cannot recover speech the model did not recognize.
Aliases must be narrow and unambiguous; a legitimate identical phrase will also
be replaced. Readiness logs only the entry count.

Decoding keeps the original timestamp-token behavior and beam size 5. Experimental
text-only decoding and model hotwords changed a synthetic phone number, so neither
is enabled. No additional model, denoiser, VAD pass or retry is added. Noise-only
hallucinations remain a limitation; the existing gateway VAD is still necessary.
See [quality/performance evidence](../../docs/validation/asr-quality-2026-10-23.md).

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

`tools/benchmark-asr-quality.py` compares baseline decoding with the actual backend
using a private synthetic EMA manifest (file hashes, text, optional required
entities) and a private replacements JSON file. It applies G.711, noise, hum and
quiet conditions, alternates paired runs, and saves raw synthetic results only to
a new private directory. Run in the frozen ASR environment with the same CUDA
library paths as the launcher and `OPENBLAS_NUM_THREADS=1`:

```sh
python tools/benchmark-asr-quality.py --fixtures .local/evaluation/fixtures.json \
  --vocabulary-file .local/evaluation/replacements.json \
  --output .local/evaluation-new --repeats 3
```

Literal word error counts include spoken-number versus digit formatting. They
are not semantic accuracy or human-carrier acceptance. Check phone/date entities
separately with `tools/validate-asr.py` before activating a configuration.

See [Linux evidence](../../docs/validation/linux-asr-2026-10-23.md) and
[dependency inventory](../../docs/DEPENDENCIES.md) for pins, measured limitations
and pending license/distribution review.

## Optional Nemotron backend (ADR 0008)

`ALOJAN_ASR_BACKEND=whisper` (default) or `nemotron` selects the worker at startup.
Set it in the private `.local/asr.env`, alongside the existing optional spelling
aliases, or export it before `scripts/run-asr.sh --port PORT`. Invalid values fail
closed. The two backends share the existing loopback gRPC service and cancellation
policy; the launcher loads only the selected model. Changes require restarting
an idle worker. Keep the active carrier on Whisper until comparison evidence
supports promotion.

Nemotron has a separate frozen environment, `services/asr-nemotron`, because its
Transformers/Hugging Face requirements differ from faster-whisper. On Linux:

```sh
uv sync --frozen --project services/asr-nemotron
# Explicit model download; runtime itself is offline and verifies every file.
uv run --frozen --project services/asr-nemotron python - <<'PY'
import json
from huggingface_hub import snapshot_download
pin = json.load(open("services/asr/nemotron.json"))
snapshot_download(pin["repository"], revision=pin["revision"],
                  allow_patterns=list(pin["sha256"]), local_dir=".local/nemotron-model")
PY
ALOJAN_ASR_BACKEND=nemotron scripts/run-asr.sh --port 15174
```

The optional adapter uses float32 CUDA, explicit `tr-TR`, 320 ms native model
chunks and fresh encoder/decoder caches for each decode. The existing gRPC worker
still recomputes cumulative audio for each one-second partial. This is **not**
persistent incremental caching across gRPC partials, and offline decode timings
are not turn-end or handset latency. No CPU/model fallback is hidden. Readiness
requires real CUDA warm-up; exact digital silence is empty, while quiet speech
remains eligible for recognition. The final partial chunk is zero-padded to avoid
losing its last word. Native decoding retains its admission slot after RPC
cancellation until it drains, just as the Whisper path does.

Use an unused port for evaluation. Never replace an active carrier call. See
[comparison tooling](../../tools/asr-compare/README.md) and
[decision](../../docs/ADR/0008-selectable-asr.md).


## Experimental endpoint partial scheduling

The optional `AudioFrame.partial_hint` can advance the next periodic partial by
at most 400 ms without resetting its budget to the early decode time. Repeated
hints cannot multiply periodic work. Stream validation, one in-flight native
inference, cancellation and final coverage remain unchanged. A hint does not
indicate that the caller has finished; the native endpoint policy makes that
decision. Final-decode work near boundaries still needs paired measurement.
The gateway emits no hints by default. The current candidate remains unaccepted;
see [endpoint evidence](../../docs/validation/endpoint-calibration-2026-10-24.md).
