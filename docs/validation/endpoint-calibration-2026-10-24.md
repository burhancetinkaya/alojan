# Endpoint scheduling experiment

Tasks: M3-01 / M4-01 / M5-03; requirements §3, §7.1–4, US-04/05/06.
Owner approved the [endpoint plan](../ENDPOINT_LATENCY_PLAN.md), excluding LLM
optimization. Current status: **deployed by the owner’s subsequent explicit request**;
the protected pause-quality gate remains failed on both baseline and candidate.
The initial experiment and rejected quality result below are retained; see the
live-activation addendum for deployment and smoke-test evidence.

## Implementation

The Linux live source was copied into an isolated test snapshot. The Mac changes
are in the attached `codex/endpoint-latency` worktree. Do not synchronize the whole
Mac tree to the live listener: it also contains inherited, unrelated unfinished
work. LLM source, model/provider, prompt, tools and reasoning settings were not
changed by this task.

- One content-free `endpoint_diagnostics` record per normal recognition teardown
  describes the final quiet epoch: candidate/score/covered-partial/stable-partial
  readiness, last blocking observations, detector jobs, PCM coverage, probability,
  and accepted boundary. Readiness offsets are PCM-domain silence offsets;
  `partial_stable_wall_ms` and `elapsed_wall_ms` use a monotonic wall clock.
  Unknown score age/readiness is -1. These overlapping observations are not
  additive durations. Queue telemetry is buffered audio duration, **not measured
  wall-clock residence age**. Media callbacks do not format or emit records.
- Additive `AudioFrame.partial_hint = 9` asks recognition to spend its next
  periodic partial decode up to 400 ms early. The next deadline remains on its
  existing budget; repeated hints cannot request a decode on every frame. The
  minimum first hinted decode is 600 ms. This is advisory scheduling, never
  permission to finalize a turn. Old senders default to false; old receivers
  ignore the added field. Final decoding, generation validation, cancellation,
  the one-inference limit and all existing frame bounds remain in place.
- The gateway's `--turn-partial-hint 1` is explicit and **off by default**. It needs
  real speech, a current positive completion score, the existing silence/onset
  guards and stale transcript coverage. Fresh scores may be reused while waiting
  only for coverage; speech resumption and the existing one-second age limit
  invalidate them. The ordinary 500 ms open-answer floor, 200 ms stability/onset
  guards and 1200/2200 ms uncertain/incomplete waits are unchanged. No 450/400 ms
  acceptance threshold was introduced.

Hinting has a bounded advance budget, not a universal equal-work guarantee: a
final decode can still differ near an interval boundary. Resource and transcript
comparisons therefore remain release gates, not assumptions.

## Diagnostic and real-API pilot

The unchanged-decision diagnostic run completed a two-turn synthetic PCMA call
using resident real Whisper/EMA and the unchanged OpenRouter agent. On its closing
turn, a score was ready at 364 ms of silence, while current transcript coverage
arrived at 844 ms. The detector had run twice; the input queue was empty. Its first
message already met the 500 ms floor, so reducing a timer would not explain the
closing delay.

An opt-in pilot used a temporary patched Whisper worker with the same pinned
model/settings, resident EMA and unchanged real API agent. Both turns and isolated
note/summary/hangup validation passed. Closing endpoint silence was 516 ms and
one detector job was used. This is a pilot with regenerated synthetic input, not
a paired speed estimate or handset measurement. Neither live service was replaced.

## Frozen paired replay and early rejection

A fixture manifest was frozen before the run: 100 continuing-turn cases (five
synthetic two-part utterances × 0.5/1/1.5/2 s pauses × five clean/quiet/noisy codec
conditions), plus 50 completed-turn cases. PCMA and PCMU transformations precede
replay. Both profiles receive identical PCM with counterbalanced order. The quiet
noisy condition was reserved as holdout; no tuning on its results occurred.

`endpoint-replay-probe` reuses the actual C++ SpeechBridge and real CPU detectors
with paced input and a temporary real CUDA Whisper worker. Only response synthesis
is fake: this probe measures endpoint acceptance, not full response audio or LLM
latency. Labeled input end and the accepted audio boundary identify premature
finalization; continued suffix audio is not silently reclassified as another turn.
All clips are synthetic and remain private; no caller recording was enabled.

After **46 completed runs / 23 pairs**, the fixed quality gate was already
unachievable. The test was deliberately stopped, retaining all observations and
the next interrupted probe. This is an early rejection, not a completed 300-run
benchmark; no 50-turn candidate percentile or full resource/capacity acceptance
is claimed.

| Observation | Baseline | Opt-in candidate |
|---|---:|---:|
| Continuing-turn pairs observed | 16 | 16 |
| Premature endpoints | 9 | 9 |
| Completed-turn pairs observed | 7 | 7 |
| Completed-turn endpoint median | 984 ms | 696 ms |
| Completed-turn endpoint maximum | 1016 ms | 716 ms |
| Whisper decodes across all 23 pairs | 113 | 113 |
| Sum of measured Whisper decode wall time | 13294.23 ms | 13227.51 ms |
| Measured ASR process CPU time during decodes | 155554.14 ms | 155754.35 ms |
| Completion-detector jobs | 75 | 65 |

The nine premature cases were the same in both profiles: no additional or removed
cutoff was observed in this small paired subset. They involved continuing clauses
or numbers after pauses; they are existing quality weaknesses exposed by the new
fixtures. Final ASR text matched exactly in all 23 pairs, which does **not** mean
that the premature transcripts contained the omitted continuation.

