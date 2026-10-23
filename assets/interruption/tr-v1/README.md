# Synthetic Turkish interruption fixture

`acknowledgment.wav` is the complete word `Evet.` generated on the authorized
Linux RTX 4080 by the already resident EMA service on 2026-10-23. It is not a
caller recording or a human listening acceptance sample. The manifest pins the
upstream model/weights and deployed package versions and hashes the saved WAV.

Generation used `voice.v1.Synthesis/StreamSynthesize` with text `Evet.`, a unique
synthetic call/generation identity and a 20-second deadline. Concatenate validated
20 ms mono PCM16 8 kHz frames, then wrap them in a standard WAV container. Reuse
the running worker; never start a second EMA instance. Service generation is not
claimed bit-reproducible across requests; the committed hash freezes this fixture.

The SIP backchannel test combines this actual synthetic word with an explicitly
fake, fresh `Evet.` ASR hypothesis. It checks native VAD and lexical policy, not
real ASR accuracy or a human false-interrupt rate. The preceding test cropped
400 ms from an unrelated phone-number utterance; VAD classification varied with
frame phase, so that incomplete-word fixture was replaced rather than weakening
the policy threshold or removing the classification assertion.

Upstream sources and unapproved redistribution questions follow
[DEPENDENCIES](../../../docs/DEPENDENCIES.md) and
[LICENSING](../../../docs/LICENSING.md). No project license or redistribution
approval is implied by generation.
