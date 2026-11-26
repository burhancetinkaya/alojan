# Pocket Turkish voice selection — 2026-10-27

TTS-01 / M2-02 / AGP-03/06; US-01/02/05; requirements §8.2/11.2; ADR 0015.

## Result

Six bundled Pocket voices are available through the existing agent voice selector,
HTTP drafts and management MCP schema. EMA remains available and the default.
Preparation and runtime resolve the same pinned model and speaker; changing voice
invalidates old prepared audio. Pocket uses release v11. Historical EMA identities
and versions remain intact. Migration 0030 extends the voice constraint without
rewriting existing profiles. Unknown/unloaded capabilities fail closed.

The Linux serving deployment was updated at 20:39:39 UTC using the existing drain,
worker-quiescence and readiness gates. Compatible management, agent, background,
voice-preparer, TTS and web artifacts were installed. Phone bindings were compared
before/after and remained identical. Route readiness and open admission were
acknowledged; the pinned preparer is active. Public login and health returned 200;
unauthenticated management MCP returned 401. No external notification was sent by
this validation. No Nazli draft/release or live number assignment was changed.

## Automated evidence

All checks below ran on the primary Linux host, not simulated Mac inference.

- Focused Python suite: **112 passed**, 24.63 s. Covers audio conversion/clipping,
  producer budget, asset/model identity, publication v11, EMA rollback, backend
  isolation, cancellation slot retention, voice jobs and worker maintenance.
- Call initialization, routing, management MCP, scoped records, lifecycle actions
  and response-experience regressions: **79 passed**, 45 s.
- Isolated HTTPS browser suite: **49 passed**, about 1.3 min. Includes saving,
  reloading and switching female/male Pocket voices and returning to EMA. Disposable
  database, synthetic accounts and fake transports; no live customer changes.
- TypeScript checking, production web build, Ruff check and formatting passed.
  Final Ruff scope: 40 files. `git diff --check` passed.
- Frozen TTS dependencies and model integrity verified. Existing EMA 1.1.2 and
  torch 2.6.0+cu124 remained unchanged. Pocket 3.3.0, Turkish wrapper 0.1.0 and
  soxr 0.5.0.post1 are pinned. All nine model/reference file hashes verified.

## Real synthesis checks

An isolated candidate container loaded the actual EMA CUDA and Pocket CPU models,
then exercised the same RPC service used by the application. No CPU quota was set
in the final run, matching the serving TTS deployment; candidate memory was bounded
to 6 GiB. Each voice synthesized the same short Turkish phrase, was interrupted
during a longer request, and successfully synthesized again after native cleanup.
PCM framing/sequence checks passed, and EMA worked both before and after Pocket.
Single admitted synthesis capacity was preserved.

| Voice | First PCM frame (ms) | Generation (ms) | Audio duration (ms) |
| --- | ---: | ---: | ---: |
| EMA, before | 24.32 | 53.73 | 2120 |
| Pocket female 1 | 55.49 | 602.49 | 2800 |
| Pocket female 2 | 50.47 | 543.36 | 2560 |
| Pocket female 3 | 57.84 | 679.86 | 2960 |
| Pocket male 1 | 54.28 | 498.85 | 2480 |
| Pocket male 2 | 43.76 | 700.22 | 2800 |
| Pocket male 3 | 49.28 | 522.80 | 2400 |
| EMA, after | 6.60 | 17.29 | 2120 |

These are warm single-sample measurements, not P50/P95, RTP playout latency, stress
capacity or end-to-end conversation measurements. Earlier four-CPU-quota trials
were materially slower; a misleadingly named private `rpc-unthrottled.log` still
had that quota and is not used for the table above. Final evidence is `rpc-final.log`.

Real evaluation found a valid vocoder sample at 1.02007 full scale. The adapter now
clips this small overshoot, as upstream WAV export does, rather than aborting the
utterance. Malformed/nonfinite audio is still rejected. A fresh stateful resampler
per generation prevents chunk seams and cross-call filter history. Native producer
length is capped before its threads start because upstream has no queue-budget API;
the pinned private estimator hook must be reviewed on dependency upgrades.

Six private 8 kHz Nazli greeting previews were generated from authored text. Female 2
is the displayed sample (6.46 s audio; direct generation 1.289 s). Preview generation
is separate from publishing a prepared asset pack or answering a telephone call.

## Deployment identities and limitations

The serving image IDs are:

- TTS: `f70f53561c65d0be3e01f53a0e0e07944ca2bbe0b3b42997335186ec6f22f9fd`
- Agent: `61aa026c9be5231879a81589e06ce9c051d3c37e4a0e70d551f5d534a11fe719`
- Background: `0fb18f5976789fe92cf1bf684b75b58b506e2909939af134fd3f93f9d7235afc`
- Management: `a46c7ec5dc90c0f11a362f9bbba40ac4e0e148542ff323d5c0088d8a8767319b`
- Web: `161d2b103b6a5c2c21ab78a233b92c219918bf4a53418cfed6219f69550728a7`

Private rollback configurations, deployment receipt, RPC logs and previews remain
outside Git. New scope does not introduce user voice cloning uploads, emotion
controls, a second concurrent synthesis lane or a new HTTP inference application.
Pocket CUDA, carrier listening, language/pronunciation quality across a broad corpus,
resource soak and multi-call performance are not qualified by this run. C++ source
was unchanged; native CTest, hosted CI and clang-tidy were not rerun for this slice.
See LICENSING.md for upstream provenance and redistribution review boundaries.
