# Call acceptance and external validation

## 2026-10-27 — Interruption evidence/recovery loopback trial; not live-qualified

M3-02/M5-03/VXP-06, US-05/06. 15 candidate loopback cases passed with real CPU
Silero/Smart Turn and explicitly scripted ASR/TTS/agent; no actual carrier call.
The tests demonstrate failure of the text-corroboration quality hypothesis:
background words still interrupt and late/absent ASR delays/misses intended speech.
One-shot clarification after a failed post-interruption capture works, including
repeat-failure polite closure. Native CTest 11/11 and 8 selected default
cancellation/monitor regressions passed (7 deliberately deselected). No live deployment or
GPU/acoustic acceptance claim. [Evidence](validation/interruption-evidence-trial-2026-10-27.md).

The owner ended this experiment before publication. Its source/test harness is
archived privately; only the previously qualified default implementation is released.

## 2026-10-27 — Silero interruption threshold sweep

M3-02/M5-03/VXP-06, US-05/06: isolated Linux CPU evaluation of 0.50/0.60/0.70
on 34 public/synthetic G.711 streams. All three retain 20/20 later and 4/4 initial
background-only sustained crossings; quiet/short clean targets retained. No live
setting changed and no handset/carrier acceptance claimed. Baseline reproduction,
boundary/timing self-checks and Ruff passed.
[Evidence](validation/silero-threshold-2026-10-27.md).

## 2026-10-27 — Hush input filter with unchanged Silero

M3-02/M5-03/VXP-06, US-05/06: 34 Linux CPU G.711 streams / 727.68 s,
three filter profiles, 96 recognition checks (92 CUDA decodes and four digital
silence short circuits). Strong Hush prevents
only 2/20 later background crossings and loses four quiet clean targets; gentle
mode preserves those targets but prevents 0/20 crossings. No live change or
handset call. Noisy-room acceptance remains failed/open.
[Results](validation/hush-2026-10-27.md).

## 2026-10-27 — Offline neovad GRU comparison

M3-02/M5-03/VXP-06, US-05/06: 30 Linux CPU G.711 streams, 667.20 s, using
public/synthetic fixtures. neovad reduced background-only sustained-threshold
crossings from Silero's 20/20 to 16/20, insufficient for live replacement.
No handset call or deployment occurred. Follow-up output was retrieved and reports
synchronized after SSH returned. The initial background-only interval crosses the
threshold in all four trials for both models; noisy-room acceptance remains
failed/open. [Measured results](validation/neovad-2026-10-27.md).

## 2026-10-27 — Offline free voice-isolation evaluation

M3-02/M5-03/VXP-06, US-05/06: VoxLock CPU automatic-enrollment trial completed
16 public/synthetic G.711 streams and 64 real CUDA recognition decodes. All four
background-first cases selected the competing speaker; live promotion rejected.
No handset call, native SIP trial or live deployment occurred. Existing noisy-room
handset gate remains failed/open. [Evidence](validation/voxlock-2026-10-27.md).

## 2026-10-27 — Post-deployment handset check: false interruption persists

M3-02, M5-03, VXP-06; US-05/06: the owner made a call after activation and
confirmed being silent when the second response stopped. The first response
completed; the second was interrupted with voice/sustained evidence both 640 ms,
8 ms quiet, VAD probability 0.699, no fresh ASR coverage and two rejected echo frames.
This proves a false interruption through the sustained-VAD path in this trial;
it does not isolate independent room speech/noise from distorted speakerphone echo.

