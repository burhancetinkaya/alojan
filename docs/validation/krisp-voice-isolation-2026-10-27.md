# Krisp VIVA voice-isolation trial preparation — 2026-10-27

Status: superseded by the owner's subsequent free/open-source-only instruction.
Do not request paid SDK access or resume this candidate without a new instruction.
The access dependency below records the earlier investigation, not current work.

Scope: M3-02, M5-03, VXP-06; US-05/06; ADR 0003/0014. The owner selected
the first proposed candidate, local Krisp VIVA, superseding the brief LiveKit
trial request. This is an isolated evaluation, not a production integration.

## Access and current status

The vendor's [quickstart](https://sdk-docs.krisp.ai/docs/quickstart-viva-sdk)
requires approved SDK access through the developer portal. Linux CPU processing
is supported. Standard and usage-reporting SDK distributions have different
initialization requirements; the latter requires a license key. Do not substitute
a similarly named public package or attempt to bypass licensing.

No matching SDK/model files were found in the checked Linux locations
(`.local` and the administrator Downloads directory, depth four). Earlier checks
found no Krisp configuration key names in the inspected local environment/config
files. These bounded searches do not prove that no account or package exists
elsewhere. The owner was asked for an existing SDK package path/access status.
The owner subsequently confirmed that SDK access is not yet available.
No SDK was installed and no Krisp inference or quality measurement has run.

The earlier LiveKit utility clone is an unused, ignored development artifact.
Its dependencies were not installed; no Cloud session or processing was started.
No live service, call binding, Jev configuration or audio-recording setting changed.

## Bounded evaluation after SDK access

1. Inspect the supplied Linux package, record its version and SHA-256, review
   licensing and model redistribution constraints, and install in an isolated
   environment. Pin the actual supplied model and SDK; do not invent versions
   from documentation. Keep packages, credentials and audio out of Git.
2. Start with the vendor's telephony voice-isolation model. The current
   [model guide](https://sdk-docs.krisp.ai/docs/voice-isolation) identifies
   `krisp-viva-vi-tel-v2.5.1` for suppression and `krisp-viva-vi-tel-v2.7`
   for ASR compatibility. Compare the latter if available and target speech
   suffers. Availability and license are not yet verified.
3. Use public/licensed Turkish recordings with distinct speakers and synthetic
   controls, preserving target references and source provenance. Include clean
   target speech, target pauses with continuous background speech, simultaneous
   voices, background-first startup, quiet/distant target, louder competing voice,
   speakerphone-like delayed echo, and short intentional interruptions. Existing
   noisy-call audio was not recorded and cannot be replayed. Artificial gain or
   echo mixtures are not a substitute for real room/handset acceptance.
4. Process paired bypass/filter inputs with identical G.711 PCMA/PCMU conversion.
   Preserve per-call state across long pauses and competing speech; reset state
   between calls. Measure target-word loss, background-word leakage, false VAD
   interruptions and missed/delayed intentional interruptions. Do not use total
   transcription WER alone: removing background words is intended behavior.
5. Measure CPU/frame P50/P95/max, startup time, memory, algorithmic signal delay
   and buffering separately. The vendor's approximately 20 ms delay is not an
   Alojan measurement. Run filter-only CPU checks before scheduling ASR comparison
   or native SIP tests; retain the unchanged ASR settings for paired recognition.
6. Only a successful offline result justifies native integration. Feed the same
   isolated signal to VAD, turn detection and ASR, outside media callbacks, with
   bounded queues and call-local state. Preserve generation invalidation, cancellation
   and sent-audio accounting. Repeat real SIP tests and a supervised noisy-room
   handset trial before claiming the acoustic issue is fixed.

## Decision limits

Krisp warns that telephony voice isolation expects proximity to the microphone
and may suppress the intended speaker beyond approximately 30 cm. This directly
affects the owner's speakerphone scenario and must be tested, not hidden by using
only close-microphone fixtures. The smart-speaker model is not a workaround for
this requirement: it does not remove background voices.

SDK access is the current execution dependency. No carrier gate is closed,
no performance gain is claimed, and no production license approval is implied.
