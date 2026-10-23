# Live Netgsm interruption check — 2026-10-23

Tasks M3-01/M3-02, US-04/US-05/US-06; owner-authorized incoming carrier test.
This is a limited live result, not full G3/G4 acceptance or conversational-agent
readiness. The owner explicitly requested real-phone validation after the native
CPU/CUDA checks. No router/firewall changes, outbound call, recording or private
transcript capture were made.

## Activation and preflight

The existing gateway had no active call when switched. Its mapped executable,
arguments and old log were saved under ignored `.local/carrier-before-interruption`
with private permissions for rollback. The new gateway uses the already-tested
binary SHA-256 `2a230b7d0824415175f47ca91bdf7b68558f88f1aaf5e3bcc0fe3cb2c1ed4a69`.
The source launcher now has explicit `greeting` (default) and `interruption`
profiles. The latter enables CPU turn models, barge-in and a 60-second call limit.
Shell syntax and isolated argument-capture checks passed for both profiles and
rejection of an unknown profile. No C++ or model change was made during this test.

One updated ASR worker was started on loopback port 15171; its standard health
reported SERVING, and a synthetic 20 ms request verified final input coverage.
The existing EMA worker on loopback 15072 also reported SERVING. The old ASR
worker was retained, and no second EMA instance was started. The active gateway
uses the existing carrier-restricted network configuration and UDP 5060.

Private runtime files: `.local/netgsm-gateway.pid`,
`.local/netgsm-interruption-asr.pid`, `.local/netgsm-active-profile.json`,
`.local/logs/netgsm-gateway.log`, `.local/logs/netgsm-interruption-asr.log`.
The development processes are detached, not reboot-supervised.

## Observed calls

All four calls negotiated PCMA. Only local serials and numeric telemetry are
retained here; telephone numbers and recognized words are excluded.

| Call | Observed behavior | Acceptance interpretation |
|---|---|---|
| 1 | ACK 14 ms, media 18 ms; nonempty ASR final (69 bytes); 4000 ms complete EMA output; zero interruptions | Live inbound ASR and outbound generated response worked; no interruption evidence |
| 2 | ACK 15 ms, media 16 ms; nonempty ASR final (60 bytes); 4000 ms complete EMA output; zero interruptions | Second ordinary turn/response; does not prove barge-in |
| 3 | ACK 13 ms, media 14 ms; `speech_interrupted` revoked `turn-1`; `speech_speaking` started `turn-2`; caller hung up at 15.532 s | Actual interruption and new-response path confirmed; owner explicitly heard the sentence cut off |
| 4 | ACK 13 ms, media 15 ms; `speech_fallback error=8` after 238 ASR input frames; controlled closing, disconnected at 12.046 s | Incomplete-turn detection could not accept a boundary; this remains calibration evidence, not a successful conversational turn |

In call 3, the last reported output-port send preceded the interrupt decision
by 1 ms. Total output-port duration across both generations was 4040 ms. The
second generation began before remote hangup; complete second-utterance playback
and per-generation aligned-history output were not logged because the call ended
before the normal completion report. Do not infer those properties from this call.
No audio packet capture was taken, so this is not independent wire-level or
handset latency measurement.

All four closures reported zero invalid PCM frames, zero last-sampled RTP loss,
reorder and duplicates. Maximum sampled jitter was 250–375 microseconds. These
are server snapshots, not final wire totals or a network-quality guarantee.

## Owner feedback and disposition

The owner initially reported no stop, then corrected that feedback to stopping
and answering. The first two server records showed only normal completed replies,
so interruption was not marked passed from that feedback alone. A focused repeat
asked the owner to speak over the generated response, rather than the opening WAV.
The owner confirmed that the sentence was cut off; call 3 independently recorded
invalidation and a new generation. **The basic real-phone barge-in path is now
confirmed for one PCMA call.**

The fourth call's incomplete-turn fallback is retained as an unresolved M3-01
calibration case. There is no retained audio/transcript to diagnose its acoustic
or lexical cause, so none is guessed. Broader natural speech, noise, backchannels,
handset echo/double-talk, PCMU carrier behavior, the 250 ms onset target, phrase
alignment and real M4 agent cancellation remain unaccepted. The opening greeting
is still uninterruptible. The generated reply is still the fixed unavailable
message, not a saved note or an agent response.

The interruption test profile remains active with the updated loopback ASR.
Use the explicit greeting profile for rollback after confirming no active call;
never launch a second gateway on the carrier port. No further model or threshold
changes were made based on a single successful interruption.
