# Waiting music v1

Original procedural instrumental prepared for Alojan, with no third-party music,
recordings, samples or external generation service. The score and renderer live
in `services/voice-gateway/src/waiting_music.cpp`; there is no runtime asset download.
This provenance does not introduce or approve a project redistribution license.

A six-second loop uses four gentle sine-based notes and a quiet sustained harmony,
with smooth note envelopes and a zero-level loop seam. Native construction prepares
48,000 mono PCM16 samples at 8 kHz before callbacks run. Playback only copies 20 ms
frames. Measured pre-codec peak: 1156 / 32768 (about -29 dBFS); RMS: 419.755
(about -38 dBFS). There are no drums, vocals or loud accents. These fixed levels
are an initial quiet profile; handset loudness and owner preference need listening.

After 800 ms waiting for the first agent response, the gateway plays the loop.
The first available speech frame takes priority immediately, with no music queued
behind it. Music does not resume between speech phrases. Interruption, cancellation,
call termination and failure stop it through the existing generation/state guards.
It enters the echo reference, but never speech playback receipts, transcript,
confirmation state or substantive-response timing. `waiting_music_ms` accounts for
music independently. The agent no longer emits the former spoken waiting phrase.

The native `waiting-music` test guards amplitude, non-silence, deterministic looping
and seam continuity. Native dialogue tests cover both G.711 codecs, fast responses,
waiting-to-speech transition, history isolation and interruption during music.
