# Turkish EMA prompts, version 3

Synthetic AI-generated announcements produced on the authorized Ubuntu RTX 4080
server on 2026-10-23. The owner accepted the v2 EMA voice as clearly intelligible and requested
that the greeting name Burhan Çetinkaya. This version applies that request.
The owner accepted the delivered named greeting on 2026-10-23. This is local
listening acceptance; carrier intelligibility remains untested.

| Text | Phone file (8 kHz) | Preview (48 kHz) | Duration |
|---|---|---|---|
| Merhaba, ben Burhan Çetinkaya’nın yapay zekâ asistanıyım. | greeting.wav | greeting-48000.wav | 3.08 s |
| Şu anda mesaj alamıyorum. Lütfen daha sonra tekrar arayın. Hoşça kalın. | unavailable.wav | unavailable-48000.wav | 4.00 s |

All files are mono PCM16 WAV, aligned to 20 ms. The default gateway plays the two
8 kHz files, then closes because the live speech/agent pipeline is absent. The
48 kHz files are listening previews and are not accepted by the phone WAV player.
No microphone, caller recording or reference speaker audio was used.

## Provenance and reproduction

- EMA Lightning 1.1.2; PyTorch 2.6.0+cu124 on the NVIDIA RTX 4080.
- Model: [canberkkkkkk/ema-lightning at e7c96f2fc0ba843cd0f86e02786655bb56f50df8](https://huggingface.co/canberkkkkkk/ema-lightning/tree/e7c96f2fc0ba843cd0f86e02786655bb56f50df8).
- Seed 0, speed 1.0, one EMA instance, `lightning(batch_size=1)` followed by
  `stream()` for each text/rate. EMA's built-in resampler handles 8 kHz output.
- The greeting uses the owner-requested name; the closing text is unchanged.
  Both texts were synthesized again for this version. WAV/text
  hashes, checkpoint hashes, package versions, timings and memory measurements
  are in `manifest.json`.

Use the [isolated generator instructions](../../../tools/ema-prompts/README.md).
No GPU/model installation is needed to play or transport-test the checked-in WAVs.
The model is not loaded by the gateway, and startup still reports
`voice_pipeline_ready=0`. See [validation evidence](../../../docs/validation/linux-named-greeting-2026-10-23.md)
for the precise tested scope and remaining acceptance.

Upstream code/weights declare Apache-2.0; preserve upstream notices and the pinned
provenance. This does not adopt an Alojan/asset license or establish blanket
redistribution clearance. Review all dependencies and generated-output terms
before release under [LICENSING](../../../docs/LICENSING.md). Internal generation
and listening were explicitly requested by the owner under ADR 0004.
