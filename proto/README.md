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


## M3-01 recovery input metadata (additive v1 convention)

`AgentRequest.context_json` additionally accepts `input_event` with exactly one of
`silence_reminder`, `clarification`, or `silence_timeout`. Such a request must have
empty `final_user_text`; ordinary requests still require nonempty caller text and
omit `input_event`. Unknown values, null, mixed event/text and extra fields fail
validation. This is internal gateway control data on the existing loopback RPC,
not a command parsed from caller speech or model output.

Recovery generates fixed Turkish speech without model/tools, never writes a
caller utterance, and preserves normal phrase receipts/cancellation. A reminder
is accepted once per call. Only `silence_timeout` sets `finish_call`; reminder and
clarification continue listening. Existing 16-turn and call resource bounds apply.
No protobuf field or generated binding changes. Upgrade the agent before the
native gateway: older agents reject event metadata; ordinary older gateways
remain compatible with the upgraded service. Roll back both for the old profile.


## AGP-03 private call setup (additive, not activated)

The development contract preserves the deployed `AudioFrame.partial_hint = 9` and
`GenerationControl.OpenCall/ReleaseCall` lease protocol. `managed-` call IDs require
one `x-alojan-lease` metadata entry matching the worker's token; release cancels
resident generations and frees context, with a bounded 300-second expiry fallback.
Legacy IDs keep existing behavior. Tokens are worker-specific, never caller identity.

`Agent.InitializeCall` receives only an opaque managed call ID, canonical called
DID, deployment-selected source (`request_uri` or `to`) and optional caller hint.
The private gateway must authenticate the carrier transport peer before this RPC.
It has no HTTP equivalent and does not accept workspace/release IDs from callers.
A deadline is required; setup is bounded to 1.8 seconds. It pins the repository's
immutable release and returns only its ID/digest plus `ready_for_answer`.

Current staging **always returns ready_for_answer=false**. Native answer integration,
node preload, model/prompt/tool/audio consumers and scoped post-call consumers are
not complete. Do not treat a successful RPC as permission to answer. The normal
agent entry point does not configure routing; a routing-injected service rejects
RunTurn to prevent silently running the legacy Kübra backend for another profile.

Concurrent same-call initialization returns ABORTED; retry after the first finishes.
Successful sequential retries preserve the original release. Invalid leases/identity,
changed identity, unavailable routing and closed calls fail. `CancelCallSetup`
requires the same lease/deadline, cancels in-flight setup and records cancellation
without a summary or delivery job. Call it before ReleaseCall when setup is abandoned.
Release/expiry discard late results; if cancellation acknowledgement is lost after a
DB commit, configured stale-call reconciliation closes the initializing row without
post-call work. Reconciliation is not evidence that the call was answered.

Deploying these additive bindings alone neither activates routing nor changes the
carrier. Before enabling it, native consumers must require a positive readiness
acknowledgement and preserve ringing, slot limits, CANCEL and generation fencing.

### Prepared audio transfer (additive, staged)

`Agent.GetPreparedAudio` requires the same live lease and explicit deadline plus
the exact call/release/digest returned by initialization. It returns the pinned
greeting and unavailable PCM with their identity and greeting lead-in. Missing,
ended, cancelled or still-initializing calls fail; it never opens files, compiles
prompts, queries DB or invokes inference. Rebinding a number cannot change this data.

Each clip is complete mono PCM16 little-endian at 8 kHz, nonempty, 20 ms aligned
and at most 480,000 bytes (30 seconds including lead-in). Greeting pad is 0–1000 ms,
20 ms aligned, silent, and followed by speech. Both clips must contain nonzero PCM.
Server outgoing and dedicated native receive limits are 1,000,000 bytes to fit
960,000 bytes of PCM plus metadata; server incoming stays 16,384 bytes and concurrent
RPC limit stays 16. Existing event/phrase validation bounds remain unchanged.