Decoder measurements were joined by a uniquely matching ordered coverage sequence;
every terminal decoded-audio position matched its probe's accepted position.
The ~0.5% wall-time reduction and ~0.13% CPU increase are within uncontrolled
measurement variation, not evidence of a resource improvement or a capacity
promise. There was no extra decode in this observed subset. The temporary extra
Whisper instance was used only for isolation and was stopped afterward.

Even if every remaining continuing fixture had passed, the candidate would still
have at least 9 failures out of the planned 100. It therefore cannot meet the
approved strict <2% cutoff gate. Existing baseline failures do not waive that
criterion. No observed candidate-only regression is a different claim from passing
absolute acceptance.

## Verification and remaining work

The initial isolated setup omitted model metadata and the fake TTS test package;
those setup failures were retained and corrected before final checks. They are
not inference-quality results. Final Linux checks:

- Native build succeeded; **9/9 CTests passed in 2.48 s**, including score reuse,
  expiry/resumption invalidation and concurrent queue diagnostics.
- **47 ASR pytest checks passed in 3.15 s**, including hint-budget abuse, a cleared
  hint, final coverage and the existing cancellation/identity/failure cases.
- **38 SIP integration cases passed in 569.15 s**: adaptive endpoints, diagnostics,
  silence recovery, cancellation, music and dialogue teardown. Inference in this
  suite is explicitly fake; real CPU turn models are used where required. One
  existing Python `audioop` deprecation warning remains.
- Changed C++ clang-format and Python Ruff lint/format checks passed. Task diff
  review and whitespace checks passed; generated bindings use the existing pins.
  The isolated worktree graph index was refreshed. No hosted CI or clang-tidy
  result is claimed.
- Final live ASR/EMA/agent health was SERVING; agent source and live gateway binary
  hashes matched the prior baseline. Test DB schemas were removed. The temporary
  endpoint ASR process was stopped. Other GPU work was visible on the shared host
  at final inspection; no GPU-capacity or universal resource-neutrality claim is
  made from this experiment.

No live activation, source replacement, recording, external notification, push or
merge occurred. The live listener retains the accepted version and the experimental
flag remains off. The 450/400 ms threshold experiments and owner phone validation
were not advanced after the failed quality gate. The complete 100-continuation /
50-completed sample, broad resource/soak verification and carrier acceptance remain
open. The next endpoint change must address general pause/incomplete-turn evidence
before rollout; this task does not authorize an LLM or prompt workaround.

Private Linux evidence: `.local/endpoint-latency-20261024/evidence/`, including
`replay/cases.json`, `holdout.json`, `manifest.txt`, `probe.log`, `progress.json`,
`early-stop.json`, `summary.json`, ASR observations and diagnostic/pilot logs.

## 2026-10-24 — Owner-directed live endpoint activation

M3-01 / M4-01 / M5-03; requirements §3, §7.1–4, US-04/05/06. After the quality
result was reported, the owner explicitly requested deployment of the new version.
The tested Linux gateway, ASR scheduling service and compatible protobuf bindings
were installed during an idle period. `ALOJAN_TURN_PARTIAL_HINT=1` enables the hint
in the private carrier configuration; the launcher defaults to zero elsewhere.
LLM/agent source, provider, prompt, reasoning, Whisper model/decoder configuration,
EMA, admission limit and the three-second answer delay were preserved.

The live gateway is listening on the carrier UDP port with the flag enabled. ASR,
EMA and agent health checks all returned SERVING. A two-turn synthetic PCMA
loopback using the deployed ASR worker, matching native binary, real CUDA speech
models and the existing OpenRouter configuration passed response, summary and
hangup checks. Endpoint silence was 500/504 ms; estimated VAD-end-to-first-output
was 3141/1463 ms. This is one functional smoke check, not a latency distribution
or handset measurement. The prior 47 ASR, 9 CTest and 38 SIP regression passes
remain the implementation evidence; no full regression rerun is claimed here.
Launcher shell syntax checks passed on Mac and Linux.

The earlier absolute pause-quality gate still failed: 9 of 16 tested continuation
pairs cut early in both versions, with no additional candidate-only failure in
that subset. Owner-directed activation is not a passing quality gate. Full replay,
soak/resource acceptance and a real carrier call on this release remain pending.
No external notification, recording, Git push or merge was performed.

Private rollback: `.local/before-endpoint-live-20261024-145055/` contains the previous
binary, selected source/bindings, launcher/configuration and process definitions.
It contains private configuration and must remain ignored and access-restricted.
Rollback requires an idle gateway, restoring those files and restarting only the
carrier gateway and ASR worker on port 15173. Disabling the hint alone does not
restore the previous detector implementation. Private validation evidence:
`.local/endpoint-latency-20261024/evidence/live-deploy-01/` and
`live-deployment-health.json` alongside it.

## 2026-10-24 — Carrier connectivity follow-up after activation

The owner initially reported a call not connecting. At inspection the gateway was
running but had no new incoming-call event. Local and Mac-to-Linux SIP OPTIONS
probes both returned 200 OK; the advertised public IP matched observed egress,
and all previous carrier network arguments were preserved. No configuration change
or rollback was made. A subsequent owner call arrived and reached CONFIRMED after
3053 ms (200 answer at 3008 ms). Its first three completed response turns had no
reported pipeline error, endpoint silence 696/684/708 ms and estimated
VAD-end-to-first-output 1834/1383/1386 ms. These are server measurements, not handset
latency or subjective quality acceptance. The first failed attempt's cause is
unresolved; absence of an application call event does not prove where it failed.
The new release has now received a real carrier call; the pause-quality gate and
broader acceptance remain open. Personal transcripts were not copied into docs.
