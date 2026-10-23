# Native interruption development evidence — 2026-10-23

Task M3-02, requirements US-05/US-06 and sections 7.3–7.4; G4 remains partial.
Branch `codex/barge-in`, Linux primary execution under ADR 0003. This implements
the opt-in interruption core on top of M3-01, not the M4 agent. Existing owner
changes, including the staged hosted-workflow removal, were preserved. No commit,
push, PR, merge, model replacement or live gateway restart was performed.

## Behavior and boundaries

The native bridge now listens during synthesized output, correlates incoming
PCM with a bounded outbound reference, applies isolated Silero state and fresh
partial ASR coverage, suppresses brief lexical acknowledgments, and invalidates
an interrupted output generation before network cancellation. Tagged queued PCM
cannot reappear under the next generation. Two seconds of bounded echo-filtered
pre-roll hand the interruption into the next recognition stream. Old workers
finish before contexts are replaced; calls and generation IDs remain isolated.

The main event loop reports privacy-safe decision/generation/send metrics. The
media callbacks do no inference, RPCs, logging or dynamic allocation. The output
reference queue is bounded at 64 frames; overflow fails safely. At most eight
responses fit inside the existing call deadline. Input remains bounded at 64
20 ms frames; output remains bounded at 32. Cancellation cannot retract an
already handed-off frame. Reference PCM, pre-roll and transcript hypotheses are
in memory only; no caller recording is enabled.

Sent history stores output-port duration per generation. A partially sent
utterance gets **no text**, because EMA currently supplies no word alignment.
Only a complete utterance contributes its known text. This avoids attributing
unsent words to the assistant but loses the text of an interrupted prefix; M4
must introduce phrase alignment and pass this conservative history into the agent.
There is no LLM stream yet to cancel. The opening WAV is not interruptible in this
profile; the generated response is. No change to the approved AI introduction.

## Native deterministic and synthetic integration checks

Eight CTests pass, including the new interruption policy/reference test. It
checks brief acknowledgments, corrections, stale ASR text, expired candidates,
sustained speech, attenuated/inverted/delayed echo, independent input, double-talk
and silence. Existing conversion, metering, caller identity, turn detector and
queue-concurrency checks remain enabled.

The new SIP suite uses the real native CPU models and actual SIP/RTP/gRPC with
explicit fake inference. It covers both G.711 codecs, correction/re-recognition,
queued old-generation discard, distinct new-generation audio, silence, a short
voiced acknowledgment with a synthetic lexical hypothesis, delayed speech echo,
hangup/reuse, seeded background noise, invalid monitor coverage and invalid CLI.
Model-artifact skips are explicit and are not passes. Synthetic acknowledgment
classification is not a claim of real human ASR accuracy.

The first eight-case run passed in 146.48 seconds. A subsequent full-suite run
exposed a test-fixture weakness: the cropped 400 ms fragment sometimes produced
fewer than 192 ms of voiced blocks, so there was correctly no interruption but
also no proven backchannel classification. The assertion was retained and the
fragment replaced with a complete EMA-generated `Evet.` fixture (440 ms), pinned
under `assets/interruption/tr-v1`. Three packet-phase variants (0/20/40 ms prefix)
exercise the native VAD boundary; synthetic ASR remains explicitly labeled.
No production threshold was relaxed to make this test pass. During PCMA/PCMU correction
checks the last old-tone RTP packet arrived respectively 0.91/2.76 ms **before**
the invalidation timestamp. Queued unsent old PCM was present and discarded;
new output was independently identified at 660 Hz instead of the old 880 Hz.
The check permits up to 100 ms for already-buffered transport and fails on any
old-tone replay later in the call. The initial four-case run also passed; these
are development runs, not independent repetitions for an SLA.

## Real CPU/CUDA model calls

The test used the pinned native Silero/Smart Turn models, one temporary updated
large-v3-turbo CUDA ASR process and the already resident EMA worker. The old ASR,
EMA and live gateway were preserved. The temporary process group was removed
in a finally block. Input was the pinned synthetic Turkish phone fixture.
Both calls interrupted the first EMA reply, recognized the continuing utterance
and delivered the full next EMA reply without a fallback.