The native setup worker passes the original absolute initialization deadline,
capped at 1.8 seconds, and cancels with both its stop flag and ClientContext.TryCancel.
The native validator rejects identity/shape/padding failures before constructing
the immutable bundle. Content hashes are verified by Python preload; this private
loopback transfer does not add a second cryptographic verification in C++.
No partial/fallback-to-legacy clip is accepted. Older agents return UNIMPLEMENTED;
that is a setup failure, never permission to answer. Generated bindings alone do
not enable ready_for_answer. Native Session now consumes this protocol only in
the explicitly isolated `--setup-test-agent-port` loopback profile. Its worker
opens a lease, requires positive initialization readiness, validates fetched PCM
and defers answer until the ringing delay. The actual staged service still refuses
readiness; scripted test peers exercise the positive path. See the
[native setup lifecycle](../services/voice-gateway/README.md#isolated-native-setup-lifecycle).


### Observed answer/end lifecycle (additive, staged)

`ReportCallAnswered(CallAnswer)` requires an opaque managed call ID, its live lease,
explicit deadline, pinned release/digest and native observed ACK Unix milliseconds.
A ready route/PCM alone is insufficient: the service also requires an internal answer
permit. Ordinary initialization still returns false and produces no permit. Only
isolated tests script positive readiness; no public endpoint can grant it.

`CallEnd` preserves fields 1–2 and adds answered_at_unix_ms=3 (zero if unanswered),
ended_at_unix_ms=4, release_id=5 and manifest_digest=6. Routed answered calls use all
fields. The end witness can repair a missing answer write and atomically enqueue one
summary. Duplicate completion cannot create another job; conflicting answer times,
wrong identity, closed leases and reversed/impossible timestamps fail. Native and DB
clocks must be synchronized within five seconds. Durations use observed timestamps,
not RPC completion time; reconciliation leaves unknown duration null.

Native persistence runs on the existing setup worker: 500 ms each for answer/end,
250 ms for release. Audio begins after SIP ACK without awaiting the database. SIP
hangup invalidates playback immediately, independent of persistence. Failed writes
produce explicit uncertain cleanup and require node-scoped reconciliation. Setup
cancellation after a recorded answer is rejected and must use EndCall instead.

Legacy clients keep their existing EndCall behavior in legacy mode. Upgrade Python
agent/contracts and native bindings together before running the isolated routed
profile; an older server's UNIMPLEMENTED answer RPC closes the staged call, never
falls back to unscoped recording. No migration or carrier activation follows from
regenerating bindings. Tests include real local SIP/RTP plus restricted PostgreSQL
roles, scripted readiness and missing answer/end writes, not live voice acceptance.


## AGP-03 pinned recognition configuration

`CallInitializationReply.recognition = 4` carries schema-version-1 spelling aliases.
The additive `Recognition.ConfigureCall` RPC accepts that configuration together
with call/release/digest identity. It requires a managed call's own ASR lease metadata
and an explicit deadline. Aliases are bounded to eight/2048 UTF-8 JSON bytes, exact
2–4-word alphabetic phrases; numeric/single-word/case-equivalent aliases fail.
The first successful configuration pins the lease. Identical retries are accepted;
configuration changes and first configuration after recognition starts fail closed.
Release/expiry cancels generations and drops the pin. An explicit empty map disables
legacy defaults for that call. No secrets or transcripts belong in this message.

Only a trusted private gateway may select these values; the ASR worker checks the
contract and lease, not a DB manifest signature or workspace authorization. Strict
workers (`--require-agent-release`) reject unconfigured streams. Older ASR workers
return UNIMPLEMENTED for the new RPC and cannot satisfy future routed readiness.
Native CallSetup now forwards this configuration under its original deadline in
the isolated setup profile. SpeechBridge uses the returned ASR lease for all turn/
monitor/cancel RPCs in native probe tests. Full routed Session integration and
readiness orchestration remain pending; ordinary InitializeCall stays not-ready
and routed RunTurn remains blocked. Both binding sets have been regenerated.


## Native managed service leases

No wire change is needed for agent/TTS handoff. The gateway opens separate service
leases with the existing GenerationControl and uses exactly one matching
`x-alojan-lease` on every turn/playback/synthesis/cancellation RPC. Agent streaming
uses a bounded conversation channel to the same configured worker as setup. TTS
OpenCall shares the original setup deadline; no worker failure triggers an unleased
fallback. Only CallSetup sends routed EndCall with answer/end witnesses.

Release/unknown acknowledgement semantics apply independently to all three services.
TTS lease acceptance alone does not validate the release's loaded voice/model revision.
The additive capability check below addresses that boundary; production readiness
remains pending and ordinary InitializeCall continues to return not-ready. Existing legacy messages remain compatible.


## AGP-03 pinned synthesis configuration

CallInitializationReply.synthesis=5 adds schema-v1 model, 40-character revision, voice,
sample_rate_hz, channels and format. Synthesis.ConfigureCall takes call/release/digest
plus this typed configuration. It requires the exact live worker lease and a deadline.
The resident backend must have declared an equal immutable capability after startup
validation; absent/mismatched capability fails FAILED_PRECONDITION. Invalid schema,
bounded identity or non-mono/PCM16/8 kHz transport fails INVALID_ARGUMENT. Same-pin
retries are idempotent; a new release/digest cannot replace an existing call pin.

Managed StreamSynthesize requires this pin even in compatibility mode. The optional
strict TTS flag also rejects legacy unconfigured IDs. Existing legacy synthesis wire
messages remain unchanged, but managed clients must upgrade agent/native/TTS/bindings
together and configure before streaming. Old ConfigureCall servers fail UNIMPLEMENTED;
there is no unleased or default-voice fallback. ConfigureCall validates private gateway
assertions, not a manifest signature or workspace membership. It grants no answer
permit by itself. Server lease expiry/release clears configuration and cancels work.


## AGP-03 pinned gateway timing

CallInitializationReply.gateway=6 carries schema-v1 max_call_seconds (10–300),
answer_delay_ms (0–5000), closing_delay_ms (0–5000), media_drain_ms (0–1000),
max_call_turns (1–16) and turn_timeout_seconds (1–20). The agent derives these
fields from the pinned release's operator-owned EnginePreset. Management users
cannot set them through agent drafts. No existing field number/type changes.

Native setup validates schema, the 256-byte envelope and all bounds before opening
speech leases/fetching PCM. A missing/old/invalid configuration fails closed; there
is no fallback to legacy launch flags. Upgrade managed agent/gateway/generated
bindings together. Legacy calls keep their existing launcher behavior. The native
call owns an immutable copy; no profile lookup occurs during a turn. SpeechBridge
requires this configuration alongside all three service bindings for managed calls.
Its agent RPC deadline is the lesser of remaining call budget and preset turn budget.

This is configuration transport/consumption, not a readiness permit: the actual
agent still returns ready_for_answer=false and rejects routed RunTurn. Full routed
Session conversation, calibration qualification and readiness gates
remain pending.


## AGP-03 native conversation calibration

GatewayConfiguration.calibration=8 is a required nested schema-v1 NativeCalibration
for upgraded managed gateways. It carries the operator preset's partial-hint flag,
VAD threshold, candidate/yes-no/open/uncertain/incomplete waits, silence reminder,
and interruption VAD/onset/sustained-speech/quiet thresholds. Native setup validates
all ranges, timing order and 20/32 ms alignment where required before PCM or speech
admission. Unknown/missing schema or unsupported values fail closed. The entire
gateway configuration has a 256-byte ceiling. No extra RPC or per-frame serialization.

Agent/managed gateway/generated bindings must be upgraded together; older managed
agents omit the nested configuration and cannot answer with the upgraded gateway.
Stored historical EnginePreset JSON without calibration retains its original v1
canonical digest. The upgraded agent explicitly resolves its frozen historical
calibration to a complete wire message; this is not a native default or CLI fallback.
New tuning is an explicit immutable calibration in a new preset/release revision.
Never change the historical compatibility defaults or mutate an active call.

Schema-v1 preserves fixed platform algorithms: echo correlation/energy/search,
lexical backchannels, 10% low-confidence onset protection, completion score/stability
and freshness guards, bounded pre-roll/history/queues, inference limits and PCM/VAD
frame sizes. These are not end-user knobs. Changing them requires versioned reviewed
implementation and quality/performance qualification. Their presence does not imply
calibrated carrier quality. The full routed Session/readiness gate remains closed.


## AGP-03 output budget handoff

GatewayConfiguration.output=9 carries schema-v1 OutputBudget. Native admission requires
it, validates the complete 256-byte gateway envelope and rejects missing/old/invalid
configuration before fetching PCM. Limits are phrase_max_chars (40–240),
phrase_max_bytes (160–1024), max_phrases (1–16), turn_max_bytes (1024–4096), with
4 * phrase_max_chars <= phrase_max_bytes <= turn_max_bytes. All old field numbers
and types remain unchanged; six generated bindings must be updated together.

The upgraded agent expands omitted historical storage fields to frozen historical
budgets. An older managed agent omitting output cannot use an upgraded gateway;
upgrade agent/gateway/bindings together. New tuning requires a new qualified preset
and release. No active call mutation or silent native fallback. The managed bridge
checks UTF-8 scalar and byte counts, phrase index/count and cumulative bytes before
queue/TTS admission. Queue size and TTS's independent 512-character ceiling stay fixed.
This is not a routed readiness permit; full conversational Session activation is pending.

## Prepared waiting speech (ADR 0014)

`PreparedAudioReply` has additive fields `waiting_pcm = 7` and `waiting_text = 8`.
Both are empty for old/default-off releases. Enabled releases require matching
prepared mono PCM16LE at 8 kHz, 20 ms alignment, at most five seconds, plus exact
release-bound text. The maximum response is bounded to 1,100,000 bytes, including
the two existing 30-second clips. Regenerate C++/Python together and coordinate
native/agent deployment before enabling this feature.

A waiting `AgentEvent` is index zero and at most once per turn. It has its own
playback receipt but does not consume substantive phrase/byte budgets, satisfy a
note acknowledgment or permit an `end` without a real response. The gateway plays
the prepared PCM without TTS; useful response PCM suppresses unsent waiting or
preempts it with a 5 ms crossfade inside the first response frame; no extra
20 ms frame is inserted. Partial sent waiting speech carries no invented
word alignment. Existing old-release/default-off behavior remains unchanged.
