# Current baseline response latency

Tasks: M4-01 / M5-03; requirements §3, §7.4, §9.1 and §12/15;
US-02/05/06. Scope: measurement of the accepted live baseline, without changing
the model, prompt, turn thresholds or deployment.

## Method

The fixed workload is 25 sequential two-turn synthetic PCMA loopback calls:
five message scenarios repeated five times in rotating order, followed by the
same explicit decline of further help and farewell. The message scenarios cover
a callback, a presentation delivery, being late to a meeting, a report sent by
email, and a product-related callback. Each includes a synthetic caller name and
declines to provide a phone number. No real caller transcript is used.

The existing `tools/validate-agent-call.py` runs a temporary loopback agent and
native gateway against resident CUDA Whisper (15173), EMA (15072), real OpenRouter
and a fresh isolated PostgreSQL schema per call. The local test uses zero answer
delay; the live three-second ringing policy is unchanged and is outside response
latency. A private harness substitutes only the first synthetic input text,
using the existing EMA input generator;
the validator, model and dialogue policy remain unchanged. Input audio is held
in memory. The validator checks two turns, note existence/unconfirmed status,
closing, termination and post-call summary persistence; it does not grade the
semantic accuracy or naturalness of every response or summary. Summary requests
occur after call teardown and are outside turn latency.

The snapshot was copied from the Linux live source, not the unaccepted Mac
dialogue candidate. It reuses the Linux native executable and resident speech
models. Configuration: `openai/gpt-oss-120b`, Cerebras-only routing with fallback
disabled, medium reasoning, temperature 0.2, maximum 4096 tokens, existing
streaming Responses path. Host: NVIDIA GeForce RTX 4080; initial sampled GPU
memory 6626 MiB, utilization 0%. Readiness returned SERVING for ASR, EMA and the
live agent before the run. No live service was restarted.

The run is warm and sequential. Repeated phrases and shared provider caches
are not reset. This is neither a cold-start nor concurrency/capacity experiment.
Five scenarios repeated five times do not constitute 50 independent scenarios,
human speech diversity, a noisy-handset sample or a production tail estimate.

## Timing boundaries

`tools/report-latency.py` reports completed substantive response generations.
Music and silence-recovery audio do not count as responses; failed, cancelled,
interrupted and missing observations must be reported separately. P50 is the
median; P95 is the nearest-rank observed percentile.

- **Endpoint to first output:** ASR half-close to the first substantive PCM
  handed to the gateway output port. This includes ASR finalization, agent work,
  first TTS chunk and output scheduling.
- **Estimated VAD end to first output:** the above interval plus the detector's
  PCM-domain endpoint silence. This is the closest existing diagnostic to the
  user's perceived wait, but it is not an independently labeled acoustic
  speech-end measurement. Input buffering/replay age and VAD uncertainty remain.
- **Agent first phrase:** includes database/context preparation and all model
  and tool steps before the first speakable response. It is not provider TTFT.
- **TTS first chunk:** request to first valid PCM, not complete synthesis.

Output-port delivery is not confirmed RTP arrival or handset playback. No
carrier transport delay is inferred. Stage percentiles must not be added to
construct an end-to-end percentile. The project targets remain P50 <1000 ms
and P95 <1800 ms for turn-end to first RTP playout across 50+ Turkish turns;
this limited synthetic proxy cannot by itself close carrier acceptance.

## Results

Run window: 2026-10-24 10:42:57–10:54:53 UTC (11 minutes 56 seconds).
All 25 call validators exited successfully. There are 50 completed agent records
and 50 completed substantive gateway response records, with no failures,
interruptions, cancellations, recovery turns, malformed records or missing
first-audio measurements. No samples were retried or discarded.

All values below are milliseconds. The estimated interval includes endpoint
silence; endpoint-to-output does not.

| Interval / group | Samples | P50 | P95 | Maximum |
|---|---:|---:|---:|---:|
| Estimated VAD end → first output, all | 50 | 1929 | 3464 | 5120 |
| Estimated VAD end → first output, message | 25 | 2504 | 3601 | 5120 |
| Estimated VAD end → first output, closing | 25 | 1643 | 1796 | 1823 |
| Endpoint → first output, all | 50 | 1259 | 2740 | 4260 |
| Endpoint → first output, message | 25 | 1739 | 2741 | 4260 |
| Endpoint → first output, closing | 25 | 799 | 940 | 999 |

