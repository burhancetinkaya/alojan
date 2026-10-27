# Prepared waiting speech: resident EMA comparison

Date: 2026-10-27. Owner requested continued measurements.
Mapping: VXP-01/02/06, PERF-02/03, M2/M4/M5, US-04/05/06/08; ADR 0014.
This qualifies a limited playback experiment, not production rollout or carrier acceptance.

## Method and operational isolation

The primary Ubuntu host used its existing resident EMA service and CUDA GPU.
One synthetic voice pack was generated in the existing fenced preparation window;
the waiting clip is 1.92 seconds. Both experiments reused the exact same pack.
Each comparison ran four sequential calls in baseline/candidate/candidate/baseline
order: 14 turns per call, 28 per variant, 56 total. The two completed comparisons
therefore cover 112 turns, excluding the six-turn smoke and aborted trial.

Native PJSIP, gRPC, PCMA/RTP and EMA synthesis are real. ASR is scripted, input
is synthetic audio, replies are fixed Turkish fixtures, and authorized-operation
delays are controlled at 50, 1600, 2100 and 3000 ms. No external MCP operation,
OpenRouter answer generation, real caller transcript or notification is involved.
Tests use disposable database schemas, a synthetic DID and isolated native gateways.
The serving gateway binary, profiles, number bindings and Jev flag were not changed.

Each operator window held the preparation advisory lock, stopped the idle preparer,
closed call admission, verified drain and worker quiescence, and reopened only the
existing TTS worker for leased synthesis. Identity/gate checks continued during the
experiment. Cleanup verified fresh readiness and reopened normal service before
restarting the preparer. Final recovery: no journal, all gates open, routes ready;
gateway, agent, ASR and TTS healthy. The verified window lasted 275.1 seconds.

## Finding and correction

The initial candidate inserted one 20 ms waiting fade frame before useful PCM.
The first 56-turn comparison showed paired useful-answer deltas of median +20 ms
and P95 +60 ms; ready-PCM-to-output P95 was 37 ms versus baseline 18 ms.
Aggregate answer P95 increased by only 20 ms, illustrating why that statistic alone
was insufficient to dismiss the extra frame.

Playback now blends the next waiting samples into the first 5 ms of the available
response frame and leaves its remaining 15 ms unchanged. There is no inserted frame,
allocation, lock or I/O in the media callback. An unsent waiting clip is suppressed;
preempted audio never resumes. Sent accounting remains at 20 ms frame resolution;
the mixed frame contains both waiting and response samples and belongs to both
receipts, so their durations must not be summed as exclusive wall-clock intervals.

A strengthened regression using negative response PCM caught unsigned arithmetic
in the first crossfade attempt. It was corrected to signed weights. An inadvertently
started intermediate benchmark was stopped and its normal-service recovery verified;
it is excluded from results. The final comparison started only after all 11 native
tests passed with the corrected signed arithmetic. Neither intermediate binary was
installed into the serving container.

## Verified comparison

Values are milliseconds, nearest-rank P95, 28 response turns per variant.
Useful-answer timing excludes waiting speech.

| Metric | Baseline P50 / P95 | Prepared waiting P50 / P95 |
| --- | --- | --- |
| Endpoint to first useful audio | 2159.5 / 3080 | 2139 / 3079 |
| Ready PCM to output | 8.5 / 17 | 11.5 / 20 |
| Agent first response phrase | 2139.5 / 3059 | 2122.5 / 3059 |
| Warm EMA first chunk | 11.5 / 15 | 10.5 / 16 |
| Endpoint to waiting audio | No waiting | 1829.5 / 1859 |

The 16 expected slow candidate turns each emitted exactly one waiting segment;
all other turns emitted none. Segments sent 320–1280 ms before preemption, with
partial receipts and no invented transcript words. All 56 turns completed without
gateway errors/fallbacks; call leases and agent streams closed. Waiting uses the
preloaded clip and requires no call-time TTS request.

Paired candidate-minus-baseline useful-answer median is 0 ms, P95 +40 ms,
maximum +40 ms. Paired PCM-to-output median is 0 ms, P95 +16 ms. Cohort useful-answer
P95 difference is -1 ms. This supports removing the extra-frame delay; it does not
show that waiting feedback makes backend work faster.

A descriptive 5,000-resample turn-pair bootstrap gives P50 difference interval
[-39, +20] ms and P95 [-21, +22] ms. Four calls contain correlated turns, so these
are exploratory intervals, not rollout confidence or full PERF-02 acceptance.
The initial candidate's corresponding upper P50 bound was +59 ms.

GPU samples every approximately two seconds: 130 samples in each run. Initial run
4082–4084 MiB, verified run 4082 MiB; observed utilization maxima 4% and 2%.
Sampling can miss short kernels/peaks. ASR was quiescent, so these values establish
neither ASR/EMA contention safety nor admitted-load capacity.

## Verification outcomes on Ubuntu

| Check | Outcome |
| --- | --- |
| Initial resident EMA ABBA run | 4 passed, 268.66 s |
| Corrected resident EMA ABBA run | 4 passed, 268.53 s |
| Native build and CTest after signed-sample fix | Build passed; 11/11 passed, 3.79 s |
| Response lifecycle, measurement-report rejection and scripted native SIP regression | 16 passed, 27.10 s |
| Changed Python Ruff check | Passed |

Both SIP runs and the focused regression suite reported the existing Python
`audioop` deprecation warning. The failed negative-PCM test and aborted trial are
documented above and are not counted as successful validation.

## Reproduction and remaining gates

The opt-in test is `tests/sip-integration/test_waiting_ema_live.py`; the report tool is
`tools/report-waiting-ema.py`. See the protected-window procedure in DEV_SETUP.
The report rejects missing/failed/partial turns, wrong ABBA order, duplicate or
missing waiting segments and unmeasured timing. It always reports full product
acceptance as false. Private synthetic artifacts are under
`.local/voice-measurements-20261027/{full,refined-verified}` on the primary host;
the aborted `refined` folder is not accepted evidence.

Still required: full ASR/endpointing/answer-model comparison with actual tools,
interruption/music/final-ready races, admitted-load contention and longer soak,
human listening/handset quality, coordinated rollout and rollback verification.
No dynamic waiting TTS, Jev-driven speech selection or live release was activated.
