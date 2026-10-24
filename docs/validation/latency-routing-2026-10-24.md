# Stage latency and same-model OpenRouter routing

Tasks: M4-01 / M5-03, requirements §3, §7.4, §9.1, §10/12/15; US-02/05/06.
Owner authorized only plan items 1 (measurement) and 4 (routing/cache comparison).
No phrase splitting, tool-roundtrip removal, TTS prefetch, speculative response,
ASR/model replacement, prompt change or notification work is included.

## Measurement contract

Agent telemetry distinguishes DB readiness, first provider text, first speakable
text, first phrase and each model/tool step. Cache usage comes from completed
provider response usage; missing counters remain unknown. Tool-only model steps
can legitimately have no text. Recovery/local replies have no model step.
The SDK hooks measure request start/end; the event consumer timestamps text
arrival separately. No timing is inferred from SSE keepalive comments.

Native per-turn records survive normal interruption, failure and disconnection;
previous sent-history logs alone covered only successfully completed dialogues.
The worker logs after inference/monitor cleanup, including partial or missing
audio. Media callbacks remain non-blocking and perform no log/API/database work.
The native opaque speech identity joins to the agent's truncated SHA-256 key.

The VAD-end-to-output estimate combines PCM-domain endpoint silence with native
endpoint-to-first-substantive-output timing. It is not a measured handset latency:
queue/replay age, VAD uncertainty and carrier transport remain outside the estimate.
`-1` means missing; recovery/music and unsuccessful turns do not improve response
percentiles. The report includes unsuccessful and missing counts. Process crashes
can still lose in-flight logs; this is not durable event ingestion or full M5-03.

## Comparison method

The same owner-selected model and unchanged prompt/tools/settings are used for
default, latency-sorted, session-affinity and combined routing. Three synthetic
two-turn scenarios cover availability/topic inquiry, message storage/correction,
and caller-initiated exit. Three repetitions rotate/reverse profile order: target
72 turns, 18 per profile. Real streaming API, synthetic in-memory storage and
simulated audio receipts; no caller recordings or external writes. Shared caches
cannot be reset; neither a first conversation turn nor a new session is guaranteed
cold. Cache-hit observations do not establish that routing caused a speed change.

Candidate adoption requires no observed behavior failures, at least 15% lower
median and no worse observed P95 than baseline, followed by a confirmation run.
With only 18 samples per profile, nearest-rank P95 is the maximum; it is not a
production tail estimate. A profile that fails a behavior check is not adopted
even if faster. This run does not prove the chosen provider identity or a hard pin.

Sources checked: [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
and [prompt caching/session affinity](https://openrouter.ai/docs/guides/best-practices/prompt-caching).
The existing stable system prompt already permits implicit provider caching;
this experiment does not pad or rewrite the prompt to force a hit.

## Validation and decision

All 72 API turns completed, producing 96 model requests. All 96 responses reported
nonzero cached input tokens, including the default arm. This does not mean the
entire input was cached. Results are time to first emitted phrase at the synthetic
gRPC client; they are not audio or carrier latency:

| Profile | Turns | Median ms | Observed P95/max ms | Behavior failures |
|---|---:|---:|---:|---:|
| Default | 18 | 2904.5 | 7055 | 0 |
| Latency | 18 | 2871.5 | 6882 | 1 |
| Sticky | 18 | 2907.0 | 6448 | 1 |
| Latency + sticky | 18 | 2996.5 | 8863 | 2 |

Decision: retain default routing. The latency arm's median improvement is only
1.14%, below the adoption criterion. No candidate satisfies the behavior gate.
The four observed behavior failures prematurely closed after a first message
save; the subsequent synthetic second turn is still measured, but cannot undo
that first-turn failure. These stochastic observations do not establish routing
as their cause or prove baseline behavior is always correct. They remain an
existing model-policy quality limitation, not a change to the phone's closing
rules in this task. No winning arm justified a confirmation/adoption run.

Default per-scenario medians: inquiry 2472.5 ms, message/save/correction 5540.5 ms,
exit 2829 ms. Across text-bearing turns, median provider-text-to-speakable-text
delay was 66.5 ms. Tool-only responses have no text delta and are excluded from
that statistic. Message handling usually requires two model requests; their
duration dominates the synthetic store cost. Removing that extra request is
plan item 3 and is outside this authorization.

Linux verification:

- Native build and nine CTests passed (2.34 s).
- 86 agent/phrase/database/native-dialogue/adaptive-turn tests passed (182.12 s),
  no skips; one known `audioop` deprecation warning. The added report test passed
  separately. After defensive normalization of optional token counters, all 74
  affected Python agent/phrase/timing/report tests passed again (5.01 s).
- Native regressions cover both codecs, failed agent streams, waiting-music
  exclusion, interruption without response audio, remote hangup during a pending
  model request, turn reuse and adaptive endpoint estimates. Seven new agent
  tests cover model/tool/cache timing, cancellation, routing settings and separate
  session IDs. Missing timings are asserted as missing, not zero.
- Ruff lint/format, affected native clang-format and diff whitespace checks passed.
  The graph index was refreshed; no hosted CI or clang-tidy validation is claimed.

A real resident CUDA ASR/EMA + OpenRouter + isolated PostgreSQL PCMA loopback
completed two turns, unconfirmed note storage, contextual farewell/hangup and
post-call summary. The temporary schema was removed. No new model was loaded,
no raw caller recording was enabled and no carrier call was placed.

| Measured stage | Message turn ms | Closing turn ms |
|---|---:|---:|
| PCM-domain endpoint silence | 512 | 876 |
| ASR finalization | 145 | 116 |
| Agent request to first phrase | 7068 | 4922 |
| First TTS chunk | 13 | 10 |
| First PCM to output port | 11 | 10 |
| Endpoint to substantive output | 7238 | 5059 |
| Estimated VAD end to output | 7750 | 5935 |

The first turn had two model steps of 3697/3374 ms and a 9 ms local note tool;
the closing model step took 4901 ms. This is functional integration evidence,
**not latency acceptance**: the current speed targets remain unmet. Telemetry
adds visibility and does not claim to accelerate provider inference.

Activated `natural-v5.2-latency-observability` after verifying an idle line.
Gateway arguments were identical; ASR/EMA were not restarted. Agent/ASR/EMA
health passed. Agent routing remains `default`; model, prompt, ringing, greeting
and closing policies are preserved. Private rollback is under
`.local/before-latency-observability`. No Git push, PR or notification occurred.
Gateway SHA-256: `4b6440ecdeb2de41214a5a7351e858090e899cdf0eeca7aa86b88caed2652dc2`.

Private reproducibility artifacts: `.local/routing-benchmark-2026-10-24.json`,
the local `.local/routing-benchmark.log`, `.local/latency-tests.log`, and
`.local/latency-cuda-2026-10-24/` on Linux. New handset timing acceptance, 50+
real audio turns and the full M5-03 hardening/soak package remain open.
