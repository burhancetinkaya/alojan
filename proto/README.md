# Voice contract baseline

Performance follow-up: agent text events may include `detail_json.kind` as
`response` or `waiting`; omission means `response` for older producers. The native
consumer rejects other values. This additive metadata separates waiting audio
from substantive latency without changing protobuf fields. See the
[measurement contract](../docs/validation/performance-review-2026-10-23.md#measurement-contract).
The later owner-selected waiting music is generated locally in the gateway and
uses no agent event or speech receipt. Current agents emit only `response`; the
`waiting` metadata remains accepted for compatibility with earlier producers.

`voice.v1` preserves the original core field numbers. Recognition is bidirectional;
synthesis and agent turns stream responses; cancellation is unary and scoped to
`(call_id, generation_id)`. IDs are opaque ASCII letters, digits, underscores or
hyphens, 1–64 characters. Do not use phone numbers or private text as identifiers.

Build the pinned native toolchain with `scripts/build-grpc.sh`, then regenerate
both tracked binding sets with `scripts/generate-proto.sh`. Native gRPC is 1.78.0
with its own pinned protobuf 6.31.1 / protoc 31.1. Python grpcio-tools 1.78.0 uses
its bundled generator and the locked protobuf 6.33.5 runtime. Native generated
code must use its matching native runtime, not an arbitrary system installation.

## Stream ownership and bounds

- Each stream belongs to one call/generation and one fixed sample rate/format.
  Audio is mono `pcm_s16le` or normalized finite `pcm_f32le`, at 8/16/24/48 kHz.
  Frames contain nonempty sample-aligned PCM, at most 20 ms;
  sequence numbers start at zero and increment by one. Capture timestamps cannot
  be negative. No compressed codecs belong inside this contract.
- Recognition half-close finalizes the turn and returns one `is_final` event.
  Empty streams, switched identities/formats, malformed PCM or invalid sequences
  return `INVALID_ARGUMENT`. Transport messages are capped at 16 KiB.
- Every streaming caller supplies a deadline; downstream work must use the
  remaining deadline, never restart its budget. Transport cancellation/expiry
  stops per-stream work. Explicit generation cancellation invalidates all work
  for that identity; it is idempotent, including before a stream starts.
- Reusing any already-started generation in the same service is rejected;
  cancelled generations return `CANCELLED`, other duplicates `ALREADY_EXISTS`.
  Different calls can use the same generation ID without sharing state.
- Before playback or emitting output, consumers must compare the current
  generation. Cancellation cannot retract bytes already in gRPC/network buffers.
  The gateway will own generation invalidation and fan cancellation out to each
  active service. That production integration remains M2/M3 work.
- Bound application queues independently of gRPC flow control. The test synthesis
  peer uses an eight-frame queue and a 200 ms write-stall budget; a slow consumer
  stops the producer and receives `RESOURCE_EXHAUSTED`. Recognition is pull-based,
  holding one frame, and the native probe permits one frame in flight. No blocking
  transport operation may run in a PJMEDIA callback.

## Evidence and limits

`tests/support/contract_server.py` is an explicit test peer, not ASR/TTS/agent
inference. Recognition returns PCM as hex text solely to prove byte integrity.
Synthesis produces a deterministic binary fixture. Tests exercise the real gRPC
transport using native C++ and Python clients, including idle-stream cancellation,
deadline expiry, stale output, call isolation, malformed frames and slow consumers.

The peer limits concurrent RPCs to 32 and retains at most 4096 generation records
until test-server shutdown, rejecting new identities when full. This intentionally
fails closed rather than evicting cancellation tombstones. Production services
need call lifecycle cleanup and fresh IDs after restart; the test registry is not
a persistent cancellation store. The agent RPC is defined/generated but has no
runtime implementation yet. Neither the test peer nor generated clients establish
model readiness, gateway-to-inference integration or production latency.

## M2-01 recognition implementation

The [native ASR worker](../services/asr/README.md) now implements the unchanged
recognition/control RPCs with pinned faster-whisper CUDA inference. Its endpoint
requires 16 kHz input, replaces the full partial hypothesis after each second,
and finalizes on half-close. It admits one stream, caps each turn at 30 seconds,
retains cancellation/duplicate tombstones and rejects overload. Native decoding
may finish after cancellation, but cannot emit cancelled output or admit another
decode until capacity is released. Full limits and error semantics are in its
README. The explicit hex-echo test peer remains solely a contract fixture; the
native C++ gateway now consumes ASR through the explicit M2-03 scripted profile.

## M2-02 synthesis implementation

The [native EMA worker](../services/tts/README.md) implements the existing synthesis
and cancellation messages without changing field numbers. Its fixed output is
8 kHz mono PCM16 in numbered 20 ms frames, with only the last frame zero-padded.
A successful EOF means the phrase completed; any failure after partial delivery
must remain a failed stream. One active stream, eight queued frames, one bounded
EMA outbox window, 512 input characters and 30 seconds of output bound development
work. Explicit invalidation, deadlines and disconnects stop further delivery;
native kernel cleanup may keep the worker busy briefly. RTP pacing, downstream
queue flush and sent-audio accounting remain gateway responsibilities in M2-03/M3.


## M2-03 native gateway consumer

The [gateway](../services/voice-gateway/README.md) now consumes these contracts
without a schema change. The scripted test half-closes ASR at an explicitly
configured synthetic capture boundary, requires a valid final and requests a
fixed EMA response. Incoming PCM is 16 kHz; playback PCM is 8 kHz. Identity,
sequence, final ordering and message/duration bounds are checked before output.
Per-call cancellation invalidates local queues and stops active RPCs; control
cancellation is best effort with bounded cleanup deadlines. Pacing occurs in
PJMEDIA. This is not M3 turn/interrupt policy or M4 agent integration.

## M3-01 recognition coverage (additive v1 field)

`RecognitionEvent.processed_audio_ms = 5` reports the duration of the input
actually decoded for that partial/final. Zero means unknown/legacy; old clients
ignore the new field and the M2 fixed-capture profile remains compatible. The
adaptive profile requires this field, monotonic partial coverage within captured
input, and final coverage equal to the half-closed duration. A partial must cover
the latest VAD speech before it can support completion. Arrival time alone cannot
prove that a slow decode includes newly resumed speech.

Deploy regenerated bindings and the updated ASR worker before enabling adaptive
turn tests. Older workers produce zero coverage and cannot complete an adaptive
turn; they fall back within the bounded capture window. Existing resident workers
must be restarted deliberately or an isolated updated worker used for testing.
No transcript is added to logs; coverage is a numeric timing field only.

## M4 agent consumer (additive RPCs)

`RunTurn` accepts a final caller utterance and a small object with only optional
`caller_number` (a gateway hint, never authorization). `text_delta` is now a
bounded complete speech phrase; `detail_json.phrase_index` is contiguous from
zero. Exactly one `end` contains boolean `finish_call`. Unknown/malformed events,
wrong IDs or a missing successful end fail closed. Existing field numbers remain
unchanged; old test peers remain valid when the agent profile is disabled.

Additive `ReportPlayback` carries phrase index, sent duration and completion.
Duplicate identical receipts are idempotent; conflicting receipts are rejected.
Only completely delivered phrases enter dialogue context. Native phrase TTS IDs
are `turn-N-pI`, while ASR monitoring and model cancellation retain the parent
turn ID. Native queues hold at most eight pending text phrases and 32 PCM frames.
`EndCall` schedules durable post-call analysis separately from media teardown.
Deploy regenerated bindings and the new agent service before enabling the profile.
