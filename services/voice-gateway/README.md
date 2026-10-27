# Native gateway speech integration (M2-03)

## Operator admission drain

The updated native binary accepts `--start-drained 0|1` (default `0`). Value `1`
starts the SIP listener with new-call admission closed. SIGUSR1 closes admission;
SIGUSR2 explicitly reopens it at the existing configured capacity. Signals only set
a signal-safe flag. The normal main loop reports `event=admission_state mode=draining`
or `mode=open`; repeated identical requests are idempotent. Trusted new INVITEs get
486 while closed; the source allowlist still takes precedence with 403. No number,
profile, model, timer or capacity setting changes.

Already admitted ringing/setup/answered calls continue through their existing flow.
RTP, ACK, CANCEL, BYE, maximum-duration and cleanup behavior remain intact. Once
the normal reaper has removed every local session, including local speech quiescence
and completed setup cleanup, the loop reports `event=admission_drained local_calls=0`
once per closed interval. SIGINT/SIGTERM retain bounded shutdown behavior; they are
not maintenance-drain commands.

For a verified **new native binary PID**, after startup:

```sh
kill -USR1 "$GATEWAY_PID"
# Observe this process's draining state, then local_calls=0 before proceeding.
# Resume only after the maintenance operation has finished:
kill -USR2 "$GATEWAY_PID"
```

Serialize operator commands; wait for the current process's state before the next
command. Unix signals are not a queued request/reply protocol. Do not use old log
entries or a previous PID as acknowledgement. A signal-only drain is volatile:
for a maintenance window, retain `--start-drained 1` in the actual supervised launch
configuration so an automatic restart fails closed. Startup health/`event=ready`
means the listener exists, not that call admission is open or the GPU is idle.

This controls this gateway only. Local drain is not remote ASR/TTS/GPU quiescence:
cleanup may have timed out (`confirmed=0`) and non-preemptible work may remain.
Verify dependent-worker cleanup/lease expiry and exclude other inference producers
before reserving the resident GPU. Do not start a second EMA process.

The resident `lifecycle-20261024` image does **not** implement these controls.
Never send USR signals to it or to its Python supervisor/container PID 1: an
unsupported signal can terminate the process. Validate the executable and actual
gateway child PID before use. The staged supervisor integration below is tested;
carrier deployment and a complete remote-worker maintenance handshake remain pending.

### Supervised persistent admission

`infra/docker/supervise.py` retains the deployed worker health/restart behavior and
adds opt-in gateway control through `ALOJAN_ADMISSION_FILE`. Its native child always
starts with `--start-drained 1`. Only after that child's first native draining
acknowledgement can the supervisor send an open signal. The Netgsm launcher forwards
these arguments and uses `exec`, so signals target the native child, never a process
group or container PID 1. Do not mix direct USR commands with file-managed control.

The private, operator-owned state file permits admission only when its complete
content is `open\n`. Use `drained\n` to close. Missing, unreadable, malformed,
symlink and non-regular files close admission. Mount its **parent directory** read-only
into the container, so atomic host-side file replacement is visible after replacement
and automatic container restart. Persist the replacement file and directory before
assuming host-crash durability. Users and management API clients cannot modify it.

Polling runs every 250 ms in the supervisor, outside media callbacks. A running
health probe can delay observation by up to its five-second timeout plus scheduling;
file writes and `event=admission_requested` are requests, not completion receipts.
Serialize operator changes and wait for fresh native draining and local-drained events
from the current process. Track a log cursor and container start identity; repeat
verification if it restarts. Closed admission still passes SIP OPTIONS health checks.
Neither health nor local-drained proves remote GPU work has finished.

