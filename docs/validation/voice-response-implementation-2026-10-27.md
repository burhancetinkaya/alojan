# Shared response experience: first candidate evidence

Date: 2026-10-27. Owner authorized implementation of the reviewed plan.
Task mapping: VXP-01/02/03/04/06, AGP-06/07/09, PERF-02/03, M2/M4/M5,
US-04/05/06/08. See ADR 0014. VXP-05 remains excluded research.

## Implemented behavior

- Optional, release-bound `response_experience`: enabled, concise/natural style,
  optional generic waiting text. Existing drafts/manifests omit it without changing
  their previous digest. UI, HTTP and management MCP share the same schema.
- One runtime-owned waiting utterance per turn, only during an actual authorized
  MCP operation or note persistence. Defaults: 1.8 s from turn processing and at
  least 300 ms active operation. Final response/cancellation suppresses late filler.
- Prepared waiting WAV is required when enabled, digest-bound and limited to five
  seconds. Preview, import, publication and preload recognize the third asset.
  Native playback uses prepared memory and consumes no synthesis slot. Useful PCM
  initially preempted with a single 20 ms fade frame. The subsequent
  [measurement follow-up](voice-response-measurements-2026-10-27.md) replaces this
  with a 5 ms crossfade inside the response frame, without adding a frame.
- Sent waiting receipts are separate from final response/note acknowledgments.
  Transcript API/UI distinguishes waiting; partial audio has duration and no invented
  words. First useful audio metrics remain separate from waiting feedback.
- Shared bounded Jev adapter with English platform instructions, unmodified Turkish
  input, exact resolved model check, scoped preloaded credentials, 750 ms deadline,
  two requests without a capacity queue, 8 KiB response limit, 16 identity states,
  per-identity three-failure/30 s breaker and no retries/redirects. Runtime shadow
  runs alongside primary inference and has no speech/tool/routing authority.
  `ALOJAN_JEV_SHADOW` defaults to `0`; no production flag was enabled.

## Ubuntu checks

All execution below used the authorized primary Linux development checkout.
The serving release directories, production agents and number bindings were not
changed. Browser checks used disposable database schemas and synthetic accounts.

| Check | Result |
| --- | --- |
| Affected Python suites: response lifecycle, decisions/shadow, agent/timing, MCP execution, calls, voice preview, management MCP, startup, drafts/runtime, preload, packs/jobs | **257 passed in 90.72 s** |
| Additional waiting-preview regression including enabled asset and changed-text invalidation | **3 passed in 2.51 s** (includes two existing preview tests) |
| Evaluation-report failure accounting | **1 passed in 0.25 s** |
| Native candidate build | Passed |
| Native CTest, including ready suppression/fade/isolation/no resume | **11/11 passed in 3.81 s** |
| Isolated real SIP/RTP, fast and slow operation | **2 passed in 27.24 s**, one existing Python `audioop` deprecation warning |
| Next.js typecheck and production build for isolated test backend | Passed |
| HTTPS Playwright journeys with newly built API image | **48 passed in 1.3 min**, zero production writes/external sends |
| Changed Python Ruff format/check and affected C++ clang-format | Passed after using the pinned project tools |

SIP/RTP tests use native PJSIP/gRPC and real loopback packets, but scripted inference
and prepared tones. Fast operations emit no waiting clip; the slow case emits one
partial waiting receipt before the final reply. Both keep exactly two response TTS
requests: waiting adds **zero** TTS requests. The slow prepared one-second tone is
preempted before completion. These are not real EMA acoustic or carrier proofs.

The initial transcript regression caught missing column-level SELECT permission for
`source_generation_id`. The role grant was corrected and tests confirm RLS still
hides unscoped data, table-wide reads/writes remain denied, and raw internal IDs are
not returned. A stale test expectation that forbade this newly necessary column was
updated. The final runs above pass; earlier failed runs are not counted as passes.

## Real Jev API, synthetic Turkish only

Requested `typesafe/jev-1.14`; accepted resolved `typesafe/jev-1.14-20261014`.
Labeled fixture: 60 cases, balanced four categories; calibration 20, held-out 40.
Cases were fixed before requests. No real call/organization data or tool dispatch.

| Split | Observed | Correct | HTTP P50 | HTTP P95 | HTTP P99 |
| --- | --- | --- | --- | --- | --- |
| Calibration | 20/20 | 19/20 | 227.5 ms | 288 ms | 692 ms |
| Held-out | 40/40 | 39/40 | 227 ms | 266 ms | 281 ms |

Both errors chose `unknown` for an explanation request. No expected-unknown case
was classified as a concrete intent. This small synthetic set is **not** a production
error-rate, language superiority, acoustic-quality or faster-answer claim. Confidence
is telemetry only; no activation threshold was tuned on held-out cases. The snapshot
may be replaced upstream; a changed model is rejected rather than silently accepted.

## Same-model contextual metadata probe (VXP-03)

Real existing OpenRouter GPT-OSS-120B/Cerebras route, medium reasoning, forced
synthetic lookup proposal; 25 paired comparisons / 50 requests, alternating order.
No tools executed, and no ASR/TTS/RTP used. Provider caches were not controlled.
Only proposal-shape compatibility and request timing were measured; no production
wrapper, semantic promise checker or dynamic speech path is claimed implemented.

| Variant | Completed | HTTP P50 | HTTP P95 | Non-null candidate |
| --- | --- | --- | --- | --- |
| Baseline | 25/25 | 430 ms | 1139 ms | n/a |
| Added optional interim text | 25/25 | 493 ms | 919 ms | 22/25 |

Paired metadata-minus-baseline median: +36 ms; P95: +449 ms; range -533 to +795 ms.
The small sample and cache/network noise do not prove causation or a latency pass.
Aggregate P95 being lower does not establish full-path non-regression. Metadata and
speculative EMA remain inactive; the prepared fallback does not add generated tokens
before tool dispatch or occupy the final-answer GPU synthesis slot.

## Remaining gates and next action

1. Prepare/review a real EMA waiting clip in the existing fenced preparation window.
2. Run matched baseline/candidate 50+ real-audio turns and admitted-load/resource
   measurements, including interruption, music, final-ready race and slow/failing tools.
3. Qualify naturalness and <=50 ms P95 useful-answer regression gate on actual RTP.
4. Coordinate gateway/agent/contracts/API/MCP/preparation/frontend deployment and
   narrow role-grant update; activate a new release only after the gates pass.
5. Perform handset acceptance and rollback verification. Existing Kübra routing is
   untouched; no test Telegram/webhook or external MCP write was sent.

Dynamic metadata/TTS and Jev-driven clip selection are not silently treated as done.
The approved plan explicitly conditions them on benefit/isolation evidence. Live
activation, full performance qualification and real EMA/handset checks remain open.
