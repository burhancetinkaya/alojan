# Turkish M1 speech fixtures, version 1

These are synthetic, prerecorded development prompts for M1-03 (US-01, requirements
sections 6 and 8.2). They contain no human recording, copied speaker voice or caller
data. The original text is stored alongside each WAV. The default gateway plays
both files in this order and closes because the speech/agent pipeline is absent:

1. `greeting.wav`: “Merhaba, ben bu hattın sahibinin yapay zekâ asistanıyım.”
2. `unavailable.wav`: “Şu anda mesaj alamıyorum. Lütfen daha sonra tekrar arayın. Hoşça kalın.”

The introduction is 4.78 seconds; the unavailable/closing announcement is 6.58
seconds. Both are mono signed PCM16 little-endian, 8 kHz, padded with silence to a
20 ms frame boundary. `manifest.json` records exact sample counts and SHA-256 hashes
of audio/text plus generation settings. Normal tests consume these versioned files
without installing or executing a synthesizer.

## Provenance and usage boundary

Generated on the authorized Ubuntu 24.04.2 x86_64 development server on 2026-10-23
using eSpeak NG 1.51, Ubuntu package `1.51+dfsg-12build1`, voice `tr`, speed 155 and
amplitude 80. The executable was extracted into ignored `.local/prompt-tools`; no
system package or service was changed. The already installed library/data packages
have the same version. CPython 3.12.3 `audioop.ratecv` converted the synthesized speech
to 8000 Hz; this offline test-fixture conversion is not the future runtime speech
resampler. Replace it before upgrading to Python 3.13.

[eSpeak NG](https://github.com/espeak-ng/espeak-ng/tree/1.51) is a formant synthesizer
under [GPL-3.0-or-later](https://github.com/espeak-ng/espeak-ng/blob/1.51/COPYING),
with additional upstream/package notices. It is only a fixture-generation tool,
not the production EMA model selected by DEC-09. These robotic samples establish
speech playback/teardown, not EMA quality, naturalness or GPU readiness.

The wording was authored for this project and is not an external recording.
[GNU's output guidance](https://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL)
distinguishes generated output from copied copyrighted program assets; this does
not constitute a blanket redistribution clearance. Keep generation provenance,
text and checksums together. Internal development use is within the authorized
project work. Release/distribution, including any bundled generator/code/data,
requires the dependency review in [LICENSING](../../../docs/LICENSING.md); no
project or asset license is adopted here. The owner listened on 2026-10-23 and reported these prompts unintelligible.
Human listening acceptance therefore failed; retain these files only as historical
test fixtures. EMA replacements are authorized under ADR 0004. Automated RTP
fidelity remains separate from intelligibility.

## Reproduction on the pinned Ubuntu host

The executable package from Ubuntu's signed APT metadata has SHA-256
`ffeac730f1f43b5cdbca708a8215d6b7310bf3bd40d7dcf0affd6a62f86aa6df`.
The generator checks the extracted executable's checksum and installed library/data
versions. Start from the project root and download/extract only if not already present:

```sh
mkdir -p .local/prompt-tools
(cd .local/prompt-tools && apt-get download espeak-ng=1.51+dfsg-12build1)
printf '%s  %s\n' ffeac730f1f43b5cdbca708a8215d6b7310bf3bd40d7dcf0affd6a62f86aa6df .local/prompt-tools/espeak-ng_1.51+dfsg-12build1_amd64.deb | sha256sum -c -
dpkg-deb -x .local/prompt-tools/espeak-ng_1.51+dfsg-12build1_amd64.deb .local/prompt-tools/espeak-ng
uv run --frozen python scripts/generate-prompts.py \
  --engine .local/prompt-tools/espeak-ng/usr/bin/espeak-ng \
  --output-dir .local/prompts-reproduced
cmp assets/prompts/tr-v1/greeting.wav .local/prompts-reproduced/greeting.wav
cmp assets/prompts/tr-v1/unavailable.wav .local/prompts-reproduced/unavailable.wav
cmp assets/prompts/tr-v1/manifest.json .local/prompts-reproduced/manifest.json
```

The host also has `libpcaudio0 1.2-2build3`; upstream/package notices are installed at
`/usr/share/doc/libespeak-ng1/copyright`. Full tool/data release inventory is still
required before redistribution. Generation is offline after obtaining the package.
No ASR/TTS/agent model, external API or microphone is needed for these fixtures.
