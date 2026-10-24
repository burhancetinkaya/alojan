# Native gateway speech integration (M2-03)

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
640 ms voiced input can interrupt without waiting for a hypothesis; candidates
expire after 800 ms quiet. This conservative profile does **not** meet the
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


## Endpoint diagnostics and opt-in scheduling experiment

`event=endpoint_diagnostics` summarizes the final quiet epoch without transcript
or raw audio. Candidate/score/coverage/stability and last-blocked offsets use
PCM-domain silence; named wall-clock fields use monotonic time. Unknown values
are -1. Queue audio duration is backlog, not wall-clock frame age. The worker
emits the record at recognition teardown; media callbacks remain unchanged.

`--turn-partial-hint 0|1` requires turn models and defaults to **0**. When enabled,
a current positive acoustic score and stale ASR coverage can request a bounded
early partial over the existing audio stream. Fresh positive scores are reused
while only transcript coverage is missing, preserving resumption invalidation
and the one-second score age bound. It does not lower endpoint, stability or
onset thresholds. A legacy ASR worker ignores the added protobuf field.

**Do not enable this as the live default:** the experimental paired pause-quality
gate failed. [Evidence and limitations](../../docs/validation/endpoint-calibration-2026-10-24.md).