The next listening turn consumed 20 seconds of input including pre-roll (18.347 s
wall time), failed to accept an endpoint, and reported incomplete-turn error 8.
The gateway then used its fallback and closed; summary and configured notification
completed. No MCP tool execution occurred. The source correction for fragmented
bursts remains independently reproduced/tested, but is insufficient for this real
acoustic case. Handset quality gate remains failed/open. No settings or services
were changed during this read-only review.
[Detailed evidence](validation/noise-interruption-2026-10-27.md#post-deployment-handset-review).

## 2026-10-27 — Noise-interruption candidate deployed under owner authorization

M3-02, M5-03, VXP-06; US-05/06, §7.3–4: the owner explicitly requested live
deployment of the tested fragmented-voice correction. Rechecked all seven source
hashes and confirmed the Linux build was current. Layered only the native gateway
binary onto the exact prior serving image; isolated policy test and binary hash
checks passed in the candidate image.

With no active/initializing calls or preparation jobs, held the existing preparation
locks, stopped the idle preparer and obtained native draining/drained acknowledgements.
Saved rollback configuration, recreated only the gateway, verified health/readiness,
and reopened admission. Number bindings, agent/ASR/TTS containers and Jev configuration
are unchanged. Post-deploy checks verified the running executable hash, zero container
restarts, a successful SIP OPTIONS response, healthy voice services, ready bound routes
and active preparer. No test call or external notification was initiated.

Live acoustic acceptance remains pending: same-room speakerphone silence and deliberate
interruption must be checked. Deployment does not prove the prior incident's sole cause
or complete noise immunity. [Evidence and rollback](validation/noise-interruption-2026-10-27.md#owner-authorized-live-deployment).

## 2026-10-27 — Fragmented interruption evidence fixed; handset qualification pending

M3-02, M5-03, VXP-06; US-05/06, §7.3–4: investigation reproduced a native
accumulation defect. Separated short voice bursts could satisfy the sustained
fallback without sustained speech. The unchanged prior Linux gateway failed a
new repeated-acknowledgment SIP/RTP regression. The candidate separates sustained
and ASR candidate evidence using existing thresholds and adds content-free
interruption diagnostics outside media callbacks.

Linux validation: initial candidate **11/11 CTest** and **13/13 SIP tests** passed.
After preserving the exact prior candidate-expiry boundary, final **11/11 CTest**
and **3/3 focused SIP tests** passed (repeated bursts plus noisy delayed echo in
both G.711 codecs; 12 deliberately deselected). Formatting/lint checks passed.
Real native CPU models/SIP/RTP, scripted ASR/TTS and synthetic fixtures only.
No new GPU, handset, carrier or onset-latency acceptance is claimed.

Source and candidate binary are ready on Linux; serving gateway/agent images,
number bindings and Jev settings were not changed. The noisy-speakerphone incident
is not conclusively attributed: continuous background speech/distorted echo remain
possible. Next is a supervised candidate deployment and matched handset trial.
[Evidence and limitations](validation/noise-interruption-2026-10-27.md).

## 2026-10-27 — Jev context deployed; default on for published MCP-tool agents

VXP-04/06, AGP-06/07/09, PERF-02/03, M2/M4/M5, US-04/05/06/08: owner
explicitly authorized deployment and default enablement. Managed Jev now defaults
on, with an operator off switch, and skips runtimes without a published MCP tool
grant before credential access. Recent dialogue is included; authority stays
observation-only. No tool-selection feature was activated.

Ubuntu: 154 tests passed; lint/format passed; the final image passed an isolated
network-disabled MCP/non-MCP history smoke. Deployed only the agent image under
existing preparation locks and drained native admission. Verified installed source
hashes, actual process flag, healthy agent, ready routes, open admission and active
preparer. Bindings unchanged: Kübra serves its existing number and skips Jev;
Nazlı is eligible but remains unbound. No new handset test; acoustic false
interruptions remain open. [Evidence](validation/jev-default-deployment-2026-10-27.md).

## 2026-10-27 — Bounded Jev conversation context implemented and measured

VXP-04/06, PERF-02/03, M2/M4/M5, US-04/05/06/08: owner requested recent
conversation for Jev and inspection of primary-model history. Added a call-local
snapshot of up to three preceding caller-led turns (12 messages/4096 UTF-8 bytes),
using completed substantive playback history. Clear contextual corrections may
inherit intent; unknown references remain conservative. Empty context preserves
the original provider request/policy. Primary LLM already receives bounded history;
verified it without reducing its context or changing agent instructions.

Ubuntu: 132 tests passed, Ruff passed. Real Jev synthetic comparison: context 16/16
expected choices, no-history 15/16 under input-specific expectations; median HTTP
229/218 ms. Existing regression stayed 58/60, both misses conservative unknown.
An earlier prompt candidate regressed and was rejected before serving deployment.
Source is synchronized to Linux; serving containers, Jev flag and Kübra binding
remain unchanged. No handset/GPU/full-path performance pass; false interruptions
remain open. [Evidence and limits](validation/jev-dialogue-context-2026-10-27.md).

## 2026-10-27 — Jev observed; noisy speakerphone trial failed

VXP-04/06, PERF-02/03, M2/M4/M5, US-04/05/06: the authorized temporary Nazlı
trial produced three valid Jev shadow decisions (666/253/250 ms). The owner
reported all speech cut off while silent, using speakerphone in a noisy room.
Native logs show three interruptions and one hangup cancellation, no completed
response turn. Echo versus independent room sound remains unproven; shadow Jev
cannot directly issue these cancellations. Treat voice quality as failed.
Kübra was restored (binding version 9), Jev disabled, admission reopened, temporary
token revoked and session closed. No prompt or acoustic threshold change.
Next work is content-free interruption diagnostics and controlled echo/noise plus
real-barge-in validation, not blind threshold tuning.
[Evidence and limits](validation/nazli-jev-shadow-2026-10-27.md).

## 2026-10-27 — Owner accepted handset voice/waiting; Jev remained off

VXP-02/04/06, US-04/05/06: the owner described Nazlı's real-call voice and waiting
experience as very good. This accepts the observed experience in that call, not
full latency/load or the deferred person-lookup behavior. Read-only checks of the
same running agent's process environment, installed startup/backend guards and
logs confirmed no Jev dispatch in the trial: the optional shadow flag was unset
(default 0), no Decisions client was constructed and no shadow observation logged.
The prepared waiting watchdog operated independently of Jev. No runtime/profile
setting changed. Remaining timing work includes the final incomplete turn near
120 seconds and model/tool response latency. [Evidence](validation/nazli-handset-quality-2026-10-27.md).

## 2026-10-27 — Nazlı handset trial completed; Kübra restored

VXP-02/06, AGP-07/09, PERF-02/03, M2/M4/M5, US-01/04/05/06/07/08:
owner authorized a temporary Nazlı binding and restoration after one quality call.
Coordinated compatible waiting-runtime deployment passed health/readiness and
preserved existing voice/model configuration. MCP prepared/published Nazlı v8,
revision 1, with natural prepared waiting speech and its existing eight read tools
and Telegram action. The real carrier trial completed; summary and Telegram delivery
succeeded. Three waiting receipts were recorded. Gateway totals: seven completed,
five interrupted, one final incomplete turn; seven-turn useful-audio P50/P95
2498/4658 ms, not full performance acceptance.

The owner reported a failed short-name lookup. Exact-name/email source matching
returned developer_not_found, which the answer overinterpreted as person absence.
The owner deferred the instruction-level clarification fix; no related prompt/tool
change was made. Restored the previous Kübra release, verified number version 7,
revoked the temporary token and closed the login session. Nazlı is no longer bound.
[Trial evidence, limits and deferred finding](validation/nazli-handset-quality-2026-10-27.md).

## 2026-10-27 — Resident EMA waiting comparison and response-frame handoff

VXP-01/02/06, PERF-02/03, M2/M4/M5, US-04/05/06/08: two completed
56-turn ABBA comparisons used real resident EMA and native SIP/RTP, with scripted
ASR, controlled operation delays and fixed replies. Initial measurements exposed
an extra 20 ms fade frame; the candidate now crossfades within the first 5 ms of
the response frame. A negative-PCM arithmetic regression was caught and fixed;
an intermediate aborted experiment is excluded.

Verified useful-answer P95: baseline 3080 ms, candidate 3079 ms; paired delta
median 0 ms, P95 +40 ms. Ready-PCM-to-output P95: 17/20 ms. Waiting began at
P50 1829.5 ms, exactly once in each of 16 expected slow turns and never otherwise.
The limited experiment does not qualify full ASR/model/handset or admitted-load
performance. Normal admission and healthy serving workers were restored after
all windows; serving binaries/releases and Jev activation remain unchanged.
[Method, results and limits](validation/voice-response-measurements-2026-10-27.md).

## 2026-10-27 — Shared waiting speech and Jev shadow candidate implemented

VXP-01/02/03/04/06, AGP-06/07/09, PERF-02/03, M2/M4/M5, US-04/05/06/08:
implemented release-bound waiting preferences/assets, deterministic slow-operation
watchdog, prepared native playback with useful-response preemption, separate
receipts/transcript kind, UI/API/MCP parity and optional bounded Jev shadow mode.
English Jev instructions preserve original Turkish input. Production switches and
agent/number bindings remain unchanged. [ADR 0014](ADR/0014-shared-response-experience.md).

Ubuntu: 257 affected Python tests, 11 native tests, two real SIP/RTP tests with
scripted inference, and 48 HTTPS browser journeys passed. Additional waiting-preview
and evaluation-report regressions passed. Real Jev synthetic evaluation: 58/60
correct (39/40 held-out), both misses conservative unknown. Same-model metadata
probe: 25 paired samples, not a full-path non-regression pass. Prepared waiting
uses no call-time TTS slot. Dynamic metadata/TTS, Jev-based selection, real EMA
quality/50+ turn/load qualification and coordinated live deployment remain gated.
[Detailed evidence and next steps](validation/voice-response-implementation-2026-10-27.md).


## 2026-10-27 — Jev access restored; six synthetic decisions passed

VXP-04 prerequisite, AGP-06/07/09, PERF-02/03, M2/M4/M5, US-04/05/06/08:
after the owner enabled model permission, the primary Linux host received HTTP 200
and the expected choice for all six synthetic Turkish cases. Resolved version:
`typesafe/jev-1.14-20261014`. Total HTTP duration was 605.5 ms for the first request
and 204.9–224.6 ms for subsequent requests. English decision instructions/criteria
were already used; the owner's follow-up makes that the shared capability's language
policy, preserving original caller input. No translation round trip is added.
This supersedes the access blocker below, not the pending held-out quality and
matched performance gates. No live agent/runtime setting or service changed.
[Evidence](validation/jev-openrouter-access-2026-10-27.md) and
[updated plan](VOICE_RESPONSE_EXPERIENCE_PLAN.md).

## 2026-10-27 — OpenRouter Jev access checked; model permission blocked

VXP-04 qualification prerequisite, AGP-06/07/09, PERF-02/03, M2/M4/M5,
US-04/05/06/08: the owner authorized the existing OpenRouter key for Jev.
Linux key validation returned 200; two bounded synthetic Decisions API requests
for `typesafe/jev-1.14` returned 404, with the diagnostic reporting
`Model blocked by guardrail`. The six-case smoke suite stopped at its first case;
no decision accuracy or inference-latency pass is claimed. Recorded the Decisions
API versus Jev Router distinction and workspace-scoped credential reuse in the
[plan](VOICE_RESPONSE_EXPERIENCE_PLAN.md). No runtime code, live configuration,
provider restriction, number binding or service was changed. No carrier/GPU test.
[Evidence and next gate](validation/jev-openrouter-access-2026-10-27.md).

## 2026-10-27 — Natural telephone response and Jev plan reviewed

Proposed VXP-01–06 under AGP-06/07/09, PERF-02/03, M2/M4/M5,
US-04/05/06/08: researched primary vendor documentation and independently reviewed
an optional Jev decision layer plus runtime-owned waiting speech. The proposal
reuses existing waiting-phrase/music/receipt behavior, separates useful-answer latency
from filler, gates dynamic TTS/metadata on non-regression and starts Jev in Turkish
shadow evaluation. Speculative planner racing is excluded from first delivery;
narrow read-only routing is research-only until actual benefit is established.
[Proposed plan](VOICE_RESPONSE_EXPERIENCE_PLAN.md) and
[review disposition](validation/voice-response-plan-review-2026-10-27.md).
No implementation, new provider connection, runtime benchmark or live change occurred.

## 2026-10-27 — Nazlı Telegram action configured through management MCP

AGP-06/07, MCP-06, M4–M5, US-08, ADR 0011–0012: at the owner's explicit request,
Nazlı draft v7 now uses the same enabled Telegram connection and action fields as
Kübra's currently bound immutable release. The `answered` call-finalized action sends
agent identity, caller-number provenance, duration and structured summary/status;
no transcript field is selected. Exact action review was checked and its standing
grant authorized through public HTTPS MCP. All other draft fields remain identical
to v6, including model, instructions, variables and eight read tools. The existing
MCP grant remains enabled, prepared voice digest is unchanged, and release preparation
returns `ready_to_publish`. Nazlı remains unpublished and the existing number binding
is unchanged. No test notification or carrier call was sent. Temporary MCP token
revoked and session logged out. Private evidence: `.local/nazli-telegram-20261027/`.
This resolves the post-call configuration item in the
[preflight record](validation/nazli-preflight-2026-10-27.md); activation remains separate.

## 2026-10-27 — Nazlı live-data preflight completed; activation pending

AGP-06/07/09, MCP-06, M4–M5, US-08: public MCP reports draft v6 voice ready and
`prepare_release` returns `ready_to_publish`; both WAV previews pass manifest checks.
Five real-data question scenarios and a three-turn email-resolution/person-cost
conversation were exercised with the selected model and production read-tool guards.
Counts, partial costs and zero values match the source; missing full-user aggregation
remains unsupported. Caller authentication/access policy is an explicit open item
for exposing organizational analytics by phone. No publication, binding or carrier
call occurred; existing bound route is ready. No post-call action is selected.
[Scope, remaining items and evidence](validation/nazli-preflight-2026-10-27.md).


## 2026-10-27 — Nazlı voice prepared through management MCP

AGP-06 / MCP-06, M2/M4/M5, US-08, ADR 0011–0012. The owner requested actual
MCP-triggered generation. Read current draft v6, invoked `alojan_prepare_voice`
with an operation key, observed queued then ready via `alojan_get_voice_status`,
and retrieved both clips through `alojan_preview_voice`. The resident Linux EMA
coordinator processed the request. Greeting: 8.28 s / 132,524 bytes; unavailable:
4.00 s / 64,044 bytes. Both are mono 8 kHz / PCM16 WAV; downloaded hashes match
MCP responses and PCM is nonempty. Preview playback quality and a real phone call
have not been accepted. The coordinator is active and gateway admission is open.
Nazlı still has no publication or number binding. Temporary agents-only personal
token revoked and account session logged out. Private evidence and previews:
`.local/nazli-voice-20261027/`; no credentials or audio committed.


## 2026-10-27 — Instruction variables and analytics preflight

AGP-06/07/09, M4–M5, CFG-01, US-08: primary Linux suites report 97, 114 and 111
passes (overlap); 47 isolated HTTPS browser cases pass. Legacy release compilation,
local midnight/timezone refresh, agent isolation, expansion limits, no-answer jobs
and currency whitespace regression covered. v10-compatible readers/preparer/UI are
live, existing bound route ready and admission open. Nazlı is draft v6 with eight
read tools and no binding/publication. Real-model synthetic analytics checks are
separate from phone/GPU/carrier/load acceptance; no new carrier pass is recorded.
[Detailed evidence](validation/prompt-variables-2026-10-27.md).


## 2026-10-27 — Self-service UI fixes validated and deployed

AGP-06/07/09, ADR 0011, requirements §11.2. Primary Linux isolated HTTPS browser
suite: **44 passed (1.2m)**. Regression cases cover history draft retention/version
conflicts, session cleanup, uncertain creation and unsafe MCP integers. Type checks
and production build passed. Private-preview web healthy after deployment;
login/registration HTTPS 200, eleven other Alojan containers unchanged. No new
carrier call, GPU test or external delivery. [Evidence](validation/ui-fixes-2026-10-27.md).

## 2026-10-27 — Self-service UI review evidence

AGP-06/07/08/09, ADR 0011, requirements §11.2. Primary Linux isolated HTTPS browser
suite: **36 passed (1.1m)**; second run including three defect-reproduction probes:
**39 passed (1.1m)**. Three P2 UI findings were reproduced at review time and were
subsequently fixed as documented above; probe success means the defect was
reproduced. No live configuration, external delivery, model or carrier
test. [Review details](validation/ui-review-2026-10-27.md).

## 2026-10-27 — MCP and webhook review regression evidence

AGP-07/08/09, ADR 0011, US-07/08, requirements §11.2. Primary Linux:
`test_mcp_runtime`, `test_mcp_discovery`, `test_mcp_tools`, `test_mcp_schema`,
`test_mcp_oauth`, `test_http_actions`, `test_http_receiver`, `test_action_delivery`,
`test_action_grants` and `test_delivery_management`: **257 passed in 201.74s**.
No confirmed P0/P1 finding from source review and these regression checks. Disposable
database schemas, synthetic MCP/OAuth peers and local HTTP receivers; no new provider,
carrier, GPU or production-delivery acceptance. No live configuration or service change.
Load/soak and latest-release live end-to-end gates remain separate.

## 2026-10-27 — Publication/restart fixes deployed

AGP-03/06/09, ADR 0011, US-01/08. **147 primary Linux tests passed in 125.08s**;
four focused regressions passed again in **16.82s** after the retirement race guard.
Restricted HTTP publication reaches managed-process readiness/binding without restart;
old call snapshots remain pinned. A revoked unbound agent cannot block healthy restart.
Synthetic speech only. Linux agent/API updated after backup/drain: one ready bound number,
admission open, data preserved, unchanged GPU workers. No new carrier call/inference/send.
[Evidence](validation/publication-activation-2026-10-27.md).

## 2026-10-27 — Single active number binding regression

AGP-03, ADR 0011, US-01/08. Primary Linux number-routing suite: **16 passed in
12.58s**. Existing single active binding, unique verified ownership, concurrent
version rejection and call snapshot retention satisfy the owner's one-agent-per-number
requirement. Tests use disposable schemas; no live number changes, external actions
or handset calls. This is routing integration evidence, not carrier/performance acceptance.

## 2026-10-27 — Coordinated Linux platform deployment complete

AGP-07/08/09, M4–M5, ADR 0011, US-01/07/08. The owner explicitly requested Linux
activation after deferring summary quality. Applied additive migrations 0020–0025
(26 ledger entries total), refreshed restricted roles, and deployed compatible web,
management, agent, summary/delivery and MCP-discovery services. The host voice-preparer
now uses an immutable matching source/runtime release. Existing three releases compile
with identical voice instructions, engine settings, speech and synthesis configuration.

Primary Linux predeployment: **170 passed in 127.44s**. Deployed read-only HTTPS owner
checks passed login/logout, Kübra configuration, existing EMA audio decoding, navigation,
MCP controls and HTTP connection/action controls with no authenticated API/browser
errors or configuration mutations. One verified number is ready; native admission is
open. Gateway, ASR, TTS, PostgreSQL and legacy health API instances were preserved.
Existing records, profiles, routing and action journal state were verified unchanged.
No new remote tool invocation or external notification was sent.

The first cutover stopped at a fingerprint check that included a newly added null
column; previous services were automatically restored. Original-column comparison
proved data preservation. The corrected second attempt completed; both attempts and
backups are retained. This is deployment/recovery evidence, not full PERF acceptance.
[Deployment evidence and rollback boundaries](validation/platform-rollout-2026-10-27.md).

Work package 1 is complete. Next: latest-release end-to-end agent/voice/tool/action
validation, then matched performance/isolation/soak and full recovery/rollback coverage.
Summary quality remains deferred; the second number and public launch remain separate.

## 2026-10-27 — Owner defers summary quality; rollout work resumes

The owner explicitly deferred further post-call summary wording/semantic quality work
until later. AGP-08 / M4–M5, US-07: preserve existing summary generation, records and
known failed evidence; do not count deferred checks as passed. Summary quality is no
longer a blocker for the current owner-directed rollout. Do not spend further model
requests on that quality corpus until the owner resumes it. This does not defer
workspace isolation, output validation, tool grants or durable action delivery, and
it does not waive live conversation quality or voice performance.

Remaining current-rollout work, grouped into four work packages:

1. AGP-07/08/09: build and activate compatible current API, web, agent and worker
   versions with required additive migrations. Check compatibility/readiness before
   opening the new MCP/webhook capabilities; preserve Kübra and disabled Berkcan routing.
2. AGP-06–09: verify the newly deployed end-to-end agent/release/number/tool/action
   flow, including real prepared assets and call records. Reuse existing accepted
   Hindsight read and loopback receiver evidence within their exact scope; other MCP
   tools/OAuth providers need qualification only when selected. Existing handset
   acceptance is retained, not erased; latest-release coverage remains separate.
3. AGP-09 / PERF-01–05: matched voice performance, interruption and background HTTP/
   worker isolation, followed by single-call soak/churn. Do not claim five/50-call
   capacity; the owner has deferred the immediate simultaneous-handset trial.
4. AGP-09 / PERF-06: validate current-release restart/recovery and rollback without
   record loss or external-write replay, then close the controlled rollout acceptance.

Public domain/email recovery and public launch remain a separate later scope from the
approved private preview. The second number/bot stays disabled until provided. Neither
is a blocker for the current single-number private rollout. Next: work package 1.
No code, deployment, test result or model setting changed in this prioritization update.

## 2026-10-27 — Linux restored; acceptance harness repaired, quality gate open

AGP-08 / M4–M5, ADR 0011, US-07/08. Linux is reachable and its distinct authorized
model key has usable quota. Relevant source files matched before changes. No account,
spending-limit or serving configuration changed.

Live test evidence paths now fail before call setup/inference, and six-second request
spacing runs outside the production worker deadline. Final primary Linux regression:
**29 passed in 1.10s**; Ruff lint/format passed. These checks include the earlier four
harness checks; counts are not additive.

A private existing-model instruction screen passed **13/13**, but the shared-policy
candidate failed the first expanded legacy case: a corrected Thursday date became
Monday. The candidate was rejected and shared production policy restored byte-for-byte.
Alternative-model screens also did not establish full acceptance. Preserve all failures;
no model, preset or release was promoted. Full summary quality and coordinated
voice/load/rollback gates remain open. [Evidence](validation/summary-model-recovery-2026-10-27.md).

## 2026-10-26 — Blocked audit: Linux and inference access required

AGP-08 / M4–M5, US-07/08. A fresh bounded SSH check again terminated with exit
255/connection timeout, on the third consecutive goal turn with this Linux blocker.
Read-only local key metadata still reports an exhausted limit. All prior test handles
are terminal; no live job is being restarted or counted as a verified wait.

Independent discovery and local diagnostics are complete. Further semantic acceptance,
remote staging and rollout require restored Linux access and a usable authorized
model connection. No failed/skipped check qualifies as readiness. The blocked audit
threshold is met; the full live-readiness objective remains unfinished.


## 2026-10-26 — Model eligibility discovered; inference access unavailable

AGP-08 / M4–M5, US-07/08. Linux remains unreachable on the second consecutive goal
turn. Read-only discovery using the local project connection returned 21 eligible
models; the earlier GPT-4.1 mini candidate is absent. A supplementary Mac probe
produced no model outputs: all requests were denied. The existing-model control and
read-only key metadata confirmed that the local test key's spending limit is exhausted.
No account setting, production model, runtime or spending limit changed.

Linux connection identity/quota still needs verification; the local credential may
differ. Stop further inference on the exhausted local key. Tests, remote doc staging
and deployment remain pending. [Evidence and recovery steps](validation/summary-fact-boundaries-2026-10-26.md).


## 2026-10-26 — Stronger final-fact checks; model controls rejected

AGP-08 / M4–M5, ADR 0011, US-07/08. Shared summary assertions now cover changed
verbs, caller/recipient responsibility, withdrawn callbacks and complete uncertainty
quotes. Replaying 27 stored synthetic managed outputs: **19 passed, 8 failed**.
Shorter/Turkish policies and an extra review call failed acceptance and were not
adopted. Alternative model/provider controls failed before valid output; no quality
claim or production change follows from them.

Linux disconnected after completed tests; three SSH attempts timed out. Final test
source is synchronized; new documentation staging and account-filtered model
discovery await reconnection. Continue semantic qualification before rollout and
matched voice/load/rollback gates. [Evidence and handoff](validation/summary-fact-boundaries-2026-10-26.md).


## 2026-10-26 — Managed summary quality coverage; quote-schema experiment rejected

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
The same nine-case, three-repeat correction corpus now runs through scoped records,
published releases, restricted credentials and the separate worker. Primary Linux:
**25 passed, 2 failed across 27 managed cases**. All completed without external action
jobs; failures retold a superseded product and invented a person in document context.
The quality gate remains open. Exact quotes alone do not guarantee correct meaning.

A bounded quote-schema candidate failed 5/12 real cases and an alternate JSON protocol
failed 1/6; both were rejected. Production files were restored to the pre-experiment
snapshots. Retained changes are managed acceptance coverage and shared assertions;
prior 429 recovery remains intact. Final consumer checks: **60 passed in 21.50s**.
No serving restart, migration, model/preset change or deployment. No external sends.
[Evidence, manual review and limits](validation/source-fidelity-2026-10-26.md).

Next: resolve final-fact/correction fidelity in both managed and legacy/shared-policy
paths before coordinated activation and matched voice/load/rollback acceptance.


## 2026-10-26 — Bounded summary throttling recovery; quality gate remains open

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
The scoped summary worker now defers explicit HTTP 429 errors using its fenced lease,
60–300 seconds per cooldown and at most three total claims. Other jobs continue;
revocation is rechecked and no final event/action is emitted before completion.
Final primary Linux boundaries: **90 passed in 48.13s**; focused retry/fencing:
**39 passed in 25.12s** (overlap). No migration/dependency/service or live-turn change.

Ambiguity instructions now preserve the uncertain phrase without inventing a referent.
A focused real-model screen passed 6 cases, but expanded acceptance produced **37 passed,
2 failed in 289.44s**. The remaining failures changed singular wording inside a required
verbatim unresolved phrase. All 12 scoped typed-output cases and the new legitimate-
person/independent-product counterexamples passed. The full quality gate is still open.
No engine/transport/schema experiment was adopted. No serving restart or deployment.
[Detailed evidence and limits](validation/summary-quality-2026-10-26.md).

Next: finish uncertainty/source-fidelity acceptance, extend complex managed-runtime
coverage, then coordinated activation and matched voice/load/rollback checks. Do not
mark the live-readiness goal complete or promote this candidate from the partial pass.


## 2026-10-26 — Real extraction and TLS receiver checks; summary qualification open

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
The final real-model run passed all **12 scoped typed-output cases**, but the expanded
summary suite still failed **3 of 18** cases (invented person references and obsolete
correction narration). Overall: **27 passed, 3 failed in 135.96s**. This is a failed
summary acceptance gate, not live readiness. Shared summary policy removes contradictory
stale-note instructions; further quality work is required before activating it.

Controlled real loopback TLS receiver: **8 passed in 13.66s**, covering POST/PUT/PATCH,
authentication/payload/idempotency headers, rejection, hostname mismatch and lost replies.
DNS/routing and receiver credentials were synthetic. Authorized Google GET through the
production transport returned `failed/rejected` in 0.625s without following a redirect;
it is connectivity evidence only, not successful webhook delivery. No external POST.
Broad Linux compatibility: **146 passed, 1 skipped**; final boundaries: **98 passed,
1 skipped** (overlap; preserved legacy consumer artifact was not selected).

No new dependency, migration, service, model switch, media-path request or serving
restart. No candidate images were promoted/rebuilt after the failed quality gate.
Next: resolve final-meaning summary failures and qualify provider-rate-limit handling,
then coordinated activation and matched voice/load/rollback checks. Hindsight read
acceptance remains as recorded below. [Evidence](validation/real-outputs-receiver-2026-10-26.md).


## 2026-10-26 — Bounded MCP schemas and real Hindsight read accepted; candidate

AGP-07/08 / M4–M5, ADR 0011, US-07/08, requirements §11.2/12/14–16.
The earlier Hindsight schema rejection is resolved by deterministic bounded qualification.
Raw schemas/digests remain pinned beside qualified input/output schemas; MCP review v2
and release v8 prevent silent historical reinterpretation. Typed/null GUI controls,
fixed-argument exclusion and runtime result limits use those same bounds. Old strict
grants remain identical. No-answer enqueue explicitly supports v8. No migration,
dependency, daemon, per-turn discovery or media callback change.

Primary Linux: **234 compatibility tests passed**; final consumer-boundary review:
**112 passed** (overlap), including v8 unanswered actions and malformed grant rejection.
Final real HTTPS browser: **36 passed**. Production images and restricted-container
validation passed. Actual Hindsight discovery found **39 tools**; one fixed-argument
`list_banks` read returned no records in **0.794s**, with override/revocation blocked.
No remote writes, production activation or serving agent change. The Google GET remains
connectivity-only. [Detailed evidence and rollout limits](validation/mcp-schema-2026-10-26.md).

Next: real structured extraction, full receiver/payload acceptance, coordinated activation
and matched voice/load/rollback validation. Other MCP tools/OAuth remain unqualified;
the live-readiness goal is still active.


## 2026-10-26 — Real integration discovery and compatibility finding

AGP-07/08 / M4–M5, ADR 0011. Owner corrected the MCP target to
`<MCP_ENDPOINT>` and authorized a Google GET.
Production bounded discovery found 39 Hindsight tools in 1.241s. Google GET returned
301 with valid TLS in 0.536s; no redirect followed or call data sent. This is network/
discovery evidence, not granted tool or webhook payload acceptance.

Real `list_banks` / `get_bank_stats` schemas fail current operator qualification on
optional nullable/default/wrapped-output schema features. Next implement bounded
schema compatibility, then test the actual granted read executor against a synthetic
unmatched query. No remote tool writes, serving change or live activation occurred.
[Evidence and next acceptance](validation/real-integration-2026-10-26.md).


## 2026-10-26 — No-answer and interrupted-call actions; candidate only

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
Agents can select `no_answer` or `interrupted` for Telegram/HTTP actions. Intent uses
release v7/review v6. Scoped unanswered end/cancellation/reconciliation queues work
only when the pinned release explicitly opts in; default agents create no new job.
Unanswered finalization uses event v4 and `not_requested`, with no model preparation,
summary inference, note/transcript read or tool-result query. Conversation fields stay
null/unavailable. Exact answered `disconnected`/`failed` outcomes match interrupted;
this includes an ordinary caller hangup and is not a semantic unfinished-call detector.

Migration 0025 adds the terminal state without backfill. Re-provision routing INSERT
on scoped summary jobs and records SELECT on scoped immutable releases. No new daemon,
dependency, native/protobuf change or media callback I/O. UI exposes both conditions,
exact review and mutually exclusive no-answer/transcript controls. Sharing disclosure
cannot be played before answer, so that combination is rejected server-side too.

Primary Linux compatibility: **300 passed in 223.43s**. Real HTTPS browser: **35 passed
in 58.2s**, with zero production writes/external sends. Container validation, builds
and frozen worker imports passed. [Focused evidence and limitations](validation/call-lifecycle-actions-2026-10-26.md).
No serving migration/restart or real external request. Next: real extraction/receiver/
MCP acceptance, coordinated activation and measured call/performance/rollback checks.


## 2026-10-26 — Explicit bounded transcript sharing; candidate only

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
HTTP actions may opt into `bounded_text.v1`, with paired body-only text/status fields,
exact recipient consent and mandatory prepared greeting disclosure. Default is off.
A matching opted-in action copies only final caller/sent assistant text from its pinned
call, bounded to the first 100 rows / 8 KiB. Raw audio, model reasoning and tool context
are not sources. Sensitive caller content is not automatically semantically redacted.
Release v6 / review v5 / event v3 protect this intent; old default digests remain valid.
No new migration, dependency, role permission, model request or media-path work.

Primary Linux compatibility: **250 passed in 186.69s**; expanded transcript checks:
**9 passed in 6.67s** (overlap). Real HTTPS browser: **34 passed in 58.0s**.
Restricted management container validation, production builds and frozen worker imports
passed. [Detailed evidence and limits](validation/transcript-sharing-2026-10-26.md).
No serving restart/migration or real external send. No-answer/interrupted lifecycle,
real integration acceptance, coordinated activation and measured live performance
remain open; this completes the transcript slice only.


## 2026-10-26 — Summary-based post-call conditions; candidate only

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.4/11/12/14–16.
Telegram and HTTP actions now select `answered` (unchanged default), `summary_ready`
or `summary_failed`. A closed predicate evaluates only durable metadata after an
answered call ends and summary processing terminates. Unmatched actions create no
job or dispatch-scope entry. Matching siblings remain independent; existing atomic
finalization, original-target retries and no-historical-replay rules are preserved.

Conditional intent uses review v4 / release v5; default configurations retain their
old schemas/digests. Changing a condition requires fresh exact owner consent. Both
editors and the review dialog display the condition. No new migration, dependency,
service, model request or media-path work. Read-only PostgreSQL examples are included.

Primary Linux compatibility: **243 passed in 188.38s**; extended condition/example
suite: **7 passed in 4.54s** (overlap). Final browser: **33 passed in 1.0m**.
[Browser/build and review evidence](validation/action-conditions-2026-10-26.md).
No live migration/restart or real external send; Kübra/EMA and second-line state stay unchanged.

Remaining: optional transcript disclosure/access policy and separate no-answer/
interrupted lifecycle filters. The current finalizer supports only answered calls;
unsupported filters are rejected, never inferred from free-form hangup reasons.
Real receiver/model/MCP acceptance, coordinated activation, performance and public
launch/carrier gates remain separate. This completes the summary-condition slice,
not all AGP-08 work.


## 2026-10-26 — Declared output integration; synthetic inference/network

AGP-08 / M4–M5, ADR 0011, US-07/08. Primary Linux compatibility: **234 passed in
183.25s**; expanded output/role/SQL example suite: **11 passed in 9.29s** (overlapping).
The real Agents SDK parsed scripted structured output; real disposable PostgreSQL
and restricted roles exercised release pinning, immutable finalization, HTTP dispatch
through a synthetic transport and scoped call-detail reads. Latest-success selection
excludes late tool results and never reruns tools. [Final evidence](validation/declared-outputs-2026-10-26.md).

No real extraction-model request, external tool/webhook/message, new SIP/RTP call,
GPU synthesis, latency/capacity claim or serving restart. Real model extraction quality
and receiver acceptance remain untested; these checks are not carrier acceptance.

## 2026-10-26 — HTTP post-call integration; synthetic transport only

AGP-08 / M4–M5, ADR 0011, US-07/08. Primary Linux **187 compatibility tests passed**,
**16 expanded HTTP cases passed**, then **26 bounds/grant tests passed** (overlapping).
Final delivery/grant suite: **95 passed in 106.22s**.
Final browser: **31 passed in 55.4s** (20 real API journeys, 11 intercepted UI contracts).
Database, role isolation, publication, event finalization and queued delivery state
use disposable PostgreSQL schemas; HTTP/Telegram peers use synthetic transports.
No external endpoint, bot, carrier call or GPU synthesis was exercised.
[Final checks and candidate identities](validation/http-actions-2026-10-26.md).

Serving schema/services were not migrated/restarted. Functional isolation does not
establish P50/P95, simultaneous-call capacity or real receiver acceptance. HTTP
candidate activation requires migration/role/API/worker coordination; unknown writes
require owner-reviewed retry, never an automatic replay. AGP-08 custom extraction,
approved tool-output projection and expanded event conditions remain open.

## 2026-10-26 — OAuth lifecycle integration; no external or carrier trial

AGP-07 / M4–M5, US-08, ADR 0011. Linux final **195 service tests passed**;
**30 browser scenarios passed** (19 real API, 11 intercepted UI). OAuth protocol and
refresh peers are synthetic; database/roles and existing scoped API journeys are real
and disposable. No approved external provider or MCP tool was contacted.
[Checks, image identities and limits](validation/mcp-oauth-2026-10-26.md).

No serving migration/restart, external send, new SIP/RTP call, synthesis/GPU
qualification or latency/capacity measurement. OAuth/MCP real-provider acceptance and
coordinated deployment remain open. Existing Kübra/EMA and disabled second mapping
retain their prior status; candidate migration 0023 is not a carrier acceptance.

## 2026-10-26 — MCP builder browser acceptance; no carrier trial

AGP-07 / M4–M5, US-08, ADR 0011. Primary Linux: **25 browser scenarios passed in
48.8s**, including the real restricted-API MCP save/review/grant/remove/revoke
journey. Six of the 25 use intercepted API responses for UI fault/role/mobile cases;
they are not database or transport evidence. Remote discovery metadata is seeded
synthetically by the disposable-schema harness; no remote tool is discovered or
executed. Existing native authentication, publication, routing and Telegram UI
journeys also pass. [Detailed evidence](validation/mcp-ui-2026-10-26.md).

Only candidate source/builds changed. No serving migration/restart, external message,
new SIP/RTP call, GPU/voice qualification or latency/capacity measurement occurred.
Real MCP/OAuth and coordinated deployment remain open; Kübra's prior acceptance
and the disabled second-number mapping are not changed by these checks.

## 2026-10-26 — MCP runtime integration; no new carrier acceptance

AGP-07 / M4–M5, US-08, ADR 0011. Linux compatibility suite: **265 passed in 128.25s**;
final runtime/selection **71 passed in 56.78s**, schema/SQL **3 passed in 4.06s**
(overlapping suites). Actual Agents/MCP SDKs and PostgreSQL/gRPC readiness used synthetic external peers
and disposable workspaces. Checks cover pinned tools/grants, schema validation,
fixed-field protection, revocation/isolation, deadline/cancellation and scoped evidence.
Combined MCP/Telegram finalization was tested without running a delivery worker.
[Final checks and evidence](validation/mcp-runtime-2026-10-26.md).

No external MCP/Telegram request, live SIP/RTP test, new synthesis/GPU qualification,
browser change or serving deployment. Migrations 0020–0022 remain candidate-only.
Kübra, EMA, routing/capacity and the second disabled number retain their prior state.
Real server, carrier/load/latency and OAuth/builder gates remain open.


## 2026-10-26 — MCP selection/consent backend; no new carrier trial

AGP-07 / M4–M5, US-08, ADR 0011. Synthetic Linux tests validate reviewed read-tool
selection, fixed/runtime parameter separation, exact owner consent, tenant isolation,
revocation, drift and explicit runtime/publication blocking. Compatibility suite:
171 passed; subsequent dependency-isolation suite: 61 passed; final selection suite:
27 passed (overlapping counts). Restricted Docker HTTP checks and independent frozen
voice-preparer imports passed. [Detailed evidence](validation/mcp-selection-2026-10-26.md).

No real MCP endpoint/tool call, browser test, SIP/RTP trial, synthesis, external
message or serving rollout. Migrations 0020/0021 are not applied to live schemas.
Kübra/EMA, active routing, capacity and the disabled second-number mapping retain
their previous acceptance status. Runtime MCP and carrier/performance gates stay open.

## 2026-10-26 — MCP discovery backend; no call-path activation

AGP-07 / M4,M5: scoped connection/discovery APIs, job fencing and egress validated on
Linux with disposable schemas and synthetic HTTP transports through the real SDK.
No tool invocation, real MCP request, new carrier call, external notification or GPU
work occurred. Existing HTTPS flows passed against the candidate management image;
serving services and schema remain unchanged. This provides no new latency, quality
or capacity acceptance. [Evidence](validation/mcp-discovery-2026-10-26.md).

## 2026-10-26 — Self-service journey; synthetic routing boundary only

AGP-06 / M2,M5: 18 real HTTPS browser scenarios and 62 Linux service tests passed.
A disposable new account configured an agent, prepared synthetic WAVs through the
real job worker, published after explicit Telegram permission, and bound a synthetic
verified DID only after synthetic node readiness. Actual CallRouter checks proved
immutable call pinning and rejection of new calls after routing was stopped. These
are database/runtime integration checks, not SIP/RTP, GPU or carrier evidence.
Deployed owner smoke only read existing records/audio and opened/cancelled lifecycle
reviews. Nine application peers retained identity/health; only web was recreated.
No new live call or external message. [Evidence](validation/self-service-journey-2026-10-26.md).

## 2026-10-26 — Response timing UI; historical observations only

AGP-06/P1: 51 Linux tests and 13 isolated HTTPS scenarios passed. Historical gateway
measurements now appear in scoped, filtered distributions with missing/excluded
counts. Imported 16 existing observations; these are server-side estimates, not
new handset measurements. Read-only owner smoke passed. Only management/web
restarted; eight peers retained identities and health. No new carrier call, external
notification, matched performance comparison or concurrent capacity acceptance.
[Evidence](validation/performance-ui-2026-10-26.md).

## 2026-10-26 — Release rollback UI; no new carrier trial

AGP-06 / M2,M5: 44 Linux release/routing/grant tests and 12 isolated HTTPS scenarios
passed. Rollback browser checks use synthetic releases, a restricted database role
and one synthetic binding; drafts and routing remain unchanged. Real owner checks
only read history, existing audio and records. Only web is updated; management,
voice and background services retain identities. No live rollback, call, external
send, GPU/capacity test or matched latency evidence.
[Evidence](validation/release-rollback-ui-2026-10-26.md).

## 2026-10-26 — Prepared audio UI and Telegram builder; no new carrier trial

AGP-05/06 browser/API tests passed (9 browser scenarios, 30 Python tests). Existing
Kübra EMA audio decoded through the private management preview. No fresh synthesis,
handset test, agent/binding change or external notification; eight voice/background/
DB peer containers retained identities and health. Only management/web were updated.
This extends UI acceptance, not carrier or latency acceptance. [Evidence](validation/web-actions-2026-10-26.md).

## 2026-10-26 — Private frontend preview; no new call acceptance

AGP-06's approved first UI slice passed seven isolated HTTPS browser scenarios and
a read-only owner account smoke. Web/TLS use separate bounded containers; only the
management API was recreated for the private preview origin. Eight peer containers,
including voice and background services, retained their identities and health.
No serving agent draft/release/binding was changed by the smoke. No call, external
notification, GPU benchmark, simultaneous-call or matched latency test was added;
the existing handset evidence below remains the latest actual voice acceptance.
See [frontend evidence](validation/web-preview-2026-10-26.md).

## 2026-10-26 — Managed handset retry passed; notification recovered

Real Netgsm inbound call at 08:05:38 UTC answered at 08:05:41 and ended at
08:06:33; answered duration **52.196 seconds**. Owner explicitly reported that
everything worked as well as before. Native PCMA media, seven caller turns, two
interruption events and confirmed cleanup were recorded; scoped DB note saved.

An older summary/delivery image initially rejected the pinned instructions at its
former length limit. Updating the shared contract in those two independent workers
left all voice services intact. Exact release image validation passed and five
Linux regressions passed (4.85s). The original job recovered without manual state
changes: summary finalized, Telegram accepted on one send attempt with a stored
remote receipt. This verifies provider acceptance, not that the owner read the
message. One successful call does not establish latency distribution, capacity,
soak or the complete carrier scenario matrix. [Details](validation/in-place-platform-2026-10-26.md#successful-handset-retry-and-post-call-recovery).

## 2026-10-26 — First handset trial rejected; prefix fix awaiting retry

The owner heard Netgsm's unavailable announcement. Trusted inbound signaling
reached the gateway, which rejected the called number with SIP 404 before setup.
Private deployment normalization was disabled for the trunk's ten-digit `850…`
Request-URI format. Explicit `ALOJAN_CALLED_NATIONAL_PREFIX=0` now converts that
format to the existing verified canonical DID; source/ownership checks are intact.

Reproduced the failure before correction. Linux regression: **3 native session
cases passed (77.99s)**, including the carrier format, interruption and cleanup;
**1 identity CTest passed (1.02s)**. Only the gateway was recreated, using its
unchanged image, and native admission reopened. Await the owner's next call for
real greeting/audio/notification evidence. Prior loopback success did not validate
the actual carrier number format. [Details](validation/in-place-platform-2026-10-26.md#first-handset-failure-and-prefix-correction).

## 2026-10-26 — Existing managed line ready for owner phone trial

Owner authorized the unused existing line for testing. Existing DB migrated with
historical preservation; Kübra is bound to the owner's account and verified DID.
**46 Linux SIP/session/admission tests passed (147.41s)** and **10 CTests passed
(3.88s)**. Two real CUDA ASR/EMA/OpenRouter loopback calls persisted scoped notes
and summaries. Final revision retained deployed partial-hint calibration and
completed in **33.29s**; synthetic actions are terminal/paused without sends.

Native admission is open; temporary INVITE firewall table removed. Next external
acceptance: owner calls the existing line and checks identity, audio, correction,
interruption, farewell and actual post-call Telegram delivery. Do not send an extra
synthetic Telegram test. Second line remains absent. Model intake behavior passed
only **3/6** checks despite six completed turns; premature topic-only note-taking
is a known failure. No new handset, matched PERF, capacity or soak pass is claimed.
[Deployment and failed harness evidence](validation/in-place-platform-2026-10-26.md).

## 2026-10-26 — Maintenance deployment on the primary Linux host

Pending documentation transfer verified complete. A privileged, owner-authorized
bootstrap INVITE fence preceded the compatible gateway change; old call lifetime
elapsed and all recorded calls/summaries were complete. The new gateway confirms
closed/local-drained, and three actual model workers pass normal and maintenance
health after startup. Only four voice containers changed. API/Telegram/PostgreSQL
remain untouched. This is real startup evidence, not carrier or PERF acceptance.

Three mixed-version fixture attempts failed at configuration/lease guards. Exact
retained-stack smoke then passed one real CUDA/OpenRouter two-turn call, durable
note/summary and resource cleanup; maintenance derivatives restored afterward.
This is functional control evidence, not matched latency or carrier acceptance.

Subsequent reconciliation errors exposed missing platform schema in production.
Resident agent is now stopped; gateway/ASR/TTS remain closed. Startup now checks the
required schema before listening. **43 Linux migration/startup/maintenance tests
passed in 20.94s**, no skips/failures. Matching candidate schema/runtime and managed
real voice remain next; no production migration or external notification occurred.
See [evidence](validation/maintenance-rollout-2026-10-26.md).

## 2026-10-26 — Worker quiescence after cancellation and cleanup

Final Linux service/call regression: **248 passed in 51.57s**, including 19 new
maintenance tests, zero skips/failures. Real gRPC checks use scripted inference:
closed setup/ASR/TTS/agent admission, lease retention, cancelled native work still
running, agent end/stream cleanup, queued summary preservation, conservative error
handling and uncached operator health receipts. EMA adapter cleanup tests simulate
CUDA synchronization and do not claim actual GPU execution.

Real local SIP/prepared/session/supervisor suites: **83 passed in 218.16s**. Following
the final shared cancellation fix, **11 managed native-session tests passed in
86.36s**, no skips/failures. Only the existing audioop deprecation warning remains.
Three isolated packages passed imports/CLI checks. No carrier/model/PERF acceptance
or live deployment was performed; the seven resident services were healthy and
unchanged at the last check. SSH was lost during the final documentation copy;
that transfer remains pending. See [evidence](validation/worker-quiescence-2026-10-26.md) for the reproduced cleanup
bug, initial failed run and exact image/validation boundaries.

## 2026-10-26 — Supervisor and Docker restart preserve maintenance admission

New supervisor/real loopback SIP-RTP checks: **12 passed in 17.60s**, no skips or
failures. PCMA/PCMU calls continue through closure; missing/invalid persisted state
rejects new calls; restart stays closed; explicit reopen admits calls. Startup
acknowledgement gating, health-failure reap and launcher forwarding are covered.
Initial existing regression: **117 passed / 11 skipped in 230.33s** because the DB
environment was omitted; skipped cases are not acceptance. DB-enabled rerun: **78 passed in 202.64s**, zero skips/failures. Together the
two regression runs cover all **128 distinct existing scenarios** successfully.

The isolated Docker gateway also passed actual automatic restart after a forced
native crash, preserved 486 while closed, SIP OPTIONS health during maintenance,
and 200 after explicit reopen. No carrier ports, GPU, DB or secrets were used.
Test container removed; seven live containers remain healthy and unrestarted.
[Evidence](validation/supervised-admission-2026-10-26.md) records exact artifacts.
Remote worker/GPU quiescence, matched latency and live deployment remain pending.

## 2026-10-26 — Native admission drain without ending existing calls

Focused real loopback SIP/RTP suite: **8 passed in 16.29s**, no skips/failures.
PCMA/PCMU media survives closed admission; new/retransmitted calls receive 486 even
with spare capacity. Explicit resume admits another call while the first remains
active. Already-ringing calls complete, pending managed setup/cleanup drains locally,
closed startup rejects until resumed, and malformed startup values fail. Native
CTest: **10/10 passed in 3.84s**. Broad existing SIP/prepared/managed-session suites:
**120 passed in 318.19s**, zero skips/failures. See
[full evidence](validation/admission-drain-2026-10-26.md) for deployment boundaries.

No CUDA/provider/carrier/PERF result is inferred. Local drain does not acknowledge
remote GPU quiescence; the timed-out cleanup case remains explicitly unconfirmed.
The seven resident services are healthy/unrestarted, and their old gateway/supervisor
must not receive the new control signals before a compatible deployment is verified.

## 2026-10-26 — Existing EMA pack reused without new inference

Verified deployed tr-v5-kubra source and image bytes; candidate draft v2 changes only
the genitive apostrophe to match its exact greeting text. Greeting (5360 ms including
400 ms silent pad) and unavailable (4000 ms) WAVs are byte-identical to live assets.
Operator repackaging checks original text/audio digests, model identity, rate, frames,
duration, silence and bounded regular files before immutable scoped installation.
Linux pack/release/cache suites: **49 passed in 8.95s**, no skips. This is artifact
integrity/reuse evidence, not new synthesis, listening, carrier or PERF acceptance.
See [evidence](validation/voice-pack-preparation-2026-10-26.md). Real voice comparison
still requires an explicit admission fence; a recent idle DB query is insufficient.

## 2026-10-26 — Live backup restoration and candidate owner preparation

Actual snapshot-consistent live backup restored with all ten original tables matching;
repeat upgrade through all 16 migrations retained original data and created no replay
or inferred ownership. Separate candidate DB now contains the requested Burhan workspace,
Kübra draft and encrypted provider/Telegram references, without grants, publications,
phone bindings or jobs. Owner password setup and production transfer remain pending.

Linux native-auth/draft/provider/Telegram/grant suites: **42 passed in 25.09s**, no skips.
Restricted secret/live-record access denial and session revocation verified. Real HTTP
probe in the independent resource-limited management container returned ready=200 and
anonymous workspace=401; no host port published. No carrier call, GPU/API inference,
message or PERF acceptance. Live schema remains at three migrations; seven resident
containers remain healthy and unrestarted. See [evidence](validation/owner-preparation-2026-10-26.md).

## 2026-10-26 — Rollback package checks and instruction migration preparation

Linux resumed: first expanded run 71 passed / 1 failed in 72.60s due to an immediate-
claim assumption under SKIP LOCKED contention. Added deterministic busy-gate coverage;
the concurrent retry may claim on the next poll but still consumes one approval and
creates one generation/attempt. Focused 2 passed in 3.01s; expanded six-suite rollback/
DB/routing/records/delivery run **115 passed in 124.70s**, no skips. Full live instruction
round-trip, 20k field limit and unchanged compiled UTF-8 budget plus draft/runtime/
release/startup suites: **71 passed in 26.06s**, no skips.

Compose and both rebuilt Docker packages passed configuration/import/schema checks
without activation. Seven resident containers remain healthy and unrestarted. A private
offline business draft holds the complete existing instructions and matches the 11 legacy
speech fields. No account transfer, publication, real inference, live rollback/SIP test,
external send or PERF acceptance. See [resume evidence](validation/platform-resume-2026-10-26.md).

## 2026-10-25 — Restricted legacy rollback consumer (AGP-09)

Primary Linux **14 passed in 8.95s**, zero skips: restrictive legacy-record policies,
forged workspace isolation, denied managed writes/secret reads, privilege rejection,
and preserved deployed consumer source processing only a synthetic legacy call.
Four module checksums matched the resident image. Telegram transport was fake;
no real message, inference, carrier call or production restart occurred.

Initial 14 setup errors exposed PostgreSQL catalog predicate evaluation order;
explicit CASE protection corrected the sequence-privilege query. Expanded regression,
Docker package build and Compose validation remain unverified because SSH timed out
after the successful focused run. No full rollback, PERF or live acceptance claimed.
See [rollback evidence](validation/legacy-rollback-2026-10-25.md) for the operator
sequence and remaining synchronization/validation work.

## 2026-10-25 — One-message Telegram acceptance and migration preflight

AGP-05/09, PERF-02: explicitly approved one synthetic message to the existing
Telegram target using the built worker image's real adapter. Telegram returned an
exact-target positive receipt; the private exclusive-create journal prevents another
send. No historical data, queue, model call or automatic retry. This validates the
adapter/destination, not recipient reading or a real scoped end-to-end call delivery.

Linux synthetic-data migration rehearsal **3 passed in 0.84s**. Expanded migration,
profile, scoped records and delivery-management regression **66 passed in 56.36s**,
zero failed/skipped. Initial collection lacked optional httpx; documented pinned test
overlays resolved it. Rehearsal covers unchanged legacy data/queue state, no inferred
ownership/action seed, repeat migration and complete rollback on late SQL failure or
bounded lock wait. No production schema upgrade or private-data clone was performed.

Two isolated benchmark tests passed in 2.16s: scoped admission n=50 P50/P95
21.54/39.68 ms; cold synthetic preload n=30 1.1114/1.1293 ms; warm in-memory pin
n=10000 0.0028/0.0028 ms. No matched voice/inference/RTP/load/soak gate is claimed.
All seven resident containers remained healthy and unrestarted. The old global summary
consumer must be fenced before managed jobs and cannot be blindly restored over them.
See [the detailed acceptance evidence](validation/platform-preflight-2026-10-25.md).


## 2026-10-25 — Owner-reviewed delivery retries (AGP-05)

Primary Linux: expanded PostgreSQL/roles/API/delivery/runtime/native loopback suite
**296 passed in 270.87s**, zero failed/skipped, existing audioop deprecation warning.
Final management role/concurrency/renderer-hardening suite **24 passed in 25.94s**.
Earlier focused runs: 15 passed in 26.37s, then 71 passed in 91.13s. External model and
Telegram transports remain synthetic; no real destination or carrier acceptance.

Coverage includes metadata privacy, owner-only selected-text review, Origin/CSRF,
explicit duplicate acknowledgement, foreign workspace/agent/cursor denial, 52-item
keyset pagination/filtering, exact rendered text after draft changes, idempotent and
distinct concurrent requests, stale-generation rejection, three-round cap, original
revoked grant/target/issuer rejection before consent and before dispatch, independent
requester demotion/disable, active/sent-job denial, failed/paused retries with restored
authority, audit rollback, irreversible consumption, concurrent consume-once, renderer
drift and role/state/consent immutability. The consumer never sends from the HTTP request.

Final management and worker images import with networking disabled/read-only filesystems
and dropped capabilities; management includes 0015. Compose validation, Ruff and nine
changed-file format checks pass. No C++ rebuild/CTest repeat, live restart/DB migration,
real Telegram message or second-line activation. Real Telegram permissions/delivery,
frontend, matched voice/PERF and controlled ownership migration remain pending.


## 2026-10-25 — Scoped Telegram delivery consumer (AGP-05)

Primary Linux evidence: final expanded suite **275 passed / 0 failed / 0 skipped**
in 250.27s, with the existing Python audioop deprecation warning. Real PostgreSQL
migrations/roles/RLS and native loopback SIP are exercised; summaries/HTTP transport
are synthetic. No real provider, speech inference, carrier or Telegram send is claimed.
Initial focused 52/1 failure was an already-consumed mock response; corrected streaming
fixture passed with 62/0 before the expanded run. See PLAN.md for exact scope.

New cases cover atomic summary/event/job rollback, same/different-workspace agent and
bot isolation, immutable original fields/targets/releases/grants, original-grant FK,
all five live revocation checks, concurrent claims, stale fences, pre-send crash retry,
post-send crash/cancellation unknown state, terminal no-replay, bounded backoff/attempts,
workspace fairness and provider 429 cooldown. Adapter tests cover exact success receipt,
wrong chat/zero/boolean message IDs, migrated targets, malformed/oversized/5xx replies,
connect versus write/read failure, DNS private/special ranges, fixed Host/SNI and disabled
proxy/redirect. Real worker subprocess stop/restart uses synthetic networking and proves
no uncertain-job replay. V2 preload succeeds only with the exact workspace.

Management/worker images built and imported with network disabled/read-only/capabilities
dropped; management packages 0014 and combined Compose configuration passes. Source Ruff
and 13-file formatting checks pass. No resident restart, production DB mutation, ownership
migration or second-line activation. C++/CTest were not rebuilt/repeated in this slice.
Actual bot permissions/delivery, audited manual retry, backlog soak and matched voice
latency/resource acceptance remain open before controlled live migration.

## 2026-10-25 — Explicit agent action consent and release binding

AGP-05 / CFG-07/15, M4/M5, ADR 0011, US-07/08. Authorized Linux checkout, disposable
PostgreSQL schemas/roles, synthetic bot tokens/identities/speech. No external send.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_action_grants.py tests/test_agent_drafts.py \
  tests/test_agent_releases.py tests/test_telegram_connections.py -q --tb=short
# Initial focused run: 38 passed in 19.76s.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_action_grants.py tests/test_telegram_connections.py \
  tests/test_provider_connections.py tests/test_summary_worker.py tests/test_managed_startup.py \
  tests/test_release_readiness.py tests/test_number_routing.py tests/test_call_initialization.py \
  tests/test_prepared_releases.py tests/test_answered_lifecycle.py tests/test_scoped_call_records.py \
  tests/test_agent.py tests/test_agent_drafts.py tests/test_agent_releases.py tests/test_agent_runtime.py \
  tests/test_agent_runtime_database.py tests/test_native_auth.py tests/test_database.py \
  tests/sip-integration/test_managed_session.py -q --tb=short
# 267 passed, 1 failed in 192.00s; existing audioop warning only.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_action_grants.py tests/test_scoped_call_records.py \
  tests/test_agent_releases.py -q --tb=short
# After historical fixture correction: 43 passed in 28.84s, no skips.
docker build -f infra/docker/management.Dockerfile -t alojan-management:action-grants-validation .
docker build -f infra/docker/action-worker.Dockerfile -t alojan-action-worker:action-grants-validation .
# Both built; both imported with --network none --read-only --cap-drop ALL
# and --security-opt no-new-privileges. Management packages migration 0013.
docker compose --env-file .local/dev.env -f infra/compose.yaml \
  -f infra/compose.management.yaml -f infra/compose.credentials.yaml \
  -f infra/compose.worker.yaml config --quiet
# Passed; no resident services started or restarted.
```

The broad-run failure was UndefinedColumn(action_grant_id) in the pre-0009 upgrade
fixture, which called the current publisher against historical schema. The fixture
now inserts its synthetic v1 release with the historical SQL contract, then applies
all migrations twice and checks scoped-job ownership, unassigned legacy jobs, empty
finalization/outbox and null action_grant_id. The current management schema requirement
was retained. The full 268-test command was not repeated; all affected grant, publication
and scoped-record suites passed in the final 43-test rerun.

Coverage: schema/field bounds and source/status coupling; owner/editor/viewer/CSRF and
cross-workspace/agent checks; changed digest/version rejection; prompt edits do not
retarget historical releases; missing consent prevents publication atomically; concurrent
consent returns one grant/audit entry; revoked grants count toward the cap; grant/target
revocation and disabled/demoted issuer prevent publication/rollback; new consent does
not replace a revoked historical grant; RLS and nonmanagement write denial; immutable
grant/FK checks; missing 0013 readiness denial; manifest v2 schema validation and explicit
runtime/preload rejection before the delivery consumer exists. Legacy v1 SIP/RTP flows
passed with scripted inference. No production ready receipts were manufactured.

Linux Ruff check and 30-file format check passed; full changed-source diff reviewed,
git diff --check passed. Sources match the Mac checkout; docs are mirrored to
`.local/agent-platform-design-review/implementation/`, preserving independently edited
Linux root docs. Code graph refreshed without a shared artifact. Native CTest was not
repeated because no C++ changed; existing separate evidence remains below. No real
model/GPU/carrier/Telegram delivery, performance, live migration or second-line acceptance.

## 2026-10-25 — Telegram destination authoring and restored Linux validation

AGP-05 / CFG-07/15, M4/M5, ADR 0011, US-07/08. Primary Linux development host;
actual PostgreSQL migrations/RLS/roles and private managed-process regression. Tokens,
identities and speech outputs are synthetic; no Telegram/provider traffic was sent.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_telegram_connections.py \
  tests/test_provider_connections.py -q --tb=short
# 10 passed in 6.20s.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_telegram_connections.py \
  tests/test_provider_connections.py tests/test_summary_worker.py tests/test_native_auth.py \
  tests/test_agent_drafts.py tests/test_agent_releases.py tests/test_number_routing.py \
  tests/test_release_readiness.py tests/test_managed_startup.py tests/test_database.py -q --tb=short
# 106 passed in 66.06s; no skips.
docker build -f infra/docker/management.Dockerfile -t alojan-management:telegram-validation .
docker build -f infra/docker/action-worker.Dockerfile -t alojan-action-worker:telegram-validation .
# Both passed. Both entry points imported with --network none --read-only,
# --cap-drop ALL and --security-opt no-new-privileges.
docker compose --env-file .local/dev.env -f infra/compose.yaml \
  -f infra/compose.management.yaml -f infra/compose.credentials.yaml \
  -f infra/compose.worker.yaml config --quiet
# Passed; no services started.
```

Regression covers owner/editor/viewer/foreign-workspace access, CSRF, metadata-only
responses/audit, immutable destination/key and irreversible revocation, purpose/scope/
identity envelope binding, old provider ciphertext compatibility, all current private
roles denied Telegram ciphertext, unsafe role reprovisioning rejection, bounded input,
missing key fail-closed, concurrent limit admission including revoked rows, and management
readiness rejecting missing migrations 0011/0012. Creation leaves legacy outbox empty.

Linux Ruff check and six changed Python files' format check passed, as did full-diff
review and git diff --check. Final source checksums match both checkouts. All pending
provider-turn documentation plus current documentation were copied to the existing
`.local/agent-platform-design-review/implementation/` mirror, preserving independently
edited Linux root docs. Graph index refreshed locally without persisted graph artifacts.

No new C++ change; CTest was not repeated (prior 10/10 result remains below). No native
latency, CUDA, real bot/chat verification, delivery, carrier or resident deployment
acceptance is claimed. Agent action/grant bindings and finalized-event delivery remain
next; no live mapping, owner migration or second line was changed.

## 2026-10-25 — Scoped provider credentials and summary worker

AGP-02/03/05 / CFG-04/07/15, M1/M4/M5, primary authorized Linux checkout.
Real PostgreSQL/RLS, private RPC, process signals and native SIP/RTP regression;
speech/model outputs are synthetic. SDK Authorization routing uses MockTransport,
and a real summary-worker subprocess handles a revoked credential without contacting
the provider. No real OpenRouter/Telegram/CUDA/carrier acceptance follows.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_provider_connections.py \
  tests/test_summary_worker.py tests/test_managed_startup.py tests/test_release_readiness.py \
  tests/test_number_routing.py tests/test_call_initialization.py tests/test_prepared_releases.py \
  tests/test_answered_lifecycle.py tests/test_scoped_call_records.py tests/test_agent.py \
  tests/test_agent_drafts.py tests/test_agent_releases.py tests/test_agent_runtime.py \
  tests/test_agent_runtime_database.py tests/test_native_auth.py \
  tests/sip-integration/test_managed_session.py -q --tb=short
# 250 passed in 191.43s, no skips; existing audioop deprecation warning only.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_provider_connections.py tests/test_summary_worker.py \
  tests/test_managed_startup.py tests/test_release_readiness.py -q --tb=short
# Final review/revocation coverage: 38 passed in 28.11s, no skips.
uv run --frozen ctest --preset local
# 10/10 passed in 3.82s; existing native build, no C++ changes.
docker build -f infra/docker/action-worker.Dockerfile -t alojan-action-worker:provider-validation .
docker build -f infra/docker/management.Dockerfile -t alojan-management:provider-validation .
# Both passed. Network-disabled entry-point imports also passed in both images.
```

Initial integration: 56 passed/7 failed because has_any_column_privilege cannot test
DELETE. The credentials-role validator now uses has_table_privilege for DELETE;
25 focused tests passed in 18.11s. Review added a regression ensuring fresh credentials
remain usable while background refresh waits for IO (7 passed in 7.05s), rejects client
creation after closure and verifies actual managed-process admission after revocation.
Ruff check passed for agent/API/contracts and four affected suites; changed files were
formatted on Linux. Final source checksum/format verification status follows below.

Coverage includes envelope tampering/identity transplant rejection, owner/CSRF/scoped
API access, no token/ciphertext response or audit leakage, dedicated-role isolation,
foreign/revoked draft selection, rollback revocation checks, historical digest
compatibility, actual SDK credential headers, no model-selection IO, expiry, managed
restart/revocation, immutable historical summary inputs, cancellation/retry and one
finalization without notification delivery. Only disposable schemas and private test
processes were used. No resident service, live migration, ownership or second line changed.

Connectivity restored on 2026-10-25. Checksum comparison of all 29 listed source/
configuration files found no Mac/Linux differences. Rebuilt the final worker image
including the post-close-client guard; the network-disabled entry-point import passed.
The combined base/management/credentials/worker Compose configuration passed validation.
Linux Ruff and git diff --check passed. Later Telegram authoring changes and their final
image/document synchronization evidence are recorded in the newer entry above.
No resident deployment, live schema change or provider/carrier acceptance follows.

## 2026-10-25 — Explicit managed-node lifecycle

AGP-03 / CFG-03/11/12/17, M1/M4/M5, authorized Linux development checkout. Actual
managed subprocesses/signals, private RPC and disposable PostgreSQL schemas/roles.
Speech peers are synthetic; real Backend uses an unused synthetic key and makes no
provider request. No CUDA/API/carrier, latency/capacity or live migration acceptance.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_managed_startup.py \
  tests/test_release_readiness.py tests/test_number_routing.py \
  tests/test_call_initialization.py tests/test_prepared_releases.py \
  tests/test_answered_lifecycle.py tests/test_scoped_call_records.py tests/test_agent.py \
  tests/test_agent_drafts.py tests/test_agent_releases.py \
  tests/sip-integration/test_managed_session.py -q --tb=short
# 199 passed in 157.58s, no skips; existing audioop deprecation warning only.
uv run --frozen ctest --preset local
# 10/10 passed in 3.80s; existing native build, no C++ changes.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_managed_startup.py \
  tests/test_release_readiness.py -q --tb=short
# Final cleanup-order change: 31 passed in 19.84s, no skips.
uv run --frozen ruff check services/agent/alojan_agent/managed.py \
  services/agent/alojan_agent/service.py tests/test_managed_startup.py
uv run --frozen ruff format --check services/agent/alojan_agent/managed.py \
  services/agent/alojan_agent/service.py tests/test_managed_startup.py
# Both passed, three files formatted.
PYTHONPATH=services/agent:services/voice-contracts:generated/python \
  uv run --frozen python -m alojan_agent.managed --help
# Passed without management app on PYTHONPATH.
```

Initial focused suite: 16 passed, one failure because shutdown left a ready receipt.
The supervisor had cancelled an already-started graceful cleanup. Coalescing stop/
cancel before waking the service fixed it; 17 passed in 9.31s before adding routing
role rejection and reconciliation assertions. Final review lets bounded background
withdrawal finish rather than cancelling it midway.

Coverage: strict bounded configuration, exact targets, two process starts with fresh
consumer IDs, occupied-port rejection preserving the existing receipt, rollback after
a missing second target, required roles without legacy fallback, scoped answer/end,
pending summary jobs without delivery, abandoned setup recovery, and preflight SIGTERM
without known lease/socket leakage. Broad tests separately cover native managed SIP/RTP
and existing CPU turn models. Remote docs use the ignored review mirror. No resident
process, live schema, second number, bot or ownership changed.

## 2026-10-25 — Node-local release readiness

AGP-03 / CFG-03/11/12/17, M1/M4/M5, primary authorized Linux checkout. Real private
gRPC health/configuration/leases and native SIP/RTP; disposable PostgreSQL schemas
and restricted roles. ASR/agent/TTS inference remains synthetic; the existing managed
interruption scenario uses native CPU models. No API/CUDA/carrier quality claim.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_release_readiness.py \
  tests/test_number_routing.py tests/test_call_initialization.py tests/test_prepared_releases.py \
  tests/test_answered_lifecycle.py tests/test_scoped_call_records.py tests/test_agent.py \
  tests/test_agent_drafts.py tests/test_agent_releases.py \
  tests/sip-integration/test_managed_session.py -q --tb=short
# 181 passed in 153.28s; no skips, existing audioop deprecation warning only.
uv run --frozen ctest --preset local
# 10/10 passed in 3.82s; no C++/protobuf change or rebuild required.
PYTHONPATH=services/app-api:services/voice-contracts uv run --project services/app-api \
  --frozen python -c 'import sys; import alojan.api, alojan.roles; assert not any(k.startswith("voice.v1") for k in sys.modules)'
# Passed in the independent management environment.
```

Ruff check/format passed for seven changed Python files; Mac/Linux diff checks and
source comparison passed. New migration 0010 was applied only in disposable schemas.
The read-only operator SQL example never fabricates a ready row or reveals a consumer
ID. No dependency, media/native contract or public HTTP endpoint change.

Coverage: real preflight enables ordinary AgentService and a two-turn native Session
without ReadyService or manually inserting ready=true. Number binding uses the actual
coordinator receipt; scoped note/summary work completes once, with no notification.
Bad/missing audio, TTS capability mismatch, cancellation, unavailable health/storage,
disabled workspace/model and closed cache all prevent readiness. Known probe leases
are reclaimed. Warm renewal uses neither preload nor ConfigureCall; duplicate target
activation is idempotent and readiness capacity is bounded by the existing cache.

Freshness/key tests reject a foreign workspace/node and a locally expired receipt
while an already admitted call still completes. Another consumer's claim prevents old
renew/withdraw from changing the successor row. The private writer cannot write another
node, read users/calls, bind a number or disable a model. Management/routing/record roles
cannot change consumer IDs. Shutdown withdraws its receipt and releases only its own
cache hold; call pins remain until normal cleanup.

Initial focused run found a mistaken dependency on the legacy profile enabled flag,
which intentionally stays false for self-service drafts. Removed that unintended gate;
managed deployment continues to use workspace/model/verified-number controls. Corrected
focus: 14 passed in 22.29s. An initial independent-import command omitted the documented
source path; the corrected command above passed without changing packaging or dependencies.

This does not test an external provider credential/quota or measure background refresh
cost under load. Legacy startup does not attach the coordinator, native managed mode
remains loopback-only, and deployment startup/target selection, per-agent credentials/
tools/actions, PERF-01–06 and actual carrier acceptance remain pending. No resident
restart, production schema application, live migration or external delivery.

## 2026-10-25 — Routed native Session conversation

AGP-03 / CFG-05/06/08/09/10/11/12/17, M1/M3/M4. Authorized Linux development
checkout, real local SIP/RTP, gRPC and disposable PostgreSQL with restricted roles.
Only test fixtures grant ready permits. ASR/agent/TTS inference is synthetic; the
interruption scenario runs real native CPU endpoint/interruption models. No CUDA,
provider API, carrier, private call or external delivery claim.

```sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen ctest --preset local
# 10/10 passed in 3.83s.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_answered_lifecycle.py \
  tests/test_call_initialization.py tests/test_agent.py tests/test_scoped_call_records.py \
  tests/test_call_lifecycle.py tests/sip-integration/test_managed_session.py \
  tests/sip-integration/test_prepared_setup.py tests/sip-integration/test_recognition_setup.py \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  -q --tb=short
```

Final pytest: **222 passed in 318.07s**, no skips; existing audioop deprecation
warning only. Ruff check/format passed for four touched Python files;
clang-format passed for five native files, and Mac/Linux diff checks passed. No new
binding, migration, dependency or container. Source review covers setup/Session/media
lifetimes, service admission/finalization, scoped repositories and existing callers.

New coverage: two sequential PCMA/PCMU calls in one gateway using separate workspaces,
release identities, scoped notes, playback receipts and one summary job per call;
no notification outbox. Conversation before answer/after revocation/end and conflicting
caller metadata are rejected. Pending model cleanup must finish before EndCall enqueues
summary work. Dependency failure uses prepared unavailable audio; greeting/model BYE
remains responsive; lost answer persistence never starts a conversational turn. Native
CPU interruption cancels old synthesis/monitor generations and records partial speech
without claiming full text delivery. CLI guards prevent test-profile carrier/legacy use.

Earlier focused runs found fixture issues: the existing published three-second ringing
delay needed a five-second peer timeout; native cleanup acknowledgement must be observed
rather than inferred from server lease deletion; DB UUID/note JSON comparisons were
corrected. A 17-pass/one-failure run overlapped binary relinking (permission error),
so build and final tests are sequential. The first broad run had 219 passes/three
failures: new answer gating delayed prepared greeting, and two old lifecycle tests
had not configured required TTS pins. Greeting now runs immediately after ACK while
storage proceeds; only conversational capture waits. Lifecycle fixtures now declare
synthetic capabilities and ConfigureCall, keeping lease/cancellation assertions intact.
They also check task/configuration reclamation across 140 sequential calls.

Production readiness/preload coordination, general credentials/tools/actions and
PERF-01–06 remain pending. Ordinary InitializeCall stays not-ready; no live worker
restart or migration. These functional tests do not close real-model dialogue quality,
historical pause-quality, carrier or load/soak gates.

## 2026-10-25 — Pinned speech output budgets

AGP-03 / CFG-06/12, M1/M2/M4. Primary authorized Linux development checkout,
real local gRPC/SIP and disposable PostgreSQL schemas. Native probe uses scripted
inference and its link-time detector double. Legacy PCMA/PCMU two-turn dialogue
also uses synthetic agent/ASR/TTS; this is not a carrier/GPU/API quality measurement.

```sh
PATH="$HOME/.local/bin:$PATH" scripts/generate-proto.sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_output_budget.py tests/test_agent_phrases.py \
  tests/test_agent_runtime.py tests/test_native_calibration.py tests/test_call_initialization.py \
  tests/test_agent_releases.py tests/test_prepared_releases.py \
  tests/sip-integration/test_prepared_setup.py tests/sip-integration/test_recognition_setup.py \
  -q --tb=short
# 253 passed in 198.74s, no skips.
uv run --frozen ctest --preset local
# 10/10 passed in 3.82s.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_agent.py tests/test_tts.py \
  tests/test_tts_configuration.py tests/test_grpc.py \
  tests/test_agent_releases.py::test_operator_catalog_revision_preserves_historical_preset \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  -q --tb=short
# 132 passed in 36.49s, no skips; two SQL cases overlap the first suite.
```

383 distinct pytest cases across the final selections. Existing audioop deprecation
warning only. The second run follows formatting, a successful native rebuild and the
final SQL example's explicit calibration. All six generated bindings reproduce
byte-for-byte. Ruff check/format passed for ten changed Python files; clang-format
passed for three native files; local/Linux diff checks passed. Independent app-api
frozen environment imports the app and compiles an explicitly bounded agent without
loading voice.v1.voice_pb2. No new dependency or schema migration.

Earlier focus: 90 passed / two fixture failures (incorrect literal string length and
one-phrase preset paired with a two-phrase silence fallback). Fixtures corrected;
publication correctly rejected the incompatible fallback. Focused config/native
rerun: 25 passed in 6.11s. The final suite includes an additional SDK speech-tool
rejection test. SQL is executed twice per example in disposable schemas and remains
disabled, while historical preset data/digests stay unchanged.

Coverage: frozen explicit/historical budgets; UTF-8 scalar/byte boundaries; concurrent
call-local splitting; fixed-speech publication and actual SDK-tool rejection; stream
count/total rejection without successful end or false completed receipt; exact
published budget transport; missing/old/malformed native budget rejection before
answer/PCM; different native DID budgets accepting/rejecting identical responses
before TTS, including four-byte scalar boundaries and cumulative per-turn reset;
lease/cancellation cleanup and unchanged legacy two-turn playback.

Normal initialization still returns not-ready and routed RunTurn remains blocked.
Full routed Session, per-agent credentials/general tools/actions, PERF-01–06,
historical pause-quality gate, real CUDA/API/carrier quality and live rollout remain
pending. No resident worker restart, actual private call or external notification.

## 2026-10-25 — Pinned endpoint and interruption calibration

AGP-03 / CFG-09/10, M1/M3/M4, primary Linux host. New calibration tests use real local
RPC/SIP/DB with scripted inference and a native detector double. Legacy speech tests
use real native CPU turn models and synthetic ASR/TTS/agent services, never resident
CUDA inference. PostgreSQL uses disposable schemas. No carrier call or live restart.

```sh
PATH="$HOME/.local/bin:$PATH" scripts/generate-proto.sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_native_calibration.py \
  tests/sip-integration/test_recognition_setup.py::test_native_bridge_consumes_release_calibration_instead_of_legacy_settings \
  -q --tb=short
uv run --frozen ctest --preset local
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_prepared_setup.py \
  tests/sip-integration/test_recognition_setup.py tests/test_call_initialization.py \
  tests/test_agent_releases.py tests/test_agent_runtime.py tests/test_prepared_releases.py \
  -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  tests/sip-integration/test_interruption.py::test_interruption_cancels_old_output_and_recognizes_correction \
  tests/sip-integration/test_silence.py::test_silence_reminds_once_then_closes_politely \
  -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_native_calibration.py -q --tb=short
```

Initial focus **41 passed in 9.35s** includes two native probe cases repeated in the
larger suite. Main regression **169 passed in 181.41s**. Final historical compatibility
fixture and input validation **39 passed in 0.13s**. **10/10 CTests passed in 3.82s**.
Legacy PCMA/PCMU dialogue/interruption/silence: **6 passed in 157.70s**. No skips;
214 distinct pytest cases across the final selections. Native build, Ruff (six Python files),
clang-format (ten native files) and diff checks passed. Existing audioop deprecation
only in SIP suites. Generated Python/C++ bindings reproduce byte-for-byte. Independent
app-api environment compiles a calibrated runtime without importing RPC bindings.

Coverage: actual publication -> pinned initialization calibration; unchanged historical
preset JSON/digest; immutable nested data and complete field transport; user draft
rejection; invalid bounds/types/order/alignment; native missing/unknown/out-of-range
configuration rejects answer before PCM. Two synthetic DIDs exercise configured waits
and weak speech despite conflicting legacy VAD settings. Configured weak-voice barge-in
cancels the old agent generation/TTS phrase and continues with a new turn. Native unit
checks cover isolated reminder snapshots, onset/sustained/backchannel/quiet windows,
echo rejection and existing score invalidation. The revision-2 SQL example is repeatable,
disabled and leaves revision 1 unchanged. No schema or live migrations are applied.

The new native probe's turn detector is explicitly a link-time double; this proves
configuration consumption/cancellation, not real speech classification. Operator ranges
are safety bounds, not quality qualification of every combination. Existing pause-quality
failures and PERF-01–06 remain pending. Ordinary routed readiness stays false; full
Session conversation, phrase/output consumers and later tools/actions remain in PLAN.

## 2026-10-25 — Pinned native call timing and turn budgets

AGP-03 / CFG-05/08/17, M1/M4, primary Linux development host. Real local SIP/RTP,
strict speech RPC and PostgreSQL with disposable schemas; scripted inference and
readiness. Existing carrier listeners and resident models were not restarted.

```sh
PATH="$HOME/.local/bin:$PATH" scripts/generate-proto.sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_prepared_setup.py \
  tests/sip-integration/test_recognition_setup.py tests/test_call_initialization.py -q --tb=short
uv run --frozen ctest --preset local
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_agent_runtime.py \
  tests/test_agent_runtime_database.py tests/test_agent_releases.py \
  tests/test_prepared_releases.py tests/test_answered_lifecycle.py tests/test_grpc.py \
  tests/test_tts_configuration.py \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  -q --tb=short
```

Final focus: **90 passed in 147.25s**. **10/10 CTests passed in 3.82s**.
Regression: **118 passed in 45.86s**, including legacy PCMA/PCMU two-turn dialogue.
Initial focus had 86 passes and three
scoped-lifecycle fixture timeouts: their three-second socket timeout coincided
with the newly effective published three-second ringing interval. Those fixtures
now wait up to five seconds; the application retains the exact published delay.
No skipped tests; existing audioop deprecation only. Native build, Ruff (five Python
files), clang-format (eight native files), and diff whitespace checks passed.

Coverage: published preset -> initialization; malformed schema/all six field bounds
reject setup before PCM; managed bridge construction refuses missing settings;
two simultaneous DIDs retain distinct answer/media-drain delays despite conflicting
legacy CLI values and subsequent source mutation; delayed ACK consumes the original
10-second call limit; independent one/two-turn limits, bounded slow-agent RPC and
lease cleanup; existing cancellation, answer/end persistence and uncertain cleanup.
Native farewell pause consumption is prepared in Session but full routed conversation
remains a later gate. Legacy two-turn conversation is included in the regression selection above.

Six generated Python/C++ bindings reproduce byte-for-byte. The independent app-api
frozen environment imports its API and compiles a synthetic runtime without loading
voice.v1.voice_pb2; serialization is lazy at the RPC boundary. No DB migration or
new dependency. Functional timing assertions are not latency/non-regression metrics.
Real CUDA/API, handset quality, full routed Session readiness and PERF-01–06 remain
pending; ordinary InitializeCall stays not-ready. Documentation is mirrored separately
to preserve independent Linux edits. No live migration or external delivery.

## 2026-10-25 — Pinned TTS capability validation

AGP-03 / CFG-12, M1/M2/M4, primary Linux development host. Real local RPC/SIP and
PostgreSQL with disposable schemas; synthetic voice/agent backends and scripted
readiness. No live service restart or external delivery.

```sh
PATH="$HOME/.local/bin:$PATH" scripts/generate-proto.sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_tts_configuration.py tests/test_tts.py \
  tests/test_call_initialization.py tests/sip-integration/test_recognition_setup.py -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_agent_runtime.py tests/test_agent_runtime_database.py \
  tests/test_agent_releases.py tests/test_prepared_releases.py tests/test_prepared_audio_transport.py \
  tests/test_answered_lifecycle.py tests/sip-integration/test_prepared_setup.py tests/test_grpc.py \
  tests/sip-integration/test_recognition_setup.py::test_tts_configuration_failure_never_answers_or_uses_prepared_audio \
  -q --tb=short
uv run --frozen ctest --preset local
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_tts_configuration.py -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup -q --tb=short
```

Focused suite **90 passed in 56.50s**. Regression selection **148 passed in 79.19s**
includes eight native configuration failure cases (six repeated from the focus suite,
two additional missing/oversized cases). Profile helper recheck **22 passed in 0.82s**.
Legacy PCMA/PCMU dialogue **2 passed in 29.11s**. **10/10 CTests passed in 3.77s**.
No skips; existing audioop deprecation warning only. Native build and formatting/lint
passed. Regenerating six C++/Python files reproduced their exact bytes. Management
API import and compile_agent ran successfully with PYTHONPATH limited to app-api and
voice-contracts in the app-api project's frozen environment; voice.v1.voice_pb2 was
not imported. This is dependency separation evidence, not a new Docker deployment.

Coverage: actual published release -> pinned runtime -> initialization -> real TTS
configuration/synthesis; immutable per-call pins and backend snapshots; wrong model,
revision, voice, PCM format, schema, identifiers, deadline or lease; duplicate metadata,
release/expiry/reopen and active synthesis cancellation. Native SIP setup rejects old
workers, failed/lost configuration acknowledgements and invalid/oversized profiles;
CANCEL remains below the existing 300 ms functional bound while known leases drain.
Native multi-turn/phrase/monitor tests use the exact configured TTS worker and lease.

Startup tests mock CUDA/EMA/model-path verification to establish declaration ordering:
failed weights or missing graphs cannot expose capability. They do not verify real
GPU kernels, weights, pronunciation or latency. Resident EMA remains untouched; no
model reload, carrier/quality/soak/performance qualification or full routed readiness
is claimed. Ordinary InitializeCall remains not-ready. See PLAN for remaining consumers.

## 2026-10-25 — Native agent/TTS service lease handoff

AGP-03, M1/M2/M4, primary Linux checkout. Local SIP/RTP plus real strict ASR/TTS
protocol services, scripted inference/agent/readiness; PostgreSQL regression uses
disposable schemas. Ordinary routed startup remains blocked.

```sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_recognition_setup.py -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_prepared_setup.py \
  tests/test_tts.py tests/test_asr_configuration.py tests/test_prepared_audio_transport.py \
  tests/test_answered_lifecycle.py tests/test_call_initialization.py tests/test_grpc.py -q --tb=short
uv run --frozen ctest --preset local
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest \
  tests/sip-integration/test_prepared_setup.py::test_speech_setup_port_requires_isolated_agent_profile \
  -q --tb=short
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  tests/sip-integration/test_interruption.py::test_interruption_cancels_old_output_and_recognizes_correction \
  tests/sip-integration/test_speech.py -q --tb=short
```

Final focused suite **23 passed in 37.57s**; existing protocol/lifecycle selection
**125 passed in 61.41s**; **10/10 CTests passed in 3.77s**; additional CLI guards
**2 passed in 0.81s**. Legacy PCMA/PCMU dialogue, actual native CPU interruption and
speech regression: **24 passed in 219.10s**. Total: 174 pytest cases plus 10 CTests.
No skips; existing audioop deprecation warning only. Native
build, Ruff (two Python files), clang-format (eight native files) and diff whitespace
checks passed. Earlier focused runs failed only newly written expected cancellation
lists, which omitted existing turn-level invalidations; the final expectations include
both phrase and turn cancellation where appropriate.

Coverage: separate tokens for two simultaneous synthetic DID setups; TTS setup failure,
timeout/shared admission budget, lost/invalid open token, lost release acknowledgement;
nonblocking SIP CANCEL during TTS open; no prepared PCM/answer on failed setup. The
native probe exercises two turns with two phrases each, monitor streams, active TTS
cancellation, authenticated playback/cancellation, malformed/foreign/incomplete native
bindings and a wrong-service token rejected by the real TTS lease boundary without
fallback. Exactly one routed EndCall per probe is emitted by CallSetup with native
answer/end timestamps. All known leases/generations are released; unknown tokens
remain explicitly uncertain until expiry.

This is transport/lifecycle evidence. Native probe VAD is a link-time double; its
agent/readiness and model PCM are synthetic. TTS loaded voice/model pinning, complete
routed Session integration, matched production quality/latency/soak, actual EMA/CUDA,
carrier and external delivery acceptance remain pending. Live workers were not restarted.

## 2026-10-25 — Native ACK/end persistence and node-scoped recovery

AGP-03 / AGP-05 dependency, primary Linux checkout. Real local SIP/RTP, gRPC and
PostgreSQL with disposable schemas and separate records/routing roles. Positive
readiness is scripted only; the actual ordinary service still refuses answer.

```sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_answered_lifecycle.py tests/test_call_initialization.py \
  tests/test_scoped_call_records.py tests/test_agent_database.py tests/test_agent.py \
  tests/test_call_lifecycle.py tests/test_number_routing.py \
  tests/test_agent_runtime_database.py tests/test_prepared_audio_transport.py \
  tests/sip-integration/test_prepared_setup.py --tb=short
uv run --frozen ctest --preset local
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q tests/test_answered_lifecycle.py --tb=short
uv run --frozen --env-file .local/dev.env pytest -q \
  tests/sip-integration/test_sip.py \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  --tb=short
```

Native build passed. Main selection **163 passed in 93.70s**, no skips; final additional
reversed-end rollback case is covered by the **6 passed in 11.70s** lifecycle follow-up.
Existing SIP/dialogue **44 passed in 144.76s**. **10/10 CTests passed in 3.80s**. Python
SIP selections report the existing audioop warning. `test_agent_database.py` remains
the existing Linux-only file. Ruff and clang-format passed. Regenerating bindings
with the pinned script reproduced all six Python/C++ outputs byte-for-byte.

Coverage: real native ACK/end reports to scoped PostgreSQL; no answer before ACK;
explicit readiness permit, lease, deadline and release/digest rejection; idempotent
answer/end, conflicting timestamp rejection, invalid end transaction rollback and
valid retry; missing answer repaired by end; missing end recovered after lease release;
unanswered calls without post-call work; original-node recovery after rebinding;
restricted role grants and RLS; two-call media/cleanup isolation; slow answer writes
do not block prepared media or SIP BYE; bounded cleanup retains admission capacity.

Final focused check: `tests/sip-integration/test_prepared_setup.py::test_answer_recording_does_not_delay_prepared_audio_or_sip_hangup`
passed **1 test in 2.51s**, using the same frozen HTTP/Starlette/DB test invocation.
The delayed-answer test checks actual non-silent A-law payload in a 250 ms pump window
while the answer RPC is still pending and BYE handling below 200 ms. This is a targeted
functional isolation assertion, not a production P50/P95 distribution. Native process
shutdown, CANCEL, setup deadlines and existing two-turn audio remain in regression.
No provider/GPU, production voice, carrier, external notification or full PERF gate
acceptance is claimed. Both answer/end messages lost means unknown answer state;
recovery never fabricates it. Ordinary startup remains legacy-only and not-ready.

## 2026-10-25 — Scoped records and leased post-call finalization

AGP-03/05, Linux primary development checkout. Real PostgreSQL in disposable schemas,
restricted nonowner roles, scripted summaries; no external notification or live schema
migration. Final command:

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_scoped_call_records.py tests/test_number_routing.py \
  tests/test_agent_runtime_database.py tests/test_database.py tests/test_agent_database.py \
  tests/test_agent.py tests/test_call_initialization.py tests/test_call_lifecycle.py \
  tests/test_native_auth.py tests/test_agent_drafts.py tests/test_agent_releases.py \
  tests/test_profile_settings.py --tb=short
```

**178 passed in 65.45 seconds**, no skips. `test_agent_database.py` is an existing
Linux-only test file and was preserved. Ruff check/format passed for records/store/
service/roles and the two affected test modules. No native source changed; native,
GPU, real model and carrier tests were not rerun or claimed for this step.

Coverage: reject missing/mismatched scope/release/node/digest, unanswered/closed writes,
conflicting utterance/note retries and invented sent speech; repeated answer/end;
atomic call-end/enqueue rollback; two real workspaces with different agent/owner names;
forced RLS without/wrong/right/reset scope and forbidden notification writes; original
release after edits; competing claims, expired lease takeover, stale/forged completion;
model cancellation, schema/output failure, durable-note confirmation, atomic summary/
event/job rollback, duplicate completion rejection; global legacy queue exclusion;
old-schema job backfill without assigning legacy ownership and repeat migrations.

First focused run: 31 passed/1 failed because the pinning trigger restored cleared
ownership rather than rejecting mutation. Validation now runs before derivation.
Expanded follow-up: 114 passed in 38.98 seconds. The final expanded command above
also covers cancellation, atomic end, upgrade/repeat and service fallback rejection.

No production ACK/EndCall integration, worker deployment/fan-out/Telegram delivery,
management record-read endpoint or performance acceptance follows from these tests.
Routed answer remains disabled. Keep live migration gated on legacy-role/worker
compatibility with forced RLS and scoped jobs; see the staged agent README.

## 2026-10-25 — Isolated native setup, answer and cancellation

AGP-03/AGP-06 dependency, primary Linux development checkout. Real SIP/RTP and
private gRPC with synthetic tone packs/scripted readiness; a separate refusal
case uses the actual agent, prepared cache, router and disposable PostgreSQL schema.
No provider, GPU, live carrier, production deployment or external notification.

```sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/sip-integration/test_prepared_setup.py tests/test_call_initialization.py \
  tests/test_prepared_audio_transport.py --tb=short
uv run --frozen --env-file .local/dev.env pytest -q \
  tests/sip-integration/test_sip.py \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  --tb=short
uv run --frozen ctest --preset local
```

Final focused selection: **54 passed in 45.89 seconds**, no skips, including 22
new setup-profile cases. Existing SIP/legacy conversation selection: **44 passed
in 144.96 seconds**. **10/10 CTests passed in 3.78 seconds**. Both Python selections
report the existing Python 3.12 audioop deprecation warning. Full native build,
clang-format for three changed native files, and Ruff check/format for two changed
Python test files passed. No Mac native build, sanitizer or hosted CI run is claimed.

Coverage: exact Request-URI/To selection without fallback, untrusted source rejection
before RPC, two concurrent agents with distinct G.711 PCM and independent cleanup,
false readiness, malformed/incorrect release PCM, failed RPCs, per-phase and shared
total preparation deadline, insufficient call duration, CANCEL during initialization,
audio retrieval and ready-but-ringing, bounded shutdown, capacity retained during
slow cleanup, explicit uncertain cleanup acknowledgement and slot reuse. The positive
ringing case waits at least three seconds for 200 and no media starts before ACK.
The setup profile rejects carrier addresses and legacy conversational options.

The actual agent/cache/router/DB refusal case verifies an ended, unanswered call
row, no remaining lease/cache pin and zero utterance/summary/outbox rows. Positive
readiness exists only in the scripted peer; the ordinary service remains not-ready.
The loopback profile plays prepared greeting/unavailable audio and does not claim
conversation or answered-call persistence. Production EndCall, scoped storage,
remaining runtime consumers and readiness coordination are separate gates.

Initial new-profile selection passed 20 cases. Adding the three-second ringing test
exposed a test socket timeout also set to three seconds; increased only the test
socket timeout. A combined follow-up had 53 passes and one fixture failure because
the total-deadline mode delayed cleanup as well as preparation. Limited that delay
to OpenCall/InitializeCall/GetPreparedAudio; the separate slow-cleanup case still
requires confirmed=0. Final complete focused selection above passed. These fixes
did not relax the native setup budget or require production code changes.

## 2026-10-25 — Private prepared-audio transport and native media output

AGP-03 / AGP-06 dependency, primary Linux development checkout; synthetic packs
and scripted inference, real loopback gRPC, native PJSIP ports, isolated SIP/RTP
and disposable PostgreSQL schemas. No live provider/GPU or carrier acceptance.

```sh
PATH="$HOME/.local/bin:$PATH" scripts/generate-proto.sh
uv run --frozen cmake --build --preset local -j 2
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_prepared_audio_transport.py tests/test_prepared_releases.py \
  tests/test_call_initialization.py tests/test_call_lifecycle.py tests/test_agent.py \
  tests/test_agent_runtime.py tests/test_agent_runtime_database.py tests/test_agent_releases.py \
  tests/test_number_routing.py tests/test_grpc.py tests/test_asr.py tests/test_tts.py \
  tests/test_agent_phrases.py --tb=short
uv run --frozen ctest --preset local
uv run --frozen --env-file .local/dev.env pytest -q \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  --tb=short
```

Broad regression: **274 passed in 41.05 seconds**, no skips. A follow-up added
individual-clip overflow rejection and the largest valid 960,000-byte pair;
`tests/test_prepared_audio_transport.py`: **18 passed in 1.13 seconds**. Real
Python/native transfer verifies distinct agent PCM, matching lease/release/digest,
no post-initialization file access, cancellation/release denial and missing/forged/
duplicate lease rejection. Native malformed/late-reply tests cover truncated,
misaligned, silent, oversized, misidentified and incorrectly padded data, failed
RPC, deadline and cancellation. The actual server/client limits accept maximum
valid clips and reject overflow before playback.

Full Linux native build passed. **10/10 CTests passed in 3.87 seconds** afterward.
New prepared-output uses the actual PJSIP conference clock and media ports with
synthetic PCM: independent greeting/unavailable cursors, exact samples and a
cancelled silent port. Existing two-turn PCMA/PCMU SIP/RTP checks passed:
**2 passed in 29.07 seconds**, one pre-existing audioop deprecation warning. These
two SIP tests exercise the shared legacy output adapter, not routed INVITE.

All six generated bindings reproduced byte-for-byte on Linux. Ruff check/format
passed for the two changed Python files; pinned clang-format passed for five native
files. Initial bare clang-format was not on PATH; corrected to `uv run --frozen`.
No dependency addition or live service restart. Independent remote native source
was preserved; Mac source review is not a separate Mac native build.

The reply requires copying bounded PCM during setup; no zero-copy or latency win
is claimed. render uses existing PJMEDIA buffers and lock-free per-call state.
Its frame counter records frames supplied to the port, not proof of handset receipt.
Routed answer integration, readiness production, scoped storage/actions and full
quality/performance/carrier gates remain pending. Normal entry-point routing is
disabled, ready_for_answer=false, routed RunTurn blocked, second DID inactive.

## 2026-10-25 — Prepared audio preload and immutable call pinning

AGP-03 / AGP-06 asset dependency, primary Linux development checkout. Test packs
are synthetic PCM tones; no new EMA inference, voice-quality or carrier evidence.
Source digests matched before targeted changes and remote files were backed up.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_prepared_releases.py tests/test_call_initialization.py tests/test_agent_releases.py \
  tests/test_agent.py tests/test_agent_runtime.py tests/test_agent_runtime_database.py \
  tests/test_agent_database.py tests/test_call_lifecycle.py tests/test_number_routing.py \
  tests/test_profile_settings.py tests/test_agent_model.py tests/test_agent_ack_intent.py \
  tests/test_agent_grounded_dialogue.py tests/test_agent_phrases.py tests/test_prompts.py --tb=short
```

Focused first run: **47 passed in 15.13 seconds**. Expanded command above:
**272 passed in 48.25 seconds**, no skips. Covers file/manifest hash and PCM identity,
lead-in, malformed RIFF/chunks despite matching hashes, missing/oversized/non-regular
files, workspace/pack/file symlinks, FIFO rejection, cross-workspace cache isolation,
no cold-cache fallback, repeated-init pin idempotency, shared release references,
LRU capacity/payload bounds, no eviction on failure, duplicate preload coalescing,
cancelled waiters retaining worker reservations and shutdown/late completion.
Existing legacy prompt provenance, startup rejection, conversation, native transport,
DB routing and lifecycle checks remain passing in that selection.

Final test review made each synthetic agent's PCM distinct, so wrong-pack selection
is observable rather than only checking text/metadata. Follow-up prepared-release
and initialization suites: **32 passed in 6.41 seconds**, no skips. Ruff check and
format passed for six changed code/test files; `git diff --check` passed.

Explicit `pytest -q -s tests/benchmark_prepared_releases.py`: **1 passed in 0.19s**.
30 application-cold/warm-OS-cache loads after five warmups: P50 1.0599 ms,
P95 1.0922 ms, max 1.1479 ms. 10,000 warm pin/unpin pairs: P50 0.0028 ms,
P95 0.0029 ms, max 0.0114 ms. Accounted entry payload 75,512 bytes; synthetic
one-second speech and 400 ms greeting pad. These are isolated small-asset observations,
not full-process RSS, largest-asset, concurrent voice or matched legacy benchmarks.

Built `alojan-management:agp-preload-review` with the pinned Dockerfile and passed
`tools/validate-management.py --image alojan-management:agp-preload-review --network
alojan-local_default --database-host alojan-local-postgres-1` using a disposable schema,
restricted DB role and temporary container. Cleanup completed. Read-only status
confirmed all seven Alojan live containers healthy on their prior images without
restart. No schema migration, dependency, public API or protobuf change in this slice.

The private service now requires an exact preloaded release; it still returns
ready_for_answer=false and rejects routed RunTurn. No production preload coordinator,
readiness writer or native PCM playback connection is enabled. Completing those
consumers and scoped storage/actions precedes real voice/latency/carrier acceptance.
No live ownership migration, external notification or second-number activation.

## 2026-10-25 — Call-local Python consumers (AGP-03 partial)

Primary Linux development checkout; scripted inference only, actual loopback gRPC,
mocked provider HTTP transport and disposable PostgreSQL schemas. No live requests,
provider credentials, GPU inference, carrier calls or external notifications.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_agent.py tests/test_agent_runtime.py tests/test_agent_runtime_database.py \
  tests/test_agent_database.py tests/test_agent_model.py tests/test_agent_ack_intent.py \
  tests/test_agent_grounded_dialogue.py tests/test_agent_update_failure.py \
  tests/test_call_initialization.py tests/test_call_lifecycle.py tests/test_native_auth.py \
  tests/test_agent_drafts.py tests/test_agent_releases.py tests/test_number_routing.py \
  tests/test_profile_settings.py tests/test_agent_phrases.py tests/test_grpc.py \
  tests/test_agent_timing.py --tb=short
```

**289 passed in 50.28 seconds**, no skips. New coverage includes two interleaved
identities/settings/contexts, immutable runtime, configured alias/guidance,
unselected tools despite hostile instructions/model output, custom recovery and
farewell, disabled invitation, UTF-8 history bounds, invalid/combined speech bounds,
actual wire temperature/reasoning/token/provider/timeout/tool selection, multi-phrase
out-of-order sent-audio receipts, per-call turn limits, historical summary identity
after draft edits and number deactivation, RLS-hidden snapshot failure and
preparation rejection before asset work. Initial test-ID/fixture/command failures
are described in PLAN; they are not counted as passing runs.

Final review restored the original legacy summary prompt and optional-invitation
heuristic exactly. Follow-up command with test_agent_runtime.py, test_agent_model.py
and test_agent.py: **135 passed in 5.84 seconds**, no skips. Original main and summary
instruction strings match the pre-change snapshot exactly. Ruff check and format:
**12 files passed**. No dependencies, migration or public protobuf changes in this
slice. The existing lifecycle and sent-audio tests remain passing.

Built isolated `alojan-management:agp-runtime-review` using the existing pinned
Dockerfile. `tools/validate-management.py --image alojan-management:agp-runtime-review
--network alojan-local_default --database-host alojan-local-postgres-1` passed real
HTTP registration, scoped authoring, qualification/verification rejection and
revocation with a restricted DB role. Disposable test container/schema/role cleanup
completed. All seven Alojan live containers remained healthy on their previous
images, without restart. Source copies were targeted and backed up; maintained
documentation is mirrored separately in the ignored design-review directory.

Not accepted by these tests: real model dialogue quality, native/audio consumer
integration, ASR vocabulary, scoped summary/record worker roles, action routing,
GPU preparation, latency/capacity non-regression, carrier acceptance or ownership
migration. ready_for_answer stays false and routed RunTurn remains blocked. The
second-number binding is still disabled. Next implement prepared-asset preload and
readiness/native consumers before measuring the complete voice path.

## 2026-10-25 — Private initialization and native DID boundary (AGP-03)

Primary Linux development workspace; live lifecycle containers/schema untouched.
All database tests used disposable schemas; inference was scripted. Source imports
preserve the deployed lifecycle/grounded-dialogue baseline rather than the older
Linux top-level checkout. Initial reviews exposed an initializer-list fixture error
and stale model/test fixture mismatches; none are counted as passing evidence.

Final command (pinned test-only HTTP dependencies, no lock/deployment change):

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest -q \
  tests/test_call_initialization.py tests/test_call_lifecycle.py tests/test_agent.py \
  tests/test_number_routing.py tests/test_grpc.py tests/test_asr.py tests/test_tts.py \
  tests/test_agent_ack_intent.py tests/test_agent_grounded_dialogue.py \
  tests/test_agent_timing.py --tb=short
```

**208 passed in 29.16 seconds**, no skips. Includes initialization lease/metadata/
deadline rejection, immutable/idempotent routing, real DB commit followed by lost
setup, late-result cancellation, explicit cancellation before setup, sanitized
unexpected failure, non-routed legacy compatibility, no fallback to the legacy
backend, abandoned setup recovery without summary/outbox, and old-lease isolation.
Preserved lifecycle regression runs 140 sequential calls and >4096 cancelled
generations per worker. Existing ASR/TTS/protobuf transport tests passed.

Generated Python/C++ protobuf bindings using the pinned generation script. Built
`caller-identity-test` and `voice-contract-probe` with two build workers. Native
caller-identity CTest: **1/1 passed in 1.04 seconds**; tests use PJSIP-parsed synthetic
messages, explicit peer allowlists and separate Request-URI/To selection. No carrier
request/header was captured. Ruff check and format: **14 files passed**;
clang-format passed on the parser/header/test. The parser executable reported
**360 checks passed**. Full native `voice-gateway` build also passed with two workers.
Regenerating all six Python/C++ binding files preserved their SHA-256 digests.
Seven existing live containers remained healthy on their prior images, without
restart. Five maintained documents passed fence/159 relative-link checks and
`git diff --check` passed. No new dependency or schema migration.

The setup reply deliberately has `ready_for_answer=false`; there is no native
INVITE caller or production readiness producer yet. Prompt/settings/tool/audio
consumption and answer lifecycle are still incomplete. No measured inference or
end-to-end voice non-regression claim follows from these tests. Live migration,
Kübra ownership transfer and second-number activation remain pending.


## AGP-03 number binding and admission repository — 2026-10-25

Primary Linux, disposable PostgreSQL schemas only:
`uv run --frozen --project services/app-api --env-file .local/dev.env pytest -q
tests/test_number_routing.py tests/test_agent_releases.py tests/test_native_auth.py
tests/test_agent_drafts.py tests/test_database.py tests/test_profile_settings.py --tb=short`
→ **80 passed in 36.11 seconds**, no skips. One pinned Starlette test-client
deprecation warning remains. Lint/format pass. Actual Docker image
`alojan-management:agp-routing-review` built with digest
`sha256:a7ec96f1c4de642abbc71d9291e6dc5750a0e5ab4d3c35d0b8da3305513be13b`.
Restricted-role bridge-network HTTP smoke passed pending-number registration and
unverified-binding rejection alongside previous authentication/draft/model guards.
Temporary container/schema/credential/role cleanup completed.

Explicit isolated benchmark (`pytest -q -s tests/benchmark_number_routing.py`):
**1 passed in 2.22 seconds**, 50 sequential admissions after five warmups, using a
restricted routing role and a fresh connection per call. P50 **28.50 ms**, P95
**38.07 ms**, max **39.26 ms**. Includes database resolution, validation and snapshot
commit; excludes native SIP, preload, inference and RTP. There is no matched baseline,
load/soak comparison or full PERF-02 acceptance from this measurement.

Initial run had two teardown failures
(Identifier API misuse), fixed and two unreferenced temporary roles removed before
the full successful run.

New coverage: pending ownership guesses, canonical DID rejection, verified-owner
uniqueness, ready-node/model gates, ETag conflicts, real separate-session binding
races, atomic admission/rebinding, immutable snapshots, same-call retries, conflicting
metadata, cancellation before/during/after setup, bounded database lock failure,
legacy call non-claiming, draining before ownership transfer, caller-hint non-authority,
strict cross-workspace foreign keys and restricted management/routing DB roles.
Readiness TTL/digest corruption is rejected at the database boundary. Test carrier
proofs, voice packs and node acknowledgements are synthetic and confer no live approval.

The admission repository is not yet connected to the native SIP/RTP path. No new
native build, real model/provider, GPU, Netgsm call, Telegram send, latency baseline
or performance acceptance is claimed. Native called-DID trust, InitializeCall,
preload/heartbeat, call-local configuration, activation and abandonment cleanup are
pending. Active production mappings, schema and images remain unchanged.

## AGP-02/06 prepared-release storage and management — 2026-10-25

Linux isolated PostgreSQL suite includes native accounts, drafts, database/profile
migrations and `test_agent_releases.py`. Coverage includes candidate qualification,
immutable definitions/releases, same-content cross-workspace audio isolation,
separate-session concurrent publication, stale preparation, rollback history,
model revocation, owner/editor permissions, real non-owner RLS, malformed audio,
symlink rejection, greeting/closing duration, email normalization/SQL agreement and
restricted-role end-to-end publication. Every record/audio fixture is synthetic;
no live call data is migrated or audio model invoked.

The independent management image is built with a code-only allowlisted context.
Its real HTTP smoke test uses a temporary restricted database login/schema and
joins the existing database bridge, with only a random host-loopback port published.
The constrained image passes email registration, scoped authoring/preview,
unqualified-model rejection and logout/session revocation. The temporary role,
schema, secret file and container are removed. The internal production Compose
network validates structurally; full tunnel and deployment isolation remain pending.
The initial smoke attempt hit a startup connection reset; the validator now retries
that transient condition during its bounded readiness period.

No native/CUDA/provider/carrier or Telegram action test is represented by these
results. Assets use synthetic tones, not EMA readiness or intelligibility evidence.
The existing seven Alojan containers remain on their prior images without a restart.
Production migration/owner transfer, automatic speech generation, all consumer
coverage and formal voice performance gates remain pending.

Final Linux command: `uv run --frozen --project services/app-api --env-file
.local/dev.env pytest -q tests/test_native_auth.py tests/test_agent_drafts.py
tests/test_database.py tests/test_profile_settings.py tests/test_agent_releases.py`:
**64 passed in 23.01 seconds**, no skips. One Starlette test-client deprecation
warning remains with the existing pinned test dependencies. Ruff lint/format,
Compose structural validation and Docker image build passed. Image tag
`alojan-management:agp-release-review`, digest
`sha256:b919f0a5a686616cd8b563eb81e43b61e78ed4a1c503825b67b16391bf77fd5b`;
restricted-role bridge-network HTTP smoke PASS. No live image tag was replaced.

## AGP-02 native account/draft foundation — 2026-10-25

Primary Linux: `pytest -q tests/test_native_auth.py tests/test_agent_drafts.py
tests/test_database.py tests/test_profile_settings.py --tb=short`: **44 passed in
13.73 seconds**, no skips. Test data is synthetic and every DB fixture uses a random
isolated schema. New coverage: atomic unrestricted registration with separate owner
workspaces, cookie/origin/CSRF, session idle/absolute expiry, password and membership
revocation, concurrent durable rate limiting, trusted-proxy address handling,
cross-workspace denial, unsafe configuration/template rejection, ETag races and
actual PostgreSQL RLS under a temporary non-owner role. Cleanup passed.

Ruff check and formatting passed for the changed management modules/tests/validator.
`infra/docker/management.Dockerfile` built successfully on Linux. The real image's
`tools/validate-management.py` check passed with 0.5 CPU/512 MiB/read-only filesystem:
readiness, HTTP registration, own-workspace agent draft, AI greeting preview and
server-side logout revocation. Its temporary container/schema/secret file were
removed. No production table migration, live process restart, carrier call or
external notification occurred. Existing gateway/agent/ASR/EMA/API/Telegram/DB
containers remained healthy on their prior images.

Review corrected fixture lint imports, scoped connection options and potential
workspace lock-conversion contention before final validation. Drafts remain
non-routable; there is no successful publish/deploy claim. The owner explicitly keeps
the unprepared second number/Telegram binding disabled. Pending: complete AGP-02
runtime-role/catalog/release/secret work, AGP-03–09, actual browser TLS/tunnel,
CPU/GPU/voice non-regression, real model/provider/carrier and delivery acceptance.

## AGP-01 platform design acceptance backlog — 2026-10-25

[ADR 0011](ADR/0011-self-service-voice-agents.md) and
[platform plan](VOICE_AGENT_PLATFORM.md) require new acceptance for authenticated
workspace isolation, verified DID possession, per-agent models/settings, pinned
releases, fixed tool configuration vs model arguments, explicit grants/revocation,
MCP auth/schema drift, prepared audio, typed output/HTTP mapping and independent
post-call delivery jobs. Test instruction injection, cross-workspace IDs/secrets,
DNS/redirect/IPv6 SSRF, missing/invalid outputs, repeated finalization and uncertain
external writes. Run actual approved provider/MCP/Telegram/HTTP/carrier scenarios
separately from synthetic fixtures. None was run by this design task. Previous
PROF-02 database tests do not establish platform runtime acceptance.


## Number-specific assistant acceptance — 2026-10-25

Rename acceptance: independently change owner/assistant names and then both;
verify regenerated greeting and every identity-bearing response/summary, unchanged
bot/chat and stable IDs, and original names on in-progress calls/queued results.
Invalid names and unready greetings must prevent publication. Tests not yet run.

[ADR 0010](ADR/0010-number-agent-profiles.md) and
[PROF-01–07](PROFILE_ROUTING_PLAN.md) add two Netgsm profiles using the same EMA
voice: Kübra/Burhan and Berkcan/Serkan, with separate Telegram bots/chats.
Design only; no new runtime/carrier/Telegram pass. Linux SSH timed out during
this design task; no changes were transferred or activated remotely.

Required new evidence: trusted called-DID parsing for each direct/forwarded line;
correct identity across greetings, replies and summaries; zero cross-scope records
or delivery; unknown/ambiguous DID rejection; mid-call binding changes retaining
old recipients; atomic publication and cancellation; authenticated API isolation;
Telegram retries, ambiguous responses, worker crash and revoked target behavior.
Real G5 requires each owner's verified bot/chat receipt, separate from fake HTTP
checks. EXT-08 now requires two bot credentials and their recipient chat IDs,
provided privately. Do not send historical calls upon enabling the worker.

Retain the qualified one-call limit until CAP work establishes concurrent inference
safety. Two configured DIDs do not prove two overlapping AI calls. The existing
carrier reachability incident below remains unresolved by this design.


## Configurable call capacity planning — 2026-10-24

The owner replaced the two-call proposal with [CAP-01–09](CALL_CAPACITY_PLAN.md):
50 calls across servers, a five-call target on the current Linux host, configurable
host quotas and SIP 486 when capacity is full. Verify local sixth-call and cluster
51st-call rejection, overlapping real inference, cross-call isolation, lifecycle
churn, per-call latency, multi-node failure and carrier channels. Existing two-call
SIP evidence remains valid only for its original scope. ADR 0009 records the target;
no new capacity test, carrier call or deployment occurred in this planning update.

Status as of 2026-10-23: **Native Linux G1 development scenario set complete; full G0/product M1 partial; live Netgsm INVITE observed, G2 incomplete**. See [Mac foundation evidence](validation/macos-foundation-2026-10-09.md), [Linux development evidence](validation/linux-development-2026-10-23.md), [Linux SIP isolation evidence](validation/linux-sip-isolation-2026-10-23.md), [Linux caller identity evidence](validation/linux-caller-identity-2026-10-23.md), [Linux spoken fallback evidence](validation/linux-spoken-fallback-2026-10-23.md), [Linux audio conversion evidence](validation/linux-audio-conversion-2026-10-23.md), and [Linux EMA prompt evidence](validation/linux-ema-prompts-2026-10-23.md). Individual passing scenarios do not complete a gate.

## Gate register

| Gate | Prerequisite | Test / required evidence | Current state |
|---|---|---|---|
| G0-local | Local M0 | Native Mac toolchain/services; Compose support services and migrations; no GPU prerequisite | Partial: native build, DB and API health pass; C++/Python transport contracts pass with a test peer; remaining service/deployment setup pending |
| G0-Ubuntu | U0-01; server access | Linux build/Compose/migrations and GPU container check; model coexistence measured in M2 | Partial: native build, DB/migrations, 161 pytest tests, 5 CTests and native/container CUDA kernel pass; remaining production service/deployment setup pending |
| G1-local | G0-local; M1-01–05 | Native Mac real SIP endpoints; INVITE/ACK/BYE, CANCEL, bidirectional WAV and cleanup | Partial: PCMA/PCMU, CANCEL, BYE, busy, RTP inactivity, max-duration and bounded shutdown pass; impairment/isolation pending |
| G1-Ubuntu | Native G0-Ubuntu build/contract/DB prerequisites; local M1 | Repeat SIP/WAV integration on Linux | Passed for the native development profile: 33 real SIP scenarios, 9 CLI checks, 14 prompt/startup checks and native codec/identity checks; v3 named greeting accepted by the owner. [M1-08 completion report](validation/linux-m1-development-report-2026-10-23.md). Full G0 deployment work, durable identity persistence and live operator acceptance remain open |
| G2 | G1-Ubuntu, EXT-01/02 | Real direct 0850 call; inbound signaling and intelligible two-way RTP; SDP/NAT match | Partial: two real PCMA calls answered, ACK confirmed, greeting intelligibility accepted by the owner, nonzero return PCM and cleanup observed. Reverse speech intelligibility and complete carrier acceptance remain open. [Live answer evidence](validation/netgsm-answer-2026-10-23.md) |
| G3 | G2; M2 and M4-01; EXT-05/06 | Live ASR, EMA speech and GPT response; warm GPU and stream cancellation | Partial: real CUDA/API synthetic dialogue and carrier readback/confirmation/closing passed; owner-reported latency remains unacceptable. Full G2/G3 quality and timing remain open |
| G4 | M3; full-agent recheck after G3 | Pauses, interruptions, echo/noise; sent-audio alignment and timestamp metrics | Partial: native and limited owner-confirmed interruption; broad calibration and full-agent waiting-phrase listening acceptance remain open |
| G5 | M4/M5; EXT-08 | Call transcript/number/summary and actual notification; outbox restart/retry; teardown | Not run |
| G6 | G2; EXT-03/04; owner device | Direct vs forwarded vs withheld CLI; manual/assisted Focus forwarding and reset | Not run |
| G7 | G3–5 | Two-call isolation in explicit test configuration, 30-minute soak, failure injection and resource report | Not run |

Keep the production admission limit at one call unless capacity is deliberately revalidated. Two-call isolation is not a promise of two-call production performance. Latency targets in requirements §3 are stretch goals; report sample count and percentile calculation, never claim an SLA from one call.

## External prerequisites

| ID | Needed from / validation | Blocking task | State |
|---|---|---|---|
| EXT-01 | Owner/network admin: routable IPv4, CGNAT and NAT access | M1-06 | Partially verified: public address matched; inbound SIP reached Linux through owner-managed Berqnet; UDP 10000–10100 roundtrip passed under a temporary source exception. Full topology and permanent address assignment not audited |
| EXT-02 | Netgsm: active trunk, codecs, source ranges, auth/registration and media details | M1-06 | Partially verified: IP-directed calls worked without REGISTER, PCMA and bidirectional packet transport observed. Complete signaling/failover/media source list and broader carrier review remain open |
| EXT-03 | Real Turkcell-forwarded CLI comparison | M6-01 | Unverified |
| EXT-04 | Owner iPhone/iOS Focus and USSD behavior | M6-02 | Unverified |
| EXT-05 | Ubuntu CUDA/PyTorch/ASR/EMA compatibility and measured VRAM | U0-01; M2-02 | CUDA smoke and persistent ASR/EMA warm-up, concurrent synthetic streams and cancellation/recovery passed within 16 GB; broader quality, soak and deployment remain pending |
| EXT-06 | Account access to requested model, streaming/settings and quota | M4-01 | Selected OpenRouter Pro streaming/tool requests verified; broader quota/capacity/latency acceptance pending (ADR 0005) |
| EXT-07 | Owner license/distribution decision; exact dependency review | Release | Proposal only |
| EXT-08 | Owner notification endpoint/credentials | M5-01 | Not provided |

SSH access and the `~/ai/alojan` workspace were supplied/authorized on 2026-10-23. ADR 0003 makes this the primary build/test environment. Connection details remain in ignored local configuration; carrier prerequisites are still pending. Public security and conduct reporting channels remain release/community prerequisites.

## Evidence format

For each attempted gate create a sanitized report under `docs/validation/` with:

- Gate/task IDs, revision, timestamp/timezone, tester and environment versions.
- Preconditions, exact commands or manual scenario, fixture identifiers and sample count.
- Expected versus observed results and pass/fail/blocked/not-run status.
- Correlation IDs, codec, packet/jitter/loss and relevant latency/resource values.
- Remaining blocker, reproducible next step, and location of private raw evidence (no credentials or personal data).

Use a monotonic clock for measured durations and wall time only for correlation. Define response latency from caller turn end to first RTP playout, and interruption latency from valid speech detection to last stale-generation output. Do not equate sent audio with confirmed handset playback.

## Scenario minimum

requirements §15 requires at least 30 synthetic/labeled Turkish dialogue scenarios, including yes/no, 1–2 second pauses, date corrections, acknowledgments, background TV/other speakers, packet loss, missing/invalid/anonymous caller data, spoofed PAI, API timeout, GPU OOM, DB unavailability, SIP CANCEL and mid-call BYE. Record fixture source/license and expected behavior. Real recordings require explicit consent and anonymization.

Under [ADR 0003](ADR/0003-linux-development.md), complete the G1 development scenario set on the primary Linux host before M2–M5; ADR 0002 remains the historical Mac sequencing decision. G0/G1 are split by environment; G2–G7 remain real acceptance gates. Local analogues of G3–G7 must be labeled supporting evidence with CPU/model/test-service details; mocks cannot satisfy real acceptance. Missing carrier access leaves M1-07 pending without blocking local implementation.

## Named greeting follow-up — 2026-10-23

M1-03 / US-01: the owner accepted the v2 EMA voice as clearly intelligible and
requested “Burhan Çetinkaya” in the introduction. V3 uses the requested name and
retains the AI disclosure and closing text. Both texts were regenerated on CUDA.
Linux validation: 89 pytest passed (1 known audioop warning, no skips, 121.62 s),
3 CTests passed (1.04 s), Ruff/formatting and changed-source clang-format passed.
See [named greeting evidence](validation/linux-named-greeting-2026-10-23.md).
The owner subsequently accepted the delivered v3 greeting and requested the next
task. This closes the local listening condition; carrier intelligibility is untested.

## G1 development completion — 2026-10-23

The [M1-08 audit](validation/linux-m1-development-report-2026-10-23.md) maps every
M1-01–05 local scenario to the latest passing suite and the owner’s listening
feedback. A fresh collection confirmed 89 test cases in 0.07 s; this was inventory
validation, not a second execution pass. The unchanged executable suite retains
the 89-pass / 3-CTest result above. M2-01 may proceed under ADR 0003. Full G0,
product M1 and live G2–G7 remain open; historical Mac G1 was not revalidated.


## M2-01 development evidence — 2026-10-23

The [native ASR report](validation/linux-asr-2026-10-23.md) records a real persistent
large-v3-turbo CUDA float16 worker on loopback, synthetic Turkish partial/final
transcription, exact digital-silence regression, cancellation and recovery. The
new lifecycle tests use an explicitly fake decoder over real gRPC; they do not
count as inference evidence. G3 is still not run: ASR is not connected to SIP,
the agent API is absent and carrier acceptance is missing. M2-02 subsequently measured limited EMA/ASR coexistence below.
The report includes the original transient SIP counter failure and the independent
empty-heartbeat classification regression/fix; no failed result was relabeled.

Final M2-01 Linux checks: 108 pytest passed (1 known audioop warning, no skips,
123.27 s), 4 CTests passed (2.06 s), Ruff/formatting and clang-format passed.
Seven real CUDA speech/silence format cases and pre-start/active cancellation
passed separately; these are limited synthetic checks, not G3 acceptance.

## M2-02 persistent speech evidence

[The Linux TTS report](validation/linux-tts-2026-10-23.md) records one resident EMA
worker with bounded output and native cancellation cleanup, six concurrent
synthetic ASR/TTS cases, 8/16/24/48 kHz numerical calibration and a measured
10,992 MiB host warm-up peak with ASR resident. First-run streaming peak was
2,996 MiB. These are sampled measurements, not a hard maximum or soak result.
Phone-number roundtrip quality and literal punctuation/foreign pronunciation
remain documented limitations. G3 is still not run; M2-03 SIP integration and
M4 agent/API work are separate prerequisites, alongside G2.

Final M2-02 Linux verification: 131 pytest passed (no skips, one known audioop
warning, 124.49 s); 4/4 CTests passed (2.07 s); native build and Ruff checks passed.
After restart, all six concurrent synthetic stream/entity checks passed again;
phone roundtrip digits remained a documented failure.

## Netgsm network reachability — 2026-10-23

M1-06 / M1-07 / G2: [network evidence](validation/netgsm-network-2026-10-23.md)
records owner-observed real INVITEs on Linux UDP 5060 and an agent-run 101/101
UDP roundtrip probe across 10000–10100. Earlier unsuccessful probes are retained
as inconclusive reachability attempts, not carrier failures. The successful probe
used a temporary source exception that the owner subsequently removed. No
recording or raw packet capture was saved to the repository. G2 remains open:
complete SIP answer/teardown, negotiated codec, correct SDP and intelligible
bidirectional carrier audio still need a live call test under the Netgsm allowlist.

## M2-03 native speech integration — 2026-10-23

[The gateway report](validation/linux-speech-gateway-2026-10-23.md) records the
explicit scripted SIP/RTP → ASR → EMA → RTP path. On Linux, 151 pytest cases
passed (no skips; one known audioop warning; 273.50 s), as did all 5 CTests
(2.06 s), the native build, Ruff and changed-source clang-format checks.
Twenty new fake-inference cases exercise real transport, failure/fallback,
cancellation/reuse, deadlines, bounded queues and two-call capacity isolation.

Two separate real CUDA calls, one PCMA and one PCMU, each captured 350 frames,
received seven ASR partials plus a nonempty final, and played all 200 EMA frames
(four seconds) before BYE. Complete received closing audio matched the approved
reference within G.711 quantization tolerance; RTP mean pacing was 20 ms.
Scripted half-close to first PCM handed to PJMEDIA was 159 ms in each case.
Sampled host GPU peak was 3,008 MiB. These are two observations, not P95, handset
latency, spontaneous turn detection or GPT response measurements.

This closes the native M2-03 task and permits M3-01. G3 remains unpassed because
the capture boundary and response are fixed, carrier G2 and agent M4 are absent.
The report retains the failed initial alignment, premature-final regression and
counter-parser failure alongside their corrections. The normal greeting keeps
the owner-approved name and AI disclosure. Both model workers remain running
for development without reboot supervision.

## Live Netgsm immediate answer — 2026-10-23

The owner explicitly requested live answering after the network preparation.
[The carrier answer report](validation/netgsm-answer-2026-10-23.md) records two
real PCMA calls through the configured NAT. Both reached confirmed/ACK state
13 ms after the gateway incoming callback, with media connections prepared at
14 ms. The owner confirmed connection and intelligible greeting. The first call
ended by remote hangup after 3.77 s; the second completed the greeting/closing
and released its session after 7.285 s. Incoming nonzero PCM had no invalid frames;
last-sampled RTP counters reported no loss/reorder/duplicates.

These timings are server state transitions, not handset latency or P95.
Incoming packet/PCM counts do not substitute for reverse speech intelligibility.
No caller recording or transcript was retained; no raw SIP trace was captured.
The basic immediate-answer request is fulfilled and the native gateway remains
running. Full G2, live identity, M3/M4 conversation, reboot supervision and broader
network/source-range/quality acceptance remain open.

## M3-01 native adaptive core — 2026-10-23

[The turn report](validation/linux-turn-detection-2026-10-23.md) separates CPU
numerical calibration, deterministic policy/fault tests, real SIP with synthetic
ASR/TTS, and actual CUDA speech calls. The full Linux suite passed 175 pytest
cases (no skips, one known audioop warning, 434.96 s) and 7 CTests (2.31 s).
The 0.5/1/1.5/2 s inserted-pause scenarios preserve the utterance while an explicitly
incomplete ASR hypothesis is present. The two-second case initially failed and
was corrected using endpoint pad plus a low-confidence resumption guard; this
regression and numerical quantization drift remain visible in the report.

The opt-in profile uses adaptive completion and a fixed EMA closing. It is not a
live agent or evidence of natural conversational understanding. The default
Netgsm listener remains unchanged and running. Parent M3-01 remains partial:
human/noisy calibration, runtime threshold settings and the seven-second reminder
are open. M3-02 echo/interruption work can use the validated native core; full
G3/G4 and live carrier adaptive acceptance remain unpassed.

Final real adaptive local PCMA/PCMU calls delivered the complete 200-frame EMA
closing with 20 ms RTP pacing. VAD-relative boundary waits were 1104/1124 ms;
half-close to first output-port PCM was 139/138 ms, giving 1243/1262 ms overall
from the last VAD speech sample. The 4,995 MiB sampled host GPU peak includes a
temporary updated ASR alongside the preserved resident workers. No adaptive
carrier call or spontaneous-human turn acceptance is claimed.


## M3-02 native interruption core — 2026-10-23

[The interruption report](validation/linux-interruption-2026-10-23.md) separates
deterministic policy/reference checks, real local SIP with fake inference, and
actual CPU/CUDA ASR/EMA calls. Both real-model codecs interrupted one reply,
recognized the correction and sent the next complete reply. The old generation
recorded 680/720 ms sent but zero aligned text; the completed next reply recorded
4000 ms and its 78-byte text. No generated-but-unsent text entered history.

The synthetic input-to-decision times were 671.78/707.03 ms; the last output-port
frame preceded the decision by 2 ms in both cases. Twenty silent RTP frames in
the next 100–500 ms window and a complete reference match on the next response
verify the stop/restart path. These do not satisfy the 250 ms onset goal or prove
human false-interrupt rates. Full G4, phrase alignment/agent integration and live
carrier interruption remain open. The approved Netgsm greeting process was not
restarted or used for these tests.


Final validation uses separate runs: 184 unchanged pytest cases passed in the full
suite; its one acknowledgment-fragment failure was corrected with a complete EMA
word, then 3 packet-phase variants passed. Eight CTests passed. The evidence report
records both attempts and does not claim a clean second full-suite invocation.
No test was skipped or relabeled as a pass; the single known audioop warning remains.

## Live M3-02 follow-up — 2026-10-23

The owner requested real-phone validation and confirmed a sentence cut off while
speaking over the generated reply. Call 3 independently logged `turn-1`
invalidation and `turn-2` startup before remote hangup. This confirms the basic
PCMA carrier interruption path; it does not establish the 250 ms onset target,
complete second-reply playback, broad false-interrupt rates or full G4.

Calls 1/2 were ordinary completed ASR/EMA turns without interruption events. Call 4
used controlled fallback because an incomplete turn was not accepted. Preserve
all four outcomes, including the unresolved M3-01 calibration case, in
[the live report](validation/netgsm-interruption-2026-10-23.md). No recording or
personal transcript was retained. The interruption test profile remains active;
its responses are fixed, and M4 message collection is not connected.
## M4 carrier follow-up, 2026-10-23

G3/G4 remain partial. See [the M4 evidence](validation/linux-agent-2026-10-23.md)
for actual API/GPU checks, failed probes and separate human results.

| Attempt | Observed result | Acceptance |
|---|---|---|
| Initial M4 carrier call | Readback and affirmative note persisted; closing interrupted, later incomplete-turn fallback | Owner reported incorrect/missing confirmation; failed experience |
| Second initial carrier call | Remote disconnect before assistant audio completed | Not accepted |
| Local-confirmation/handoff update | Correct readback, confirmed note and completed closing; 139 ms confirmation half-close to output, 3–4 s earlier model responses | Owner accepted message accuracy but reported excessive waiting |
| Waiting-phrase update | Real synthetic CUDA/API call passed; waiting text ready at 801 ms, substantive content at 6315 ms | Final owner listening/latency check pending |

Retest with a synthetic name/message, wait for the complete readback/question,
then explicitly affirm. Check both initial-response waiting and confirmation
closing. Separately verify interruption during the waiting phrase. Preserve
unconfirmed notes when the question is cut off or the caller corrects the message.
Do not treat the waiting acknowledgement as substantive response latency, a note
confirmation, a delivered notification or handset playback proof.

## Performance review follow-up, 2026-10-23

[Performance evidence](validation/performance-review-2026-10-23.md) separates
scripted clause timing, actual API experiments, native protocol checks and real
CUDA loopback calls. The latter confirmed a note and produced closing audio at
138 ms after ASR half-close. An explicit-goodbye call closed at 139 ms and left
its draft unconfirmed. Initial meaningful response audio still took 3739/3499 ms;
waiting audio at 960 ms does not satisfy the latency goal. No new carrier call
was made. Human/noisy Turkish and 50-turn distribution acceptance remain pending.

## Waiting music follow-up, 2026-10-23

Owner requested quiet music instead of the spoken waiting sentence. Both-codec
native tests passed music/response transition, receipt isolation and interruption
with silent RTP after revocation. A real synthetic GPU/API call played 3280 ms of
music, began the substantive response 15 ms after text arrival, confirmed the note
and saved a summary. [Detailed evidence](validation/waiting-music-2026-10-23.md).
No new carrier acceptance: listen for comfortable level, immediate transition to
speech and normal interruption behavior. Do not classify music as a spoken reply.

## Greeting opening-word follow-up, 2026-10-23

Owner reports `Merhaba` missing. V4 protects the original greeting with a 400 ms
silent lead-in; both-codec local tests retain the full opening after discarding
300 ms. [Evidence and failed test-alignment attempt](validation/greeting-start-2026-10-23.md).
Retest the actual number: verify the complete opening word and AI disclosure,
then normal message collection and quiet waiting music. Keep listening pending
until the owner confirms; the waveform check alone cannot close carrier acceptance.

## Ringing and duplicate-question retest (2026-10-23)

M1-03/M1-06 and M4-01/02, US-01/02/05: verify audible ringing for at least
three seconds before answering, then the complete named AI greeting. Ask to
speak to the owner, give a name/message when requested, correct one detail,
and confirm the corrected readback. Check that each missing-detail question is
asked once before waiting, known details are reused, and only the corrected
message is confirmed. Carrier retest is pending; local SIP/API evidence and
last-two-call findings are in [the report](validation/ringing-dialogue-2026-10-23.md).

## Kübra flow retest (supersedes confirmation scenario, 2026-10-23)

US-01/02/05/07, ADR 0006: verify three-second ringing and the approved Kübra
greeting asking how to help. Ask whether Burhan Bey is available; expect the
owner-selected unavailable/possible-meeting answer. Supply a clear message;
expect no readback or “Doğru mu?”, only the requested closing after storage.
Verify approximately three seconds between closing audio and disconnection.
DB note and summary must stay unconfirmed; no notification delivery claim.
Local tests do not replace this handset check.

## Declining a message (2026-10-23 regression)

After the availability response, decline a message and say you will call later.
Expect a short farewell, then disconnection three seconds after its audio ends,
with no note created. Contrast with thanks plus another question (keep listening)
and asking Burhan to call later (save message, then close). Latest carrier failure
and regression evidence: [report](validation/farewell-hangup-2026-10-23.md).

## Natural conversation retest (ADR 0007, 2026-10-23)

Give a callback message without saying goodbye: verify acknowledgement and an
opportunity to continue, with no automatic hangup or readback confirmation. Add
a detail; verify it is retained with the original note and no repeated checklist
question. Say that is all: expect a natural farewell, then the closing pause.
Also test a caller who already says goodbye with the message (no unnecessary
extra question), declined-message exit, and thanks followed by another question.
Human acceptance is pending; automated evidence is recorded separately.

2026-10-23 automation evidence: four synthetic real-API scenarios and a two-turn
CUDA/EMA/ASR/OpenRouter loopback passed. The updated natural-v1 development line
is active and healthy. These checks are not human carrier acceptance; the above
handset scenarios remain pending. Details: [natural-agent evidence](validation/natural-call-agent-2026-10-23.md).

Purpose-question refinement (natural-v2): ask only whether Burhan Bey is available;
expect an unavailability explanation and one polite question about the reason for
calling. In a separate call provide the reason immediately; expect no repeated
purpose question. Synthetic API checks passed; these handset cases remain pending.

Publication regression (2026-10-23): the accumulated snapshot passed all 255
Linux loopback/unit/database tests (815.44 s, no skips), plus nine CTests. This adds
no human carrier acceptance; privacy checks and exact results are recorded in
[publication evidence](validation/main-publication-2026-10-23.md).

## ASR quality follow-up — 2026-10-23

M2-01 / M5-03: [ASR spelling/CPU evidence](validation/asr-quality-2026-10-23.md)
records paired synthetic noise/quiet evaluation, seven real CUDA service fixtures
and successful PCMA/PCMU native fixed-response loopbacks. Numeric entities passed;
no extra inference or noise filter is enabled. The development line now uses the
bounded exact spelling vocabulary and one-thread BLAS launcher on ASR port 15173.
Targeted name misses decreased on the exploratory synthetic set; nonspeech
hallucinations remain. G3 and general noise-quality acceptance remain open.

Pending owner handset check: say the confirmed product name in a natural request,
then a synthetic callback number and a short yes/no answer. Check understanding,
response delay and that the short answer is not replaced by a product/person name.
Use only consented evidence; do not commit private transcripts or recordings.

## Uncertain-answer closing regression — 2026-10-23

The owner reported a product inquiry; stored recognition instead contained a stock
outro, after which the agent closed without saving a note. The owner requested a
repeat question whenever an answer is unclear or does not address the question.
The new natural-v3-clarification policy passed 59 focused tests and a three-turn
real CUDA/API/isolated-DB PCMA loopback: clarify, accept another answer, close only
on explicit exit. [Evidence](validation/clarification-recovery-2026-10-23.md).

Human acceptance remains pending: repeat the inquiry, confirm that an unclear
answer prompts another question and the call stays open, then explicitly end it.
No raw caller recording has been enabled. Full silence/incomplete-turn timeout
handling remains separate from this recognized-text recovery.

## Prompt decision review — 2026-10-23

Natural-v4-prompt-review passed 16 synthetic behavior cases and 59 focused Linux
tests. Callback requests remain open after saving; only topic announcements prompt
for the actual question; additions avoid repeated invitations; explicit exits
close naturally. Fourteen cases used the real API and two exercised local guards.
See [review evidence](validation/prompt-review-2026-10-23.md). No new handset or
CUDA/audio run is claimed; pending carrier checks from the clarification follow-up
still apply to the revised prompt.


## M3-01 silence recovery follow-up — 2026-10-23

The adaptive agent now distinguishes silent input, incomplete speech evidence and
actual dependency/contract failure. One reminder follows seven quiet seconds;
listening resumes, and continuing silence uses the bounded timeout farewell.
Incomplete evidence requests repetition. Runtime endpoint thresholds retain their
previous defaults. See [Linux evidence](validation/silence-recovery-2026-10-23.md).

Handset acceptance remains pending: after the approved opening, stay silent for
about seven seconds, hear one reminder, then speak during it or near its end.
Check that Kübra hears the request, continues appropriately and never repeats the
idle reminder. Separately verify that 0.5–2 second pauses inside an unfinished
sentence do not trigger a farewell. Broad noise/human calibration, G3 latency and
G4 interruption acceptance are not closed by this implementation.

Activation evidence: final Linux build, 9 CTests and 95 focused pytest cases passed;
5 functional real-CUDA/DB synthetic cases passed. One stricter short-reminder
cutoff attempt failed and is retained in the report; it is not handset acceptance.
`natural-v5-silence-recovery` is active after an idle restart, preserving previous
runtime arguments. Worker health passed; ASR/EMA were not restarted. Owner handset
confirmation is pending.

Owner follow-up: reminder and farewell were heard, but automatic hangup failed.
Logs show the agent requested finish and the gateway restarted listening without
a confirmed interruption. The pre-roll cancellation bug is corrected in the
gateway; see the recovery report for checks. Retest continuing silence through
the farewell and verify hangup about three seconds after it ends. A genuine
interruption during the farewell must still resume listening. This handset
failure supersedes the earlier pending-only status; carrier revalidation remains
required after the fix.

The fix is active as `natural-v5.1-silence-close`. Nine Linux CTests, all eight
recovery SIP cases and one new resident-CUDA/isolated-DB silent call passed.
The late-backchannel regression failed on the previous binary and passed on the
fixed binary; confirmed interruption of the farewell still resumes recognition.
Only the idle gateway restarted, retaining the existing three-second closing
delay. These checks do not replace the requested handset revalidation.

## Selectable ASR evaluation — 2026-10-23

M2-01 / M5-03, US-02/04/06, ADR 0008. Offline paired real-CUDA evaluation completed
480 decodes: 24 public human recordings and 16 synthetic utterances, four audio
conditions, Whisper plus Nemotron 320/1120 ms. Both Nemotron profiles had higher
human WER; keep Whisper on the carrier development line.

The optional config-selected Nemotron worker and the updated Whisper launcher
were tested sequentially on loopback port 15174. All seven PCM/partial/final/
silence cases and cancellation/recovery passed for each. Nemotron's existing exact
entity validator failed name spacing and spoken-number formatting; Whisper passed.
Do not count those failures as proven wrong digits or claim full quality acceptance.
Both temporary workers were stopped. No carrier calls, caller recordings or live
configuration changes were made. Distinct-speaker coverage, persistent incremental
partial caching and human handset comparison remain pending. See
[the detailed report](validation/nemotron-asr-2026-10-23.md).

## Turkish-adapted Whisper offline evaluation — 2026-10-24

M2-01 / M5-03, US-02/04/06. TurkMedSTT general Turkish large-v3 and the current
Turbo completed 320 real-CUDA decodes on identical human/synthetic fixtures.
Human PCMA WER tied at 11.40%; noisy and quiet speech improved, while clean WER,
product spelling and latency regressed. Three evaluation checks passed; eight
additional silence/noise diagnostics showed both models can emit text on noise.
No carrier call, recording, service replacement or model-default change occurred.
This is offline evidence, not handset or streaming-service acceptance. See
[results and limits](validation/turkmed-asr-2026-10-24.md).

## Per-stage latency and routing comparison — 2026-10-24

New `agent_latency` and `turn_latency` records expose first response timing and
failures without caller text. `tools/report-latency.py` reports distributions,
missing measurements and unsuccessful statuses; recovery/music are excluded.
The VAD-end-to-output metric is an estimate using PCM-domain silence, not a
handset or network measurement. See [measurement contract and results](validation/latency-routing-2026-10-24.md).

72 synthetic real-API turns compared four routing profiles. Default is retained:
no candidate met speed/behavior criteria. All observed requests already used
prompt cache. The two-turn real CUDA/DB/PCMA check completed storage, farewell,
hangup and summary, but its 7238/5059 ms endpoint-to-output timings do not pass G3.
Native failures, cancellation and missing-audio telemetry have regression coverage.

`natural-v5.2-latency-observability` is active after an idle gateway/agent restart.
Handset timing checks remain pending. Do not count the 72 text/receipt-only turns
as the required 50+ timed real-audio turns or mark M5-03 complete. No new recording
or carrier call was performed by the validation tools.

### DeepSeek selection: live validation pending (2026-10-24)

M4-01 / M5-03, DEC-11, §9.1: the owner-selected
`deepseek/deepseek-v4.1-flash` is prepared locally with reasoning disabled and
Responses streaming retained. Mac simulated-agent checks passed (74 tests).
The Linux host was unreachable over SSH, so no DeepSeek API, CUDA, carrier or
handset test was performed and the live agent was not restarted. Validate note
creation/correction, topic clarification, natural closure and structured summary
before an idle activation; then measure actual response latency separately.

### GPT-OSS 120B candidate: not yet tested on the line (2026-10-24)

M4-01 / M5-03, DEC-11, §9.1–3: owner now requests `openai/gpt-oss-120b` on Cerebras
with an optimized prompt, superseding the undeployed DeepSeek candidate. 77 Mac
simulated tests passed, including typed reasoning-event isolation and wire-request
settings. Subsequent owner-authorized Mac real API tests found faster first text
but failed closing-tool, repeated-question and speech-content checks. Revised
prompt runs passed 14–15/18 automatic scenarios and 6/8 novel paraphrases; the
same baseline suite passed 18/18 with Luna. These are synthetic tool conversations,
not actual calls. Linux remains unavailable; no CUDA or carrier call ran and no
process was restarted. Conditional deployment is already
authorized after speed/behavior gates pass. See the [evaluation record](validation/gpt-oss-120b-2026-10-24.md)
for the failed behavior gate and paired phrase-latency, database/summary and
native call checks still required. Do not activate this candidate yet.

### 120B reasoning/tool-channel follow-up (2026-10-24)

The owner reaffirmed 120B and restored Linux connectivity. The current medium
reasoning/4096-token candidate uses required speech tools and excludes raw model
text from TTS. 87 Linux regression tests and real DB/summary checks passed. A
synthetic adaptive PCMA call with resident Whisper/EMA passed, with first audio
1459/639 ms after endpointing and correct message/closing/summary behavior.
These are loopback measurements, not a carrier call or human acceptance.

37/38 final synthetic dialogue checks passed; one adversarial request caused an
unnecessary closing and remains open. Do not mark full dialogue/security or G3
acceptance passed. The owner's selected development model and actual rollout
status are tracked in the [follow-up report](validation/gpt-oss-reasoning-2026-10-24.md).
The 120B agent is now active on the development line after an idle agent-only
restart. Agent/ASR/TTS health checks passed; actual owner/handset validation of this
model remains pending. The prior live model is retained for rollback.

## 2026-10-24 executive-assistant follow-up — carrier listening pending

Latest carrier transcript review found a concrete product question dismissed
without note storage and repeated anything-else invitations. This is a failed
conversation-quality observation, not a new acceptance pass. The refined agent
is active on the idle development line; model remains GPT-OSS 120B / Cerebras.

Linux evidence: 101 focused tests; synthetic native PCMA + real CUDA ASR/EMA +
OpenRouter + isolated PostgreSQL completed note storage, natural close and summary.
First endpoint-to-audio was 1,939 / 720 ms. Test pending on the actual phone:
state a concrete product problem, add a detail, then thank the assistant; verify
ownership, no readback/repeated invitation, and farewell followed by hangup.
Also check a vague topic remains a question rather than an invented message.
Unknown product follow-up and general paraphrase handling remain quality gaps.
See [sanitized evidence](validation/executive-assistant-2026-10-24.md).

## 2026-10-24 — Duplicate acknowledgement follow-up

Owner's latest call demonstrated one note write but two spoken storage
acknowledgements. New receipt/version-aware suppression and the researched
conduct prompt passed 108 Linux tests, a 13-turn synthetic real-model replay and
real CUDA ASR/EMA/API/DB loopback (first audio 1659 / 1540 ms). Carrier listening
remains pending: leave a concrete request, wait for acknowledgement, then thank
the assistant; expect only a social farewell and the existing delayed hangup.
Separately request a repetition or correct a detail; those must remain possible.
See [evidence and limits](validation/natural-closing-2026-10-24.md).

## 2026-10-24 — Once-per-call invitation follow-up

Latest carrier logs confirmed a social farewell and local disconnect, but an
intermediate reply repeated acknowledgement and dismissed the request for further
help. The owner now requires one invitation per call, superseding the earlier
no-invitation expectation. Updated agent has 110 Linux regression passes and seven
real-model simulated conversations with one invitation each. Carrier test pending:
leave a concrete request, hear the invitation, add another request, then decline
more help; expect no repeated invitation and a farewell before delayed hangup.
Separately verify an explicit goodbye does not force another question.
See [evidence and remaining quality limits](validation/once-offer-2026-10-24.md).

## 2026-10-24 — Researched service practices

Added source-mapped positive conduct and clarified essential-question priority.
Real 120B replay covered 14 synthetic turns: final note/finish states passed, with
first phrase mean 935 ms / max 1917 ms. Product elicitation and vague speaking
requests improved in this sample; empathy and repeated delivery intentions remain
language-quality limitations. This is not carrier acceptance. Phone test pending:
state an unnamed product problem with frustration, provide the product when asked,
then add/correct a detail and decline further help. Verify focused questions,
one further-help invitation and a contextual farewell before delayed hangup.
See [research and evaluation](validation/service-conduct-2026-10-24.md).

## 2026-10-24 — Adversarial dialogue follow-up

The reviewed development agent is active. Synthetic real-model evaluation passed
57/58 current turn checks across 34 conversations; 126 Linux regressions passed.
No new carrier call was placed. Phone listening remains pending: ask whether
Kübra is human, state a concrete request, add a separate request after saying
“İyi günler, bir dakika...”, and finally decline more help. Expect both requests
retained, one further-help invitation, no premature disconnect and a short final
farewell. Separately test a same-turn correction such as “Yarın, yok cuma”; the
selected text evaluation still retained the discarded day in the stored message.
Do not mark this case accepted until the correction is normalized correctly.
[Evidence and language limitations](validation/dialogue-review-2026-10-24.md).


## 2026-10-24 — Offline noise-suppression evaluation

WebRTC low/moderate, RNNoise and Speex were compared with bypass on public and
synthetic Turkish speech. All profiles were fast on CPU, but no candidate
preserved recognition quality across conditions. No carrier profile was changed
and no new listening acceptance is claimed. Noise/hum-only hallucinations remain
possible even after filtering. Any later promotion must first improve offline
entity/clean/quiet accuracy, then validate streaming cancellation, barge-in and
real carrier listening. See [evidence](validation/denoise-2026-10-24.md).

## 2026-10-24 — DTLN offline follow-up

Original DTLN and an exploratory half-strength blend completed 812 paired real
Whisper decodes across public/synthetic speech and nonspeech controls. Both failed
the recognition-preservation gate; noise-only hallucinations also remained.
21 Linux boundary/alignment checks passed. The live carrier path was unchanged;
no new call, listening, latency, barge-in or cancellation acceptance is claimed.
See [DTLN evidence](validation/dtln-2026-10-24.md).

## 2026-10-24 — Reviewed M4 dialogue-quality candidate

The approved candidate was built/tested in isolated Linux source snapshots. New
regressions cover semantically tagged acknowledgements, complete versus partial
playback groups, early/late receipts, cancellation and failed note updates.
Real-model text comparisons and isolated PostgreSQL summary tests did not pass
the meaning/naturalness release gates. The running listener was not replaced;
there is no new carrier acceptance or reason to treat current phone behavior as
the candidate. Preserve existing human-listening evidence separately.

Before any future promotion, resolve correction/independent-request loss and
premature closing on a new unseen set, preserve secret exclusion, and repeat the
paired timing and synthetic speech checks. Inspect final stored notes after
farewell-only turns, not just spoken replies or intermediate drafts.
[Evidence, exact checks and limitations](validation/dialogue-quality-2026-10-24.md).


## 2026-10-24 — Owner-placed M3/M4 phone test

The existing Netgsm listener completed one actual six-turn agent conversation.
Four interruption/cancellation events, sent-audio accounting, a corrected final
note and eventual system-initiated hangup were observed. The owner subsequently
confirmed disconnection and accepted the overall experience as comfortable.
Retain the technical caveats: a recognized explicit farewell was followed by another
further-help question, and the summary introduced uncertainty absent from the
final note. The owner deferred summary improvement and will use the readable
conversation and final note. Exact interruption/closing delay was not measured;
this does not establish all M3/M4 gates. No raw recording or candidate rollout.
[Evidence and outstanding checks](validation/carrier-m3m4-2026-10-24.md).


## 2026-10-24 — M4-01 / M5-03 response-latency baseline

The measurement subtask is complete on the accepted Linux baseline: 25 sequential
synthetic PCMA calls, five message scenarios repeated five times, 50 completed
response turns using real resident CUDA Whisper/EMA, OpenRouter gpt-oss-120b and
isolated PostgreSQL. All 25 call validations passed; no response timing samples
were discarded, failed or missing. No live runtime/prompt/model change occurred.

Estimated VAD-end to first server output: P50 **1929 ms**, P95 **3464 ms**, maximum
**5120 ms**; 4/50 turns exceeded three seconds. Message-taking P50/P95 is
**2504/3601 ms**, closing **1643/1796 ms**. Endpoint-to-output alone is
**1259/2740 ms**. Endpoint silence (median 824 ms) and two model requests on
message turns dominate; local ASR finalization and first TTS PCM medians are
120 ms and 9 ms. The slowest turn spent 4071 ms in two model requests.

The warm repeated synthetic sample reaches the 50-turn count but fails the
latency target and does not close human/carrier G3 or full M5-03 acceptance.
Existing report regression passed (1 test); final services were SERVING, test
schemas removed, and live source/binary hashes unchanged. Summary quality stays
deferred as requested. [Method, distributions and limits](validation/response-latency-2026-10-24.md).

## 2026-10-24 — Offline Qwen ASR comparison

M2-01 / M5-03, §8.1, US-02/04/06: 320 real CUDA decodes plus eight controls
completed on the primary Linux host. Human telephone-band WER regressed from
11.40% (Whisper) to 17.11% (Qwen3-ASR-1.7B), with slower measured inference and
additional synthetic entity/short-phrase errors. Candidate rejected for promotion;
Whisper and the carrier listener remain unchanged. Four evaluator tests passed.
This adds no handset, Qwen streaming/cancellation, multi-call or carrier acceptance.
[Evidence and runtime limitations](validation/qwen-asr-2026-10-24.md).

## 2026-10-24 — Standard large-v3 offline comparison

M2-01 / M5-03, §8.1, US-02/04/06: standard large-v3 improved human PCMA WER
from 11.40% to 9.65% and quiet PCMA from 21.93% to 11.40%, but increased PCMA
human median inference from about 142 to 360 ms and regressed one product name.
The paired CUDA evaluation adds no carrier, streaming-partial, cancellation or
concurrency acceptance. Current live/default Turbo remains unchanged; three
evaluator checks passed. [Evidence and shared-host limits](validation/whisper-large-v3-2026-10-24.md).


## 2026-10-24 — Endpoint scheduling implementation and quality gate

Owner approved the endpoint plan while excluding LLM optimization. Implemented
content-free gate diagnostics and a default-off, bounded early-partial scheduling
candidate in `codex/endpoint-latency`; all Linux work used an isolated snapshot.
The 500 ms endpoint floor and existing stability/resumption safeguards remain.

The frozen replay planned 100 continuing and 50 completed fixtures per profile.
It stopped after 46 runs / 23 pairs because the absolute cutoff gate was already
unachievable: both profiles cut the same 9 of 16 observed continuing cases; no
candidate-only cutoff was observed in that subset. Seven completed-turn pairs
had endpoint medians 984 ms baseline and 696 ms candidate. All 23 pairs had equal
final ASR text and equal decode counts (113 each), which does not validate omitted
continuations or establish general quality/resource acceptance.

47 ASR tests, 38 SIP cases and 9 CTests passed on Linux; formatting and task diff
checks passed. **No live rollout:** the candidate remains default-off, and the
full quality/timing sample, lower-threshold trials and owner phone validation
were not advanced after rejection. LLM/prompt/model settings and live hashes
remain unchanged. General pause/incomplete-turn handling is the next prerequisite.
[Implementation, evidence and limitations](validation/endpoint-calibration-2026-10-24.md).

## 2026-10-24 — Large-v3 acceleration screening

M2-01 / M5-03, §3/8.1, US-02/04/06: seven decoder profiles, stage timing and
nine targeted repeats completed 1,169 real CUDA decodes. Up to 19.8% lower median
PCMA inference came with recognition loss; no tested profile preserved quality
across every condition. INT8/beam-three added a spurious subtitle phrase in a
quiet closing on all three repeat attempts. FlashAttention failed at startup.
Three evaluator tests passed. Live Turbo remains unchanged; no Qwen/large-v3
carrier, streaming-partial, multi-call or cancellation acceptance was added.
[Research, measured tradeoffs and untested follow-ups](validation/whisper-large-v3-speed-2026-10-24.md).

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

## 2026-10-24 — Owner-reported carrier dialogue quality failure

After the connectivity follow-up, the owner reported an initially inaudible attempt
and an audible subsequent conversation containing incorrect information. Read-only
inspection of the latest persisted caller utterances, aligned sent-response text
and the accepted live prompt confirms a dialogue-quality failure despite successful
transport/pipeline events: the assistant supplied an unsupported product catalog,
then offered a correct catalog immediately after admitting it lacked the facts.
It also reused a generic privacy refusal for an ordinary company-information
question and repeated its earlier refusal instead of explaining it.

A fictional product name from the prompt's behavioral examples appears in the
unsupported response. Example-to-fact contamination is a strong hypothesis, not
a proven model-internal cause. The current prompt lacks an explicit distinction
between illustrative entities and verified business facts. Recognition also
contains unclear short phrases, but the product-list request was intelligible
in the stored transcript; ASR does not account for the unsupported catalog.

No raw call recording was enabled, so no claim of listening to the audio or
verifying handset audibility is made. Sent-audio accounting does not prove the
caller heard it. The initial silence remains unresolved. No LLM, prompt, model,
endpoint or live configuration was changed during this inspection. A future
prompt repair must use Skill Creator, general evidence/knowledge and recovery
rules, and cross-scenario evaluation, not a product-name blacklist. Technical
call success must not be reported as conversational quality acceptance.


### 2026-10-24 — Grounded dialogue candidate: release withheld

M4-01/02, US-02/06/08: Linux access restored. Prepared and tested general grounding
and delivered-response repetition changes in an isolated workspace. Linux unit
checks pass (131 passed, 1 skipped), but real OpenRouter conversation review still
fails the quality/latency gate. Shorter-prompt and policy-transport experiments
introduced regressions and were rejected. No deployment or new carrier acceptance;
task remains open. See [investigation and evidence](validation/grounded-dialogue-2026-10-24.md).


### 2026-10-24 — Owner-authorized grounded-dialogue phone trial

The owner explicitly requested deployment despite the known conversation-quality
and latency failures. Installed only the retained agent backend after checking
that calls were idle and taking a private rollback backup. Agent/EMA/ASR report
SERVING; the existing gateway remains running. M4-01/02 acceptance stays open;
owner's real phone test is pending. See the
[live trial and rollback record](validation/grounded-dialogue-2026-10-24.md#owner-authorized-live-trial).


### 2026-10-24 — Owner reports no ringing/audio after trial deployment

M1-06/M4-01, US-01: agent, EMA and ASR returned SERVING. The existing gateway
process remained alive with UDP 5060 bound to the configured LAN interface.
Synthetic OPTIONS requests from both the Linux host and the owner's Mac received
SIP 200 OK. Configured public address matched observed egress (addresses private).
No new call-state event appeared; the gateway log's last modification was 14:58:08
server local time before this investigation. The deployed trial backend hash was
unchanged. No process, firewall or routing configuration was changed.

During the owner's reported retry, bounded metadata-only interface observation
printed only the diagnostic OPTIONS request/reply. It ended with two packets
captured, three received by the kernel filter, zero dropped; the extra filter
count is not evidence of a decoded carrier INVITE. No raw packet/audio file was
created. This proves local SIP responsiveness, not external carrier reachability.
The owner subsequently confirmed dialing the Netgsm 0850 number directly; mobile
forwarding is therefore excluded for this attempt. A Netgsm portal tab was found,
but browser access timed out while the computer-control tool reported a locked
Mac. Portal inspection awaits owner unlock. Inspect the trunk/NAT routing path
and repeat correlated carrier observation before diagnosing a specific upstream
device or declaring phone service restored. Owner hearing/answer acceptance is failed/pending.


### 2026-10-25 — PROF-02 configuration storage validation

The Linux host became reachable. Copied only new migration/example/test files;
existing remote source edits were preserved. Tested fresh/upgrade migrations and
repeat seeds in disposable schemas: 24 tests passed in 2.74s, no skips, including
cross-scope rejection, immutable revisions, invalid names/settings and mandatory
safety flags. Ruff lint and formatting passed. The live schema was not migrated;
no service was restarted. This is database evidence only, not profile routing,
CUDA, carrier, Telegram or frontend acceptance. Those gates remain open.


### 2026-10-25 — Platform non-regression gates planned

[PERF-01–06](AGENT_PLATFORM_PERFORMANCE_PLAN.md) require a fresh deployed baseline,
matched configuration overhead/full-model measurements, independent HTTP API and
worker failure/load tests, bounded GPU asset jobs, churn/soak and carrier canary.
Historical sequential latency and PROF-02 DB tests do not pass these new gates.
No benchmark, Docker rollout or live service change occurred in this design task.


### Configuration completeness review — 2026-10-25

[CFG-01–18](AGENT_CONFIGURATION_AUDIT.md) adds field-by-field runtime effect tests,
DB/API/native bound parity, two-agent interleaving, literal-removal classification,
ASR vocabulary isolation, TTS chunking/closing/recovery and release pinning checks.
The review found existing schema/runtime limit mismatches; those remain unresolved.
No new tests or refactoring were performed in this documentation review. Prior
migration tests prove storage constraints only, not effective live configuration.


### System-managed optimization clarification — 2026-10-25

Test automatic engine preset resolution, user override rejection, compatible-agent
preset reuse, model-specific capability checks, version pinning, canary/rollback
and no mutation of active calls. Ordinary users configure business behavior only.
The CFG inventory remains a consumer-coverage gate, not an all-settings user form.
No runtime test was run for this planning clarification.


## 2026-10-25 — AGP-03 per-call recognition vocabulary

Primary authorized Linux development checkout, isolated loopback workers and
disposable PostgreSQL schemas. No live service restart, actual caller/notification,
real inference, performance acceptance or second-line activation.

```sh
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 --with numpy==2.5.4 \
  --env-file .local/dev.env pytest tests/test_asr.py tests/test_asr_configuration.py \
  tests/test_agent_runtime.py tests/test_agent_drafts.py tests/test_agent_releases.py \
  tests/test_call_initialization.py tests/test_prepared_releases.py \
  tests/test_answered_lifecycle.py tools/asr-compare/test_compare.py -q --tb=short
# 150 passed, one existing audioop deprecation warning, 25.67s; no skips.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/test_grpc.py \
  tests/sip-integration/test_prepared_setup.py \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  -q --tb=short
# 52 passed, one existing audioop deprecation warning, 78.22s; no skips.
uv run --frozen cmake --build --preset local -j 2
# Full native build passed.
uv run --frozen ctest --preset local
# 10/10 passed, 3.81s.
```

An initial protocol selection included nonexistent tests/test_speech_bridge.py;
pytest exited 4 with no tests collected. Corrected selection is recorded above.
Ruff check/format passed for all 17 affected Python files; git diff --check passed.
No C++ source changed; generated C++/Python bindings use the pinned generation script.

Evidence covers pinned published vocabulary despite subsequent draft edits, separate
ASR leases, malformed config/deadline/forged/duplicate metadata, immutable retries,
interleaved aliases and explicit empty override, preserved numbers/acknowledgements,
release during non-preemptible decode, cleanup/reopen with no inherited configuration,
Whisper/Nemotron shared defaults and retained partial-hint cadence. Agent/ASR handoff
is driven by a Python test peer; the native gateway does not yet call ConfigureCall.
Worker model responses are scripted; no GPU or quality/latency claim follows.


## 2026-10-25 — AGP-03 native ASR configuration/lease handoff

Primary authorized Linux development checkout. Real private gRPC and loopback SIP,
synthetic conversation/speech, disposable database schemas. Native recognition probe
uses a link-time turn-detector double; separate legacy interruption regression uses
the existing native CPU models. No CUDA/provider/carrier or live migration evidence.

```sh
uv run --frozen cmake --build --preset local -j 2
# Passed, including recognition-setup-probe.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_recognition_setup.py -q --tb=short
# 14 passed in 23.63s, no skips.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest tests/sip-integration/test_prepared_setup.py \
  tests/test_asr_configuration.py tests/test_prepared_audio_transport.py \
  tests/test_answered_lifecycle.py tests/test_call_initialization.py tests/test_grpc.py -q --tb=short
# 102 passed in 60.81s, no skips.
uv run --frozen ctest --preset local
# 10/10 passed, 3.82s.
uv run --frozen --with httpx==0.28.1 --with starlette==1.9.0 \
  --env-file .local/dev.env pytest \
  tests/sip-integration/test_agent_dialogue.py::test_two_turns_complete_audio_before_hangup \
  tests/sip-integration/test_interruption.py::test_interruption_cancels_old_output_and_recognizes_correction \
  tests/sip-integration/test_speech.py -q --tb=short
# 24 passed in 219.24s, no skips.
```

Existing audioop deprecation warnings only. Ruff check/format passed for both changed
Python suites. clang-format --dry-run --Werror passed for the seven changed/new native
source/header/probe files. git diff --check passed. No protocol regeneration required.
Earlier focused stages passed 11 tests in 18.18s and 13 in 22.56s; the final suite
includes lost ASR OpenCall acknowledgement and strict-worker monitor cancellation.

Coverage: exact separate ASR lease, two DID-selected dictionaries, immutable worker/
call binding across two turns, monitor/cancel metadata, unsupported config/worker,
negative acknowledgement, failed/lost configuration reply, slow open/configure,
original cumulative setup deadline, prompt SIP CANCEL, two-service cleanup and
uncertain open/release acknowledgement. Lost-open test deliberately retains an ASR
lease until fixture teardown (production relies on expiry); it never reports confirmed
cleanup. Setup failure never emits media or SIP answer. Configured native monitor
cancellation is acknowledged by the actual GenerationControl implementation.

The SIP setup profile still only plays prepared clips. Native two-turn/monitor
configuration consumption is exercised separately in the probe. Ordinary agent
readiness remains false; full routed Session conversation and agent/TTS leases,
remaining native settings and measured performance/quality gates remain pending.

## 2026-10-26 — Resident audio preparation

AGP-06: 57 Linux automated cases and nine isolated HTTPS scenarios passed. Actual
resident EMA produced two synthetic-text assets inside an acknowledged maintenance
window; admission resumed. No new SIP/carrier call or Telegram message was sent.
The owner’s previous handset acceptance remains unchanged. See
[preparation evidence](validation/voice-preparation-queue-2026-10-26.md); matched PERF
and additional handset quality acceptance are still pending.

## 2026-10-26 — Scoped call-detail UI

AGP-06/P1: 47 Linux API/RLS/regression cases and 10 isolated HTTPS scenarios
passed. The existing owner's call summary/note/delivery result was viewed through
the deployed UI, with no call or external send triggered. Only management/web
restarted; all eight local peers were preserved. This is read-path/browser evidence,
not a new SIP/carrier, concurrent-capacity or matched performance test. See
[call detail evidence](validation/call-detail-2026-10-26.md).

## 2026-10-26 — Transcript and informed notification retry

AGP-06/P1, US-05/07: 48 Linux tests and 11 isolated HTTPS scenarios passed.
Finalized/sent-only transcript paging and owner-reviewed retry survive a deliberately
lost HTTP response with one durable consent request. Fake transport only; no real
retry message or new call. Owner read-only browser smoke verified an existing
populated transcript and the honest empty state of a different record. Management/
web alone restarted, eight peers preserved. No new carrier/performance acceptance.
[Evidence](validation/transcript-retry-ui-2026-10-26.md).


## 2026-10-26 — Registration frontend update (no new carrier trial)

AGP-06 / M2,M5, ADR 0011. Approved registration journey deployed to the private
preview after 17 isolated HTTPS browser scenarios passed in 31.1s. Existing owner
read-only smoke passed, including prepared audio decoding. Only web restarted;
nine application peers preserved. No SIP/RTP call, voice restart, external send,
capacity or latency acceptance. [Evidence](validation/registration-ui-2026-10-26.md).

## 2026-10-27 — Management MCP supplementary validation

MCP-01–06 / ADR 0012: control-plane synthetic preparation/publication/number gates
and scoped call search passed supplementary tests. No carrier call, real voice
preparation, external notification or shared-host performance result is claimed.
Linux final acceptance and Cloudflare/real-client tests remain pending connectivity.
See [separated evidence](validation/management-mcp-2026-10-27.md).

Management MCP follow-up: actual Codex and Claude Code clients completed local
HTTPS token discovery. Added read-only release readiness polling; 29 supplemental
readiness/MCP/number tests passed. No carrier or public-domain acceptance is implied.


### 2026-10-27 Management MCP public deployment

MCP-01–06 / AGP-06/07/09: primary Linux 217 integration and 45 browser tests passed.
Public HTTPS, actual Codex/Claude Code discovery, SDK synthetic draft mutations/retry
and token revocation passed. Existing voice containers and number bindings preserved.
No new carrier call, real voice publication/activation or external notification. Full
matched voice/load/soak gates remain open. See
[public MCP evidence](validation/management-mcp-2026-10-27.md).

## 2026-10-27 — Password-policy maintenance

AGP-02 / M0,M5: owner-approved eight-character password minimum deployed to API/web;
29 authentication/token tests and 45 isolated HTTPS browser tests passed. Account
recovery and public login/logout verified. No handset call or carrier reacceptance;
all twelve non-target Alojan container identities, including voice, were preserved.
[Sanitized evidence](validation/password-policy-2026-10-27.md).

## 2026-10-27 — MCP admission capacity maintenance

MCP-06 / AGP-09: pending capacity fix deployed with explicit owner authorization.
Eleven Linux tests passed; synthetic saturation/cancellation/timeout and public
unauthenticated HTTPS smoke verified. Only the MCP container changed; thirteen
other containers preserved. No new carrier call or voice/load acceptance.
[Evidence](validation/mcp-capacity-2026-10-27.md).

## 2026-10-27 — Nazli MCP authoring

Owner-requested draft v2 created/read/updated through public management MCP. No live
call, publication or routing change. Deliver2.ai authentication and diagnostic tools/list
succeeded; protocol/schema compatibility blocks outbound runtime qualification.
No business tool executed. [Evidence](validation/nazli-authoring-2026-10-27.md).

## 2026-10-27 — Self-service outbound MCP endpoints

ADR 0013 / AGP-07/09: removed manual endpoint preapproval, preserving bounded public
HTTPS transport and per-agent grants. 147 Linux tests passed. Native admission drained
before replacing agent/discovery; one bound number ready, admission reopened. No new
handset call, live external business query or measured voice/load acceptance.
[Evidence](validation/mcp-self-service-endpoints-2026-10-27.md).


## 2026-10-27 — Deliver2.ai compatibility deployed; no new carrier acceptance

AGP-07/09 and MCP-06 / M4–M5. Linux service groups: 135 and 110 passes (overlap);
46 HTTPS browser scenarios. Three existing releases preserve compiled voice/model
configuration. Native admission drained for deployment, one existing binding fresh-ready
and gate reopened; speech peers unchanged. Real authenticated MCP task-outcome read:
2.077 seconds / 1811 bytes, no private payload retained. Nazlı draft v3 now has eight
configured read tools and exact grant; no release or number binding. No phone call,
GPU/load benchmark or eight-tool real workload was performed.
[Evidence](validation/mcp-deliver2ai-2026-10-27.md).