The arithmetic mean estimated interval is **2176.34 ms**. Four of 50 responses
(**8%**) exceed 3000 ms; all are message responses (4/25, **16%**). An equal mix
of short closings and message-taking turns makes the combined percentile more
favorable than message-taking alone. The observed P95 is sample-specific, not a
guaranteed service bound.

| Stage | P50 ms | P95 ms | Maximum ms |
|---|---:|---:|---:|
| Endpoint silence | 824 | 880 | 924 |
| ASR finalization after endpoint | 120 | 139 | 148 |
| Agent request → first phrase, including preparation/tools | 1117.5 | 2575 | 4113 |
| TTS request → first PCM | 9 | 12 | 13 |
| First PCM → output port | 9.5 | 19 | 19 |
| Agent DB readiness (inside agent interval) | 15 | 25 | 44 |
| Sum of tool execution time per turn (inside agent interval) | 4.5 | 11 | 20 |

All 25 message turns required two model requests; all 25 closing turns required
one. Summed model-request duration per message has P50 1518 ms, P95 2519 ms and
maximum 4071 ms. Closing model-request duration has P50 651 ms, P95 789 ms and
maximum 857 ms. The 75 response-path requests reported nonzero cached input
in 74 cases, with no missing cache counters. This does not mean every input
was cached. All 50 free-text first-delta measurements are unavailable because
these responses use tools; they are not zero-duration TTFT observations.

The slowest response took an estimated 5120 ms: 860 ms endpoint silence,
133 ms ASR finalization, 4113 ms agent work, 8 ms first TTS chunk and 4 ms output
scheduling, with a 2 ms residual across the measured boundaries. Its two model
requests took 1000 and 3071 ms, respectively, and reported 300 and 100 output
tokens. The telemetry includes API transport, provider processing and SDK work;
it cannot determine whether provider queueing, network delay or inference
caused the second request's tail. It does show that local speech synthesis and
database operations did not account for this delay.

## Verification and decision

- Existing Linux timing-report regression: **1 passed in 0.01 s**. Private
  analysis also checked nearest-rank P95, timing sums and exactly one agent
  record per measured gateway generation.
- **25/25 real-inference synthetic call validations passed**, including note
  persistence, two-turn completion, hangup and isolated summary persistence.
  These checks do not replace semantic dialogue review.
- Reported loopback receive loss, reordering and duplicate packets: **zero**.
- All temporary validator schemas were removed; the remaining schema count
  for the validator prefix was **zero**.
- Final readiness: ASR, EMA and live agent all **SERVING**. Recorded baseline
  source/binary hashes were unchanged. Live agent and carrier gateway log
  cursors had unchanged inodes and byte counts throughout the window.
- No native/runtime code change, rebuild, rollout, restart, carrier call,
  recording or notification was performed. This task adds sanitized evidence.

**The 50-turn synthetic measurement subtask is complete; the latency target is
not met.** Even the favorable warm synthetic estimate exceeds the project goals
of P50 <1000 ms and P95 <1800 ms. Human/carrier timing, noisy input, pause/cutoff
calibration, cold starts, concurrency and the broader M5-03 soak/failure/retention
acceptance remain open.

The next optimization should first evaluate the two sequential model requests
on message-taking turns and their tail latency, while preserving durable-note
acknowledgement and natural dialogue. Endpoint silence is the next material
budget item; reducing it requires labeled pause tests to avoid cutting callers
off. The present measurements do not justify replacing Whisper/EMA, applying
noise reduction or changing the accepted prompt. No such change is made here.

## Reproducibility and privacy

Private harness, frozen source, per-call logs, manifest and content-free aggregates
are under Linux `.local/latency-measurement-20261024/`. The manifest records the
fixed inputs, return codes, wall-clock run window, source/binary hashes and live
log cursors. Synthetic logs and local environment files are not published.

Baseline SHA-256:

| File | Digest |
|---|---|
| `services/agent/alojan_agent/backend.py` | `1db8a966bb46c3487728b65649b2e8c5b1f40b4af5954cca3b8418ddffd42b96` |
| `services/agent/alojan_agent/models.py` | `58fb41134a6087d13fc927590595598f94d742bb1185c0c6f53f2fb5667af20e` |
| `services/agent/alojan_agent/service.py` | `5ad779b017879278255bc5d21b42369dd152405faae596ef87e8cc80876790b4` |
| `build/local/voice-gateway` | `4b6440ecdeb2de41214a5a7351e858090e899cdf0eeca7aa86b88caed2652dc2` |
