# Endpoint latency calibration plan

Date: 2026-10-24. Status: owner-approved; diagnostics and opt-in experiment implemented. Quality gate
failed on baseline and candidate. The owner subsequently explicitly requested live
activation; the scheduling hint was activated with rollback retained. The absolute
pause-quality gate remains failed and carrier verification remains pending. See
[execution evidence](validation/endpoint-calibration-2026-10-24.md).
Tasks: M3-01 / M4-01 / M5-03. Requirements §3, §7.1–4; US-04/05/06.

## Owner constraints

Improve the wait between speech ending and accepting the caller's turn. Do not
optimize or change the LLM, provider, prompt, reasoning, tools or model-request
sequence. The owner identified a Qwen 3.6 35B deployment on Splash Engine as a
separate future comparison; its endpoint, model identifier and capabilities have
not been verified and it is not activated by this plan. Keep the currently
accepted conversation behavior and existing recording policy.

## Evidence and hypotheses

The [50-turn baseline](validation/response-latency-2026-10-24.md) measured endpoint
silence P50 824 ms, P95 880 ms, maximum 924 ms. These are detector-relative audio
timings, not independently labeled acoustic speech-end or handset measurements.

Source and live command-line inspection show default endpoint settings: candidate
250 ms, open answer 500 ms, uncertain completion 1200 ms, incomplete input 2200 ms.
Completion also requires 200 ms of stable text covering the last voiced sample,
a valid Smart Turn score, and the low-confidence speech-resumption hold. Whisper
partials are decoded every 16000 input samples (one second). The native question
context is fixed for the bridge; the 350 ms yes/no path is not evidence of an
active per-question classification feature.

A stale partial, its stability timer, detector scheduling or input backlog may
explain time beyond the 500 ms open-answer floor. Current aggregate logs cannot
attribute the extra time to one of these gates. Do not assume that a one-second
partial cadence adds a full second to every turn, or that reducing the silence
threshold alone will remove the measured wait.

## Proposed sequence

1. **Attribute endpoint waiting without changing decisions.** Add bounded,
   content-free per-turn diagnostics: last VAD speech/low-confidence activity,
   candidate entry, first current score and score age, partial coverage arrival,
   text stability readiness, queue/replay age and decision time/reason. Keep
   PCM-domain and monotonic wall-clock measurements distinct. Aggregate gate
   blocking/last-release information; do not log per-frame text/audio or sum
   overlapping gate durations. Use labeled synthetic audio boundaries to expose
   differences between actual fixture end, VAD end and acceptance time.

2. **Remove avoidable scheduling delay before shortening safeguards.** Compare
   baseline with one change at a time on an isolated Linux snapshot. First reuse
   a still-valid detector result and avoid redundant completion work while only
   transcript coverage is missing, if telemetry demonstrates that pattern. If
   partial freshness dominates, prototype a bounded silence-candidate-triggered
   partial that replaces/coalesces a scheduled decode, rather than globally
   doubling Whisper cadence. The candidate hint must remain advisory; it cannot
   finalize recognition or authorize a reply. Specify a backward-compatible
   control message only if the existing stream cannot express the hint. Retain
   one in-flight decode, cancellation/generation isolation, fresh coverage and
   final decoding; discard stale candidate requests when speech resumes. Compare
   decode counts and time per input-audio second, CPU, GPU and VRAM to baseline.
   Reject an approach that adds sustained load or harms ASR accuracy.

3. **Calibrate the high-confidence fast path only if a gap remains.** Keep the
   existing 500 ms open-answer setting as the first comparison. Evaluate 450 ms
   and then 400 ms only for fresh, high-confidence completion with stable,
   speech-covering text and no resumption/hesitation evidence. These values are
   experiments, not guaranteed safe defaults; the current CLI lower bound is
   500 ms and any experimental extension must remain explicit and opt-in. Keep
   the 1200/2200 ms uncertain/incomplete waits and 200 ms stability/onset guards
   in this first iteration. Do not classify all short utterances as completed,
   set the entire conversation to yes/no, or add model/prompt classification.

4. **Evaluate cutoffs, recognition and resource cost together with speed.**
   Establish the test set and holdout before tuning: at least 100 labeled
   continuing-turn cases covering 0.5/1/1.5/2 s pauses, numbers, dates, names,
   hesitations, corrections, quiet speech and background noise; plus 50+ completed
   turns for timing. Synthetic fixtures are distinct from human evidence. Exercise
   both G.711 codecs, resumption during pending decisions, stale scores/partials,
   interrupted generations, missing ASR and detector failures. Build and run
   affected C++/Python/SIP tests on Linux. Use paired baseline/candidate order and
   unchanged fixtures/model settings; report failures and missing samples. Keep
   final recognized entities and note inputs unchanged on regression fixtures.

5. **Release only the measured winner after phone validation.** Require no new
   cutoffs on protected regression cases, observed premature cutoff <2% and false
   interruption <3% on explicitly labeled applicable sets, no meaningful latency
   tail regression, and no sustained CPU/GPU/VRAM/decode-count increase beyond
   baseline measurement variability. Report sample sizes; these rates are not
   population guarantees. Initial goal for confidently completed turns is
   endpoint median around 500–600 ms, roughly 200–300 ms below the present mixed
   sample; confirm with a paired comparison rather than treating it as a promise.
   Keep conversational quality above a fixed speed target. Follow with owner-
   placed phone cases including a deliberate pause, correction and quiet answer.
   Preserve the existing baseline and a single-setting rollback. Do not activate
   a candidate merely because the synthetic benchmark is faster.

## Boundaries and delivery

The first implementation should cover diagnostics and the smallest justified
scheduling change, not all speculative options. Preserve media callbacks,
bounded queues, low-confidence onset protection, generation invalidation and
sent-audio accounting. No new speech model, denoiser, speculative LLM request,
external writes or raw caller recording is included. Greeting/ringing and the
three-second farewell hangup policy are unrelated and stay unchanged.

Deliver a before/after report separating endpoint decision delay from ASR final,
agent and TTS time, including errors, cutoffs and resource cost. Link results from
PLAN.md and CALL_TEST_PLAN.md. Total response latency targets and broader M5-03
acceptance remain separate; endpoint savings cannot remove model-request tails.