The [setup procedure](../../docs/DEV_SETUP.md#supervised-admission-validation-package)
and [isolated Linux/Docker evidence](../../docs/validation/supervised-admission-2026-10-26.md)
cover the compatible validation image and overlay. The resident image is unchanged.

## Staged AGP-03 prepared output

`prepared_audio.hpp` provides a private loopback setup-worker client and immutable
greeting/unavailable PCM bundle. Fetch uses the existing lease and original setup
deadline, validates release/digest, full clip sizes/alignment and greeting lead-in,
and fails closed on errors/cancellation. Share the bounded channel across calls;
never fetch on a SIP/media callback. The caller owns ClientContext until completion
and invokes TryCancel together with its stop flag when abandoning setup.

`PreparedPlayback` has one render thread per call and independent cursor/cancel
state. Each render fills an existing 320-byte frame, with no allocation, IO or
mutex; cancel/end produces silence. `sent_frames` counts frames supplied to the
media port, not remote handset receipt. Keep the playback object alive until the
port is destroyed. `PreparedOutput` and legacy `SpeechOutput` share the original
PJMEDIA buffer/lifetime implementation through `PcmOutput<Renderer>`.

Build all Linux targets and run `ctest --preset local` plus
`pytest -q tests/test_prepared_audio_transport.py` using the frozen uv environment.
These test real Python/C++ transfer and actual PJSIP conference ports with synthetic
PCM. The isolated setup profile below now exercises Session/INVITE selection.
The opt-in loopback conversation profile below exercises the pinned native Session.
Production readiness and general tool/action consumers are still pending; legacy
SIP tests cover the shared output adapter separately. No live performance acceptance
is implied.

### Isolated native setup lifecycle

`--setup-test-agent-port PORT` selects the private setup protocol, not the existing
conversational `--agent-port` profile. It requires both SIP bind/public addresses to
be exactly `127.0.0.1`, explicit `--trusted-identity-ip` entries and no legacy speech,
WAV or prompt-directory override. Turn models require the explicit conversation
profile below. It cannot be used for carrier traffic.
`--called-source request_uri|to` selects one authoritative field (default Request-URI);
`--called-national-prefix none|0` independently controls Turkish DID normalization.
The selected field must contain a trusted valid 0850 destination; other headers
never repair a missing/invalid destination. Invalid calls receive 404 before any RPC.

Session starts `CallSetup` from the main loop. One worker per admitted call opens
the lease, initializes the route and fetches matching prepared PCM under one
1.8-second deadline measured from admission. Only a positive ready_for_answer plus
validated complete audio permits 200, after the configured ringing delay. Speech
waits for ACK. Not-ready, transport failure, bad PCM or insufficient call duration
returns 503 without legacy fallback. By default the test profile plays the pinned
greeting and unavailable clip, then closes. The opt-in conversation profile below
connects ASR/agent/TTS after the greeting. Both modes persist the native SIP
ACK/termination through scoped repositories. Positive
readiness is still supplied only by scripted test peers.

CANCEL/BYE/shutdown invalidate local playback and cancel in-flight setup RPCs.
The SIP CONFIRMED callback captures the first ACK timestamp and wakes the existing
worker; it performs no network/database work. Prepared greeting playback starts
after ACK without waiting for persistence. Conversational capture waits for the
answer write; neither operation blocks the SIP callback. ReportCallAnswered has a
500 ms deadline;
failure closes the call rather than allowing conversation with uncertain storage.
EndCall repeats the same ACK witness, release and digest with the native termination
time, allowing atomic repair of a lost answer write. Native outcomes are completed,
disconnected or failed; dependency fallback is failed. EndCall is bounded to 500 ms,
then ReleaseCall to 250 ms. Unanswered setup still uses CancelCallSetup (250 ms).

A disconnected call retains its admission reservation until the worker finishes,
bounding threads under rapid disconnect/retry. Main-loop reaping joins only finished
workers. Missing cleanup acknowledgements are logged as confirmed=0; lease expiry
and node-scoped stale-call reconciliation remain necessary after RPC/process loss.
Recovery closes abandoned setup without post-call work. Previously answered calls
get exactly one scoped summary job with unknown duration and an explicit failure.
Prepared-only setup performs no model inference or transcript work. The opt-in
conversation profile stores scoped notes/transcripts; neither mode sends notifications.

Run `tests/sip-integration/test_prepared_setup.py` with the frozen test environment
and private development DB configuration. It includes real SIP/RTP with scripted
readiness, actual scoped PostgreSQL lifecycle writes with restricted roles, lost
answer/end repair, and the ordinary agent/cache/router/PostgreSQL refusal path.
Ordinary initialization still returns ready_for_answer=false; only a permitted,
persisted answered call can run a routed turn.
Production activation needs remaining credential/tool/action consumers, readiness production,
post-call worker deployment and complete performance/quality acceptance.

## Existing speech profile

The gateway now connects loopback SIP/RTP to the existing ASR/TTS gRPC contracts.
This is a **scripted development profile**, not a conversational assistant. M3
owns end-of-turn/barge-in decisions; M4 owns GPT responses. Default execution
continues to play the accepted AI greeting and unavailable message, then close.
`voice_pipeline_ready=0` stays honest until the complete assistant is integrated.

## Run on the authorized Linux host

Start the real workers with `scripts/run-asr.sh` and `scripts/run-tts.sh` in their
own sessions. Build with the frozen commands in [DEV_SETUP](../../docs/DEV_SETUP.md),
then run:

```sh
build/local/voice-gateway --speech-test-ms 7000 --max-call-seconds 25
```

By default SIP/RTP are loopback-only; internal gRPC always stays on loopback.
The separately authorized [Netgsm answer profile](../../docs/NETWORK_NETGSM.md)
uses explicit LAN/public addresses and a source allowlist. Speech-test options are:

| Option | Meaning |
|---|---|
| `--speech-test-ms` | Explicit synthetic test capture: 1000–10000 ms, divisible by 20; absent means existing WAV fallback mode |
| `--asr-port` | Loopback ASR port, default 15071 |
| `--tts-port` | Loopback EMA port, default 15072 |

Do not combine the scripted profile with `--wav`. Use the approved prompt pair
for the AI introduction and dependency failure. This profile is for synthetic
local peers: a fixed capture window is **not** a silence detector or a product
turn decision. No caller recording, transcript persistence, agent, notes or
external actions are enabled.

After ACK the gateway plays the named greeting. At greeting EOF it opens the
scripted capture window, streams PJMEDIA-resampled mono 16 kHz PCM to ASR and
reads replacement partial hypotheses concurrently. It half-closes after the
configured frame count and requires one valid final event. Only then does it
request the fixed unavailable/closing phrase from EMA. Generated mono 8 kHz
PCM is played through PJMEDIA at 20 ms intervals into negotiated PCMA or PCMU.
The complete response drains before BYE. This tests both speech directions
without inventing an agent response or interpreting a timer as a user turn end.

## Ownership, bounds and failure behavior

- One bridge belongs to one call and one generation. IDs include a random process
  nonce so they are not reused after restarting the gateway. Separate calls never
  share queues, cancellation contexts or audio history.
- Media callbacks only validate/copy fixed PCM and update atomic counters. Input
  has a 64-frame single-producer/single-consumer queue (1.28 s, 40 KiB); output
  has 32 frames (640 ms, 10 KiB). There are no application locks, network calls,
  logging or model work in these callbacks. PJMEDIA's existing lifetime group
  lock protects teardown; the native output port uses its supplied frame buffer
  instead of allocating a new PJSUA2 vector on every callback.
- gRPC reads/writes and cancellation RPCs run on background threads. Transport
  messages are bounded to 16 KiB. A full input queue marks the stream failed;
  a producer waiting more than 250 ms for output consumption fails instead of
  growing the queue. An already blocked gRPC operation is bounded by cancellation
  and its deadline; overflow cannot synchronously preempt a blocked native write.
- ASR gets the earlier of the remaining call deadline and capture duration plus
  five seconds. TTS inherits the original call deadline. Each control-plane
  cancellation has a separate bounded 150 ms cleanup grace; this does not extend
  inference time. No transcript or model/transport error text is printed.
- ASR IDs, final ordering and text size are checked. A final before half-close is
  rejected. TTS IDs, sequence, format/rate/channels, size, timestamps and the
  30-second output bound are checked before PCM can enter the playback queue.
- Hangup/shutdown immediately invalidates local delivery and cancels both stream
  contexts. Background cleanup fans out idempotent generation cancellation to
  both workers for interrupted/failed work. A disconnected call is retained until
  its worker finishes, so cleanup does not join a live RPC in the normal event
  loop. Ports detach before their bridge is destroyed; asynchronous PJMEDIA
  removal cannot dereference freed call state.
- Input/model/contract failures discard queued generated audio, play the local
  unavailable WAV and close after its completion. If the call's maximum duration
  is already exhausted, normal bounded hangup takes precedence over a new prompt.
  Defaults retain one-call admission. Explicit two-call tests prove isolation;
  the one-stream speech workers can reject the other call with controlled fallback.

`output_port_ms` counts PCM handed to the conference bridge, not proven handset
playback or aligned transcript text. Actual RTP timing/continuity is checked by
the synthetic peer. Production sent-audio/transcript accounting and barge-in
still belong to M3. Completed test streams are not revived; playback callbacks
ignore all queued data once the call is invalidated.

## Checks

```sh
uv run --frozen pytest -q tests/sip-integration/test_speech.py
uv run --frozen ctest --preset local
# Requires actual ASR/EMA on their default loopback ports; synthetic fixtures only.
uv run --frozen python tools/validate-gateway-speech.py \
  --output .local/gateway-speech-new
```

The pytest suite starts explicit fake speech workers on separate ports while
using real native SIP/RTP/gRPC. The standalone validation uses the resident CUDA
workers, seven seconds of synthetic input and both G.711 codecs. It verifies
complete generated closing audio against the approved PCM reference and records
packet pacing, capture/finalization and latency counters under ignored `.local/`.
See [Linux evidence](../../docs/validation/linux-speech-gateway-2026-10-23.md).

## Adaptive single-turn development profile (M3-01)

Build the optional native CPU detectors using the [setup guide](../../docs/DEV_SETUP.md).
Start an ASR worker with the new coverage field and the existing EMA worker, then:

```sh
build/local/voice-gateway --turn-model-dir .local/turn-models --max-call-seconds 30
```

`--turn-model-dir` replaces `--speech-test-ms`; neither it nor fixed capture may
be combined with custom `--wav`. `--turn-context open|yes-no` selects the preceding
question context for this test (default open). It is an explicit fixture context,
not an inferred agent question. Missing/unloadable models fail before SIP readiness.
Default WAV/Netgsm behavior stays unchanged. `voice_pipeline_ready=0` remains set.

The bridge worker reframes 20 ms / 16 kHz PCM into Silero's 512-sample blocks with
64 samples of model context and isolated recurrent state per call. VAD threshold
is 0.50; at least 96 ms of voiced blocks is required. All input, including pre-roll,
is sent to ASR. The latest eight seconds are retained only in bounded process
memory for Smart Turn. There is no caller recording path.

After a 250 ms silence candidate, one background CPU Smart Turn job analyzes a
snapshot. At most one job is active per call; candidates refresh after 320 ms.
Resumed VAD speech invalidates its epoch and prior scores. Low-confidence onset
(at least 0.10) also invalidates scores and holds decisions until 200 ms of
candidate-free input; it cannot itself create a turn. This protects resumed
speech while Silero confidence is still rising after a long pause. Scores older than one
second are rejected. A 1500 ms inference watchdog triggers the existing local
fallback; it cannot preempt a stuck native ONNX call, whose completion may delay
worker cleanup but cannot restart playback after cancellation. Model work never
runs in media callbacks or the SIP event loop.

Completion also needs a nonempty ASR partial covering the last voiced sample,
stable for 200 ms. Initial policy uses 350 ms for a yes/no answer with probability
at least 0.50, 500 ms for open answers at least 0.75, and 1200 ms for lower-confidence
completion at least 0.50. Turkish lexical hesitation/conjunction hints block early
completion even if the acoustic model is confident. These are conservative local
heuristics, not semantic understanding. Incomplete/unknown results wait 2000 ms
plus the 200 ms endpoint pad; failure plays the unavailable WAV, never a guessed
agent response. The single-turn capture ceiling is 20 seconds. Quiet-only input
cannot create a turn even if ASR or Smart Turn hallucinates a completion.

After accepting a turn, input delivery stops, ASR half-closes, and the existing
fixed EMA closing plays after a valid final. This tests adaptive timing; it does
not implement a conversation, barge-in, a clarification response or the once-at-seven-
seconds silent-caller reminder. Those remain explicitly open in the plan. Initial
thresholds retain the original calibration defaults; validated runtime options
are now available in the M3-01 follow-up below. The default carrier process was not restarted into this profile.

Numeric completion logs include VAD-relative silence, model probability and
observed background inference time. Half-close-to-output is a separate metric;
neither is handset latency or P95. Run `tests/sip-integration/test_turn.py` with
the CPU build/artifacts enabled. These tests use real CPU detectors and real SIP,
but synthetic ASR/TTS. With real GPU workers, add `--turn-model-dir .local/turn-models`
and optionally `--asr-port PORT` to `tools/validate-gateway-speech.py`.

## Interruption development profile (M3-02)

Add `--barge-in 1` to the adaptive profile. This requires native turn models and
an updated ASR worker; it defaults to off. The approved opening WAV remains
uninterruptible in this development profile. Once the first caller turn ends,
the bridge monitors inbound PCM throughout synthesized response playback.
The next turn still produces the same fixed unavailable reply, not an agent answer.

The worker compares incoming 16 kHz PCM (downsampled for comparison) with a bounded
8 kHz outbound reference. A normalized absolute correlation above 0.82, up to
400 ms delay, and inbound/reference energy ratio at most 2.25 classifies echo;
these frames become silence for monitor VAD/ASR. This is an initial echo-rejection
heuristic, not acoustic echo cancellation. Real handset double-talk, reverberation
and arbitrary delay require further calibration. Media callbacks only copy fixed
frames into bounded single-producer/single-consumer queues and update atomics.

A separate Silero state requires 192 ms of voiced blocks. A fresh ASR hypothesis
covering the latest voiced input can confirm a correction. Exact brief `evet`,
`hı hı`, `hıhı` and `tamam` hypotheses are treated as backchannels up to 640 ms of
voiced blocks. Missing or stale ASR cannot confirm a short interruption. Sustained
640 ms voiced input can interrupt without waiting for a hypothesis. This uses a
separate counter: a quiet gap of at least 160 ms resets sustained evidence, so
separated short bursts cannot accumulate into the fallback. Shorter VAD dips
retain evidence; the ASR candidate still expires after its existing 800 ms window.
These defaults use the release's existing validated interruption settings.
The `speech_interrupted` event includes voice/sustained/quiet durations, last VAD
probability, ASR coverage freshness and monitor echo-frame count, without text or
audio. These measurements do not identify who spoke or prove an acoustic cause.
This conservative profile does **not** meet the
speech-onset-to-stop target of 250 ms. Natural Turkish acknowledgment/semantic
classification and threshold calibration remain acceptance work.

Interruption first revokes the output epoch locally, then cancels the active TTS
RPC. Every queued PCM frame carries its epoch; the audio consumer discards revoked
frames, including any enqueue racing with cancellation. At most an already handed
off 20 ms frame can remain in flight. The old producer and monitor are joined
before fresh RPC contexts/generation IDs are created. Best-effort cancellation RPCs
have 150 ms deadlines; local invalidation does not depend on their success.

The monitor keeps at most two seconds of echo-filtered input for handoff. This
pre-roll plus continuing bounded input is recognized under a new generation;
there is no raw audio recording. Up to eight responses are permitted within the
existing call deadline; exhausted limits and monitor/model/protocol failures use
the existing controlled local fallback. The current ASR/TTS services admit one
active context each; two-call tests remain overload/isolation tests.

`SentSpeech` is an in-memory, per-generation record, readable after the bridge
worker finishes. It stores the duration handed to the output port. Only a fully
sent utterance receives text. An interrupted, failed or cancelled utterance has
empty aligned text, even when some of its audio was sent. This deliberately
conservative whole-utterance alignment must become phrase-level alignment when
M4 streams agent text; never estimate words from a duration ratio. No text is logged.
The `sent_speech` event exposes only generation, milliseconds, byte count and an
interrupted flag. `speech_interrupted` includes monotonic decision/last-send times;
these are not handset timestamps. Agent/LLM cancellation is deferred until M4
actually connects that service, and no agent readiness is asserted here.

Run `tests/sip-integration/test_interruption.py` for real local SIP/CPU detection
with explicitly fake ASR/TTS. Run `tools/validate-interruption.py --output
.local/interruption-new --asr-port PORT` with an updated real CUDA ASR worker and
the resident EMA worker for the separate GPU check. See
[the evidence and limitations](../../docs/validation/linux-interruption-2026-10-23.md).

## Owner-selected waiting music

The agent profile now plays [quiet original waiting music](../../assets/waiting/README.md)
locally after 800 ms without a first response PCM frame. Music is prepared outside
callbacks and copied in 20 ms frames; no file/network/model work occurs in the
media callback. First response PCM always takes priority and music stays off for
later phrase gaps. Existing epoch, state and stop guards cancel music along with
speech. Outbound echo reference includes music, while speech frame counters,
receipts and aligned text exclude it. `waiting_music_ms` records its separate
output duration at completion/interruption. The old agent waiting sentence is off.


## M3-01 silence recovery and runtime calibration

The adaptive **agent** profile (`--turn-model-dir`, `--barge-in 1`, `--agent-port`)
now emits one silent-caller reminder per call after seven seconds of quiet input:
“Buradayım, sizi dinliyorum.” A low-confidence speech onset postpones the reminder;
a confirmed spoken turn uses endpoint/clarification logic instead. The timer starts
when recognition starts after the opening or a response, not while greeting,
thinking, speaking or playing waiting music. The seven-second threshold marks the
request; actual audibility also includes bounded service/TTS startup time.

After the reminder, a fresh bounded recognition stream continues listening. If
that stream contains no confirmed speech for its existing 20-second capture
budget, a polite no-audio farewell precedes the normal three-second hangup drain.
The reminder does not repeat. If acoustic/partial evidence stays incomplete at
the endpoint threshold, the agent profile instead asks the caller to repeat and
continues listening. Detector, malformed transport and dependency failures retain
the existing controlled fallback. Overall call/turn budgets are unchanged.

Recovery uses typed gateway metadata, not invented caller text or an LLM request.
Only delivered assistant phrases enter stored history. The existing echo monitor,
interruption cancellation and output epochs apply during recovery speech. Up to
two seconds of echo-filtered pre-roll preserves speech beginning near the prompt's
end before it reaches the interruption threshold. No raw recording is added.
Waiting music is disabled for these immediate control responses. The standalone
adaptive test without an agent retains its previous failure behavior.

The following validated CLI options retain the existing defaults. These tune turn
endpoint decisions, not the separate interruption classifier. Invalid bounds or
ordering fail before SIP readiness; custom values require turn models.

| Option | Default | Allowed range |
|---|---:|---:|
| `--turn-vad-percent` | 50 | 20–90 |
| `--turn-candidate-ms` | 250 | 100–500 |
| `--turn-yes-no-ms` | 350 | 350–1000 |
| `--turn-open-ms` | 500 | 500–1500 |
| `--turn-uncertain-ms` | 1200 | 1200–2000 |
| `--turn-incomplete-ms` | 2200 | 2200–5000 |

Require candidate ≤ yes/no ≤ open ≤ uncertain < incomplete. Incomplete includes
the endpoint pad. The 200 ms partial stability/onset hold, model score thresholds,
96 ms minimum voice and bounded model watchdog remain fixed. Runtime options
permit calibration without rebuilding; they are not proof of human/noisy-speech
accuracy. The current carrier profile keeps the default values.

Run `tests/sip-integration/test_silence.py` alongside the existing turn,
interruption and agent-dialogue tests. They use real SIP and CPU turn models but
explicitly synthetic ASR/TTS and an in-memory agent store. Real CUDA/DB and handset
results must be reported separately.
## Per-turn latency diagnostics

M5-03 emits one `event=turn_latency` record from the worker after each attempted
turn, including interrupted, cancelled and failed turns. `call_trace` is the
gateway-generated speech identity, not the carrier SIP Call-ID; SHA-256 of this
value truncated to 12 hex characters matches the agent's `call_key`. No transcript
or caller number is included. Audio callbacks only update fixed-size atomics.

The record distinguishes endpoint-to-ASR-finalization, agent-request-to-first
phrase, first TTS request-to-PCM and PCM-to-output-port delays. Waiting music is
excluded. `endpoint_silence_audio_ms` is the detector's PCM-domain silence at its
accepted decision. Adding that to endpoint-to-audio produces
`vad_end_to_audio_estimate_ms`: a server estimate, not measured caller-stop-to-ear
latency. Replay/queue age, VAD error and carrier/handset transport are not measured.
Fixed-capture and recovery turns have no accepted VAD endpoint; missing values
remain `-1`. Recovery kind is explicit so reminders are not counted as fast LLM
responses. Existing `sent_speech` receipts and cancellation behavior are unchanged.


## AGP-03 isolated recognition setup handoff

The loopback-only `--setup-test-agent-port PORT` profile optionally accepts
`--setup-test-asr-port PORT`. It opens a separate ASR lease and forwards the exact
InitializeCall release/digest/recognition configuration to Recognition.ConfigureCall.
ASR must acknowledge before prepared audio is fetched and the local setup is ready.
All setup RPCs share the original 1.8-second deadline; CANCEL/shutdown cancels pending
ASR open/configure RPCs. No RPC runs in SIP/media callbacks. The ASR channel retains
the existing 16 KiB message ceilings, independently of the larger PCM setup channel.

CallSetup owns both leases. ASR release gets at most 250 ms, off the SIP thread;
cleanup is confirmed only when both services acknowledge. A lost ASR OpenCall reply
has no usable token and remains uncertain until worker lease expiry. Do not infer
cleanup success from SIP termination. Admission remains reserved until cleanup ends.

SpeechBridge accepts an immutable binding to that exact ASR worker/call/lease and
uses it for normal turns, the interruption monitor and ASR generation cancellation.
It rejects mismatched call IDs. The setup owner must outlive consumers and release
after their cancellation. Two-turn/monitor tests exercise this path through a native
probe and real strict RecognitionService with scripted models. Existing legacy
constructors retain their original behavior.

The default SIP setup profile plays prepared greeting/unavailable clips. The opt-in
conversation profile now integrates Session with pinned calibration and speech
consumers; production readiness coordination remains pending.
Ordinary AgentService remains not-ready and routed RunTurn is blocked. Keep live
workers unchanged until these gates and measured voice/performance acceptance pass.


## AGP-03 agent and synthesis lease handoff

The isolated setup profile also accepts `--setup-test-tts-port PORT`, only with
`--setup-test-agent-port`. TTS OpenCall shares the original 1.8-second setup deadline
and must succeed before PCM fetch/readiness. CallSetup exposes immutable
CallServiceBinding values for recognition, agent and synthesis only after successful
setup. Agent conversation and setup channels address the same configured worker;
conversation/ASR/TTS keep their 16 KiB send/receive caps, while prepared PCM uses its
separate larger channel. No service token is sent to another service.

Managed SpeechBridge construction requires all three bindings. Missing, foreign-call,
malformed-token or null-channel bindings fail before media starts. RunTurn, playback
reports, each synthesis phrase and all generation cancellations use the matching
lease. There is no unleased retry. CallSetup alone owns routed answer/end persistence;
SpeechBridge only invalidates its final agent generation. Cancel/join consumers before
releasing the setup owner. Existing legacy construction and EndCall remain unchanged.

Cleanup releases TTS and ASR with separate 250 ms caps before agent end/cancellation
and release. Answered cleanup is bounded to 1.25 seconds (plus an already-running
500 ms answer report). Failed/lost open or release acknowledgement leaves cleanup
unconfirmed. The existing admission slot is retained until cleanup finishes. No RPC,
allocation or configuration lookup was added to audio/signaling callbacks.

Native probe tests use real ASR/TTS protocol services and scripted inference, readiness
and agent behavior. They cover two turns/two phrases, interruption monitoring, active
synthesis cancellation, foreign service tokens and one routed end report. This does
not grant production readiness. TTS capability matching is implemented below;
pinned preset consumers and opt-in Session integration are now connected.
Production readiness and remaining credential/tool/action consumers are still required.


## AGP-03 pinned synthesis capability

InitializeCall now returns typed synthesis identity from the preloaded agent runtime.
After TTS OpenCall, CallSetup sends the exact release/digest/profile to
Synthesis.ConfigureCall with that worker's lease and the original setup deadline.
A schema other than v1 or a configuration exceeding 512 bytes fails locally; the
worker validates model/revision/voice/PCM fields and acknowledges only an exact match
with its loaded capability. Old workers, negative/lost acknowledgements and mismatched
profiles cannot fetch prepared audio, reach local ready or answer. CANCEL also cancels
the pending configuration RPC. Known leases still drain through bounded cleanup.

The native two-turn probe uses a real strict TTS service with a synthetic backend.
Real SIP tests cover mismatch, missing/oversized configuration, old workers, deadlines,
uncertain acknowledgement and cancellation. These checks establish release alignment
for the private setup path; ordinary InitializeCall still returns not-ready until
production readiness coordination and remaining credential/tool/action consumers
are complete.


### Pinned call timing and turn budgets

Managed CallSetup now requires GatewayConfiguration from the same InitializeCall
reply as the release/digest. The frozen operator preset supplies call duration,
answer delay, farewell pause, media drain, maximum conversation turns and agent
turn deadline. Missing/unsupported/out-of-range settings reject setup before PCM
or speech admission. GatewaySettings validates within the published v1 ceilings;
SpeechBridge rejects managed construction without settings and service bindings.

For the isolated setup profile, legacy `--answer-delay-ms`/`--max-call-seconds`
flags do not override the preset. Duration starts at inbound call creation, includes
ringing and delayed ACK, and never resets when media starts. Before initialization,
the infrastructure ceiling applies while the separate 1.8-second setup deadline
remains unchanged. Prepared greeting/unavailable playback uses the pinned media
drain only; a conversational farewell uses closing delay plus drain. The opt-in
managed Session profile exercises the latter path. Legacy CLI and
three-second conversational farewell behavior remain unchanged.

Call-local immutable copies prevent source changes from retiming active calls.
No DB/HTTP request, model reload or blocking media-callback operation is added.
Run native build/CTests, `test_prepared_setup.py`, `test_recognition_setup.py`,
`test_call_initialization.py` and legacy dialogue regression after changing these
consumers. The tests use real local protocol transport and synthetic speech; they
are not CUDA, carrier or performance acceptance. Ordinary routed readiness remains
false; endpoint/barge-in qualification and phrase/output presets are subsequent work.


### Pinned endpoint and interruption calibration

The managed GatewaySettings snapshot now includes validated TurnSettings and
InterruptionSettings from the operator-owned release. SpeechBridge uses that turn
snapshot even when a caller supplies conflicting legacy TurnSettings. Normal
recognition consumes VAD/candidate/wait/partial-hint/reminder settings; its speaking
monitor consumes the separate interruption VAD, onset, sustained speech and quiet
windows. Both preserve per-call state and existing immediate generation invalidation.

Legacy constructors/CLI retain their previous defaults and behavior. Echo rejection,
backchannel words, completion scores/stability, low-confidence onset protection and
bounded resource policies remain the fixed schema-v1 platform algorithm. No additional
model pass, callback IO, model instance, media queue or settings fetch is introduced.
Operator ranges are transport/safety bounds, not proof that all combinations produce
good speech. Qualification still requires the labeled pause/echo/quality suite and
PERF gates before changing a live preset.

Tests combine real local setup/ASR/TTS RPC with scripted inference and a native
link-time detector double. Two synthetic DIDs use distinct completion waits; low-level
CLI thresholds cannot override the release. Synthetic weak speech exercises a configured
interruption VAD/onset and cancels the old phrase. Native unit tests cover separate
reminder timing, snapshot isolation, backchannels and sustained speech. Production
InitializeCall remains not-ready; this does not activate routed Session conversation.


## Managed speech output budgets

Managed setup pins schema-v1 OutputBudget from the selected release's EnginePreset.
Before enqueueing each phrase, SpeechBridge checks its UTF-8 scalar count, encoded
bytes, phrase index/count and cumulative turn bytes. Excess output fails the agent
generation through existing cancellation; it is never queued for TTS or reported as
completed playback. Already played valid phrases remain actual sent audio. The eight
pending-phrase slots and PCM queues are unchanged. Unconfigured legacy native calls
keep their byte-only admission; managed calls require explicit valid output settings.

Limits may only narrow the fixed 240-character/1024-byte phrase, 16-phrase and
4096-byte turn ceilings. Historical stored profiles explicitly expand to those defaults
at initialization without changing digests. Upgrade the managed agent and generated
bindings with the gateway; missing output configuration fails before answer. No new
RPC or model work. Production readiness remains pending; the opt-in Session profile
is described below.


## Opt-in routed Session conversation (AGP-03, isolated)

Add `--setup-test-conversation 1`, all three `--setup-test-*-port` options and either
`--speech-test-ms 1000` for fixed synthetic capture, or `--turn-model-dir PATH
--barge-in 1` for native CPU endpoint/interruption models. This remains loopback-only
and requires explicit trusted identity sources. Legacy `--agent-port`, custom turn
thresholds/context, WAV and prompt-directory overrides are rejected. Ordinary
initialization never supplies the ready permit: tests explicitly inject it.

After ACK, Session immediately plays the release greeting. Once the greeting and
answer persistence complete, it starts SpeechBridge with the same immutable runtime
settings and agent/ASR/TTS leases. The bridge handles
multiple turns, playback receipts, interruption and configured farewell timing.
Dependency failure plays that release's prepared unavailable clip. No legacy identity
or media fallback is used for a routed call.

Termination immediately cancels local media and records the end timestamp. The setup
worker retains leases until SpeechBridge finishes generation invalidation and receipt
work, then performs its existing release/end sequence. `finished()` means playout has finished;
`quiesced()` means the worker has also completed final RPC cleanup. Main-loop reaping
uses the latter, so it never joins a worker still waiting on network cleanup. Admission
remains reserved during cleanup. The Session destroys speech before its setup owner.

Run `tests/sip-integration/test_managed_session.py` and the existing prepared/setup,
recognition, answered-lifecycle and legacy-dialogue regressions. Coverage includes two
workspaces/two codecs, scoped notes/playback/summary jobs, failed model/answer write,
BYE during greeting/model work, and actual native CPU interruption with synthetic
ASR/TTS/agent inference. See CALL_TEST_PLAN for evidence and pending production gates.
