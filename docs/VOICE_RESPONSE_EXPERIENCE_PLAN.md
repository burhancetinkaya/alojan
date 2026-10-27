# Natural telephone responses and optional Jev decisions

Date: 2026-10-27. Status: owner-approved implementation in progress; live activation pending evidence.
Scope: AGP-06/07/09 and PERF-02/03, M2/M4/M5; US-04/05/06/08 and requirements
section 3. The owner requested research, a final plan, and independent subagent
review. Preserve ADR 0001/0003/0009/0011, self-hosted ASR/EMA, native C++ media
control, explicit AI identity, and isolated HTTP management. The owner subsequently approved implementation.
[ADR 0014](ADR/0014-shared-response-experience.md) records the shared runtime extension.

## Product objective

Make the caller feel heard through appropriate timing, short relevant speech,
reliable answers, and interruption handling. Faster filler is not faster completion.
Do not pretend to be human or manufacture progress. Do not require users to write
a waiting sentence for every MCP tool.

## Research and current implementation

TypeSafe's [introduction](https://docs.typesafe.ai/introduction) documents typed
Choice/Score/Noul outputs, rather than generated prose. Its
[model directory](https://docs.typesafe.ai/models) currently lists Jev 1.14 and
1.13; audio is unsupported, English is strongest, and language-specific validation
is necessary. Qualify and pin an exact version, never a moving alias. The vendor's
[launch measurements](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
report 70–500 ms in its settings and disclose US West Coast measurement origins.
Those figures do not establish latency or accuracy from this Linux host in Turkish.
[Confidence](https://docs.typesafe.ai/confidence) summarizes an output distribution;
a confident or schema-valid answer is not proof of semantic correctness.

[Microsoft](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-voice-live-interim-response)
supports small-model-generated and static interim speech with latency/tool triggers.
[ElevenLabs](https://elevenlabs.io/docs/changelog/2026/4/27) documents automatic
pre-tool speech based on recent tool latency.
[Retell](https://docs.retellai.com/build/single-multi-prompt/custom-function)
supports generated/static waiting speech and distinguishes interrupted speech from
an endpoint request that continues executing.
[LiveKit](https://docs.livekit.io/agents/logic/tools/async/) separates meaningful
progress updates from quiet-period fillers and bounds repetition.
[Vapi](https://docs.vapi.ai/tools/api-request/reliability) separates tool start,
delayed, completed, and failed messages. These are reference patterns, not new
hosted orchestration dependencies or measured comparisons with Alojan.

Pre-implementation inspected code: `Backend.stream` produces speech after a validated final
speech tool completes; its stream loop does not currently play an interim utterance.
`MCPExecutor.execute` validates arguments, checks current turn/grant, bounds work at
four seconds, two calls per turn and eight per call, and retains capacity for
non-cooperative cancellation. New interim speech must not call `respond` as if it
were the final output and terminate the SDK run. No new public MCP tool is required
to let the model use Jev; optional decisions belong to the runtime.

## OpenRouter qualification update — 2026-10-27

The owner selected the existing OpenRouter credential for Jev evaluation. Use the
shared runtime decision capability with an authorized workspace credential reference;
do not hard-code an agent/connection ID or share one workspace's key across tenants.
The [official Decisions API example](https://openrouter.ai/blog/insights/what-is-jev/)
uses `POST /api/alpha/decisions`, `typesafe/jev-1.14`, and typed `state`/`questions`.
Keep this alpha protocol behind a small bounded HTTP adapter using existing client
infrastructure, with response validation and fallback; it is not a chat model swap.
[Jev Router](https://openrouter.ai/typesafe/jev-router/api) selects other generative
models and is not a substitute for direct typed decisions in this design.

After the owner enabled model access, the Linux six-case synthetic smoke returned
HTTP 200 and the expected choice in all six cases. Requested `typesafe/jev-1.14`;
resolved model `typesafe/jev-1.14-20261014`. First request: 605.5 ms; subsequent
requests: 204.9–224.6 ms, measured as total HTTP round trips using one client.
The earlier guardrail failure is historical, not the current access status.
This establishes access and basic response compatibility, not held-out Turkish
quality, production latency, or a speed improvement over the existing agent.
See [sanitized evidence](validation/jev-openrouter-access-2026-10-27.md).

Owner-selected language policy: author platform-owned Jev decision instructions
and criterion descriptions in English. Keep caller utterances in their original
language; the smoke used Turkish inputs and English instructions/criteria. Do not
add a translation-model round trip or translate user-authored agent instructions
implicitly. This policy applies to the shared decision capability for every agent,
not to the primary conversational model's user-configured instructions or spoken
language. Evaluate multilingual decision quality separately; this small smoke does
not prove English instructions outperform Turkish instructions.

## Approved responsibilities

| Layer | Responsibility |
| --- | --- |
| Existing VAD/Smart Turn and native gateway | Determine actual turn end, control playback and interruption; no remote dependency in the audio callback |
| Optional Jev adviser | Choose from eligible intent/response categories; return uncertainty; never produce prose, authorize tools or decide audio timing |
| Primary model | Resolve ambiguous requests, construct complex arguments, generate a contextual interim candidate and the grounded final response |
| Application controller | Track actual operation state, continuous idle time, speech ownership, deadlines, cancellation and duplicate suppression |
| Existing ASR/EMA and prepared assets | Recognize speech and render one consistent voice; prioritize useful answers over optional fillers |

### 1. Deterministic response lifecycle first

Add typed internal lifecycle events for tool start, result, failure, response ready,
and interim speech. Correlate every event with workspace, pinned release, call,
turn, operation and generation. Maintain one playback arbiter and bounded queues.
An interim segment finishing must not finish the logical assistant turn, cancel the
tool, trigger a caller-silence reminder, or enable final hangup. Reuse the existing
`kind="waiting"` phrase contract, playback receipts and separate substantive-response
metrics in `agent_bridge.cpp`/`speech_bridge.cpp`; do not create a second audio path.
The gateway already starts waiting music about 800 ms after response start. Music
updates audio timestamps but must NOT reset the speech-quiet watchdog. Count caller
and actual agent speech separately from music. With the feature enabled, stop/duck
music for interim speech and do not resume it after that first spoken interim in v1.
The feature-off path preserves current music behavior. The native state machine
retains authority. Timeout/error feedback must also win over stale filler.

An independent watchdog observes continuous session quiet after confirmed user
turn end. Start with a tunable platform preset around 1.5–2 seconds, then calibrate.
No output during caller speech. Recheck eligibility immediately before playback.
Prefer a final reply if ready; drop unsent interim text/audio. If interim audio is
already playing, do not wait for a full sentence to finish. Test segment-level
preemption with a short audio-frame fade (initial engineering budget <=40 ms),
without invalidating the tool or final-response generation. Measure actual
final-speech-ready to first useful RTP, not just model completion. The existing
matched P95 <=50 ms regression gate remains authoritative; no exception is silently
introduced for filler. A smooth handoff and the latency gate must both pass. If
frame-level interruption sounds clipped/unnatural or misses the gate, suppress that
candidate speech policy rather than claim early filler as a speed improvement. Valid interruption stops playback under the existing <250 ms
target, invalidates old-generation audio and follows existing tool cancellation.
Remote cancellation is best effort, never proof a write was undone.

Use at most one initial waiting statement per logical turn, shared across all tools.
No repeat loop in the first release. Subsequent factual phase changes and truly
long-running conversational tasks are a later, separately qualified capability.
The current tool timeout remains unchanged until a measured bounded budget proposal
is reviewed. Do not promise future notification or continue a cancelled request.

### 2. Dynamic text plus prepared speech fallback

The primary model can supply a short, optional utterance with a tool proposal in
the same model round trip. The runtime separates this local metadata before remote
MCP schema validation; it never reaches the remote server or changes grants/fixed
arguments. Missing or invalid metadata must not reject an otherwise valid call or
add a model-repair round trip. Pin compatible wrapper versions and test collisions.
Same-round-trip metadata still adds generated tokens before complete arguments are
available: it can delay tool dispatch. Compare tool dispatch P50/P95 with and without
metadata. Never dispatch partially validated JSON to hide that cost. Dynamic metadata
stays disabled if it fails the existing per-turn/full-path non-regression gates.
Interim candidates describe only work that is actually authorized and dispatched.
Do not speak provider-controlled tool descriptions or unvalidated streamed fragments.

Validate language, length and allowed purpose; do not claim success, a percentage,
an ETA, delivery or permission. Runtime state and a safe fallback are authoritative;
semantic filtering alone cannot guarantee arbitrary generated text is appropriate.

Prepare a small, platform-maintained speech palette in each selected voice at
publication, with agent-level style and safe optional overrides. Users do not write
tool-specific sentences. Example categories: generic processing, checking records,
and interpreting retrieved results. Name/category mappings must not assert a more
specific action than the runtime can prove. Fresh model prose provides specificity
when ready; otherwise use the best eligible cached clip.

Dynamic TTS is optional and speculative: at most one short candidate per turn,
bounded node-wide capacity, drop if final speech is ready, do not queue behind ASR
or useful reply speech. EMA kernels may be non-preemptible; a lower queue priority
is insufficient by itself. If measured isolation cannot be met, disable speculative
TTS and use prepared assets. Cache only exact content/voice/revision matches within
the appropriate scope; never share personalized audio across workspaces.

Persist actual sent interim speech as a distinct event for receipts/transcripts.
Unsent text is not conversation history. If sent context is exposed to the model,
represent it as delivered progress, never a new user request or final answer. Test
that the model does not acknowledge its own filler or repeat it.

### 3. Jev as an optional parallel adviser

First evaluate with synthetic/anonymized Turkish text. Do not transmit real calls
or organization data merely to benchmark. A new provider requires an explicit
configuration/data-handling decision before real-call use; credentials stay private.

Start in shadow evaluation, where decisions cannot alter speech or tools. Only
promote advisory decisions if they outperform deterministic selection on relevant
cases. Known tool category and task state usually need no Jev call at all.
For qualified ambiguous categories, run at most one bounded request per final turn,
alongside the primary model,
without holding up baseline model dispatch. Use a short state containing the final
utterance and minimal relevant dialogue, plus known operation state. Batch a few
independent decisions in that request: intent category, which eligible prepared
reaction fits, and whether context is ambiguous. Always offer an unknown option.
Late, stale, low-confidence, malformed, unavailable and rate-limited results are
ignored. No automatic retry or backoff on the critical path; bounded connection
pool and concurrency, circuit breaker, and baseline behavior when disabled.

Implemented context extension (2026-10-27, owner authorized): the intent shadow
now snapshots at most three prior caller-led turns, 12 messages and 4096 UTF-8
content bytes. It uses existing receipt-backed model history; excludes current
utterance duplication, partial/unsent assistant phrases, waiting speech and raw
tool results. A bounded whole-message suffix starts with its originating caller
question. English contextual policy resolves unambiguous follow-ups/corrections;
empty context retains the original policy/request. Primary-model history remains
unchanged. Additional decision questions and operation-state enrichment above are
still planned, not claimed by this change.
[Context tests, measurements and limits](validation/jev-dialogue-context-2026-10-27.md).

Jev can select an existing clip without a generative-model/TTS round trip. It cannot
invent a personalized sentence, extract arbitrary names/IDs/dates as strings, or
replace acoustic turn detection. Silence thresholds, available results and known
task status are computed by code, not purchased from a model. An advisory result
never executes a tool or changes a permission. This stage may improve responsiveness if evaluation passes;
it is not claimed to reduce actual MCP/backend execution time.

### 4. Qualify a narrow fast route only after measurements

Potential real answer-speed gain: replace an initial large-model planning step for
well-defined read-only requests. Candidate Nazlı examples are aggregate today's
session count and today's cost, with known workspace, trusted date/timezone and
fixed authorized tool arguments. Jev picks only among explicit, release-bound
recipes; deterministic code constructs arguments. No freely generated executable
workflow and no special-case tool-name guessing. An agent with arbitrary MCP tools
keeps the general path unless an eligible recipe binding is explicitly qualified.

Person lookup, unresolved pronouns, arbitrary date ranges, corrections, multi-part
requests and uncertain ASR fall back to the primary model unless separately proven.
Jev does not calculate totals or repair incomplete cost data. All tool dispatch still
uses the existing grant, schema, provenance, budget and audit path. Final speech is
grounded in the actual result, including unknown/partial totals.

This is a separate research experiment, excluded from the first delivery. Do not
race two tool-capable planners in v1. Restrict a decision-first experiment to an
explicitly qualified small request family; one Jev decision selects a fixed read-only
operation, then the answer model receives its result. Ordinary calls bypass Jev.
A low-confidence or late decision falls back to the normal model and therefore adds
the routing wait to that turn: report this penalty, including rejected cases, and
ship only if the cohort meets the full latency/quality gates. Define the eligibility
rule and maximum routing wait before measurement; do not tune on held-out cases.

A future race is not approved by this plan. It would require a separate design for
single ownership across ALL effects, including speech, hangup, note persistence and
tools, not merely MCP deduplication. It must also account for duplicate model load,
cancellation and continuation correctness. No live fast path is promised if the
simpler experiment shows no net gain.

Partial-ASR intent preparation is a later experiment: debounce and revision-tag it,
perform no external tool calls and no speech before confirmed turn end, and recheck
against the final transcript. Never assume partial speech is authorization or keep
results from an earlier correction. No partial-ASR Jev fan-out in the first release.

## Configuration and operational scope

Agent owns automatic waiting enablement, concise/natural style, optional generic
fallback text and approved integrations. UI, HTTP API and management MCP have equal
access. Version and snapshot settings and voice assets into a new immutable release;
existing agents/releases keep their previous behavior until explicitly enabled.
Qualified engine presets own thresholds, clip duration, decision timeout, confidence
gates, retries and all resource caps. Jev should be an optional platform capability,
not another per-agent latency-tuning screen. New HTTP management stays in its own
Docker app; no new HTTP server is needed on the voice path for this plan.

Do not add fake keyboard sounds, continuous filler, premature acknowledgments or
new acoustic backchannels in this scope. Preserve the assistant's AI disclosure.

## Staged tasks and acceptance

| Task | Work | Required evidence before next stage |
| --- | --- | --- |
| VXP-01 | Matched baseline and Turkish evaluation corpus | Component timings, real handset silence and final-answer latency; labeled corrections/pauses/ambiguity and source-grounded answers |
| VXP-02 | Lifecycle, playback arbiter, one prepared fallback | Fast tool/no filler; slow tool/one filler; result-filler race; caller interruption; no stale playback, hangup or reminder; existing regression suites pass |
| VXP-03 | Same-model contextual candidate and optional bounded TTS | Tool-dispatch P50/P95 with added metadata; no repair round trip; missing text fallback; EMA/ASR, final-ready-to-useful-RTP and total-answer non-regression under contention |
| VXP-04 | Jev shadow comparison; optional advisory clip selection | Exact model/API qualification, Turkish error/coverage report, host P50/P95/P99, provider failure/429 circuit behavior; no critical-path dependency |
| VXP-05 | Optional authorized recipe fast route | Research only: qualified cohort, complete arguments, single dispatch, rejection/fallback penalty and measured actual-answer improvement without quality loss; otherwise omit |
| VXP-06 | UI/MCP settings, release migration and controlled rollout | Old releases unchanged, publication validates assets/settings, rollback flag, real SIP/RTP and handset acceptance |

Compare A: current baseline; B: lifecycle/dynamic/fallback without Jev; C: B plus
Jev adviser; D: qualified fast routes. Use the same recorded synthetic or consented
Turkish inputs, provider results, fault schedules and load. Include at least the
existing 50+ turn requirement and expand for decision quality; split calibration
and held-out cases. Do not count a small clean sample as proof of low error rates.
Measure coverage as well as error rate for confidence-gated routes. Keep a separate
latency distribution for accepted fast routes and rejected/fallback routes, plus the
weighted total cohort; never hide slow fallbacks by reporting only successful routes.
Include music-on/music-off, final-ready just after interim playback starts, maximum
queued audio, and non-preemptible EMA work. Compare transcript/receipt ordering and
prevent interim segments from satisfying note acknowledgement or final-turn completion. Include
"bugün, hayır dün", "tamam ama...", silence/noise, interrupted filler, early/late
results, unavailable Jev, and slow/failed/malformed MCP tools.

Report first audible feedback and first useful answer separately, longest continuous
silence, final-answer P50/P95/P99, interruption delay, false turn endings, repeat
announcements, duplicate tools, late audio, accuracy, CPU/GPU/VRAM and cost. Preserve
requirements targets: first RTP P50 <1000 ms/P95 <1800 ms, valid interruption <250 ms,
premature cutoff <2%, false interruption <3%; report actual outcomes and failures.
Use the performance plan's matched non-regression rules, not a filler timestamp to
claim completion-speed gains. Test one call then provisioned admitted load; five
and fifty calls remain targets, never assumed hardware capacity.

## Review and unresolved evidence

Independent subagent review completed on 2026-10-27. Three P1 planning findings
were accepted: reuse existing music/waiting contracts, resolve filler versus the
strict useful-answer latency gate, and account for same-model metadata dispatch cost.
A targeted re-review found no remaining P1 planning ambiguity in first-delivery scope.
The speculative planner race was removed from initial scope, and Jev starts in shadow
mode with deterministic selection as its comparator. Review disposition:
[review record](validation/voice-response-plan-review-2026-10-27.md). The original review was a planning-only change. The owner then approved implementation.
The first candidate now implements prepared waiting speech, UI/API/MCP preferences
and bounded Jev shadow observations. A 60-case synthetic Turkish evaluation and
a paired metadata-cost probe are recorded in the
[implementation evidence](validation/voice-response-implementation-2026-10-27.md).
A subsequent [resident EMA comparison](validation/voice-response-measurements-2026-10-27.md)
measured 56 matched turns per experiment using scripted ASR/operations/answers.
Full-path ASR/model latency and handset quality remain unqualified.
Dynamic candidate/TTS activation and fast routing are not delivered by these tests.


## Implementation status — 2026-10-27

| Task | Current state | Remaining gate |
| --- | --- | --- |
| VXP-01 | Synthetic Turkish split, metadata timings and resident EMA 56-turn ABBA comparisons recorded | Full ASR/model matched turns and admitted-load measurement |
| VXP-02 | Prepared lifecycle/receipts and 5 ms in-frame handoff tested with native SIP/EMA | Human handoff quality, real ASR/model and handset interruption acceptance |
| VXP-03 | Same-model metadata timing probe completed; active runtime unchanged | Candidate semantics/schema boundary, non-regression and speculative GPU isolation; no dynamic TTS activation |
| VXP-04 | Bounded contextual Jev shadow deployed; managed default on for published MCP tools under owner approval | Broader quality/benefit evidence before advisory selection; no speech/tool authority |
| VXP-05 | Excluded from initial delivery as approved | Separate qualified-recipe research, only if beneficial |
| VXP-06 | UI/API/MCP parity, asset validation and coordinated rollout instructions implemented | Temporary Nazlı handset trial and Kübra restoration completed; reported lookup quality issue deferred, full voice/load acceptance pending |

Owner-authorized [Nazlı handset trial](validation/nazli-handset-quality-2026-10-27.md)
completed after coordinated runtime deployment. This is one carrier conversation,
not overall quality or latency acceptance. Kübra was restored; instruction-level
person-lookup clarification was deferred at the owner's explicit request.
