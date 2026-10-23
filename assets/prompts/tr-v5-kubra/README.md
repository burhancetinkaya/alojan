# Kübra greeting, EMA v5

Owner-approved text, including the later Burhan Bey wording correction:

“Merhaba, ben Kübra. Burhan Bey’in yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?”

Synthesized on the authorized Ubuntu GPU server through the resident pinned
EMA service on 2026-10-23. The service uses EMA Lightning 1.1.2 and model revision
`e7c96f2fc0ba843cd0f86e02786655bb56f50df8`. No reference voice or caller recording.
Mono PCM16, 8 kHz, 20 ms frames; prepend 400 ms of silence for carrier readiness.
The unavailable announcement is copied unchanged from v3. Manifest hashes cover
text and audio. This is generated content; handset listening acceptance is pending.

For reproduction, send greeting.txt to the resident Synthesis.StreamSynthesize
service, concatenate validated 8 kHz PCM16 frames, prepend 3200 zero samples and
write a mono WAV. Do not overwrite this version; record new hashes for new output.
Upstream model/code declare Apache-2.0; existing licensing review and provenance
requirements in docs/LICENSING.md still apply. No new project license is adopted.