| Metric | PCMA | PCMU |
|---|---:|---:|
| Synthetic input start to interrupt decision | 671.78 ms | 707.03 ms |
| Last output-port send minus interrupt decision | -2 ms | -2 ms |
| Silent RTP frames in the 100–500 ms post-decision window | 20 | 20 |
| First generation sent duration | 680 ms | 720 ms |
| First generation aligned text bytes | 0 | 0 |
| Second generation sent duration | 4000 ms | 4000 ms |
| Second generation aligned text bytes | 78 | 78 |
| Complete second response relative RMS error | 0.013384 | 0.014022 |

The reference comparison checks the full reply, not merely nonempty audio.
The sampled host GPU peak was 4,995 MiB, including both ASR instances plus EMA.
It is not the normal single-ASR footprint. The reported decision delay starts at
synthetic input injection, not a manually labeled human speech onset. Two calls
are not P50/P95 evidence; stopping after an accepted decision is distinct from
detecting that decision. The <250 ms speech-onset-to-stop target remains unmet.

Gateway SHA-256: `2a230b7d0824415175f47ca91bdf7b68558f88f1aaf5e3bcc0fe3cb2c1ed4a69`.
The separately running live gateway still mapped the accepted original binary
`624ed461fce0832c89da2e3cbee5c97ecdc10a73377261417ec0f1948238036c`.
Ignored Linux diagnostics: `.local/barge-tests.log`, `.local/barge-cuda-final/result.json`,
`.local/barge-asr.log`, `.local/barge-gpu.csv`, `.local/barge-full-suite.log`.
No carrier recording or personal transcript was retained.

## Build and hygiene checks

The Linux native build passed. All eight CTests passed in 2.31 seconds. Ruff check
and formatting passed for 38 Python files; all changed C++ files passed the pinned
clang-format check. The separate `build/no-turn` voice gateway and interruption
unit target also built; the unit check passed and enabling adaptive interruption
without model support was rejected before readiness. No protobuf or dependency
lock change was needed. Documentation links and `git diff --check` passed.

The corrected complete-word acknowledgment fixture passed all three 0/20/40 ms
phase variants in 59.01 seconds (9 unrelated interruption tests deselected).
This targeted regression is separate from the initial full-suite run containing
the now-replaced fragment. No C++ behavior changed after the real GPU validation.
Both preserved resident speech services reported `SERVING` after the tests.

The full Linux pytest invocation completed with **184 passed, 1 failed**, no skips,
in **623.47 seconds**. Its only failure was the cropped acknowledgment fixture
explained above. The corrected final fixture then passed **3 phase variants** in
**59.01 seconds**; the other 184 cases were unchanged. Final covered cases are
therefore 184 unchanged passes plus 3 replacement passes (187 unique cases).
There was no second all-suite invocation after the fixture-only correction;
these are explicitly separate runs, not a fabricated single 187-pass report.
The only warning was the known Python 3.12 `audioop` deprecation. The final graph
refresh reported 1,949 nodes and 4,287 edges, without persisted graph artifacts.

## Remaining acceptance

- Natural/noisy Turkish and real handset echo/double-talk calibration; 250 ms
  onset-to-stop and <3% false-interrupt targets require labeled broader evidence.
- Semantic/question-aware acknowledgments and polite clarification belong with
  M4 dialogue; the present lexical/duration rule is an explicit initial profile.
- Phrase-level sent-text alignment and actual agent/LLM cancellation integration.
- Opening-prompt interruption while preserving the required AI identity.
- The M3-01 seven-second reminder, runtime threshold settings and broader turn
  acceptance remain open; this change does not silently close them.
- Live adaptive/interruption carrier acceptance, Mac model revalidation,
  clang-tidy, hosted CI, production supervision and soak are unperformed.

M3-02's native core is implemented; full US-05/US-06/G4 acceptance remains partial.
