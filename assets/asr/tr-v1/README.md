# Synthetic Turkish ASR evaluation fixtures, version 1

These two project-authored texts were synthesized on the authorized RTX 4080 with
pinned EMA Lightning 1.1.2 on 2026-10-23. `date-time` exercises a fictional name,
date and time; `phone` exercises a synthetic number spoken in groups and a callback
request. Neither is a caller recording or a real contact record. Do not dial the
synthetic number or treat it as assigned/unassigned carrier evidence.

The generator is the existing `tools/ema-prompts/generate.py`, using seed 0,
speed 1.0, batch size 1 and the same pinned EMA model as the approved introduction.
To reproduce without changing deployed prompt files, put `date-time.txt` in a
fresh input directory as `greeting.txt` and `phone.txt` as `unavailable.txt`, then:

```sh
uv run --frozen --project tools/ema-prompts python tools/ema-prompts/generate.py \
  --text-dir .local/asr-eval-text --output-dir .local/asr-eval-ema-new
```

The resulting `greeting-48000.wav` and `unavailable-48000.wav` are renamed
`date-time.wav` and `phone.wav` here. The manifest preserves their generation
hashes, package/model pins and signal metadata. The original generator's deployment
profile label is not used for this separate evaluation set. Both are 48 kHz mono
PCM16, with final 20 ms alignment; no reference speaker or microphone was used.

The evaluation tool verifies hashes and uses Python 3.12 `audioop.ratecv` for
48→16 kHz conversion. This offline test conversion is not the gateway resampler
and must be replaced before moving the test tooling to Python 3.13. The accepted
owner introduction/closing are reused from `assets/prompts/tr-v3-ema`; one second
of zero PCM is generated in memory for silence regression.

This is a small synthetic smoke set, not independent human speech or a validated
Turkish benchmark. Human listening of these two evaluation files is not claimed.
Model-output number formatting is checked separately from literal word edit counts.
No reference text or correct answer is supplied as a Whisper decoding prompt.
Upstream EMA code/weights declare Apache-2.0; project/output distribution approval
and the complete dependency/license review remain pending.
