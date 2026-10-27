# Nazlı Jev shadow handset trial — 2026-10-27

Scope: VXP-04/06, PERF-02/03, M2/M4/M5, US-04/05/06; ADR 0014.

## Outcome

The owner reported that all Nazlı speech was cut off, then confirmed remaining
silent with speakerphone enabled in a noisy room. This is a failed handset
quality trial with owner-reported false interruptions, not Jev acceptance.
The gateway logged three speech-interruption decisions and no media error in
those turn records. Echo leakage, background sound, or their combination is
plausible; the exact acoustic source is not established. Raw recording remained
off. The call cannot be acoustically replayed to resolve that distinction.

## Jev observations

The optional shadow switch was enabled for the trial. Three valid observations
were recorded using the existing workspace credential and pinned Jev model:

| Turn purpose | Observed category | Confidence | Duration |
|---|---|---|---|
| Current-day session lookup | lookup | 0.63 | 666 ms |
| Definition request | explanation | 0.75 | 253 ms |
| Correction of the requested day | unknown | 0.92 | 250 ms |

These categories match the configured policy, which conservatively sends
corrections to unknown. Three observations do not establish accuracy, calibrated
confidence, or latency distribution. The planned conversation/farewell case was
not completed. Shadow decisions only populate telemetry; they do not choose
speech, tools, or interruption behavior. The native interruption monitor has no
Jev dependency. This does not prove zero indirect timing/load effect; the two
handset calls were not a matched performance experiment.

## Playback evidence

The call connected for 44,480 ms. Three remote tool executions succeeded, summary
processing completed, and the existing Telegram action was sent. Gateway results
were three interrupted turns and one final cancelled recognition turn at hangup,
with no completed response turn. Agent generation completion must not be equated
with speech heard by the caller.

Recorded partial output included 1,060 ms and 540 ms of substantive audio and
2,280 ms and 700 ms of waiting speech. Partial receipts do not establish complete
spoken sentences. The second turn produced no substantive output before its
interruption. The short interval between last-sent audio and cancellation is not
a measurement of caller speech onset to playback stop.

## Mechanism inspected

`SpeechBridge::monitor` suppresses frames matched against the sent-audio
reference, then evaluates VAD and fresh partial recognition. `interruption_policy`
also permits sustained VAD evidence without recognized words. `EchoReference`
is a bounded correlation-based rejection heuristic, explicitly not an acoustic
echo canceller. Distorted or noise-mixed speakerphone return can evade it.
Current trial logs do not identify which policy branch fired or retain the
acoustic evidence needed to distinguish echo from independent room speech.

No threshold change or suppression engine is justified by this call alone.
Earlier denoising candidates failed the project's recognition-quality promotion
gate; do not activate them on the assumption that noise suppression fixes this.

## Next acceptance work

1. Add bounded, content-free interruption diagnostics outside media callbacks:
   decision branch, voiced/quiet duration, recognition freshness and echo counts.
   Do not log partial recognition text or raw audio.
2. Reproduce with controlled speakerphone echo plus room noise; compare pure
   echo, independent background speech, short acknowledgments and intentional
   near-end interruption. Preserve call isolation and cancellation semantics.
3. Evaluate the smallest shared-runtime correction against both false-cut and
   real-interruption latency gates before promotion. Do not disable interruption
   or require a remote model decision on the cancellation path.
4. Repeat handset verification after a candidate passes; no claim of a fix or
   full performance acceptance is made by this report.

## Restoration and checks

Restored the exact previous Kübra release and verified binding version 9, healthy
agent, ready routes and open gateway admission. Jev was disabled again. The
short-lived MCP token was revoked and login session closed. Nazlı is unbound.
No prompt, tool selection, VAD threshold or echo setting changed. The deferred
person-lookup instruction issue remains deferred.

This follow-up inspected code and saved trial evidence; only maintained evidence
documentation changed. No new inference, GPU, acoustic regression or carrier call
was run after restoration. Private diagnostic artifacts remain ignored under
`.local/nazli-jev-trial-20261027/`; no transcripts or credentials are published.
