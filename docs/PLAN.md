# Implementation plan

## 2026-10-27 — Interruption evidence candidate rejected; recovery isolated

M3-02/M5-03/VXP-06, US-05/06: implemented an off-by-default, unmanaged-loopback-only
text-corroboration/recovery trial. Real native CPU VAD/turn models and SIP/RTP,
scripted ASR/TTS/agent: empty text suppresses both background and intended callers;
fresh background words still interrupt; delayed text adds about 845 ms in a paired
case. Candidate fails the early quality gate; do not deploy. Post-interruption
capture-limit recovery clarifies once and accepts the next valid turn; repeated
failure closes politely. 11 CTest and 15 candidate cases passed (including explicit
negative quality cases); 8 default cancellation/monitor regressions passed, with
7 other cases deliberately deselected. Graph refresh is pending due to tool transport failure.
No live setting/service change. [Evidence](validation/interruption-evidence-trial-2026-10-27.md).

The owner ended this experiment before publication. Its source/test harness is
archived privately; only the previously qualified default implementation is released.

## 2026-10-27 — Silero threshold sweep completed; current threshold retained

M3-02/M5-03/VXP-06, US-05/06: compared 0.50/0.60/0.70 on the same 34 Linux
public/synthetic G.711 streams (727.68 s), keeping 640/160 ms evidence timing.
All three produced 20/20 later and 4/4 initial background-only crossings.
Quiet clean and short clean targets remained detected; higher thresholds added
up to 32/64 ms target-window delay. Baseline reproduced exactly; policy/boundary
self-checks and Linux Ruff passed. No live change; noisy-room issue remains open.
[Evidence](validation/silero-threshold-2026-10-27.md).

## 2026-10-27 — Hush as preprocessing before Silero tested; default rejected

M3-02/M5-03/VXP-06, US-05/06: owner explicitly retains Silero. Tested Hush
as an additional input filter on Linux: 34 public/synthetic G.711 streams,
727.68 s, three profiles and 96 recognition checks (92 CUDA decodes, four digital
silence short circuits). Strong Hush reduces
later background crossings from 20/20 to 18/20 but loses all four quiet clean
long utterances; gentle 20 dB filtering preserves them but leaves 20/20 crossings.
Some overlap recognition improves. Filter latency is low; quality is insufficient
for global activation. State/reset/two-session/calibration/Ruff checks pass.
No live change; Silero remains active. [Evidence](validation/hush-2026-10-27.md).

## 2026-10-27 — neovad CPU screening completed; live replacement not qualified

M3-02, M5-03, VXP-06; US-05/06: tested pinned Apache-2.0 neovad pretrained GRU
against the serving Silero model on 30 public/synthetic G.711 streams (667.20 s).
Background-only sustained-threshold crossings improved from 20/20 to 16/20,
but still fail the caller-preservation/no-false-interruption goal. Maximum
per-stream P95 neovad processing was 0.689 ms per 32 ms block on one CPU thread.
Fixture/policy/state/streaming-parity checks and Linux Ruff passed. No live change.
Follow-up results were retrieved after SSH returned: both detectors crossed the
threshold in all four initial background-only windows; both detected the four
clean short phrases when a 500 ms tail was included. Reports are synchronized;
native SIP and handset qualification remain pending.
[Evidence and limitations](validation/neovad-2026-10-27.md).

## 2026-10-27 — Free VoxLock trial completed; automatic live mode rejected

M3-02, M5-03, VXP-06; US-05/06: owner requires a free/open-source candidate;
Krisp/LiveKit access work is superseded. Ran pinned Apache-2.0 VoxLock int8 on
Linux CPU: 16 G.711 streams (396.48 seconds), followed by 64 real CUDA Whisper
decodes. Target-first competing speech improved substantially, but all four
background-first cases selected the wrong voice and lost the caller's words.
Do not promote automatic enrollment to the live line. Chunk processing met the
tested 80 ms cadence; this does not close native/handset/latency acceptance.
Self-checks/lint passed; no serving changes. [Evidence](validation/voxlock-2026-10-27.md).

## 2026-10-27 — Local Krisp VIVA trial selected; SDK access pending

Historical preparation, superseded by the free-only decision above.

M3-02, M5-03, VXP-06; US-05/06: the owner corrected the LiveKit selection
to the first candidate, local Krisp VIVA telephony voice isolation. Verified
vendor installation/model requirements and prepared the paired evaluation scope,
including continuous competing speech and distant speakerphone target retention.
No SDK/model package was found in the checked Linux development/download paths;
the owner confirmed SDK access is not yet available. SDK inference, quality and
latency measurements remain pending vendor access. No live behavior changed.
[Preparation and limits](validation/krisp-voice-isolation-2026-10-27.md).

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


## 2026-10-27 — Instruction variables deployed; Nazlı analytics configured

AGP-06/07/09 and MCP-06 / M4–M5, CFG-01, US-08, ADR 0011–0013. Per-agent literal
variables and trusted identity/time fields are available through UI, HTTP and MCP.
Release-v10 pins definitions/timezone; turn-local one-pass expansion adds no IO and
preserves legacy releases. All readers, host preparer and web are deployed; one
bound line remains ready. A model currency-space rejection found during analytics
validation was fixed without relaxing other speech guards.

Linux suites: **97**, **114**, and **111** passes (overlap); **47 HTTPS browser
scenarios passed**. Three existing releases compile unchanged. Nazlı draft v6 has
updated question-to-tool guidance, session count selection and exact authorization;
no publication/binding. All-user aggregation is unavailable from the selected source;
partial pages must not be presented as complete distribution. Six real-model
synthetic analytics scenarios passed after refinement. Real voice/load and
broader conversational acceptance remain separate.
[Evidence and rollback](validation/prompt-variables-2026-10-27.md).


## 2026-10-27 — Deliver2.ai schema compatibility deployed; Nazlı tools configured

AGP-07/09 and MCP-06 / M4–M5, US-08, requirements §11.2–11.3, ADR 0011–0013.
June/November MCP negotiation and UUID/date-time schemas are supported. Optional
output schemas use bounded JSON and explicit grant v3 / release v9; legacy releases
are unchanged. Primary Linux test groups: **135 passed** and **110 passed** (overlap);
**46 real HTTPS browser scenarios passed**. Three current releases compiled unchanged;
compatible API/web/agent/workers/preparer deployed, existing bound line ready.
Real Deliver2.ai discovery found 19 tools; one runtime read succeeded in 2.077s.
Nazlı draft v3 has eight reviewed/configured/granted read tools, saved over public
management MCP; temporary token revoked. No publication or number binding. Real
Nazlı phone/model acceptance and multi-tool/load performance remain separate.
[Evidence](validation/mcp-deliver2ai-2026-10-27.md).

## 2026-10-27 — Manual MCP endpoint approval removed and deployed

AGP-07/09 / M4–M5, US-08 and accepted ADR 0013. Owners can register public HTTPS
MCP servers without an operator URL file. Discovery and runtime retain DNS/IP/TLS,
credential binding, tenant, grant and bounded-work controls. Primary Linux:
**147 tests passed in 84.39s**. Only agent/discovery replaced after native drain;
twelve other containers and all existing routes/releases preserved. One bound
number ready; admission open and preparer active. Deliver2.ai protocol/schema
compatibility remains separate pending work. [Evidence](validation/mcp-self-service-endpoints-2026-10-27.md).


## 2026-10-27 — Nazli draft created through public management MCP

MCP-06 / AGP-06–07, M4–M5, requirements §11.3. Owner-requested Nazlı draft v2
created/read/updated over MCP with the existing model and EMA voice. No publication
or number binding. Owner-saved deliver2.ai bearer connection authenticates and exposes
19 tools, but Alojan's strict protocol/schema support prevents qualification. Add
bounded `2025-06-18` compatibility and qualify supported tool schemas before selection
and execution; do not bypass existing review or runtime limits. Temporary credentials
revoked. [Evidence](validation/nazli-authoring-2026-10-27.md).


## 2026-10-27 — MCP capacity fix deployed

MCP-06 / AGP-09, M4–M5, requirements §11.3 and ADR 0012. Owner-approved
non-waiting four-request admission now returns 503 when full; cancellation and
deadline release capacity. Primary Linux: **11 tests passed in 8.03s**, image built
and MCP-only deployment verified. Thirteen other Alojan containers preserved;
API/web/MCP healthy, public anonymous MCP rejected with 401. Matched voice/load/soak
and full conversational activation acceptance remain open. New agent identity and
instructions requested from the owner. [Evidence](validation/mcp-capacity-2026-10-27.md).


## 2026-10-27 — Owner-requested password minimum deployed

AGP-02 / M0,M5, ADR 0011, US-08: minimum password length is now eight characters
across API, registration, account settings and operator recovery. Primary Linux:
**29 authentication/token tests** and **45 browser tests** passed; web typecheck,
production builds and service health passed. Only API/web containers changed;
twelve other Alojan containers were preserved. Requested account recovery and
public HTTPS login/logout verified. Existing sessions and MCP tokens were invalidated
by password recovery. [Evidence](validation/password-policy-2026-10-27.md).
The broader MCP development goal remains paused; its pending capacity fix was not deployed.


## 2026-10-27 — Management MCP publicly deployed

MCP-01–06, AGP-06/07/09, M4–M5, requirements §11.3, accepted ADR 0012.
Owner-approved `<MCP_ENDPOINT>` is deployed through the existing
Cloudflare Tunnel. API/web/MCP and loopback ingress are healthy. Migrations 0027–0029
and restricted grants applied; existing voice containers, profiles and bindings preserved.
Primary Linux: **217 API/integration tests and 45 browser tests passed**; builds,
typecheck, Ruff, whitespace and nginx checks passed. Actual Codex and Claude Code
connected over public HTTPS. SDK create/update/read/idempotent retry and token
revocation passed with a synthetic account, subsequently disabled. No live number
or external notification changed. No persistent user client configuration was installed.
Full matched voice/load/soak and conversational publication/activation acceptance
remain open; basic public MCP connectivity is complete.
[Evidence, rollback and limitations](validation/management-mcp-2026-10-27.md).

## 2026-10-27 — Three self-service UI findings fixed and deployed

AGP-06/07/09, M4–M5, ADR 0011, requirements §11.2. Session-scoped draft retention,
uncertain-creation retry protection and safe MCP numeric validation resolve the
three UI review findings. Primary Linux: **44 browser tests passed (1.2m)**;
type checks, production build, formatting and whitespace checks passed. Only the
private-preview web service changed; healthy, login/registration HTTPS 200, eleven
other Alojan containers unchanged. No external action or new handset test.
[Implementation, evidence and limits](validation/ui-fixes-2026-10-27.md).

## 2026-10-27 — Self-service UI correctness review

AGP-06/07/08/09, M4–M5, ADR 0011, requirements §11.2. Three P2 defects reproduced:
unsaved tool edits lost on browser Back; duplicate agent creation after a lost response
and retry; unsafe MCP integers silently rounded. This historical review preceded
the fixes documented above.
Primary Linux isolated HTTPS baseline: **36 passed (1.1m)**. With three probes that
assert the observed defects: **39 passed (1.1m)**. No production or external writes.
[Findings, reproduction and limits](validation/ui-review-2026-10-27.md).

## 2026-10-27 — MCP and webhook critical-defect review

AGP-07/08/09, M4–M5, ADR 0011, US-07/08 and requirements §11.2. Reviewed
scoped connection/grant authorization, pinned tool schemas and arguments, execution
cancellation, OAuth credential handling, HTTP destination validation, action projection
and delivery/retry fencing. No confirmed P0/P1 finding in this review. Primary Linux:
**257 passed in 201.74s**, across MCP runtime/discovery/tools/schema/OAuth and HTTP
actions/receiver/action-delivery/grants/delivery-management suites. Isolated database
schemas and synthetic peers/local receivers only; no new external request, handset
test, runtime change or deployment. This is not a load/soak or exhaustive security
acceptance; existing end-to-end and performance gates remain pending.

## 2026-10-27 — Publication activation and restart isolation fixed

AGP-03/06/09, M4–M5, ADR 0011, US-01/08. Owner-approved P1 fixes are deployed:
trusted node-assigned publications are discovered/prepared without restart, and
unavailable individual releases no longer prevent healthy agents from starting.
Single active number binding, explicit owner rebind, pinned calls and readiness/grant
checks remain enforced. Primary Linux: **147 passed in 125.08s**; after the final
retirement race guard, four focused regressions passed again in **16.82s**. Ruff and
whitespace checks passed. Migration 0026/restricted grants are active; only agent/API
containers changed. One bound number is ready, admission open, business data preserved.
No external action or new handset test. [Evidence](validation/publication-activation-2026-10-27.md).
Continue latest-release end-to-end and performance/operational gates; summary quality,
second-number provisioning and public launch remain deferred.

## 2026-10-27 — Single active agent per number confirmed

AGP-03, M4–M5, ADR 0011, US-01/08. Owner reiterated that one number must have
only one active agent, without automatic selection. Existing implementation already
enforces a single active binding, globally unique verified number ownership, and
row locking/version checks for concurrent replacement. Historical bindings do not
receive new calls; admitted calls retain their pinned release.

Primary Linux: `tests/test_number_routing.py` **16 passed in 12.58s**, covering
ownership uniqueness, concurrent binding conflicts, atomic admission and pinned
calls across replacement. Disposable-schema integration only; no live route or
service change, external send or handset test. No runtime change was necessary.
Continue the latest-release end-to-end acceptance package next.

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

## 2026-10-26 — Declared conversation and tool outputs; candidate only

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.3–4/12/14–16. Agents now
own up to eight typed post-call fields from the bounded conversation/note or an
explicit property of a selected reviewed MCP read tool. One existing summary request
extracts conversation fields; finalization projects the last successful tool invocation
completed before call end. No new tool call, model request or media-path I/O.

Release v4, action review v3 and final-event v2 pin definitions, selected tool bindings,
values and per-field status. Older empty-output drafts/manifests retain their digests.
Next.js supports declaration, tool-property selection, HTTP mapping/consent and scoped
call-detail display. Missing/invalid/unavailable data stays null with an explicit state.
New PostgreSQL example is read-only; existing JSON storage requires no new migration.

Primary Linux: **234 compatibility tests passed in 183.25s**, including eight new
output cases; expanded output/privilege/example checks **11 passed in 9.29s**
(overlapping). Final HTTPS browser: **33 passed in 57.5s** with zero production
writes or external sends. [Final browser/build evidence](validation/declared-outputs-2026-10-26.md).
No serving migration/restart, real model/tool/webhook request or voice/model change.

Remaining AGP-08 work: additional event filters and explicit transcript policy;
then approved real receiver acceptance and coordinated activation. Richer nested
mappings/dynamic paths remain unsupported. Real extraction quality, provider/MCP
acceptance, load/latency and public-launch/carrier gates are still separate.

## 2026-10-26 — Typed HTTP post-call actions; candidate only

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.3/12/14–16. Implemented
scoped HTTPS destinations, encrypted optional bearer credentials, typed flat JSON/
query mapping, synthetic preview, exact owner grant, immutable release/event intent,
and bounded dispatch/reviewed retry in the existing separate action worker. Next.js
provides connection, mapping, consent and revocation controls beside Telegram.

Primary Linux compatibility: **187 passed in 163.58s**; expanded HTTP checks:
**16 passed in 7.00s**; final bounds/grant regression: **26 passed in 16.61s**
(overlapping suites). Final delivery/grant regression: **95 passed in 106.22s**.
Final browser: **31 passed in 55.4s**, including 20 real API journeys and 11
intercepted UI contracts. Restricted-container, frozen worker/voice
imports and production builds passed. [Final evidence](validation/http-actions-2026-10-26.md).

Migration 0024 and matching service images remain candidates; no live migration,
serving restart or real external write. Existing voice/EMA and second-line state
are unchanged. This is the existing scalar-field slice of AGP-08, not its completion.
Next: declared validated extraction fields and approved tool-result projections,
then additional event conditions/transcript policy and approved real receiver
acceptance. AGP-07 real-provider acceptance, coordinated activation and public-launch/
performance/carrier gates remain open.

## 2026-10-26 — MCP OAuth lifecycle validated on Linux; candidate only

AGP-07 / M4–M5, ADR 0011, US-08 and §9.3/12/14–16. Added owner-reviewed
preregistered-provider login, session-bound PKCE callback, encrypted credentials,
background rotation and scoped readiness/revocation. No refresh I/O in the media
or tool-turn path. Migration 0023 and registry/SQL/deployment examples are included.

Linux final compatibility **195 passed in 100.55s**; HTTPS browser **30 passed in
48.3s** (19 real API journeys, 11 intercepted UI contracts). Restricted-container,
frozen worker, TypeScript/build, formatting, Compose and nginx checks passed.
[Detailed evidence and candidate identities](validation/mcp-oauth-2026-10-26.md).

Migrations 0020–0023 and matching images remain unactivated. Real approved-provider/
MCP acceptance and coordinated activation are pending; no serving restart, external
request, message, call or model change. Next independent work: AGP-08 typed post-call
HTTP/webhook actions. Public launch and performance/carrier gates remain open.

## 2026-10-26 — MCP builder UI validated on Linux; candidate only

AGP-07 / M4–M5, ADR 0011, US-08 and §9.3/12/14–16. The separate Next.js frontend now
offers workspace MCP connection/discovery controls, reviewed agent tool selection,
usage guidance, typed fixed parameters and exact owner permission/revocation.
Historical grants remain revocable after draft tools are removed. Secrets stay
write-only; discovery, authorization, publication and routing are distinct actions.

Primary Linux: **25 browser scenarios passed in 48.8s** (19 real restricted-API
journeys and 6 intercepted UI contracts). TypeScript, build, Python Ruff/format,
Prettier and whitespace checks passed; the independent production web image built.
Mac build/typecheck and 6 mock UI checks passed separately. Full diff and mobile
layout reviewed. [Evidence, initial failures and image identity](validation/mcp-ui-2026-10-26.md).

No serving deployment, live migration, MCP network request, message, voice/model
change or new carrier acceptance. Migrations 0020–0022 and the web image remain
candidate-only. Next AGP-07 work: OAuth lifecycle and approved real-server acceptance,
then coordinated activation; AGP-08 HTTP actions and public-launch gates remain open.

## 2026-10-26 — MCP immutable releases and bounded read-tool runtime validated

AGP-07 / M4–M5, ADR 0011, US-08 and §9.3/12/14–16. Version-3 releases now pin exact
MCP grants/tools/parameters. Migration 0022 adds scoped immutable execution evidence.
The optional dedicated executor enforces endpoint/schema/credential boundaries,
node/turn/call limits, timeout/cancellation and two-second permission freshness.
Revocation withdraws only the affected release; summaries and authorized Telegram
finalization remain independent. Non-MCP paths keep their existing contracts.

Linux compatibility: **265 passed in 128.25s**; final runtime/selection: **71 passed
in 56.78s**; final schema/SQL checks: **3 passed in 4.06s** (overlapping suites).
Restricted management-container validation, independent frozen voice/worker imports,
18-file Ruff/format and whitespace checks passed. [Full evidence, final checks and limits](validation/mcp-runtime-2026-10-26.md).

No live migration/restart or external request. Candidate migrations 0020–0022 remain
unactivated. Next AGP-07 work: MCP builder UI/journeys and OAuth; real approved-server
acceptance stays separate. AGP-08 and public-launch/performance gates remain open.


## 2026-10-26 — MCP selection and owner-consent backend validated

AGP-07 / M4–M5, ADR 0011, requirements US-08, §9.3/12/14–16. Added operator-reviewed
read capabilities, per-agent MCP selection/aliases/fixed parameters and exact owner
consent. Migration 0021 enforces workspace isolation and immutable review/grant
records. Changed selected tool definitions and revoked connections/reviews/owners
block permission reuse. No whole-server permission or annotation-based approval.

Linux compatibility suite: **171 passed in 58.59s**. After separating optional MCP
imports, selection/draft/voice preparation: **61 passed in 18.15s**; final expanded
selection cases: **27 passed in 10.53s** (overlapping suites). Real restricted Docker
management validation and frozen voice-preparer import passed. Ruff/format/diff
checks passed. [Evidence and staging limits](validation/mcp-selection-2026-10-26.md).

No serving migration/restart, call, message, model or voice change. Existing drafts
keep their historical digests. MCP selections explicitly fail compilation/preparation/
publication while execution is unavailable; no unusable release is marked ready.
Next: MCP release pinning, admission/readiness/drift, bounded call execution and live
revocation, then builder UI/OAuth. Candidate images stay unactivated until these
consumers exist. AGP-08 and public-launch acceptance remain open.

## 2026-10-26 — MCP connection/discovery backend validated

AGP-07 / M4,M5, ADR 0011, requirements §9.3/12/14–16. Added scoped immutable MCP
connections, purpose-bound encrypted bearer credentials, explicit discovery jobs,
least-privilege worker provisioning and an independent bounded Docker overlay.
The real pinned SDK handles JSON/SSE discovery only. Exact operator-approved HTTPS
endpoints, vetted DNS/IP pinning, no redirects/proxies/compression, bounded schemas,
lease fencing and revocation are enforced. Remote tool annotations never grant rights;
all manifests remain unreviewed and no tool invocation path is enabled.

Linux final compatibility suite: **114 passed in 43.71s**, including 46 MCP cases.
Management/worker images built; real restricted management-container checks passed.
Existing HTTPS journeys: **18 passed in 44.5s** against the candidate API. No production
migration or service restart; no external discovery, call, message, model or voice change.
[Evidence, image identities and limits](validation/mcp-discovery-2026-10-26.md).

Next AGP-07 slice: reviewed tool capabilities, agent selection/fixed parameters,
explicit grants, immutable release/readiness/schema-drift handling and bounded runtime
execution, then builder UI and OAuth. Real approved-server acceptance is separate.
AGP-08 HTTP actions and public launch remain open. Discovery alone is not an executable
agent integration, so candidate images remain unactivated on the serving stack.

## 2026-10-26 — Self-service journey and lifecycle controls deployed

AGP-06 / M2,M5, ADR 0011, requirements §1/12/14–16. The real HTTPS UI/API journey
now validates register → configure model/Telegram → prepare/listen → grant → publish
→ separately verify/bind. Voice generation and operator/node readiness are synthetic
and isolated; no production bypass endpoint. Bound/pinned releases survive draft
edits; stopping routing rejects new calls while preserving the pinned call.

Added owner-reviewed number deactivation and provider/Telegram connection revocation
using existing APIs. Cancel, stale versions and committed-but-lost responses are
covered. Readiness errors explain the blocked step. No backend/schema/dependency or
media-path change. Linux **18 HTTPS scenarios passed in 42.6s; 62 service tests in
32.39s**. Mobile review, formatting, TypeScript, builds and deployed read-only owner
smoke passed. Only web restarted; nine application peers retained identity/health.
No new carrier call, real synthesis or external send. Second number remains disabled.

AGP-06's functional self-service journey is accepted through the synthetic routing
boundary; real new-agent carrier/voice acceptance remains separate. Next: AGP-07
MCP connections/selection, then AGP-08 typed HTTP actions; public launch stays open.
[Evidence and limits](validation/self-service-journey-2026-10-26.md).

## 2026-10-26 — Approved registration journey deployed

AGP-06 / M2,M5, ADR 0011, requirements §1/12/14–16. Implemented the approved
account → optional first agent → preparation flow through existing native/scoped
APIs. Distinct account/agent identity, skip/empty state, saved draft continuation,
mobile layout and uncertain-result recovery are delivered. No automatic publication,
number binding or external action. No backend/schema/dependency change.

Linux **17 HTTPS browser scenarios passed in 31.1s**; formatting, TypeScript and
production builds passed. Deployed registration and existing owner read-only smoke
passed. Only web restarted; nine application peers preserved. No new calls or sends.
Next: remaining AGP-06 prepare/publish/bind workflow acceptance, then staged MCP/HTTP.
[Evidence and limits](validation/registration-ui-2026-10-26.md).

## 2026-10-26 — Registration journey visual proposal

AGP-06 / M2,M5, ADR 0011, requirements §1/12/14–16. Prepared a three-step
account → first agent → preparation mockup and captured the actual deployed login.
Proposal distinguishes account and agent identity, permits skipping agent creation,
and keeps voice preparation, verified number binding and notification permission
explicit. Linux browser review covers desktop/mobile, transitions and empty state.
No production implementation, account creation, external send or voice change.
Owner visual review is pending; existing workflow acceptance remains open.
[Design brief and visuals](design/registration-mockup-brief.md).

## 2026-10-26 — Scoped response performance UI deployed

AGP-06 / M2,M5, P1, ADR 0011, requirements §2/3/12/14–16. Added an agent-filtered
performance page and on-demand per-call distributions. The existing gateway logs
are imported outside the media path into immutable, RLS-protected numeric records;
no caller content or new inference operations. P50/P95 exclude failed/interrupted/
recovery turns and preserve missing values. Windows and server-versus-handset limits
are explicit. Separate bounded oneshot container/timer imports existing logs.

Linux **51 tests passed in 32.29s; 13 HTTPS scenarios in 22.5s**. Ruff, TypeScript,
production builds, desktop/mobile review and deployed owner read-only smoke passed.
Migration 0019 completed in **0.058s** after backup; 16 existing timing observations
imported without malformed/unowned rows. Management/web alone restarted; eight peers
preserved. Collector timer active; voice admission remains open. No new calls,
external sends, engine changes or latency/capacity acceptance.

Next: remaining AGP-06 self-service workflow acceptance (register/create/configure/
prepare/publish/bind), then staged MCP/HTTP work. Second number remains disabled.
[Evidence and limits](validation/performance-ui-2026-10-26.md).

## 2026-10-26 — Release rollback UI deployed

AGP-06 / M2,M5, P1, ADR 0011, requirements §1/2/11.2/12/14–16.
Added on-demand latest-100 release history, immutable revision identity/lineage,
owner-only selection and explicit rollback review using the existing API. The UI
keeps publication separate from routing, preserves drafts, blocks dirty/stale writes
and requires a fresh review after uncertain responses. No API, schema or dependency
change. Current permission and model/asset checks remain authoritative.

Linux **44 tests passed in 25.41s; 12 HTTPS scenarios in 21.3s**. Ruff, TypeScript,
production builds and desktop/mobile checks passed. Isolated browser checks prove
cancel/no write, draft preservation, version conflict, lost-response recovery and
unchanged synthetic binding. Only web is updated; owner smoke is read-only.
No live rollback, new calls, external sends or performance acceptance.

Next: AGP-06/P1 latency views and remaining workflow acceptance; staged MCP/HTTP
work and public launch remain open. [Evidence](validation/release-rollback-ui-2026-10-26.md).

## 2026-10-26 — Transcript and informed retry UI deployed

AGP-06 / M2,M5, P1, US-05/07, ADR 0011, requirements §2/7.3/11.2/12/14–16.
Added scoped transcript pages with finalized/sent-audio filtering, stable cursors,
plain-text display and honest missing-text segments. Owner retry UI uses the existing
exact-target/message review, unchecked duplicate-risk consent and idempotent request
API; lost HTTP responses retain the same request identity. Reading never sends.

Linux **48 tests passed in 49.93s; 11 HTTPS scenarios in 20.0s**. Ruff, TypeScript,
production builds and desktop/mobile checks passed. Deployed owner smoke read an
existing populated transcript and sent result without configuration writes or retry.
The newest call had no transcript rows; its empty state was correctly preserved.
Migration 0018 completed in 0.021s after backup; management/web alone restarted,
eight peers preserved. No new calls, real Telegram sends or voice/performance claims.

Next: AGP-06 release rollback UI and remaining workflow acceptance; P1 latency views
and staged MCP/HTTP work remain open. [Evidence and failed attempts](validation/transcript-retry-ui-2026-10-26.md).

## 2026-10-26 — Scoped call history and detail deployed

AGP-06 / M2,M5, ADR 0011, requirements §1/2(P1)/12/14–16. Aramalar now shows
real workspace-owned calls with agent filtering and bounded cursor pagination.
Detail shows pinned historical identity, timings, summary, latest note/confirmation
and delivery result without resending. Added two history indexes and narrow
read-only grants, preserving RLS and excluding unscoped legacy calls.

Linux **47 tests passed in 45.85s; 10 HTTPS scenarios in 16.3s**. Ruff,
TypeScript/build and desktop/mobile review passed. Owner read-only smoke verified
an existing call and its sent notification. Additive migration took 0.053s after
backup; only management/web restarted, eight peers preserved. No new calls/sends
or voice restarts; no new performance/capacity acceptance.

Next AGP-06/P1 slices: call transcript/latency views and existing owner-reviewed
retry/rollback workflows in the UI, followed by staged MCP/HTTP work. Summary,
latest note and delivery-result detail are complete; full dashboard acceptance is
not implied. [Evidence and limits](validation/call-detail-2026-10-26.md).

## 2026-10-26 — Durable resident audio preparation deployed

AGP-06 / M2,M5, ADR 0011, requirements §11.2/12/12.1/14–16. Added scoped
versioned request/status APIs, durable deduplicated jobs with bounded quotas/retries,
least-privilege roles and a separate private host coordinator. UI now requests new
audio and shows queued/preparing/ready/failed states across reloads. The coordinator
drains admission, proves all workers quiescent, opens only resident EMA, installs
verified immutable assets, then proves cleanup/readiness before reopening calls.
Lost ownership/restarts remain fenced for operator recovery; no second model or
management work enters the call path. Publishing and number binding stay separate.

Linux final **57 tests passed in 23.23s; 9 HTTPS browser scenarios in 14.3s**.
TypeScript/build/Ruff and real owner read-only/audio smoke passed. Actual resident
EMA generated two isolated test clips in **4.252s** with all voice process identities
preserved during generation; admission reopened. Initial deployment split the TTS
gate with a drained same-image TTS restart. HTTP/web rollout preserved eight peers.
No production agent changes, new calls or external sends. No new handset, concurrent
capacity or matched performance acceptance.

Next: scoped full call detail (summary, note and delivery result).
[Evidence, failed attempts and limits](validation/voice-preparation-queue-2026-10-26.md).

## 2026-10-26 — Prepared audio playback and Telegram builder deployed

AGP-05/06 / M2,M5, ADR 0011, requirements §1/12/14–16. Added authenticated,
version-checked playback of prepared greeting/unavailable WAVs, with bounded integrity
validation and a read-only asset mount. The UI now creates/removes up to four Telegram
actions, selects allowed outputs with required provenance/status, displays exact target/
field review, and explicitly grants/revokes permission using existing APIs. Saving,
granting, publishing and number binding remain distinct. No new dependency/migration.

Linux: **30 Python tests passed in 16.83s; 9 HTTPS browser scenarios in 12.3s**;
Ruff, TypeScript and production build passed. Test publication stayed in a discarded
restricted-role schema, with zero number bindings/jobs/sends. Real owner smoke decoded
Kübra’s existing EMA audio without changing its configuration. Updated management/web
only; eight peer container IDs/health preserved, private preview returns 200.

Next AGP-06 work: durable requests and coordinated drained-window generation of new
audio with resident EMA, then full call detail. Missing audio remains blocked; no new
voice/performance/carrier acceptance. [Evidence and limits](validation/web-actions-2026-10-26.md).

## 2026-10-26 — Approved frontend first slice and private preview

AGP-06 / M2,M5, ADR 0011, requirements §1/12/14–16. Owner approved the
Next.js/shadcn mockups and selected a private preview. Implemented native account
entry, scoped agent create/list/edit, preserved long configuration, text preview,
guarded prepare/publish, number/connection controls and delivery metadata. This
is the first approved slice; audio preparation/playback and new post-call grants/
output selection are the next AGP-06 work, followed by full call detail. MCP/HTTP
builders and public launch remain later acceptance. Capacity stays one.

Linux TypeScript/build and Ruff passed; **7 HTTPS browser scenarios passed in 9.3s**
against an isolated restricted-role schema, with no production configuration writes
or external sends. Corrected long-text layout and model-label integration after
visual review. Real owner read-only browser smoke passed with no browser errors.
Separate bounded web/TLS services are healthy; the private SSH-forwarded preview
returns 200. Only management's origin/container changed; **eight peer containers
and their health were preserved**. Owner first-login credential was created through
audited recovery and retained privately. Self-signed TLS requires a browser exception.

No new handset/performance/load acceptance is claimed. See [evidence and remaining
limits](validation/web-preview-2026-10-26.md) and the [approved design brief](design/agent-builder-mockup-brief.md).

## 2026-10-26 — Managed handset retry and scoped notification verified

AGP-03/05/09, M1/M4/M5, US-01/05/07, requirements §6/12: the owner's retry
answered after 3 seconds and completed a 52.196-second conversation. The owner
reported that everything worked as well as before. Native PCMA input/output,
seven turns, two interruption events and confirmed setup cleanup were observed;
the call matched the owner's scope and pinned release, with one saved note.

The real post-call worker initially rejected the release because its retained image
still capped instructions at 6,000 characters. Aligned only the shared configuration
contract with the already deployed 20,000-character definition in summary/delivery
images. Exact pinned-release image preflight passed; **5 Linux worker/instruction
regressions passed in 4.85s**. Seven peer containers, including all voice services,
were preserved. The existing job recovered through normal lease expiry: summary
done after six claims, one finalization, Telegram **sent on its first attempt with
a remote receipt**. No job reset or additional synthetic message.

This establishes one real managed carrier/notification round trip, including owner
audio feedback. It does not close matched PERF, load/soak, complete handset scenario
coverage, frontend or account recovery work. [Evidence](validation/in-place-platform-2026-10-26.md#successful-handset-retry-and-post-call-recovery).

## 2026-10-26 — First handset failure: carrier prefix corrected

AGP-03/09, M1/M4, US-01, requirements §6/12. The owner's first actual
call received the carrier unavailable announcement. Native signaling recorded
trusted INCOMING → DISCONNECTED/404 at 0 ms, before media or agent setup.
The deployment incorrectly used `called-national-prefix=none` although retained
Netgsm Request-URI users have the ten-digit `850…` format. Enabled the existing
explicit `0` normalization setting in private gateway configuration; canonical
verified binding and source trust remain unchanged.

Reproduced rejection in the new synthetic carrier-format scenario (one expected
failing run). After applying the setting, **3 native session scenarios passed in
77.99s**, and **caller-identity CTest passed in 1.02s**; Ruff and whitespace checks
passed. Drained/recreated only the gateway with the same image; eight peer
containers retained their identities and health. Native admission is open.
**Handset retry and real post-call delivery remain pending**, not carrier acceptance.
[Evidence](validation/in-place-platform-2026-10-26.md#first-handset-failure-and-prefix-correction).

## 2026-10-26 — Existing-line managed trial opened

Owner explicitly chose the unused current line/host, without another environment
or an intermediate legacy reopening. AGP-03/05/09, M1/M4/M5, US-01/05/07/08,
§11.2/12/12.1: backed up and migrated the existing DB to all 16 migrations with
historical row preservation; installed Kübra's account/profile/connections and
verified the existing DID from retained carrier signaling and owner authorization.
Second DID remains absent. Added explicit managed carrier startup, retaining
loopback-only test flags, source trust, prepared releases and scoped cleanup.

Linux: **46 SIP/managed/admission tests passed in 147.41s**, **10/10 CTests in
3.88s**, format/lint/shell checks passed. Reused resident speech workers/WAVs;
managed agent and independent HTTP/summary/delivery containers are running without
recreating PostgreSQL. Preserved the deployed partial-hint setting in immutable
engine revision 2. Two real managed CUDA/OpenRouter loopback calls saved scoped
notes and real summaries; final revision smoke took **33.29s**. Synthetic actions
are terminal/paused without network sends. Failed harness attempts are retained.

Fresh readiness/binding verified; native admission opened and bootstrap INVITE
fence removed. **Ready for the owner's phone trial.** No new carrier call or
Telegram send is claimed. Six real model turns completed, but only **3/6** behavior
checks passed: topic-only premature note-taking remains open. Full matched PERF,
load/soak, handset quality, frontend and interactive account setup remain pending.
[Evidence and limits](validation/in-place-platform-2026-10-26.md).

## 2026-10-26 — Compatible maintenance deployment and real worker receipts

Ponytail full; AGP-09 / PERF-01/03 preparation, M1–M5, requirements §12/12.1.
Restored SSH and verified all eight pending documentation copies. With the owner's
explicit privileged-operation authorization, installed a narrow temporary INVITE
fence and waited beyond the old call lifetime; 29 calls ended, 29 summaries done.
Recreated only gateway/ASR/TTS/agent using verified images and persistent closed
admission. Gateway acknowledged closed/local-drained; all three real workers passed
normal health and fresh maintenance receipts after pinned model startup. API,
Telegram and PostgreSQL were not recreated. Rollback identities/config are retained.

Three mixed-version fixture attempts failed at lease/configuration checks; no guard
was weakened. Exact retained-stack real-model smoke then passed one two-turn
loopback call, note/summary persistence and cleanup; maintenance derivatives were
restored with fresh receipts (**89.86s** switch/test/restore). No external send.

Follow-up found that the new agent's background work requires platform tables absent
from production despite normal RPC health. Stopped the agent; gateway/ASR/TTS remain
fenced. Added a fail-before-listen schema check. Linux migration/startup/maintenance
regression: **43 passed in 20.94s**, no skips/failures. This is a concrete deployment
hold, not live readiness. Next: matching isolated candidate schema/runtime and real
managed voice, then matched PERF and controlled production migration. See
[evidence](validation/maintenance-rollout-2026-10-26.md).

## 2026-10-26 — Dependent-worker admission and quiescence receipts

Ponytail full; ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M2–M5,
requirements §12/12.1. Added optional operator-file fencing to ASR, TTS and both
agent launchers using their existing private gRPC listeners. New work closes while
cleanup continues. On-demand maintenance checks account for requests, leases,
agent lifecycle/summary work, native futures and confirmed cleanup. Normal health
and default deployments remain compatible; no HTTP app or protobuf change.

Review found that cancellation could hide a cleanup exception and falsely attest
idle; fixed the shared cancellation path and agent double-abort handling. EMA and
stream cleanup failures now block the maintenance receipt. Legacy summary claims
pause without dropping queued jobs. Technical controls stay operator-owned.

Final Linux regression: **248 passed in 51.57s**, including **19 new maintenance
cases**, zero skips/failures. Real local SIP/prepared/session/supervisor regression:
**83 passed in 218.16s**; after the cancellation fix, managed native-session coverage
reran with **11 passed in 86.36s**. Earlier failures and exact scope are retained in
[evidence](validation/worker-quiescence-2026-10-26.md), not counted as passes.

Three source-only validation images passed isolated imports/CLI checks; compose,
Ruff, whitespace and source review passed. No models were loaded in these checks.
Read-only live probes confirmed ordinary health succeeds but old workers cannot
supply the new receipt. At the last check, seven live containers remained healthy
with original start times. SSH became unavailable during the final documentation
copy, after source/image hash verification and all tests completed. The eight updated
local documents are retained; their Linux review-copy transfer remains pending.
Restore connectivity and finish that transfer first. Next: coordinated compatible maintenance rollout and real-worker receipt validation,
then fresh matched real voice/PERF measurement. No live route/account/publication,
external send, GPU/carrier acceptance, push or merge occurred.

## 2026-10-26 — Supervised persistent admission control

Ponytail full; ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M1/M5,
requirements §12/12.1. Reused the preserved Linux supervisor/health implementation
and added optional operator-file admission control. Native children always start
closed and can open only after their own acknowledgement. Atomic directory-mounted
state survives Docker restart; missing/invalid/non-regular state closes admission.
The Netgsm launcher forwards startup arguments and retains the existing Linux
national-prefix setting. Other workers retain their health/restart behavior.

New Linux supervisor and real SIP/RTP suites: **12 passed in 17.60s**. Initial broad
regression: **117 passed / 11 skipped in 230.33s** because the command omitted its
explicit DB environment; those skips were not counted as acceptance. DB-enabled rerun: **78 passed in 202.64s**, zero skips/failures. Together the
two regression runs cover all **128 distinct existing scenarios** successfully.

An isolated, resource-limited, network-disabled Docker gateway passed closed SIP
486, explicit reopen SIP 200, healthy closed admission and persistence through an
actual native crash / Docker automatic restart. Test container removed; image,
source hashes and artifacts retained, operator state restored closed. Compose,
Ruff, shell syntax, scoped review and whitespace checks passed; graph refreshed.
See [evidence](validation/supervised-admission-2026-10-26.md).

Seven resident containers remain healthy with original starts. No live route,
account, model, publication or external-send change. Next: dependent-worker
quiescence and coordinated compatible maintenance deployment, then fresh matched
real voice/PERF measurements. No GPU/carrier/PERF gate is closed by these tests.

## 2026-10-26 — Local maintenance admission drain

Ponytail full; ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M1/M5,
requirements §12/12.1. Added signal-safe new-call close/resume controls and validated
`--start-drained 0|1` to the development native gateway. Existing capacity, source
policy, accepted ringing/answered calls, RTP and shutdown semantics remain intact.
Main-loop acknowledgements distinguish admission closure from completed local cleanup;
they deliberately do not claim remote GPU quiescence after missing cleanup receipts.
No per-turn lookup, HTTP service, model reload or concurrency increase.

Linux focused real SIP/RTP: **8 passed in 16.29s**. Native CTest: **10/10 passed in
3.84s**. Broad SIP/prepared/managed-session regression: **120 passed in 318.19s**,
zero skips/failures. Exact deployment limits are in
[evidence](validation/admission-drain-2026-10-26.md). Clang-format/Ruff
passed; source changes are synchronized and graph refreshed. Seven resident services
remain healthy and unrestarted. The lifecycle gateway/supervisor still lack these
controls; do not send USR signals to the old image or supervisor PID 1.

Next: supervised maintenance deployment and dependent-worker quiescence, then matched
real voice/PERF comparison. Persist closed startup across restart for the maintenance
window; a signal-only state is volatile. No carrier/inference test, live migration,
external send, push or merge. General max_calls=0 reload remains capacity-plan work.

## 2026-10-26 — Reused deployed EMA audio for the candidate profile

Ponytail full; ADR 0003/0011, AGP-02/03/09, M2/M4/M5, requirements §11.2/12.
Verified the running gateway selects tr-v5-kubra and its manifest, text and WAV bytes
match the retained source. Added the operator-only `alojan.voice_pack` command to
convert trusted legacy packs using existing immutable installation and WAV validation.
Mismatched text, model, rate, pad, sample count, content or unsafe file references fail
before installation. No synthesis, database publication or new service is introduced.

Candidate Kübra draft v2 aligns only the genitive apostrophe with the deployed spoken
text. Full instructions, tools, model/action references and other fields stay identical.
Prepared both audio files: greeting 5360 ms with 400 ms silence, unavailable 4000 ms.
Both are byte-identical to the deployed files; no GPU preparation window was needed
for this exact reuse. Files are staged, not registered as qualified database assets.

Primary Linux pack/release/cache regression: **49 passed in 8.95s**, no skips/failures.
Ruff passed after formatting two new files. Candidate package checks passed; account
session revoked. Model qualification, publications, grants and bindings remain absent.
Management image/CLI validation and final review are recorded in
[evidence](validation/voice-pack-preparation-2026-10-26.md).
Next: a verified admission fence and matched real voice/PERF measurement. Gateway
SIGTERM is bounded shutdown, not a long-call drain; max_calls=0 is still design-only.
No GPU/API inference, external message or live route/process change occurred.

## 2026-10-26 — Restored live backup and isolated owner workspace

Ponytail full; ADR 0003/0011, AGP-02/03/05/09, M1/M4/M5, requirements §9–12.
Restored a real, snapshot-consistent live logical backup into a temporary database:
all ten tables matched. Applied all 16 migrations twice and retained all original
data/columns outside the extended migration ledger; no historical replay or ownership
inference. Temporary restoration DB removed; private backup retained on Linux. This
is logical restoration evidence, not full-host recovery or loaded migration timing.

Created a separate candidate DB, restricted management role and the requested Burhan
owner workspace with one Kübra draft and two encrypted connections. Full instructions
and business fields preserved; Telegram configuration includes number provenance and
summary status. Zero publications, number bindings, grants, jobs or active sessions.
Initial random password was not distributed; owner password setup is still needed
before interactive acceptance. Model/preset catalog exists with qualification disabled.
**Production ownership is not yet transferred.** The second number remains absent.

Five Linux account/profile/connection/grant suites: **42 passed in 25.09s**, no skips.
Restricted-role secret/live-record denial, credential/draft round-trip and session
revocation passed. Existing management Docker image passed real candidate HTTP readiness
and anonymous-access rejection with resource limits and no published host port. Seven
resident services remain healthy/unrestarted; live schema unchanged. One missing import
path and an incomplete draft output-field selection were corrected in private operator
scripts; no application guard was weakened. See [evidence](validation/owner-preparation-2026-10-26.md).
Next: fenced EMA preparation, matched voice/PERF, scoped canary and eventual production
cutover. No new external send, GPU inference, push or merge.

## 2026-10-26 — Resumed rollback validation and complete instruction migration

Ponytail full; ADR 0003/0011, AGP-02/03/09 / CFG-01/03, M4/M5, requirements
§9–12. Linux restored; source checksums matched and outstanding rollback overlay/docs
were synchronized. Compose validation proves missing explicit rollback configuration
fails, the restricted file replaces database_env for old agent/API/Telegram, and service
definitions stay unchanged. No resident service was started or restarted.

First expanded run: **71 passed, 1 failed in 72.60s**. The concurrency test assumed an
immediate claim, but a retry consumer can hold the job while its peer holds the dispatch
gate; both legitimately SKIP LOCKED, leaving reopened work for the next poll. Corrected
the assertion without changing worker behavior; deterministic gate-contention coverage
proves consumed approval, pending state and one subsequent claim/attempt. Focused
**2 passed in 3.01s** (23 intentionally deselected). Expanded six-suite rollback/schema/
routing/records/delivery regression: **115 passed in 124.70s**, no failures/skips.

Voice preparation found the 6,000-character authoring field cannot hold the deployed
18,159-character instructions. Raised only that field to 20,000 characters; draft
60,000-byte and compiled prompt 32,768-byte ceilings stay unchanged. Full-text storage/
compilation, 20,001-character rejection and compiled UTF-8 budget tests plus draft/
runtime/release/startup suites: **71 passed in 26.06s**, no skips. Prepared a private
offline business draft with all 11 speech fields matching LEGACY_RUNTIME. The deployed
backend hash matches the snapshot; its instruction hash matches the retained legacy
module. The 23,574-byte compiled prompt includes mandatory platform context and differs
from the old prompt; matched infrastructure runs must hold the effective prompt constant
and report migration quality/length effects separately. No qualification is inferred.

Both management and worker images rebuilt after the contract change and passed offline,
read-only, capability-dropped import/schema checks. Final Ruff/format/diff checks passed;
graph refreshed without persisted cache. Seven resident containers remain healthy.
See [resume evidence](validation/platform-resume-2026-10-26.md). No production schema,
role, secret, ownership, binding or process change, external send, GPU inference, push
or merge. Next: scoped owner deployment and qualified EMA assets in a fenced window,
then matched real voice/PERF and scoped end-to-end canary.

## 2026-10-25 — Legacy-only rollback database identity

Ponytail full; ADR 0003/0011, AGP-09 / M4/M5, requirements §9–12. Added operator
`legacy-rollback` role provisioning with both permissive and restrictive legacy-only
RLS, strict effective privilege validation and a separate required-secret Compose
overlay. The preserved consumer cannot read/update managed call contents or insert
their notes/notifications, even with a forged workspace context. Three opaque route
identifier columns remain visible for existing invoker-rights triggers/predicates;
no numbers, manifests, credentials, account state or scoped action jobs are exposed.
No migration/data reset, new dependency/service or media code change.

Primary Linux focused suite: **14 passed in 8.95s**, including the preserved old Store
and Notifications lifecycle with fake transport and a pending managed call. Four
source hashes matched the deployed image. Initial run had 14 setup errors from catalog
sequence-function evaluation order; explicit CASE guarding fixed it. Original image
and snapshot untouched. Ruff/format passed before that small SQL guard correction;
final local syntax and whitespace checks passed.

SSH then timed out. Expanded five-suite regression, management image build and Compose
validation did not complete and remain pending; the new overlay/docs still need Linux
synchronization. Python implementation/tests were synchronized before the passing run.
See [evidence and exact rollback order](validation/legacy-rollback-2026-10-25.md).
No production role/secret/schema change, service restart, ownership transfer, external
send, push or merge. Next: restore connectivity, synchronize remaining files, complete
container/Compose and broad regression checks, then resume owner deployment/EMA and
matched real voice preparation. This does not close the voice/performance gates.

## 2026-10-25 — Real Telegram adapter acceptance and legacy upgrade rehearsal

Ponytail full; ADR 0003/0011, AGP-05/09 / PERF-02, M1/M4/M5, requirements
§9–12 and US-07/08. Read-only Linux inventory established the actual resident
`lifecycle-20261024` container deployment and its unchanged three-migration schema.
All seven Alojan containers healthy; 29 ended calls/complete summaries and eight
delivered notifications, no active/pending work at inspection. This is not an
admission fence. Platform account/roles/key/worker configuration and ownership
transfer remain undeployed; second-number mapping remains absent/disabled.

After explicit owner approval, the built scoped-worker image's production Telegram
adapter sent exactly the approved synthetic message to the existing target. Exact
destination and positive receipt verified; exclusive private journal prevents repeat
invocation. No DB access, historical payload or automatic retry. This is real adapter/
destination acceptance, not a real scoped summary/grant/job canary or recipient-read
confirmation. See the [sanitized evidence and cutover order](validation/platform-preflight-2026-10-25.md).

Added three disposable-schema migration rehearsals from the exact deployed baseline:
all original columns retained, no automatic owner/route/grant/job creation or historical
replay, idempotent upgrade, late DDL failure atomic rollback and bounded lock-contention
rollback/recovery. Initial **3 passed in 0.84s**; expanded schema/profile/scoped-records/
delivery-management checks **66 passed in 56.36s**, no failures/skips. An initial expanded
invocation failed collection because optional httpx was absent; reran with the documented
pinned httpx/Starlette test overlays. Ruff/format and whitespace checks pass.

Existing isolated performance fixtures: **2 passed in 2.16s**; admission n=50,
P50/P95=21.54/39.68 ms; cold synthetic preload n=30, 1.1114/1.1293 ms; warm pin/unpin
n=10000, 0.0028/0.0028 ms. No matched voice/control/confidence, GPU/API, carrier, load
or soak acceptance. No new production behavior or image rebuild in this slice.

Review found a cutover/rollback gate: the deployed old summary loop has no workspace
filter and bypasses RLS. It must stop before managed jobs exist; an unmodified old
consumer cannot be restarted over pending managed jobs during rollback. This sequencing
is now explicit in setup and evidence. Runtime remains untouched. Next: establish the
tested rollback consumer boundary, prepare the owner's scoped deployment and real EMA
assets in a fenced window, then matched voice/PERF and scoped end-to-end canary before
live binding. No production migration, ownership transfer, restart, push or merge.

## 2026-10-25 — Scoped delivery history and explicit owner retry

Ponytail full; ADR 0011, AGP-05 / CFG-07/15, M4/M5, requirements §9/§10/§11.2/§12
and US-07/08. Added member-readable, workspace/agent-scoped delivery list/detail
APIs with indexed keyset pagination (50 metadata rows) and a bounded retry history.
Owner-only review exposes the exact original target/configuration, selected rendered
message and payload digest with an explicit duplicate-delivery warning. Retry POST
requires a fresh exact review digest, request UUID and accept_duplicate_risk=true;
Origin/CSRF/session/role guards remain enforced. No editable payload, target or receipt
is accepted. A sent/active job cannot retry, and no endpoint fabricates success.

Migration 0015 adds immutable scoped consent, a consumption marker and a maximum of
three manual generations. Consent/audit are atomic and request-ID replay is idempotent
even after completion; a stale review cannot authorize a later generation. Only an
approved original-job transition can reset attempts; original release/grant/target
and selected values remain immutable. Temporary authority loss can pause a retry;
permanently revoked grants/targets cannot be replaced to revive old jobs. The worker
rechecks both original authority and the requester's current enabled owner membership.

The existing worker atomically consumes at most 32 indexed pending approvals, preserves
fair/rate-limited scheduling and fences subsequent attempts. Renderer/action/payload
drift after approval fails closed. Prior uncertainty remains in immutable review
history. Each round retains the existing five-attempt ceiling. No management request
performs HTTP, and approval is never reported as delivery. Rendering/projection moved
unchanged to shared pure contracts, so management imports no voice runtime. Management
gets SELECT plus immutable-id row-lock permission, not queue-state writes; the worker
cannot author consent. Provisioners reject unexpected existing state/consent privileges.

Linux initial management integration: **15 passed in 26.37s**. With indexed consumption,
nonretryable/inactive-state coverage and audit atomicity: **71 passed in 91.13s** across
management/delivery/grant suites. Expanded PostgreSQL/role/auth/records/runtime/managed-
startup/native loopback SIP regression: **296 passed in 270.87s**, no skips, one existing
audioop deprecation warning. Final role-hardening, distinct concurrent request and
renderer-drift checks: **24 passed in 25.94s**. Final Ruff source checks and nine-file
format check pass; changed-source diff and whitespace checks pass. Shared renderer
functions were also compared structurally with the previous implementation unchanged.

Both images built and passed network-disabled/read-only/capability-dropped imports;
management packages 0015 and was rebuilt after final role hardening. Combined Compose
validation passed. Source checksums and maintained-document mirrors are synchronized;
graph refreshed without persisted cache artifacts. Test data/transports are synthetic;
PostgreSQL and native SIP loopback are real Linux execution. No separate CTest rerun,
C++ rebuild, real Telegram/provider/CUDA/carrier send or performance acceptance is claimed.

Next: controlled real Telegram destination acceptance, matched voice/performance gates
and the reviewed existing-agent ownership/live migration. Frontend and general HTTP/MCP
actions remain later scope. No production migration, resident restart, ownership transfer,
second-number activation, Git push or merge occurred in this slice.

## 2026-10-25 — Scoped finalized-event delivery and uncertain-send recovery

Ponytail full; ADR 0011, AGP-05 / CFG-07/15, M4/M5, requirements §9/§10/§11.2/§12
and US-07/08. Migration 0014 adds immutable selected-field action jobs, original
release/grant composite FKs, workspace RLS, indexed due/expired work and separate
scheduler state. Summary completion, finalized event and up to four selected jobs
commit together; no historical backfill. Missing fields remain null. Later draft,
connection or grant changes cannot retarget already pinned calls.

The independent delivery_worker runs in its own Docker service using a dedicated
actions role. It cannot read call transcripts, provider keys, passwords or sessions,
nor author destinations/grants/jobs. Dispatch rechecks original grant, issuer enabled
owner membership, workspace and target; revocation pauses pending delivery. Rendering
selects only reviewed scalar fields in one plain-text bounded message, with explicit
ellipsis for clipping and link previews disabled. Networking pins vetted public DNS
addresses while retaining Telegram TLS hostname verification, disables proxies and
redirects, and bounds response/time budgets. No DB transaction spans HTTP.

Workspace round-robin selection/rate gates, fenced 30-second claims, five-attempt caps
and bounded recovery distinguish pre-send failures from uncertain external writes.
Sending is committed before the request. Complete 429 rejections/proven connection
failures can retry; wrong/malformed/oversized receipts, interrupted POSTs and stale
sending leases become delivery_unknown without automatic replay. Exact chat and
positive message receipt are required for sent. Grant replacement cannot resurrect
historical authority. Revocation cannot recall already-authorized in-flight requests.

The schema-v2 compile/preload staging gate is removed; compilation now requires its
exact workspace. Management requires migration 0014 and reports adapter capability
plus requires_delivery_worker, never a fabricated running-worker/delivery guarantee.
Existing v1 behavior/digests remain covered. Setup, read-only SQL diagnostics,
dependency inventory and performance isolation documentation were updated together.

Linux initial focused run: **52 passed, 1 failed in 63.19s**; the mock HTTP reply was
already consumed, unlike a live streaming response. The fixture now supplies a raw
stream; no production fallback was added. Revised focused run: **62 passed in 64.69s**.
Final expanded real-PostgreSQL/role/auth/records/delivery/runtime/managed-startup/native
SIP regression: **275 passed in 250.27s**, no skips, one existing audioop deprecation
warning. This includes two agents in the same/different workspaces, exact targets,
atomic fan-out rollback, grant/target/issuer/membership/workspace revocation, crash
fencing, shared cooldown/fairness, receipt/network boundaries and real delivery-process
SIGTERM/restart with a synthetic transport. No external request was sent by these tests.

Linux Ruff source checks and 13-file format check passed; changed-source diff review
and git diff --check passed. Both management/action-worker Docker images built and
passed network-disabled, read-only imports; migration 0014 is packaged. Combined
Compose validation passed. No C++ change/rebuild or separate CTest rerun. Source and
maintained-document mirror synchronization and graph refresh accompany this entry.

Next: owner-visible delivery outcomes and the explicitly reviewed reconciliation/retry
workflow for paused/failed/unknown jobs, then controlled real Telegram acceptance and
matched voice/PERF/live-migration gates. General HTTP/MCP actions remain future scope.
No resident restart, production migration, ownership transfer, second-number activation,
real provider/CUDA/Telegram/carrier acceptance, Git push or merge in this slice.

## 2026-10-25 — Reviewed agent action grants and immutable publication

Ponytail full; ADR 0011, AGP-05 / CFG-07/15, M4/M5, requirements §9/§10/§11.2/§12
and US-07/08. Drafts select up to four fixed Telegram actions with unique aliases,
workspace connection references and 23 allowlisted scalar output paths. Number
provenance and summary status accompany their dependent fields; unknown values use
explicit null. Empty lists preserve historical v1 digests. No caller/model-selected
trigger, credential, arbitrary path, transcript, URL or executable mapping is accepted.

Owner-only explicit consent requires the exact displayed review digest and draft
version. Reviews include agent/workspace, fixed chat/connection, adapter, event,
condition, missing policy and fields. Draft saves/publication never manufacture a
grant. Migration 0013 stores immutable scoped grants, irreversible revocation,
serialized idempotence and a 1000-grant lifetime cap per agent. Publication checks
live connection/grant/issuer account/owner membership and pins grant ID plus review
in schema-v2 manifests with same-agent/workspace FKs. Rollback must retain its original
grant; a new grant cannot resurrect revoked historical authority. Draft editing and
consent/publication use consistent draft-before-target lock order.

Deployment is deliberately gated: schema-v2 action releases validate for offline
publication, but compile/preload rejects them until scoped delivery is integrated.
The API reports delivery_available=false / post_call_delivery_pending. Existing v1
runtime behavior remains covered. No network send or action job was introduced.

Linux initial focused regression: **38 passed in 19.76s**. Expanded suites including
native SIP/RTP Session: **267 passed, 1 failed in 192.00s**, existing audioop warning.
The failure was a historical-schema fixture invoking today's publisher before 0013;
it now seeds a v1 release using historical SQL and verifies the upgraded grant remains
null. No production compatibility workaround was added. Final action/record/publication
rerun: **43 passed in 28.84s**, no skips. Linux Ruff check/30-file format check and full
diff review passed. Both final Docker images built, network-disabled/read-only imports
and combined Compose validation passed. Source checksums and the documentation mirror
were synchronized; graph refreshed without persisted artifacts.

Next: transactionally fan out finalized events to immutable action jobs; implement
bounded field projection/rendering, live dispatch revocation, leased/fenced attempts
and uncertain-send handling in the independent worker. Remove the v2 deployment gate
only with that consumer and acceptance evidence. No real Telegram/provider/CUDA/carrier
validation, latency benchmark, resident restart, ownership transfer, second-line
activation, push or merge in this slice.

## 2026-10-25 — Reconnected Linux and Telegram destination storage

Ponytail full; ADR 0011, AGP-05 / CFG-07/15, M4/M5, requirements §9/§10/§11.2/§12
and US-07/08. Closed the previous SSH interruption: all 29 source/configuration
checksums matched, the final summary-worker image was rebuilt and independently
imported, and the combined Compose configuration passed validation.

Migration 0012 and the owner-only telegram-connections API now store fixed bot/chat
pairs with workspace RLS, authenticated encryption and metadata-only responses.
Explicit credential purpose prevents provider/Telegram envelope substitution while
preserving old provider ciphertext compatibility. Tokens never enter manifests/audit.
Targets and ciphertext are immutable; revocation cannot be reversed. A serialized
100-connection lifetime cap bounds each workspace. Current management/voice/summary/
provider-reader roles cannot SELECT Telegram ciphertext. No Telegram execution reader
or external send grant is created. Readiness now requires both credential migrations,
fixing the previous healthy response when those required tables were absent.

Linux focused integration: **10 passed in 6.20s**. Expanded database/auth/provider/
summary/draft/release/routing/readiness/managed-process regression: **106 passed in
66.06s**, no skips. Ruff check and six-file format check passed; full changed-source
diff review and git diff --check passed. Both final Docker images built and passed
network-disabled/read-only import checks; management packages migration 0012. Compose
validation passed. Source checksum and documentation mirror synchronization completed.
No native media code or call-path IO was added; no latency/capacity measurement claimed.

Next: agent-specific action selection, reviewed output fields, explicit owner grants
and immutable release binding, then transactional finalized-event jobs and Telegram
delivery with uncertain-send handling. This is the credential/destination authoring
foundation, not completion of AGP-05. No Telegram request, real inference/carrier test,
live migration/restart, owner transfer, second-number activation, push or merge.

## 2026-10-25 — Scoped provider credentials and independent summary worker

Ponytail full; ADR 0011, AGP-02/03/05 / CFG-04/07/15, M1/M4/M5,
requirements §9/§10/§11.2/§12/§17.1 and US-07/08. Migration 0011 adds immutable,
workspace-RLS OpenRouter connections with authenticated encrypted credentials.
The external key file is separate from DB/images/source. Owner-only write/revoke API
returns metadata, never tokens/ciphertext. Management cannot SELECT ciphertext;
a separate read-only credentials role cannot read users/calls or mutate connections.

Drafts/releases select model_connection. Draft write/publication/rollback reject
foreign or revoked references; historical omission preserves canonical digests.
Managed startup rejects unbound releases and has no legacy key/client override.
Prepared runtimes bind the route's workspace. Bounded preflight/background refresh
loads at most 16 isolated clients; turns select in memory. Two-second monotonic
freshness bounds revocation, including subsequent turns; already-dispatched requests
are not recalled. Replacement requires a new connection/release, not in-place rotation.

The independent summary worker has its own pinned project, Docker image and opt-in
Compose service without HTTP/RPC/GPU. It consumes only scoped leased jobs and uses
historical release/credential/instructions. Each sequential job owns a client; crash/
cancellation leaves the claim for retry. Missing/revoked credentials or model failure
finalize failed/null summaries. Infrastructure errors retain leased work. Finalization
preserves confirmation evidence and does not deliver Telegram/webhooks. Build contexts
are explicitly allowlisted; management's key mount is a separate optional overlay.

Linux initial integration: **56 passed, 7 failed**, exposing use of a column-privilege
check for table-level DELETE in role provisioning. Corrected the privilege selector;
focused integration then **25 passed in 18.11s**. Expanded auth/draft/publication/runtime/
records/readiness/native regression: **250 passed in 191.43s**, no skips, existing
audioop warning only. Final review preserves still-fresh credentials during refresh,
prevents post-close client creation and verifies actual process revocation. Focused
final rerun: **38 passed in 28.11s**; additional refresh regression: **7 passed in 7.05s**.
**10/10 CTests passed in 3.82s**, existing native build. Management/worker images built;
network-disabled import checks proved independent entry points without voice RPCs in
the worker or agent imports in management. Final image refresh/sync status is recorded
in CALL_TEST_PLAN. No live schema, resident restart, external provider/Telegram request,
ownership migration, second-number activation, push or merge.

Next: configured tool/action grants and Telegram delivery from immutable finalized
events, then UI/remaining consumers, PERF-01–06 and real model/carrier acceptance before
controlled migration. This completes scoped model-key selection and summary-worker
wiring, not AGP-03/05 or the entire self-service application. Frontend, in-place key
rotation, general MCP/HTTP actions and real provider quota/quality remain pending.

## 2026-10-25 — AGP-03 explicit managed-node startup

Ponytail full; ADR 0011, AGP-03 / CFG-03/11/12/17, M1/M4/M5,
requirements §8/§9.1/§10/§11.2/§12/§17.1 and US-01/07. The existing voice app now
has an explicit loopback `alojan_agent.managed` entry point. Its bounded schema-v1
operator file selects 1–16 exact workspace/release pairs, installed assets and
distinct private ports. Separate routing/records/readiness credentials are mandatory.
No database-wide autoactivation, legacy DSN fallback or public activation endpoint.

Startup reserves an exclusive listener before receipt claims, checks routing access,
preloads/probes every target and refreshes the whole set before serving. Failed startup
withdraws owned receipts; restart obtains new consumer IDs. Stop closes admission and
completes bounded readiness cleanup before RPC leases/cache/channels/client teardown.
Existing scoped reconciliation runs every 30 seconds with a system-owned 600-second
recovery age, above the engine hard limit. No legacy summary/Telegram worker starts
here; scoped jobs remain durable for the separate worker. Deployment JSON/setup added.

Review/test found and fixed a cancellation race: the supervisor could cancel an
already-started graceful shutdown and interrupt receipt withdrawal. Stop now requests
cancellation once before waking the service; bounded readiness cleanup finishes
without another cancellation. Actual process tests cover restart, occupied-port
rejection before claims, failed target/credentials, preflight SIGTERM, scoped calls
and abandoned-call recovery.

Linux initial focused: **16 passed, 1 failed** (shutdown race); after fixing it:
**17 passed in 9.31s**. Expanded DB/RPC/legacy/native regression: **199 passed in
157.58s**, no skips. Final cleanup-order review and startup/readiness rerun:
**31 passed in 19.84s**. **10/10 CTests passed in 3.80s**, existing native build,
no C++ change. Ruff check/format passed for three affected Python files; documented
CLI/imports passed with only voice paths. Source/diff checks pass; graph refreshed
without shared artifacts. Remote docs use the ignored review mirror.

AGP-03 remains partial. Next implement agent-specific credential/tool/action consumers
and the separate scoped summary/delivery worker, then real model/PERF-01–06/carrier
acceptance and controlled migration. Tests use synthetic speech and an unused provider
key with real processes/DB/RPC; no agent credential isolation or API quality claimed.
Kübra ownership/live migration and second-number activation remain pending. No live
schema changes, resident restart, external delivery, Git push or merge.

## 2026-10-25 — AGP-03 node-local preload/readiness coordinator

Ponytail full, ADR 0011; AGP-03 / CFG-03/11/12/17, M1/M4/M5;
requirements §8/§9.1/§10/§11.2/§12/§17.1 and US-01/07. ReleaseReadiness now loads
an authoritative immutable release, retains its validated runtime/PCM cache pin,
checks local agent compatibility and record-writer access, probes actual ASR/TTS
ConfigureCall with temporary leases, and publishes an expiring readiness receipt.
No inference, asset generation or external notification occurs during preflight.

Normal AgentService can now issue ready_for_answer from this coordinator without a
test subclass. Initialization adds only an in-memory key/freshness check; admitted
calls keep their snapshot after readiness loss. Warm background refresh checks
health and workspace/model qualification without reloading assets or configuring
speech. A two-second local monotonic expiry is stricter than the ten-second DB TTL;
missed/failed refresh cannot keep local admission open. Stop withdraws owned receipts.

Additive migration 0010 adds consumer_id. Successor claims fence delayed old renewals
and withdrawals; this is bounded propagation, not strict instantaneous distributed
revocation. A dedicated readiness role has workspace RLS plus a restrictive node
policy and cannot mutate users/calls/bindings/model qualification. Existing management,
routing and record roles cannot update consumer IDs. No new dependency, service,
container, wire contract or native code. The legacy assistant_profiles.enabled field
is not repurposed as a managed deployment flag; workspace/model/number controls remain.

Linux focused coordinator/native test: **14 passed in 22.29s**. After warm-refresh,
capacity and scope-boundary additions, final publication/routing/runtime/scoped-record/
native regression: **181 passed in 153.28s**, no skips. **10/10 CTests passed in
3.82s** using the existing native build. Ruff check/format passed for seven Python
files. Independent app-api environment imports API/role provisioning without RPC
bindings. Mac/Linux source and diff checks pass; graph refreshed without a shared
artifact. Remote docs use the ignored review mirror to preserve independent edits.
See CALL_TEST_PLAN for commands and evidence limitations.

The coordinator is an internal deployment component, not a new public endpoint or
automatically attached production launcher. Next wire trusted deployment target/startup
lifecycle and remaining agent-specific credential/tool/action consumers, then validate
PERF-01–06 and real model/carrier behavior before migration. Legacy startup and live
Kübra remain unchanged; second-number activation, ownership migration and external
delivery remain pending. No live schema migration, resident restart, Git push or merge.

## 2026-10-25 — AGP-03 routed native Session conversation

Continued Ponytail full under ADR 0011, AGP-03 / CFG-05/06/08/09/10/11/12/17,
M1/M3/M4, requirements §7/§8.2/§9.3/§10/§11.2/§12/§17.1 and US-01/04/05/06/07.
The isolated native Session now connects prepared greeting to existing pinned
ASR/agent/TTS consumers for multiple turns, interruption, playback receipts and
farewell. Model/dependency failure plays the same release's prepared unavailable
clip. The explicit test option requires loopback, all three services and a bounded
capture mode; it cannot enable carrier traffic or combine legacy agent overrides.

Routed RunTurn now requires runtime/route/audio pins, a readiness permit and a
persisted answer, and rejects conflicting caller metadata. Ordinary InitializeCall
remains not-ready and the production entry point stays legacy. Greeting starts after
ACK without waiting for storage; conversational capture waits for both greeting and
answer persistence. No extra first-audio wait, per-turn config IO, RPC, inference,
model instance, media queue, dependency, DB schema or user engine knob is added.

Termination captures its timestamp and cancels media immediately. Setup retains
leases until speech workers finish generation invalidation/receipts. Main-loop
reaping distinguishes completed playout from completed worker cleanup; Session
lifetime destroys consumers before the setup owner. Routed EndCall waits for active
turn cleanup within its existing deadline before finalizing records/summary work.
Missing cleanup acknowledgements remain uncertain and require reconciliation.

Linux build passed. Final RPC/DB/native/legacy regression: **222 passed in 318.07s**,
no skips. **10/10 CTests passed in 3.83s**. Ruff check/format, clang-format and diff
checks passed. Review preserved immediate greeting after a regression exposed an
unnecessary storage wait; two old lifecycle fixtures now supply required TTS pins.
The suite verifies reclamation across 140 sequential calls. Exact commands and
initial failures are recorded in CALL_TEST_PLAN. Source matches Linux; independent
remote docs are preserved via the ignored review mirror. Graph refreshed without
shared artifact.
AGP-03 remains partial: next implement production preload/readiness coordination,
then remaining per-agent credential/general tool/action consumers. PERF-01–06,
real CUDA/API dialogue quality, historical pause-quality gate and carrier acceptance
remain open. The managed Session uses synthetic inference over real local SIP/RTP,
gRPC and PostgreSQL; CPU interruption uses actual native turn models. No live Kübra
restart/migration, second-number activation, external delivery, push or merge.

## 2026-10-25 — AGP-03 pinned speech output budgets

Continued Ponytail full under ADR 0011, AGP-03 / CFG-06/12, M1/M2/M4,
requirements §8.2/§9.3/§10/§11.2/§12/§17.1 and US-04/05/06. System-owned
EnginePreset now supports frozen OutputBudget for phrase characters/UTF-8 bytes,
phrase count and cumulative turn bytes. Historical omission preserves canonical
JSON/digests and frozen 240/1024/16/4096 defaults. New tuning requires an explicit
qualified preset/release; no user engine knobs or active-call mutation.

The shared existing phrase policy now serves publication, completed speech-tool
validation and AgentService streaming. Fixed recovery/closing and combined note
acknowledgements must fit before publication. InitializeCall sends the complete
nested schema-v1 budget; native admission rejects missing/invalid/old settings.
SpeechBridge checks character/byte/count/total limits before queueing text to TTS.
Four-byte Unicode scalars fit the byte budget; no encoded text splitting. The old
unconfigured native path retains byte-only admission. Existing cancellation, sent
playback accounting, queue bounds and TTS's independent 512-character ceiling remain.

The gateway envelope remains 256 bytes. No extra RPC/config IO, inference/model,
queue, dependency or applied DB migration. Optional agent_output.sql adds disabled
revision 3 with explicit calibration/output while preserving earlier examples.
Management imports/compiles independently without generated RPC bindings. Six
regenerated bindings reproduce byte-for-byte; upgrade managed agent/gateway/bindings
together because older peers omit the required output configuration.

Linux build passed. Configuration/publication/runtime/native setup suite: **253
passed in 198.74s**. Agent/TTS/protocol/SQL and legacy PCMA/PCMU dialogue: **132 passed
in 36.49s**, including two SQL cases repeated from the first group; **383 distinct
pytest cases**, no skips. **10/10 CTests passed in 3.82s**. Ruff check/format,
clang-format and diff checks passed. Exact commands and evidence limits are in
CALL_TEST_PLAN. Source matches Linux; independently edited remote documentation is
preserved using the ignored review mirror. Graph refreshed without shared artifact.

AGP-03 remains partial. Next complete routed Session conversation/readiness and
remaining per-agent credential/tool/action consumers. Ordinary InitializeCall stays
not-ready and routed RunTurn blocked. Synthetic inference over real local transport/
DB and legacy dialogue are not real CUDA/API, handset quality, latency/capacity/soak
or carrier qualification. PERF-01–06 and the historical pause-quality gate remain
open. Live Kübra, ownership, second-number activation and external delivery are
unchanged; no resident restart, live migration, push or merge.

## 2026-10-25 — AGP-03 pinned endpoint and interruption calibration

Continued Ponytail full under ADR 0011, AGP-03 / CFG-09/10, M1/M3/M4,
requirements §7/§10/§11.2/§12/§17.1 and US-04/05/06. Operator-owned EnginePreset
now supports frozen NativeCalibration for VAD, candidate/yes-no/open/uncertain/
incomplete waits, partial hinting, silent-caller reminder and interruption VAD/
onset/sustained-voice/quiet windows. InitializeCall sends the typed calibration in
its existing gateway configuration; native admission validates schema, bounds,
ordering and alignment before PCM/speech work. The bounded envelope grows from
128 to 256 bytes. Missing/old/invalid wire configuration cannot silently use defaults.

Managed SpeechBridge uses the pinned turn configuration instead of legacy caller/CLI
settings. TurnDetector consumes the reminder threshold and existing turn fields;
the speaking monitor/policy consume the separate interruption settings. Per-call
state, generation revocation, sent-audio accounting, echo rejection and bounded
queues/history remain. No new RPC, inference pass/model instance, callback IO or
per-turn configuration read. Fixed schema-v1 echo/lexical/score/stability/freshness
and resource rules remain platform algorithms, not new user controls.

Historical presets without calibration keep their canonical JSON/digests and frozen
historical behavior, including summaries of old calls. They are explicitly expanded
by the upgraded agent to complete wire configuration. New tuning is an explicit
immutable preset revision, never a mutation of defaults or active calls. Optional
agent_calibration.sql adds disabled revision 2 without changing agent_catalog.sql
or activating anything. No applied DB migration or new dependency. Management
compilation remains independent of RPC bindings; six generated bindings reproduce.

Linux build passed. Initial focused configuration/native probe tests: **41 passed in
9.35s** (two are repeated in the larger suite). Full setup/service/publication/runtime/
prepared-release regression: **169 passed in 181.41s**. Final historical compatibility
fixture/validation check: **39 passed in 0.13s**. **10/10 CTests passed in 3.82s**.
Legacy PCMA/PCMU dialogue, native CPU interruption and silence regression:
**6 passed in 157.70s**, no skips. There are 214 distinct pytest cases across the
final selections. Ruff, clang-format and diff checks passed.
Exact commands and evidence limits are in CALL_TEST_PLAN. Source matches Linux;
documentation is mirrored separately to preserve independent remote edits.

AGP-03 remains partial. Next connect remaining output/phrase budgets, then complete
routed Session conversation/readiness and remaining per-agent credential/tool/action
consumers. Ordinary InitializeCall stays not-ready and routed RunTurn blocked.
Synthetic protocol tests and legacy native CPU/SIP checks do not qualify actual
CUDA/ASR/TTS/API, handset quality or performance. The historical pause-quality gate
and PERF-01–06 remain open. No live restart, ownership migration, second-number
activation, external delivery, push or merge.

## 2026-10-25 — AGP-03 native call timing and turn budgets

Continued Ponytail full under ADR 0011, AGP-03 / CFG-05/08/17, M1/M4,
requirements §6–7/§10/§11.2/§12/§17.1 and US-01/05/07. InitializeCall derives
six timing/turn fields from the pinned release's operator-owned EnginePreset:
call duration, ringing delay, farewell pause, media drain, conversation turn count
and agent RPC deadline. The additive schema-v1 GatewayConfiguration is validated
within a 128-byte native envelope before speech leases/PCM. Missing, old-schema or
out-of-range values cannot answer or silently use legacy launch defaults.

Session pins an immutable copy. Ringing and delayed ACK consume the original call
budget; settings changes cannot retime an active call. Prepared fallback uses media
drain only. The farewell consumer derives closing plus drain from the same copy;
full routed conversational Session activation is still pending. Managed SpeechBridge
requires settings alongside its three service bindings, applies the configured
turn count, and caps agent RPC time by both preset and remaining call deadline.
Legacy CLI, default 16-turn/20-second bridge limits and farewell behavior remain.
Readiness-loss checks also prevent dereferencing missing settings/PCM during setup.

No new RPC, per-turn config lookup, dependency, DB migration, model instance, media
queue or callback IO. Independent management compilation remains free of generated
RPC dependencies. All six generated bindings reproduce byte-for-byte. Review covered
initialization/publication, setup/Session, bridge deadlines/cancellation and legacy
callers. Source changes match the Linux workspace; independent remote documents are
preserved via the ignored review mirror.

Linux build passed. Final focused SIP/RPC/DB suite: **90 passed in 147.25s**;
**10/10 CTests passed in 3.82s**. Runtime/publication/lifecycle/protocol/TTS and
legacy PCMA/PCMU dialogue regression: **118 passed in 45.86s**, with no skips. Initial focus
run had 86 passes and three scoped-lifecycle fixtures timing out at the now-effective
published three-second ringing delay; those fixtures now allow five seconds. No
runtime deadline was relaxed. Ruff, clang-format and diff checks passed. Exact final
commands/results and remaining evidence limits are recorded in CALL_TEST_PLAN.

AGP-03 remains partial: native endpoint/barge-in calibration and output/phrase
consumers, full routed Session conversation, readiness coordination and per-agent
secrets/general tool/action execution remain. Ordinary InitializeCall stays not-ready
and routed RunTurn blocked. Tests use synthetic inference over real local transport
and disposable databases, not real CUDA/API or carrier calls. PERF-01–06, ownership
migration and live rollout are pending. No resident worker restart, second-number
activation, external notification, push or merge occurred.

## 2026-10-25 — AGP-03 pinned TTS capability validation

Continued Ponytail full under ADR 0011, AGP-03 / CFG-12, M1/M2/M4,
requirements §8.2/§11.2/§12/§17.1 and US-01/03/07. Immutable runtime compilation
now binds the approved voice, model/revision and fixed PCM contract. InitializeCall
returns that profile; native setup requires Synthesis.ConfigureCall with the same
release/digest and its separate TTS lease before fetching PCM or becoming ready.
The new RPC shares the original 1.8-second setup budget; native schema/512-byte and
worker field validation reject unsupported configuration. Negative/lost acknowledgements,
old workers, timeouts and capability mismatch cannot answer or fall back to another voice.

EMA declares its capability only after verified offline weights and successful CUDA
graph warm-up. The service captures that frozen declaration at startup, pins one
release/profile per existing bounded lease, permits identical retries and rejects
changes. Managed synthesis always requires configuration; `--require-agent-release`
also rejects unconfigured legacy calls when explicitly enabled. Release/expiry clears
the pin and cancels generations. No model reload or per-phrase manifest/DB/HTTP read;
no new dependency or applied DB migration. Independent management compilation remains
free of RPC/generated bindings through lazy serialization at the agent boundary.

Review covered backend startup, runtime/publication, initialization, native setup,
stream/cancel/expiry and the independent management environment. Linux native build
passed. Focused service/initialization/native suite: **90 passed in 56.50s**; runtime,
publication/PCM/lifecycle/protocol/setup regression (including two additional malformed
native configuration cases): **148 passed in 79.19s**. Final profile helper regression:
**22 passed in 0.82s**; legacy PCMA/PCMU two-turn dialogue: **2 passed in 29.11s**.
**10/10 CTests passed in 3.77s**. No skips; only the existing audioop warning. The six
generated Python/C++ bindings reproduce byte-for-byte. Management imports and compiles
a synthetic agent in its own dependency environment without loading RPC bindings.
Ruff, clang-format and diff checks passed. Exact commands are in CALL_TEST_PLAN.

AGP-03/CFG-12 remain partial. TTS identity matching is implemented; remaining native
engine-preset consumers, full routed Session conversation and readiness coordination
are next. Normal InitializeCall stays not-ready and routed RunTurn remains blocked.
Tests use real local RPC/SIP/DB, synthetic model output, and explicitly mocked startup
checks; they do not qualify real CUDA inference, voice quality, performance or carrier
behavior. PERF-01–06, live ownership migration and rollout remain pending. Source and
bindings are synchronized; documentation is mirrored separately to preserve independent
Linux edits. No live restart, notification, second-number activation, push or merge.

## 2026-10-25 — AGP-03 native agent/TTS service lease handoff

Continued Ponytail full under ADR 0011, AGP-03, M1/M2/M4,
requirements §6–8.2/§11.2/§12/§17.1 and US-01/03/07. CallSetup now opens a
separate synthesis lease within the original 1.8-second setup deadline, before
prepared PCM or local readiness. The isolated profile accepts `--setup-test-tts-port`
only with its loopback setup agent profile. Immutable CallServiceBinding replaces
the ASR-only binding and carries exact worker/call/token authority to all consumers.
Agent setup/PCM and conversation channels target the same configured worker;
conversation, ASR and TTS retain their 16 KiB transport limits.

Managed SpeechBridge requires all three valid bindings. Every agent turn/playback
report, TTS phrase and service generation cancellation carries that service's lease;
foreign tokens cannot synthesize and failures cannot retry without authority. Only
CallSetup finalizes routed calls with answer/end witnesses; legacy finalization is
unchanged. TTS/ASR release each have a 250 ms cap. Answered cleanup totals at most
1.25 seconds, plus any already-running 500 ms answer report, off signaling/media
callbacks. Lost OpenCall tokens or release acknowledgements stay explicitly uncertain;
admission remains held until the worker finishes.

Review covered setup, bridge/monitor/finalization callers, limits and fixtures. A
separate bounded agent conversation channel preserves the former 16 KiB ceiling
instead of inheriting the larger prepared-PCM limit. Linux build passed; focused
service handoff suite **23 passed in 37.57s**, existing setup/TTS/ASR/PCM/lifecycle/
protocol regression **125 passed in 61.41s**, isolated CLI guards **2 passed in 0.81s**,
and **10/10 CTests passed in 3.77s**. Legacy PCMA/PCMU dialogue, native CPU interruption
and speech regression: **24 passed in 219.10s**. Total: 174 pytest cases plus 10 CTests.
No skips; existing audioop deprecation warning only. Initial focused runs exposed incorrect cancellation expectations in the new
test fixture; assertions were corrected to include existing per-turn invalidation.
Ruff, clang-format and git diff --check passed. Detailed commands and evidence limits
are recorded in CALL_TEST_PLAN. Sources are synchronized to Linux; documentation is
mirrored separately to preserve independent server documentation. No wire change,
new dependency, per-turn lookup, media queue, inference pass or model instance.

AGP-03 remains partial. Next validate the loaded TTS voice/model against the pinned
release, connect remaining native engine-preset consumers and assemble the routed
Session conversation lifecycle/readiness coordinator. A TTS lease is transport
authority, not model readiness. Ordinary InitializeCall remains not-ready and routed
RunTurn stays blocked. The isolated SIP setup still plays prepared clips only.
No live worker restart, ownership migration, second-number enablement, external
notification, GPU/carrier qualification, push or merge occurred. PERF-01–06 stay open.

## 2026-10-25 — AGP-03 native recognition configuration handoff

Continued Ponytail full under ADR 0011, AGP-03 / CFG-11, M1/M2/M4,
requirements §6–8.1/§11.2/§12/§17.1 and US-01/03/07. The isolated loopback
setup profile accepts `--setup-test-asr-port` only with `--setup-test-agent-port`.
CallSetup opens a separate ASR lease and forwards the exact initialized release,
digest and recognition configuration before fetching prepared PCM or becoming ready.
Open/configure use the original 1.8-second setup deadline, including prior agent IO;
there is no per-service reset. Unsupported configuration, negative acknowledgement,
old/unavailable worker and deadline failure cannot answer or start audio.

SIP cancellation also cancels pending ASR open/configure without network work in
callbacks. The worker releases ASR with a 250 ms cap before agent cleanup; completion
requires acknowledgements from both. Lost ASR OpenCall tokens or release replies
remain explicitly uncertain, with expiry/reconciliation required. The admission slot
stays held through cleanup. An immutable worker/call/lease binding is available only
after successful setup. SpeechBridge uses that exact bounded 16 KiB channel/lease
for normal turns, interruption monitoring and ASR generation cancellation. It rejects
a binding for another call. Legacy construction remains compatible.

Real local SIP tests exercise two separate agent vocabularies and leases, failures,
shared setup budget, CANCEL and uncertain cleanup. A native probe uses the production
CallSetup/SpeechBridge and real strict RecognitionService across two conversation turns
and interruption monitors, verifying recognized spellings and successful monitor
cancellation for two dictionaries. Only ASR protocol/lifecycle is real: agent, speech
inference, TTS and probe turn detection are explicitly scripted. The setup SIP profile
still plays prepared greeting/unavailable; it does not start routed conversation.

Linux native build passed. Final focused suite: **14 passed in 23.63s**. Existing
setup/ASR/PCM/lifecycle/protocol regression: **102 passed in 60.81s**. Legacy
PCMA/PCMU dialogue, real native CPU interruption and speech tests: **24 passed in
219.24s**. **10/10 CTests passed in 3.82s**. No skips; existing audioop deprecation
warnings only. Ruff/clang-format and git diff --check passed. Earlier focused suites
passed 11 tests in 18.18s and 13 in 22.56s before the lost-open case was added.
Exact commands and evidence limits are recorded in CALL_TEST_PLAN.
Independent Linux endpoint diagnostics/partial-hint code and turn-detector dependencies
were preserved and brought into the Mac checkout. No generated protocol change was
needed. Source/tests are synchronized; maintained documents are mirrored in the ignored
review directory without overwriting independent Linux documentation.

AGP-03/CFG-11 remain partial pending full routed Session conversation integration,
agent/TTS lease handoff, remaining native preset consumers, readiness coordination
and measured quality/performance gates. Ordinary InitializeCall stays not-ready and
routed RunTurn remains blocked. Next bind the remaining native runtime/agent/TTS
consumers and assemble the routed conversation lifecycle. No live worker restart,
carrier/provider/GPU qualification, ownership transfer, notification, second-number
enablement, push or merge occurred.

## 2026-10-25 — AGP-03 pinned recognition vocabulary

Continued Ponytail full under ADR 0011, AGP-03 / CFG-11, M2/M4,
requirements §8.1/§11.2/§12/§17.1 and US-01/07. Agent drafts accept bounded
`asr_replacements`; validation is shared by authoring and the speech worker.
The immutable runtime copies aliases, and business `vocabulary` now appears in
prompt context without enabling unqualified decoder hotwords. Existing JSON
storage supports the additive optional field; no applied migration was changed.

InitializeCall returns typed schema-version-1 recognition configuration from the
pinned release. New private Recognition.ConfigureCall requires an explicit deadline,
exact live ASR lease and bounded call/release/digest/configuration. Repeated identical
configuration is accepted; a different release/digest/alias set or first configuration
after recognition starts is rejected. Release/expiry clears the pin and cancels
active generations. Strict `--require-agent-release` mode rejects unconfigured
streams; default legacy behavior remains available. The private gateway remains
the authority for release selection; ASR does not authenticate end users or verify
DB ownership independently. Never expose this loopback endpoint publicly.

Whisper and optional Nemotron accept per-decode spelling options without model
reload, global mutation, decoder algorithm changes or extra inference jobs. Empty
agent aliases override legacy defaults. Numeric/single-word replacement is rejected;
case-equivalent ambiguous aliases also fail. The Linux-only partial-hint optimization
was brought into the Mac copy and preserved; repeated-hint budget regression added.
Both generated bindings were regenerated and the native build passed.

Primary Linux evidence: **150 passed in 25.67s** (ASR, new configuration boundary,
draft/release/runtime/initialization/preload/lifecycle plus NumPy-only Nemotron adapter
checks); **52 passed in 78.22s** (native protocol, real local prepared SIP and
PCMA/PCMU two-turn regression); **10/10 CTests passed in 3.81s**. No skips. Existing
audioop deprecation warnings only. Ruff check/format passed on all 17 affected Python
files. Earlier focused selections passed 108 tests in 20.49s and 58 in 9.86s.
One initial regression command named a nonexistent test_speech_bridge.py and
collected no tests; the corrected protocol/SIP selection above passed. See the call
log for exact commands. Synthetic inference is not CUDA/model/voice-quality evidence.

AGP-03/CFG-11 remain partial: native setup/turn/interrupt orchestration must forward
this configuration and acknowledge readiness before strict-worker/routed activation.
Ordinary InitializeCall remains ready_for_answer=false; routed RunTurn is blocked.
Next implement native speech/runtime configuration handoff, preserving cancellation
and setup deadlines, then remaining native calibration and readiness/performance gates.
No live restart/migration, carrier/provider/Telegram acceptance, ownership transfer,
second-number enablement, push or merge occurred. Independent remote source was
preserved; maintained documents are mirrored under the ignored review directory.

## 2026-10-25 — AGP-03 native answered/end persistence and scoped recovery

Continued Ponytail full, ADR 0011, AGP-03 with AGP-05 dependency, M1/M4/M5,
requirements §6–7/§9.4/§10–12/§15–16 and US-01/03/05/07. The isolated native
profile now captures SIP CONFIRMED/ACK and termination timestamps, and reports them
through the existing per-call worker. New additive ReportCallAnswered and CallEnd
fields preserve legacy field numbers/behavior. Exact live lease, release/digest,
internal answer permit, clock window and call-state checks fence every scoped write.
Setup cancellation after a recorded answer is rejected without dropping the call pin.

Prepared media starts after ACK without waiting for persistence; signaling/media
callbacks perform no DB/model/HTTP work. Answer/end RPCs each have a 500 ms deadline;
release has 250 ms. End repeats the original ACK witness and repairs a missing answer
write atomically with completion/enqueue. Retries do not duplicate jobs or change the
original answer timestamp. Unanswered calls never enqueue summaries. Playback stops
immediately on hangup while bounded cleanup retains its admission slot.

Reconciliation now dispatches by runtime mode. Legacy recovery touches only unscoped
rows. Routed recovery discovers at most 16 old calls for its own node using admission
credentials, then rechecks each original scoped call under the records role/row lock.
It closes abandoned initialization without a summary; answered missing-end calls get
one summary job, explicit failure metadata and unknown duration. Existing role setup
adds bounded directory-time reads and failure/event writes; no new superuser worker.
The existing optional 30-second maintenance loop remains disabled by default.

Linux full native build passed. Main Python/DB/SIP selection: **163 passed in 93.70s**,
no skips. Follow-up lifecycle/rollback selection: **6 passed in 11.70s**. Existing
SIP plus PCMA/PCMU two-turn regression: **44 passed in 144.76s**. **10/10 CTests passed
in 3.80s**. Existing audioop deprecation warning remains. Ruff/clang-format passed;
C++/Python bindings reproduced byte-for-byte. Earlier focused selections: 57 passed
in 64.33s and three actual SIP/DB write-loss cases passed in 7.52s. See CALL_TEST_PLAN
for final commands; the final non-silent delayed-persistence audio check passed
1 test in 2.51s.

The actual PostgreSQL/role/lifecycle repository participates in real local SIP tests;
positive readiness and PCM/model behavior are scripted. Ordinary AgentService still
returns ready_for_answer=false, grants no answer permit and blocks routed RunTurn.
No production routed activation, provider/CUDA/carrier/performance acceptance,
notification, live migration, ownership transfer or second-number enablement occurred.
Source/bindings/tests were synchronized to Linux; maintained docs are mirrored in the
ignored review directory, preserving independent remote edits. No push or merge.

AGP-03 remains partial. Next connect the remaining native conversation and speech
runtime consumers to the pinned release, then readiness coordination and measured
non-regression gates. AGP-05 independent worker/action configuration/fan-out/delivery,
frontend and live migration remain separate work. Reprovision private worker roles
and synchronize host clocks before any future activation; missing both answer/end
reports remains unknown, never an inferred answered call.

## 2026-10-25 — AGP-03 scoped records and AGP-05 finalization foundation

Continued Ponytail full under ADR 0011, AGP-03/AGP-05, M1/M4/M5,
requirements §9.4/§10–12/§15–16 and US-03/05/07. CallRecords binds each write to
its exact immutable route, requires answered/active state, preserves actual sent-audio
accounting and rejects conflicting retries. Call completion and summary enqueue are
atomic. Forced RLS covers calls and child tables; records and summaries use separate
restricted roles. Management/admission roles cannot acquire conversation-write access.

The existing queue now pins scope/release and leases each job with a fencing token.
A second worker cannot claim an unexpired job or finish a replaced claim. Summary
input/model/prompt use the original release after draft changes or number deactivation.
Summary, immutable bounded call.finalized.v1 event and completion commit together.
Model/output failures produce explicit null summary; confirmation is derived from
the saved note. Cancellation leaves a recoverable lease. Legacy polling excludes
scoped jobs and the legacy global notification outbox rejects routed call inserts.
No new dependency, broker, HTTP endpoint, model or runtime activation was added.

Primary Linux final regression: **178 passed in 65.45 seconds**, no skips, covering
new ownership/lease/finalization/upgrade cases plus routing, auth, drafts, releases,
profile settings, initialization, lifecycle and existing agent/database behavior.
Ruff lint/format passed. The first focused run had 31 passes and one failure: clearing
job ownership was silently restored by the trigger. Moved immutable-update validation
before ownership derivation; the final suite verifies rejection. Intermediate expanded
selection: 114 passed in 38.98 seconds. See CALL_TEST_PLAN for reproduction.

This is private repository and one-job worker evidence with scripted model output,
not a deployed summary/action service. Native ACK/EndCall/recovery still must use these
consumers; ordinary startup remains legacy-only, ready_for_answer remains false, and
routed RunTurn remains blocked. AGP-03 and AGP-05 remain partial. Independent worker
lifecycle, bounded infrastructure retry/dead-letter policy, configured action fan-out,
Telegram/HTTP delivery, custom extraction and record-access UI/API remain pending.
Next integrate native answered/end/recovery persistence before readiness production.

Source and tests were synchronized to the authorized Linux development checkout;
independent remote documentation is preserved through the ignored review mirror.
Migration ran only in disposable test schemas. No live migration/deployment, ownership
transfer, external notification or second-number activation. Forced RLS requires a
legacy-role audit and coordinated worker upgrade before live migration. No new GPU,
carrier or measured end-to-end performance acceptance is claimed.

## 2026-10-25 — AGP-03 isolated native setup/answer lifecycle

Continued Ponytail full, ADR 0011, AGP-03 with the AGP-06 asset dependency,
M1/M2/M4/M5, requirements §5–7/§10–12/§15–16 and US-01/03/05/07. Native Session
now exercises the complete private setup sequence in an explicit loopback-only
test profile. The existing DID parser selects only the trusted configured field;
malformed/untrusted destinations fail before RPC. A bounded worker opens the lease,
initializes the release and retrieves exact PCM under one 1.8-second deadline.
Only positive readiness and valid complete clips allow answer after ringing;
playback still waits for ACK. Failures return 503 without legacy identity/audio.

Cancellation stops pending RPCs and playback. Cleanup sends CancelCallSetup then
ReleaseCall off the signaling thread, with 250 ms per operation. The session keeps
its admission slot until cleanup finishes, preventing unbounded workers under
rapid cancel/retry. Unconfirmed cleanup is reported explicitly; lost lease replies
and uncertain DB cleanup still require server expiry/reconciliation. No new service,
dependency or protocol change. The remote main.cpp partial-hint option was preserved
and brought into the Mac copy; other independent Linux native changes were untouched.

Linux native build passed. Final setup/initialization/PCM transport selection:
**54 passed in 45.89 seconds**, no skips. Existing SIP and two-turn PCMA/PCMU
regression: **44 passed in 144.96 seconds**. **10/10 CTests passed in 3.78 seconds**.
Python suites report the existing audioop deprecation warning. Ruff/clang-format
checks passed. Review corrected two test fixture issues: a socket timeout equal
to the three-second ringing delay, and preparation-delay injection also affecting
cleanup RPCs. Final tests distinguish total preparation timeout from uncertain
cleanup acknowledgement. See CALL_TEST_PLAN for commands and evidence boundaries.

The real agent/cache/router/PostgreSQL test rejects answer, closes the initializing
record, releases pins/leases and creates no summary/outbox work. Positive readiness
in the isolated SIP profile is scripted only. That profile plays greeting/unavailable
PCM; it has no conversational turns or answered-call persistence and cannot bind
to a carrier address. The ordinary agent remains not-ready and rejects routed RunTurn.
AGP-03 remains partial. Next implement scoped call records/finalization and remaining
native/speech runtime consumers before readiness production and routed activation.
No live deployment, migration, ownership transfer, notification or second-DID activation.

## 2026-10-25 — AGP-03 private prepared-audio transport and native playback

Continued Ponytail full under ADR 0011, AGP-03/AGP-06 dependency, M1/M2/M4/M5,
requirements §5–7/§10–12/§15–16 and US-01/05/07. Added private GetPreparedAudio
for the exact live lease and initialized release/digest. It returns only already
verified, pinned PCM; no DB, asset file or inference work runs in this operation.
Cancellation/release removes access. The native setup-worker client has a bounded
reply, the existing absolute setup deadline (at most 1.8 seconds) and cancellation.
It rejects identity mismatches, malformed/oversized PCM, bad lead-in and silent clips
before constructing an immutable playback bundle.

PreparedPlayback owns a per-call cursor and cancellation flag. Its 20 ms render
callback does no allocation, IO or locking. The existing PJMEDIA output adapter
is shared through a small template, retaining its buffer and teardown behavior.
PreparedOutput is exercised through actual PJSIP conference ports; native Session
does not yet select it during INVITE. This is a complete tested transport/playback
component, not completed routed call orchestration or readiness production.

Linux full native build passed. Broad regression: **274 Python tests passed in
41.05 seconds**. Final size-boundary follow-up: **18 passed in 1.13 seconds**.
All **10 CTests passed in 3.87 seconds** after the full build. Existing scripted
PCMA/PCMU SIP/RTP dialogue tests: **2 passed in 29.07 seconds**, with the existing
audioop deprecation warning. Generated C++/Python bindings reproduced byte-for-byte.
Ruff and clang-format passed using the pinned uv environment. An initial formatter
invocation outside that environment was unavailable; the corrected check passed.
See CALL_TEST_PLAN for exact scope and reproduction.

AGP-03 remains partial: readiness coordinator, native INVITE/answer/CANCEL wiring,
scoped storage/action consumers and measured voice non-regression gates remain.
ready_for_answer remains false; normal startup stays legacy-only and routed RunTurn
remains blocked. No live deployment, ownership migration, notification or second-DID
activation. Independent Linux native edits were preserved, and maintained documents
are mirrored under the ignored review directory instead of overwriting remote docs.
Next implement the native initialization/answer lifecycle using this playback boundary.

## 2026-10-25 — AGP-03 prepared audio preload and call pinning

Continued Ponytail full, ADR 0011, AGP-03 with the AGP-06 asset dependency,
M1/M2/M4/M5, requirements §5–7/§10–12/§15–16 and US-01/05/07. Added a bounded
workspace/release/digest cache containing immutable compiled runtime and verified
PCM for greeting and unavailable speech. All file reads, WAV decoding and prompt
compilation run before admission on worker threads. InitializeCall only pins an
existing exact cache entry; a valid readiness row alone cannot bypass a cold cache.
Missing preload fails closed and never selects legacy identity/audio. The current
API remains private dependency injection; no production preload/ready producer is
wired into the normal entry point.

Directory-descriptor traversal rejects workspace/pack/file symlinks, FIFOs and
non-regular or oversized files. Installed manifests must match the release, and
PCM hashes, format, frame count, lead-in and non-silence are rechecked. Shared WAV
validation now checks complete RIFF/chunk lengths as the native validator does,
returns decoded PCM and avoids allocating a full list of sample integers. Matching
hashes cannot conceal an incomplete container. No new decoder/dependency is added.

Defaults: 16 entries, 16 MiB accounted payload, two concurrent loads, no queued
third load. Duplicate loads share one task; cancelling a waiter does not free a
still-running worker slot. LRU eviction excludes pinned calls. Capacity/validation
failure preserves existing entries; shutdown prevents late installation. Calls
share immutable bytes only within the same workspace/release identity. Repeated
initialization adds no second pin. Setup cancellation and lease release/expiry
unpin idempotently; active references remain valid despite on-disk changes.

Linux focused validation: **47 passed in 15.13 seconds**. Expanded regression:
**272 passed in 48.25 seconds**, no skips, including synthetic packs, filesystem
attacks, concurrent cancellation/shutdown, real DB/loopback setup and legacy speech
fixtures. Final distinct-PCM fixture review passed 32 tests in 6.41 seconds; Ruff
check/format passed for six files. Separate management image/HTTP validation passed with disposable schema
and restricted role. Explicit synthetic benchmark: application-cold preload P95
1.0922 ms (warm OS cache, 30 samples); warm pin/unpin P95 0.0029 ms (10,000 samples).
These are small synthetic assets, not maximum-duration, GPU, voice-latency or
matched-baseline evidence. See CALL_TEST_PLAN and the performance plan.

AGP-03 remains partial. Native gateway PCM consumption, node readiness heartbeat,
INVITE/answer integration, scoped record/action workers and full voice acceptance
are still required. ready_for_answer stays false and routed RunTurn stays blocked;
there is no flag to turn this slice into live activation. No live migrations,
service restart, ownership transfer, EMA generation, carrier call or notification.
The second number remains disabled. Next connect the verified prepared data to the
native playback/initialization boundary before enabling readiness acknowledgements.

## 2026-10-25 — AGP-03 call-local Python consumers

Continued Ponytail full under ADR 0011, mapped to M1/M4/M5, requirements
§7/§10–12/§15–16 and US-01/03/05/07/08. Added a shared, IO-free compiler for
immutable releases: identity, business instructions, resolved speech, selected note
tool/alias/guidance, summary style and the operator-owned engine preset. Preparation
and publication run the same compiler. Individually valid speech that cannot fit
combined acknowledgement/invitation/closing bounds is rejected before preparation.
A keyword-only runtime field preserves the existing Call constructor contract.

Private initialization now constructs the call-local runtime. Backend model clients,
settings and SDK tools are per-call objects over the shared transport, without
mutating process globals or querying management/DB for settings on each turn.
Unselected note tools are absent from the SDK list and rejected by local state;
instructions cannot enable them. Configured clarification, silence, goodbye,
callback repair, acknowledgement and further-help behavior use the pinned release.
Delivered audio receipts recognize custom multi-phrase invitations; truncated speech
does not complete them. History, output, call-turn and model-step budgets use the
preset. Post-call summary input loads the historical route release, not the current
draft or number binding. Hidden/missing/corrupt releases fail closed; a dedicated
least-privilege summary worker is still a rollout gate.

Legacy entry-point behavior remains explicit in legacy.py, with the original main
and summary instructions preserved. It is only for existing non-routed calls and
rollback, never an unknown-DID fallback. Remove the adapter after migration and
rollback-window acceptance. Intent dictionaries, fixed schema/transport ceilings,
AI disclosure and permission checks remain platform policy.

Review found reused scripted tool IDs in two new tests; unique IDs restored the
intended rejection/retry scenario. Combined speech validation then exposed a
multi-sentence invitation fixture incompatible with the note-enabled preset;
the receipt-only fixture now selects no note tool. One broad invocation collected
nothing because of a missing remote test and a nonexistent filename; corrected
before the final run. Final primary-Linux regression: **289 passed in 50.28 seconds**,
no skips. The independent management image passed real HTTP checks with a restricted
DB role and disposable schema. The final legacy-compatibility follow-up passed
135 tests in 5.84 seconds; Ruff check/format passed for 12 files. See CALL_TEST_PLAN.

AGP-03 remains **partial**. ready_for_answer remains false, routed RunTurn stays
blocked and the ordinary entry point has no router. Next: prepared audio preload,
readiness producer, native INVITE/answer/CANCEL and scoped storage/action consumers,
then actual voice-quality/latency non-regression gates. ASR vocabulary, native
calibration, arbitrary tools/MCP and post-call Telegram/webhook configuration are
not completed by this slice. No live schema/image/source activation, ownership
transfer, external notification or second-number activation occurred.

## 2026-10-25 — AGP-03 private setup RPC and called-number boundary

Continued Ponytail full under ADR 0011, mapped to M1/M4/M5, requirements
§10–12/§15–16 and US-01/03/05/07/08. Added versioned `InitializeCall` and
`CancelCallSetup` RPCs with the existing managed-call lease, explicit deadline,
1.8-second setup budget, serialized per-call initialization, immutable route pinning
and cancellation. Repeated successful setup returns the pinned release; concurrent
in-flight setup is retryable ABORTED. No manifest, credential or phone number is
returned in the reply. Missing/forged/duplicate leases, invalid identity metadata,
ended calls and conflicting routing fail closed.

The native PJSIP called-number parser checks the transport peer against the explicit
allowlist and reads exactly the configured Request-URI or To field. It accepts only
Netgsm 0850 SIP telephone users, with optional explicit Turkish prefix conversion.
Missing/duplicate To, other number ranges, URI passwords/headers, invalid selection
and untrusted peers are rejected. From/PAI/Diversion cannot choose an agent. The
parser is tested with actual PJSIP message parsing, but not yet invoked by the native
INVITE/answer state machine. No carrier field/source policy has been activated.

Reconciled the development agent, shared generation control and protobuf with the
preserved deployed lifecycle source: retain partial_hint field 9, OpenCall/ReleaseCall,
lease expiry, sent-speech acknowledgement and grounded-dialogue repairs. Reviewed
source backups precede targeted Linux copies; no broad synchronization or live
release overwrite. Existing read-only snapshot files are absent from the code graph,
so exact source comparisons were used for that baseline. Reconciliation now ends
abandoned initializing calls without summary/notification work; stale active legacy
calls retain their existing post-call recovery. Release/CANCEL/deadline discard late
setup results. A DB commit whose release response is lost can remain initializing
until the configured reconciliation window; it never authorizes answering.

Review found an initial C++ fixture type mismatch and older Linux model/test fixtures
that predated the deployed acknowledgement/lease contract. Corrected the fixture,
restored the matching deployed model/backend and test expectations, and retained
both prior versions in ignored backups. Final Linux validation: **208 passed in
29.16 seconds**, no skips; includes real loopback RPC, disposable PostgreSQL schemas,
140 sequential managed calls and >4096 cancelled generations per worker. Native
caller-identity CTest passed (360 parser checks); the full native gateway and
contract probe compiled, and cross-language transport tests passed. All six generated
binding files reproduced identical digests. Ruff check/format (14 files) and clang-format passed. These are scripted
inference/local protocol checks, not real GPU/model/carrier acceptance.

AGP-03 remains **partial**. The RPC is disabled in the normal legacy entry point;
in an injected routing service it returns `ready_for_answer=false`, and routed
RunTurn is explicitly rejected until all consumers are connected. No operational
switch bypasses this guard. Next: call-local prompt/model/tool/audio consumers,
qualified node preload, then native INVITE initialization/answer/CANCEL integration
and matched voice/performance gates. This step adds no live migration, target-account
transfer, Telegram send, carrier call or second-number activation.

## 2026-10-25 — AGP-03 number binding and admission repository

Continued the next implementation step under Ponytail full, mapped to M1/M4/M5,
requirements §1/§6/§10/§12/§14–16 and US-01/03/07/08. Added migration 0008 without
rewriting prior migrations: pending number claims, immutable operator verification
records, immutable release bindings, bounded node-readiness acknowledgements and
immutable call routing snapshots. Added scoped owner list/register/bind/deactivate
HTTP endpoints and private evidence-recording/revocation commands. Native carrier
verification is a separate event, not an effect of these commands or tests.

The new async `CallRouter` resolves a verified canonical DID, serializes with binding
changes and persists a frozen release pointer before returning configuration.
Same-call retries are idempotent; conflicting initialization, unknown/disabled DID,
wrong node, stale readiness or revoked model fail closed. Pending claims cannot
reserve global ownership. Transfer/re-verification requires draining all prior DID
calls; historical records are not reassigned. Cancellation before/after initialization
leaves no summary/notification job. Existing unscoped calls cannot be auto-claimed.

Management and private routing roles are separate and tested without superuser/RLS
bypass. Only the private routing role reads the minimal cross-workspace directory;
it sets scope for release reads. Users cannot verify numbers, forge readiness or
choose a deployment host. Node heartbeat duration is enforced against the original
acknowledgement time, not just a future expiry. Number identity, snapshot digest,
workspace and binding relationships have database constraints.

Review 1: 12 test bodies passed; teardown exposed an incorrect psycopg Identifier
attribute. Fixed cleanup and removed exactly two unreferenced synthetic test roles.
Review 2 expanded cross-workspace FK tests, real separate-session races, admission
vs rebind interleaving, bounded lock failure, task cancellation and readiness limits.
Linux suite: **80 passed in 36.11 seconds**, no skips, one existing Starlette test-client
deprecation warning. Ruff and actual isolated-image HTTP checks passed. The separate
50-sample restricted-role admission measurement observed P50 28.50 ms / P95 38.07 ms,
including new DB connections. It is not native/voice non-regression acceptance.
Image, cleanup and measurement evidence is in CALL_TEST_PLAN.

AGP-03 is **partial**: the repository is not yet wired into native `InitializeCall`,
PJSIP DID extraction, node preload, live prompt/settings/assets or answer lifecycle.
Readiness has no enabled producer, so no production number can be activated through
this foundation alone. Reconcile abandoned initializing calls when wiring lifecycle.
Next implement those consumers against the preserved deployed lifecycle release,
then complete CFG/voice/performance tests. No live schema/source/image activation,
account transfer, carrier call or Telegram send occurred. Existing Kübra stays on
its prior release; second-number configuration remains disabled as instructed.

## 2026-10-25 — AGP-02/06 prepared releases and email login

Continued the approved plan with Ponytail full. Mapped to M0/M5, requirements
§1/§12/§14–16, US-01/07/08, ADR 0011 and AGP-02/06. Additive migrations 0006/0007
provide immutable engine/model definitions, scoped preparation/asset/release records,
a current publication pointer, and backward-compatible ASCII email login identifiers.
No earlier migration checksum changed. Public registration remains independent;
an email match never grants ownership of an existing agent/workspace.

Implemented preparation, qualified model listing, owner publication and rollback
HTTP endpoints with separate draft/publication preconditions. Publishing pins the
business configuration, selected model/preset and verified audio manifest atomically.
Rollback creates history rather than overwriting it. A stale draft, missing audio,
revoked model or mismatched account/profile fails closed. Mandatory AI greeting
identity is preserved. Technical settings remain outside the editable draft.

The trusted asset import command verifies hashes/text/model provenance metadata,
PCM format/frame alignment, duration/closing room, greeting pad and non-silent
content, then installs immutable workspace-specific files atomically before marking
ready. It does not synthesize speech. Automatic resident-EMA generation still needs
the drained-window handshake and listening/quality acceptance; synthetic WAV tests
are not inference evidence. A repeatable disabled catalog SQL example is included.

Provisioned/tested dedicated management role grants in disposable schemas. The role
can author and publish but cannot qualify models, insert ready-asset records, enable
profiles, elevate memberships or read live call tables. Compose now uses an internal
management bridge with host-loopback HTTP publication, with bounded CPU/RAM/processes.
Its PostgreSQL network addition requires coordinated rollout, not an immediate live
Compose apply. Docker build context excludes private data and unrelated artifacts.

Review corrected the initial validator's transient connection-reset handling and
added real separate-session publication races, workspace asset isolation, restricted
role end-to-end tests and greeting/closing-duration checks. See
[management implementation](../services/app-api/README.md) and
[acceptance evidence](CALL_TEST_PLAN.md). Linux: **64 passed in 23.01 seconds**, no
skips; one pinned Starlette test-client deprecation warning. Ruff lint/format,
Compose structural validation, image build and real restricted-role bridge-network
HTTP smoke passed. No new dependency was added.

Still pending: AGP-03 live snapshot consumers/DID routing and complete CFG-01–18,
secret storage/configured tool and action execution, automatic audio synthesis,
builder UI, MCP/HTTP, PERF-01–06 and live migration. Production catalog remains
unqualified, existing voice services/schema remain unchanged, and second number/
Telegram binding remains disabled. Transfer to the owner's specified email account
is a live-migration task, not completed by enabling email login. Preserve existing
live lifecycle enhancements when integrating consumers; the release snapshot remains
the authoritative baseline, not the older top-level checkout.

## 2026-10-25 — AGP-02 native authentication and scoped authoring

Owner authorizes implementation with Ponytail full, stepwise review and eventual
tested Linux live migration. Follow-ups explicitly select native authentication
and public registration: every account gets its own workspace/owner membership
and may create/publish its own agents, subject to runtime readiness and verified
number binding. No separate operator publication approval or per-user container.
The second number/Telegram configuration is not ready; its binding must stay disabled.

Implemented additive 0004/0005 migrations, native account/session/password recovery,
atomic public registration, role checks, draft RLS, strict business configuration,
scoped create/read/update/preview with ETags and safe identity placeholders. Added
an independent management application/image/Compose service with resource limits.
No engine tuning input is accepted. Tests cover separate registered owners,
concurrent draft updates, non-owner PostgreSQL RLS, forged scope/role/headers,
session/password revocation, expiry, rate limits, malformed templates and body limits.
See [HTTP/setup contract](../services/app-api/README.md).

The actual live lifecycle release is newer than the Mac checkout. Preserved it
under ignored local baseline snapshots; no broad source overwrite. Imported its
unchanged `0003_telegram_outbox.sql` (SHA-256
`9cf8a43d1c45833284ae0064d941838624260743cb793cd4693970844e53b63b`), keeping
both existing 0003 filenames/checksums. No live schemas or runtime were upgraded.

Review 1: auth/schema tests passed; separate image built. Review 2: scoped drafts,
ETag conflicts and RLS tests passed. Corrected test fixture lint imports, preserved
test-schema connection options, serialized per-workspace draft admission without
lock conversion, and bounded credential work/cleanup. Review 3 adds proxy address
trust validation and actual isolated-container HTTP verification. Final Linux result:
**44 passed in 13.73 seconds**, no skips; Ruff lint/format and Docker build pass.
The actual resource-constrained image passed readiness, registration, scoped draft,
preview and logout checks in a disposable schema/container. CALL_TEST_PLAN records
the boundary of this evidence; existing live services remained healthy/unrestarted.

AGP-02 remains partial: runtime-role deployment grants, formal OpenAPI, secret
storage, catalogs/presets and immutable releases remain. AGP-03–09 (live consumers,
tool/action configuration, assets, builder UI, MCP/HTTP, performance qualification
and migration) are not complete. No publish/deploy endpoint is claimed. Existing
Kübra live traffic is unchanged; disabled second-number preparation is not a blocker
for continuing implementation. Do not treat these isolated management checks as
voice non-regression, GPU, carrier, notification or full-platform acceptance.

## 2026-10-25 — User simplicity and system-owned optimization

Owner clarifies that users must not optimize technical settings while building
agents. This supersedes the preceding blanket per-agent tuning requirement.
[Platform ownership model](VOICE_AGENT_PLATFORM.md) and
[CFG ownership matrix](AGENT_CONFIGURATION_AUDIT.md) now separate user business
choices from immutable operator-managed `engine_presets` and deployment controls.
Approved model selection remains agent-specific; generation/audio/timing/resource
presets are automatic, validated and shared by compatible agents. New preset
rollouts preserve business configuration and active-call snapshots, with PERF gates.

AGP-02 schema/API must reject user-supplied engine overrides. AGP-06 UI exposes
business fields, model catalog and configured tools/actions, not DSP/token/timeout
sliders. Migration 0003 remains untouched; future migrations create preset ownership
rather than duplicating every technical field per agent. Plan revision only; no
runtime or live DB change. Prior CFG bound mismatches remain implementation blockers.


## 2026-10-25 — Configuration completeness review

[CFG-01–18 audit](AGENT_CONFIGURATION_AUDIT.md) found unaddressed fixed behaviors
across Python, native turn/interruption/playback and shared speech services. In
particular migration 0003's 3600-second call/30000-ms ringing bounds exceed gateway
300-second/5000-ms bounds; profile 1000-character replies exceed backend's 400.
These are unresolved consumer-contract mismatches, not working options.

AGP-02/03 now require a typed versioned coverage register, compatible DB/API/protobuf/
native bounds, removal/classification of production behavioral literals, effective
config diagnostics and per-field two-agent isolation tests. Expand asset/ASR/TTS/
recovery/tool/action configuration coverage as enumerated in the audit. No shared
mutable settings and no per-turn config IO. Keep protocol/security/hardware ceilings.
PERF-01–06 and the quality/cost scorecard gate all optimizations. This task revises
the plan only; no runtime refactoring or new performance result is claimed.


## 2026-10-25 — Performance preservation and separate HTTP application

Owner requires no degradation from the new platform and an independent Docker
service for HTTP. [Performance plan](AGENT_PLATFORM_PERFORMANCE_PLAN.md) adds
PERF-01–06: fresh deployed baseline, deterministic overhead tests, real matched
CUDA/API comparisons, management/background-load isolation, soak/churn and carrier
canary. AGP-02/03/05/06/09 must satisfy these gates before rollout.

`services/app-api` remains an independent application and gets its own image/service
`management-api`; `action-worker` is separate. No management HTTP dependency in the
live turn path. Immutable prepared release caches, bounded DB pools/queues, reserved
live-model budgets and drained GPU asset-preparation windows protect calls.
Netgsm is the sole carrier; private deployment configuration replaces the proposed
generic user trunk setup. No Compose/runtime changes or new benchmarks were made.
Design/doc checks only; all performance and container-isolation gates remain pending.


## 2026-10-25 — AGP-01 self-service voice agent redesign

Owner explicitly expands the target to user-created agents, verified 0850 numbers,
editable instructions, selectable system-defined tools with agent-specific config,
future MCP configuration, and deterministic post-call Telegram/HTTP actions with
selected call/output fields. The follow-up also makes model/provider and runtime
settings agent-specific. [ADR 0011](ADR/0011-self-service-voice-agents.md) and
[VOICE_AGENT_PLATFORM](VOICE_AGENT_PLATFORM.md) supersede the earlier admin-only,
single-target/global-settings design. Global controls remain infrastructure and
hard security/resource ceilings, not a shared mutable agent configuration.

AGP-01 design complete; AGP-02–09 implementation pending. Roadmap: membership/schema/
per-agent settings → DID/releases/runtime → configured tools/grants → Telegram →
builder/assets → MCP → HTTP mapping → full integration/carrier/capacity acceptance.
PROF-02 migration 0003 remains valid groundwork and is not rewritten. Future additive
migrations preserve IDs and history, copy defaults into agent revisions and avoid
historical sends or implicit grants. No live model/service/schema was changed.

Documentation validation and primary-source review only in this task; existing
24-test Linux result belongs to PROF-02, not to these unimplemented capabilities.
Detailed implementation tests and evidence gates are specified in AGP-01–09. Local validation passed: nine documents, 157 relative links,
JSON example parsing, fence/whitespace checks and `git diff --check`. The new ADR
and platform design were copied to the authorized Linux workspace; companion docs
were copied into an ignored review directory to preserve independent remote edits.
No runtime checks were repeated for this documentation-only redesign.


## 2026-10-25 — PROF-02 profile and system settings storage

Implemented additive `0003_profile_settings.sql`: scoped profile identities,
immutable profile revisions with editable names, role/tone, availability, greeting,
response style and recovery/summary templates; typed singleton `system_settings`
for model/provider, budgets, call/transport/DB timeouts, text limits and mandatory
safety policies. Optional disabled Kübra/Burhan and Berkcan/Serkan examples are in
[the SQL setup guide](../infra/examples/README.md). No credentials or live routes.
PostgreSQL SQL is used, not SQL Server T-SQL. Applied migrations remain untouched.

Linux source sync succeeded on this follow-up. Isolated database validation:
`pytest -q tests/test_database.py tests/test_profile_settings.py`: **24 passed in
2.74s**, no skips. Ruff lint and format check passed. Earlier Ruff fixture-import
failure was fixed before rerunning. Existing application data/settings survive
upgrade/repeated seeds; cross-scope references, revision mutation, invalid settings
and disabled safety flags are rejected. Tests did not migrate the live schema.

PROF-02 is partial: configuration storage is implemented; number/target bindings,
call snapshots and scoped runtime repositories remain pending. PROF-03–05 runtime
loading, renderer, API and Telegram delivery remain pending. The active agent and
launcher still use existing constants; stored settings do not change live behavior.
No native build, GPU/API/carrier call or Telegram send was needed/performed.


## 2026-10-25 — Number-specific assistants and Telegram routing

Owner clarification: both number-owner and agent names must be editable. PROF-01
now specifies independent `owner_display_name`/`agent_name` revision fields,
validation, regenerated greeting readiness and rename acceptance tests. PROF-03/04
must expose this through the shared renderer/API without changing stable IDs,
Telegram targets or active-call snapshots. This remains a design-only update.

[ADR 0010](ADR/0010-number-agent-profiles.md) records the owner's requested
Kübra/Burhan and Berkcan/Serkan profiles, both Netgsm and the same EMA voice,
with separate Telegram destinations and future frontend-managed mappings.
[PROF-01–07](PROFILE_ROUTING_PLAN.md) defines the schema, API, call snapshot,
trusted DID routing, delivery failure policy, migration and acceptance sequence.
This supersedes one-owner/number scope and the prior webhook-first notification
selection; it does not change the model or qualify simultaneous-call capacity.

PROF-01 / M0: design complete. PROF-02–07: implementation and activation pending.
The management API and Telegram worker described here do not exist yet. Existing
M5-01 delivery and M5-02 API work now include these requirements; frontend remains
later work. Unknown DIDs must not fall back to Kübra, and ongoing calls retain
original profile/recipient revisions across configuration edits.

Validation: source/schema/protobuf and graph inspection; six changed documents
checked locally, 141 relative links resolved, no trailing whitespace or unclosed
code fences; scoped `git diff --check` passed. No executable tests are warranted
for this documentation-only change. Linux SSH connection timed out on this date;
no remote sync, runtime tests, migration, carrier call or Telegram send occurred.
Keep the carrier reachability incident open. Private number/bot/chat provisioning,
real per-number delivery and shared inference concurrency remain separate gates.


## 2026-10-24 — Configurable capacity: five per host, fifty total

The owner superseded the two-call proposal with a 50-concurrent-call architecture
and per-server limits; the current Linux target is `max_calls = 5`, with excess
calls rejected busy. [CAP-01–09](CALL_CAPACITY_PLAN.md) replaces C2-01–08 and maps
implementation, infrastructure sizing, load tests and rollout to M0–M6 / US-01–08.
[ADR 0009](ADR/0009-call-capacity.md) records the accepted target and proposed
Kamailio/RTPengine plus complete-call-server topology. Primary-source research and
planning are complete. Five/50-call GPU/API/carrier acceptance, implementation and
activation remain pending; current live configuration is unchanged.

Updated: 2026-10-23. Status: **Linux GPU server development/build/test authorized and in progress**.

The owner authorized primary development/build/test on the supplied Linux GPU server in `~/ai/alojan` (ADR 0003), and subsequently authorized the live Netgsm answer test. Continue on `codex/agent-dialogue`, preserving the uncommitted M0/M1/M2 foundation. Publication and the license choice remain separate. Ponytail `full` guides the breakdown: use existing protocol primitives, introduce only required services, and prove the smallest end-to-end slice first.

All section references below resolve to [technical requirements](REQUIREMENTS.md); DEC/US identifiers retain their original meanings.

## Task conventions and sequence

Each row is a task with purpose/output, prerequisite IDs, requirements references, environment, and acceptance evidence. Current status is recorded below; unlisted tasks remain **not started**. Change status to in progress, blocked (with reason), or done (with evidence link) as work proceeds. Keep sanitized test reports in `docs/validation/`; never commit private captures. Split a task further only if review size or evidence warrants it.

Development track: M0 → M1-01–05 / complete G1 scenario set → M1-08 development report → M2–M5. Ubuntu validation track: U0-01 → G0-Ubuntu/G1-Ubuntu → M1-06–07 / G2 → live G3–G7. [ADR 0003](ADR/0003-linux-development.md) makes Linux the primary development host while retaining the sequencing from [ADR 0002](ADR/0002-macos-development.md). Missing carrier access does not block independent development. Explicit test services can validate contracts and unblock downstream local work, but cannot satisfy real-model/API/notification acceptance. Track local and deferred results separately; no task with unmet real acceptance criteria is wholly done.

## Preparation delivery

| ID | Purpose and output | Dependencies / references | Environment | Acceptance |
|---|---|---|---|---|
| PRE-01 | Branch and pinned Ponytail installation | Owner preparation plan | Mac | Correct branch, installed skill hash and source revision recorded — done |
| PRE-02 | Requirements, agent rules, contribution/security docs and README | PRE-01; requirements §16–18 | Mac | Requirements extracted; document links and diff reviewed — done |
| PRE-03 | Tasks, call gates, license recommendation and blockers | PRE-02; requirements §14–18 | Mac | Reviewable plan delivered; **approved for macOS development** |

## Primary execution environment

[ADR 0003](ADR/0003-linux-development.md) supersedes the earlier Mac-first scheduling below. New source is synchronized to `~/ai/alojan` and builds/tests run on Linux. Historical Mac results remain valid only for that environment. The original task tables retain their acceptance scope; Linux now becomes the default for implementation and test execution. Finish the existing G1 scenario set before M2–M5; carrier access remains a separate gate.

## Branch scope

The U0-01/M0-08 server setup used `codex/linux-development`. M1-02/M1-05 packet
impairment and two-call isolation work used `codex/sip-isolation`. M1-04 caller
identity work used `codex/caller-identity`. M1-03 spoken fallback used
`codex/spoken-fallback`; M1-02 codec/resampling used `codex/audio-conversion`. Offline EMA
prompt generation now uses `codex/ema-prompts`, carrying forward existing
uncommitted work without merging or publishing it. ADR 0004 permits this limited
GPU synthesis step. M1-08 completion and the owner’s named-greeting acceptance
are recorded on `codex/m1-development-report`; the native Linux G1 scenario set
is now complete. M2-01 development used `codex/asr-service`; M2-02 persistent EMA streaming and GPU
coexistence used `codex/tts-service`. M2-03 gateway integration uses
`codex/speech-gateway`; native validation is complete and M3-01 turn decisions are next.
The owner's immediate-answer follow-up uses `codex/netgsm-answer` for M1-06/07:
two real PCMA calls connected and the owner accepted the intelligible greeting.
The remaining-work request starts M3-01 on `codex/turn-detection`, preserving the
live carrier process while validating an opt-in adaptive single-turn profile.
M3-02 continues on `codex/barge-in` with opt-in interruption, generation invalidation
and conservative sent-history accounting; live carrier behavior is preserved.

## Current implementation status

Evidence: [macOS foundation report](validation/macos-foundation-2026-10-09.md), [Linux development report](validation/linux-development-2026-10-23.md), [Linux SIP isolation report](validation/linux-sip-isolation-2026-10-23.md), [Linux caller identity report](validation/linux-caller-identity-2026-10-23.md), [Linux spoken fallback report](validation/linux-spoken-fallback-2026-10-23.md), [Linux audio conversion report](validation/linux-audio-conversion-2026-10-23.md), and [Linux EMA prompt report](validation/linux-ema-prompts-2026-10-23.md).

| Tasks | Status | Remaining acceptance |
|---|---|---|
| M0-01, M0-02 | Done for native development | Mac and Ubuntu toolchain/build checks passed; production deployment remains separate |
| M0-03 | Partial | App API, native ASR/TTS and agent entry points exist; full production packaging remains pending |
| M0-04 | Done locally | Pinned C++/Python bindings, byte roundtrip, half-close, deadline/cancel, stale generation, isolation and slow-consumer contracts pass with an explicit test peer on Mac and Ubuntu |
| M0-05 | Partial | Seven-table migration, idempotency/rollback tests pass; separate runtime DB role pending |
| M0-06 | Partial | Loopback PostgreSQL Compose and API health work; service Dockerfiles/GPU deployment pending |
| M0-07 | Partial | Ruff/clang-format, CTest/pytest and pre-commit configuration added; the GitHub Actions workflow is currently absent, and clang-tidy and hosted CI validation remain pending |
| M0-08 | Partial | Linux execution/synchronization guide, source graph and evidence available; full G0 remains open |
| M1-01, M1-02, M1-05 | Done for native Linux G1 development | Full local lifecycle, codec/resampling, paced RTP/impairment and isolated-call scenario set passed; deployment/carrier validation remains separate |
| M1-03 | Done for native Linux G1 development; v3 listening accepted | Owner accepted the named EMA greeting on 2026-10-23; complete playout, BYE interruption, ACK gating and recovery passed. Live TTS integration and license/distribution review remain open |
| M1-04 | Local parser/integration complete | Configurable source trust/precedence, Turkish normalization, privacy, redirects and log redaction pass on Linux; persistent call-record integration and live US-03 carrier evidence remain pending |
| M1-08 | Development report complete; carrier addendum pending | [Consolidated native Linux G1 evidence](validation/linux-m1-development-report-2026-10-23.md) delivered; M2-01 prerequisite satisfied. M1-06/07 and overall M1 carrier acceptance remain pending |
| U0-01 | Partial; development environment ready | Frozen Linux builds, latest 184 unchanged pytest cases plus 3 corrected acknowledgment variants (separate runs, no skips), 8 CTests, DB migrations and native/container CUDA kernel passed; production service containers and host-network integration pending |
| M2-01 | Native development implementation complete; limited real CUDA checks passed | Persistent pinned large-v3-turbo float16 service, partial/final text, cancellation, isolation, capacity/error handling and synthetic Turkish evaluation. [ASR evidence](validation/linux-asr-2026-10-23.md); broader real/noisy speech quality, long-turn/lifecycle hardening and production supervision remain open |
| M2-02 | Native development implementation complete; limited real CUDA coexistence passed | Persistent bounded EMA streaming, cancellation/recovery, 8/16/24/48 kHz calibration and concurrent ASR on the 16 GB GPU. [TTS evidence](validation/linux-tts-2026-10-23.md); broader pronunciation/number quality, production supervision and soak remain open |
| M2-03 | Complete for native development; scripted CUDA path passed | Real local PCMA/PCMU → ASR → EMA → RTP, bounded queues, cancellation and fallback; 20 new pytest cases and queue CTest. [Gateway evidence](validation/linux-speech-gateway-2026-10-23.md). Fixed capture/response only; M3/M4, broader speech quality and full G3 remain separate |
| M3-01 | Native adaptive single-turn core implemented; full acceptance partial | Pinned Silero/Smart Turn CPU inference, fresh ASR coverage, contextual timing and bounded background decisions. [Turn evidence](validation/linux-turn-detection-2026-10-23.md). Synthetic 0.5–2 s pause/failure checks and real CUDA local calls are separate from human/carrier quality. Silent-caller reminder and runtime threshold configuration are implemented in the M3-01 follow-up below; broader human/noisy calibration remains open; M3-02 now has a separately validated native interruption core; M4 dialogue is now implemented separately; carrier latency acceptance remains open |
| M3-02 | Native interruption core implemented; full acceptance partial | Echo/backchannel policy, immediate generation revocation, TTS cancellation, bounded pre-roll handoff and conservative sent-history accounting. [Interruption evidence](validation/linux-interruption-2026-10-23.md). Real CPU/CUDA local calls and one owner-confirmed PCMA carrier interruption/new-response path passed. [Live follow-up](validation/netgsm-interruption-2026-10-23.md). 250 ms onset target, broader human/carrier calibration, broader phrase alignment remain open; M4 LLM cancellation now has separate native tests |
| M1-06 | Native carrier profile running; full network review partial | Private LAN/public mapping, UDP 5060, RTP/RTCP within 10000–10100 and exact incoming signaling-source check configured; two real PCMA calls worked under the existing router policy. Complete provider failover/media ranges and broader network review remain open. [Live evidence](validation/netgsm-answer-2026-10-23.md) |
| M1-07 | Immediate answer/greeting accepted; full G2 partial | Two real calls answered, ACK confirmed, incoming nonzero PCM received, remote hangup/local closing released sessions. Owner accepted intelligible greeting. Reverse speech intelligibility, live identity and full carrier acceptance remain open |

**M1-02/M1-05 impairment and two-call isolation subitems: done on Linux**, including a regression for PJSUA2 2.16 reorder statistics. Default admission remains one; two calls require an explicit test flag. The subsequent consolidated M1-08 audit completes the native Linux M1-05 scenario set; this does not imply Mac revalidation.

**M1-02 codec/resampling subitems: done on Linux.** The receive port now uses PJMEDIA to deliver 16 kHz / 20 ms PCM; playback stays at negotiated 8 kHz. The owner subsequently listened on 2026-10-23 and rejected the formant fixtures as unintelligible. The owner accepted EMA v2 as clearly intelligible on 2026-10-23 and requested a named greeting; v3 implements that request under ADR 0004. The owner subsequently accepted the delivered v3 greeting. No model readiness follows from these conversion tests.

The native Linux G1 development scenario set is complete, including owner listening acceptance. [The M1-08 completion report](validation/linux-m1-development-report-2026-10-23.md) satisfied the prerequisite for the now-implemented M2-01 worker. M2-02 and the M2-03 scripted native speech path are implemented and validated on Linux. M3-01/02 native cores now have local evidence; remaining calibration and M4 dialogue acceptance stay separate. No full model/API or carrier gate is marked passed. ADR 0004 remains the historical authorization for offline EMA generation before G1 completion.

Named greeting follow-up: [Linux evidence](validation/linux-named-greeting-2026-10-23.md), mapped to M1-03 / US-01 and §6,8.2. V2 and v3 acceptance are local listening results, not carrier-call results.

M2-01 uses a separate pinned Linux environment and retains one model on the GPU. The phone gateway still reports `voice_pipeline_ready=0`; M2-03 now exposes an explicit scripted speech test, while M3 turn/interruption cores are opt-in and M4 agent responses remain pending. A full-suite audit also corrected empty PJMEDIA heartbeats being counted as invalid PCM, with a deterministic native regression.

## M0 — Foundation (implementation-ready tasks)

| ID | Purpose and deliverable | Depends on | Requirements | Environment | Acceptance evidence |
|---|---|---|---|---|---|
| M0-01 | Inspect Mac OS/CPU architecture, compiler, CMake, Python/uv and Docker; pin reproducible compatible toolchains. | PRE-03 implementation approval | DEC-01–03; ADR 0002 | macOS | Sanitized inventory and local dependency smoke checks; Ubuntu/CUDA explicitly unverified |
| M0-02 | Add CMake C++20 gateway target with pinned PJSIP/PJSUA2 source/checksum; use PJMEDIA capabilities instead of a parallel SIP stack. Add build presets and dependency inventory. | M0-01 | DEC-04,07; §6,16 | macOS; later Ubuntu | Clean reproducible configure/build; a linked PJSUA2 initialization/shutdown smoke test; dependency notices recorded |
| M0-03 | Add Python/uv workspace for the specified services, pinned lockfile and minimal entry points. Keep inference unloaded until its milestone. | M0-01 | DEC-08,09,11; §16 | macOS; later Ubuntu | Frozen dependency installation; entry-point smoke checks; no fake model readiness |
| M0-04 | Define `voice.v1` protobuf messages and streaming services; generate and track C++/Python bindings with pinned generators. Document ownership and bounded stream behavior. | M0-02,03 | DEC-12; §10; US-05 | macOS; later Ubuntu | Cross-language PCM roundtrip; regeneration leaves no diff; deadline/cancellation, stale generation and slow-consumer contract tests |
| M0-05 | Add PostgreSQL schema migrations for calls, utterances, events, summaries, actions, notes and outbox; private DB role/config. | M0-03 | DEC-13; §11; US-07,08 | macOS; later Ubuntu | Fresh migration and repeat invocation; unique note version; FK behavior; transactional outbox insertion rollback test |
| M0-06 | Add Dockerfiles, Compose, .env.example and health checks; Mac core profile runs support services with loopback ports, native gateway/Python; separate Ubuntu host-network/GPU configuration. | M0-02–05 | §10,12,16; G0-local | macOS / Linux CI | Mac core start/stop and migrations; explicit test profiles; unavailable production models not ready; Ubuntu GPU checks deferred to U0-01 |
| M0-07 | Add pinned format/lint/test tools, pre-commit and GitHub Actions: clang-format/clang-tidy, Ruff, CTest/pytest, binding regeneration and Compose/build checks. | M0-02–06 | §15.1,16 | macOS / hosted Linux CI | Run real commands locally; deliberately failing test/lint fails the job; CI uses read-only permissions and no production credentials or office self-hosted runner |
| M0-08 | Document real local build/test/run commands and deferred Ubuntu checks; index source with Codebase Memory. | M0-01–07 | §15–18 | macOS / Linux CI | Fresh-checkout local reproduction and G0-local evidence; Ubuntu acceptance pending |

M0 choices: CMake/CTest for C++, uv/pytest/Ruff for Python, SQL migrations tracked in Git, Docker Compose for deployment, and GitHub Actions as the intended CPU-check provider. The hosted workflow is currently absent; pin versions against the inspected Mac architecture in M0-01 and validate the CUDA compatibility matrix in U0-01/M2. None are claimed tested now. Use existing libraries before adding custom tooling.

### M0 contract task boundary

Preserve the technical baseline's `AudioFrame`, `TurnEvent`, `AgentRequest`, and `AgentEvent` field numbers/types. Add `StreamRecognize`, `StreamSynthesize`, `RunTurn`, and `CancelGeneration` with documented stream direction, completion/error events, and per-call/generation isolation. Keep binary PCM over gRPC, never HTTP audio webhooks. Cancellation must invalidate queued results across all services, not merely close the caller's stream. Bound application queues and define overflow/slow-consumer behavior; propagate deadlines. Document these decisions with the proto before consumers are implemented. Do not generate speculative MCP/calendar service contracts.

## M1 — SIP/RTP (implementation-ready tasks)

| ID | Purpose and deliverable | Depends on | Requirements | Environment | Acceptance evidence |
|---|---|---|---|---|---|
| M1-01 | Implement PJSUA2 endpoint and isolated CallSession lifecycle: inbound INVITE, answer/ACK, BYE, CANCEL, timeout and idempotent cleanup. | M0-08 | US-01; §6,7 | macOS; later Ubuntu | Local peer tests for normal call, pre-answer CANCEL, remote BYE, inactivity, duplicate cleanup and shutdown; no leaked session |
| M1-02 | Connect PJMEDIA receive/playback ports for PCMA/PCMU, PCM conversion and 20 ms pacing. Reuse jitter/codec facilities; keep callbacks free of blocking IO. | M1-01 | US-01; §5–7 | macOS; later Ubuntu | Synthetic reference audio both ways; codec known-vector tests, resampling duration, reorder/loss/jitter checks and paced packet trace |
| M1-03 | Add licensed synthetic greeting/fallback WAV fixtures and unavailable-dependency policy. Complete closing playback before intentional hangup. | M1-02 | §6,8.2; US-01 | macOS; later Ubuntu | Audible AI introduction; dependency-down path plays fallback and ends; remote hangup interrupts playback immediately; fixture provenance recorded |
| M1-04 | Parse caller identity with configurable operator trust, E.164 normalization, redirect metadata and PII redaction. | M1-01 | US-03; §6,14 | macOS; later Ubuntu | Tests for Turkish formats, invalid/withheld/unknown, forwarded calls and spoofed PAI from an untrusted source; sanitized logs |
| M1-05 | Build deterministic local SIP peer scenarios and smoke script. Test admission limits and call isolation without AI models. | M1-02–04 | §12.3,15.1–2; G1 | macOS; later Ubuntu | INVITE/ACK/BYE, CANCEL, packet impairment and two-call isolation pass; default one-call limit gives controlled busy behavior; no cross-call audio |
| M1-06 | Configure advertised addresses, media range and carrier allowlist with operator-confirmed values. Document NAT/SDP diagnosis. | M1-05; U0-01; EXT-01,02 | DEC-05,14; §12.2 | Ubuntu + office router | Restricted reachability and consistent signaling/SDP/DNAT; private configuration; no claim of Cloudflare UDP transport |
| M1-07 | Run direct Netgsm inbound call with WAV audio; record codec, identity and teardown. | M1-06; U0-01 | US-01,03; G2 | Ubuntu + real phone | Actual two-way carrier audio; no CUDA/model dependency for WAV; forwarded identity pending G6 |
| M1-08 | Deliver local M1 report and later append carrier acceptance. | M1-05 for local report; M1-07 for final acceptance | §16,18 | macOS; later Ubuntu | G1-local unlocks local M2; mark M1-06/07 pending and M1 not fully accepted until G2 |

## Ubuntu validation

| ID | Purpose and deliverable | Depends on | Requirements | Environment | Acceptance evidence |
|---|---|---|---|---|---|
| U0-01 | Inspect server OS/GPU/driver/Docker/toolkit; reproduce locked builds, migrations, network configuration and local SIP tests. | Server access; local M0/M1 | DEC-01–03; EXT-05 | Ubuntu | G0-Ubuntu and G1-Ubuntu evidence; GPU container check; model coexistence still belongs to M2/G3 |

M1-06 also requires U0-01. Server unavailability blocks this acceptance track only. Preserve reproducible local progress and report outstanding gates.

## Later packages

These retain required capability and acceptance boundaries. Refine implementation details from M1 evidence before starting, without expanding requirements scope.

| ID | Purpose / output | Depends on | Requirements | Environment | Acceptance |
|---|---|---|---|---|---|
| M2-01 | Persistent faster-whisper partial/final service; CPU smoke where supported, explicit test service otherwise. | M1-08 local report | US-02; §8.1,10 | macOS CPU; later Ubuntu GPU | Local contract/revision/cancel tests; real Turkish ASR and CUDA acceptance separately required |
| M2-02 | EMA streaming/resampling/normalization; CPU smoke where supported, explicit test service otherwise. | M1-08 local report | §8.2,10 | macOS CPU; later Ubuntu GPU | Local chunk/playout tests; real voice plus warm-up/ASR coexistence in 16 GB deferred to Ubuntu |
| M2-03 | Integrate local speech contracts and record labeled CPU or test-service measurements. | M2-01,02 local contracts | §3; G3 speech portion | macOS SIP; later Ubuntu | Local pipeline/cancellation allows M3 work; G3 requires real models, CUDA, G2 and M4 API |
| M3-01 | Silero/Smart Turn and contextual adaptive wait | M2-03 | US-04,06; §7.2 | macOS; later Ubuntu | Labeled 0.5–2 s pauses, incomplete phrases and detector failure fallback |
| M3-02 | Echo/backchannel policy, generation invalidation and sent-audio transcript accounting | M3-01 | US-05,06; §7.3–4; G4 | macOS; later Ubuntu | Old generations never replay; queue flush/cancel; correction, echo/noise tests with timestamp evidence |
| M4-01 | Integrate SDK streaming/context with an explicit test client; verify requested model/API when account available. | M3-02 local checks; EXT-06 for real API acceptance | DEC-11; §9 | macOS + API; later Ubuntu | Stream isolation/timeout/cancel locally; real account/model acceptance separate; full G3 deferred |
| M4-02 | Implement take_note/finish_call, tool authorization/idempotency and a minimal Streamable HTTP MCP adapter boundary | M4-01 | US-02,08; §9.2–3 | macOS; later Ubuntu | Duplicate notes prevented; closing audio completes; injection/unauthorized actions rejected; adapter contract tested without live MCP integrations |
| M4-03 | Persist utterances and schema-validated post-call summary | M4-02 | US-07; §9.4,11 | macOS; later Ubuntu | Confirmed versus unconfirmed facts preserved; summary failure recoverable; caller not held for analysis |
| M5-01 | Durable webhook outbox with local test receiver; owner endpoint configured later. | M4-03 local checks; EXT-08 for actual delivery | US-07; §10,11 | macOS; later Ubuntu + endpoint | Retry/restart/deduplication locally; actual notification pending G5; no exactly-once claim |
| M5-02 | Private REST endpoints and HTTP-only Cloudflare Access guide | M4-03 | §10,12; P0 API | macOS; later Ubuntu | Auth/owner-only retry enforced; live/ready distinct; no dashboard required |
| M5-03 | Observability, retention/backup restore, failure injection and soak | M5-01,02 | §3,12,14,15; G4,5,7 | Ubuntu GPU/phone | 30+ labeled scenarios, 50+ timed turns, two-call isolation and 30-minute soak; report targets versus measured values |
| M6-01 | Compare direct, forwarded and withheld caller identity | M1-07; EXT-03 | US-03; §13; G6 | Phone + carrier | Sanitized header comparison; no caller identity guarantee |
| M6-02 | Test manual/assisted iOS Focus forwarding and document limitations | M6-01; EXT-04 | US-09; §13; P1 | Owner iPhone | Owner-authorized enable/status/disable tests; no assumed unattended USSD support |

Default notification is a generic webhook to minimize new provider-specific dependencies; endpoint credentials stay private. P1 dashboard, contacts and live MCP integrations remain deferred. M6 is a separate carrier/device feasibility report and must not conceal an otherwise functional P0 as either proven or broken without evidence.

## Coverage and decision gates

| Requirement | Tasks |
|---|---|
| US-01 | M1-01–03, M1-07 |
| US-02 | M2-01, M4-01–03 |
| US-03 | M1-04, M1-07, M6-01 |
| US-04 | M3-01 |
| US-05 | M0-04, M3-02 |
| US-06 | M3-01–02 |
| US-07 | M0-05, M4-03, M5-01 |
| US-08 | M4-02 adapter boundary; live MCP integrations deferred |
| US-09 | M6-02 (P1 / external) |

The owner reviews this task plan and [license proposal](LICENSING.md) independently. Implementation-plan approval unlocks M0/M1, not publication or license adoption. Follow [the gate register](CALL_TEST_PLAN.md) for all EXT-01–08 dependencies. No additional autonomous runner or multi-agent delegation is introduced in this preparation.

M2-02 keeps EMA resident on loopback port 15072 and ASR on 15071. Six concurrent
synthetic cases passed transport/audio and independent ASR entity checks; a TTS
phone-number roundtrip had an extra ASR zero and remains a quality limitation.
The pinned normalizer also reads trailing phone punctuation literally. These
results do not satisfy broader pronunciation/WER, G3 or carrier acceptance.

M2-03 final Linux checks: 151 pytest passed (no skips, one known audioop warning,
273.50 s), 5 CTests passed (2.06 s), native build and formatting/lint passed.
Both real CUDA local calls delivered 350 ASR input frames and the complete
200-frame EMA response with 20 ms RTP pacing. Scripted half-close to first
output-port PCM was 159 ms for each codec; sampled host GPU peak was 3,008 MiB.
These two observations are not P95 or end-to-end conversational latency.

## M3-01 continuation boundaries (historical)

The silence recovery follow-up below supersedes the reminder/configuration backlog
in this historical single-turn implementation record.

The native adaptive core is an explicitly selected local test profile, with a
fixed closing response. It can unblock M3-02 echo/interruption work, while the
parent M3-01 acceptance remains partial. Finish the once-at-seven-seconds reminder
with safe continued listening after the M3-02 outbound-reference policy is in place;
retain runtime threshold configuration and real human/noisy pause calibration as
M3-01 follow-ups. This refinement does not remove requirements or mark G4 passed.
No adaptive mode was enabled on the live Netgsm listener, and no agent/API,
recording, note or external write action was introduced.

M3-01 final evidence: 175 pytest passed (no skips, one known audioop warning,
434.96 s), 7 CTests passed (2.31 s), final strengthened hangup/reuse case passed
separately, both model-enabled and model-disabled builds passed their checks,
and binding regeneration was unchanged. Final real local PCMA/PCMU CPU+CUDA calls
measured 1243/1262 ms from last VAD speech to first output-port PCM, including
ASR partial freshness; this is neither handset latency nor P95. The running
carrier greeting and both resident GPU workers remained healthy.


## M3-02 continuation boundaries

The native core supports a validated transition from generated speech through
interruption into a new recognition/response generation. The response remains
fixed. Full US-05/US-06/G4 acceptance remains partial: measured real-model onset
proxy to decision was 671.78/707.03 ms, above the 250 ms target. Short-ack semantic
classification and phrase alignment need M4 context/streaming. Do not present
these local synthetic checks as a live conversation or restart the carrier
listener implicitly. M4 can build on the cancellation/history boundary while the
listed M3 calibration, reminder and live-acceptance work remains visible.


M3-02 validation: native build and 8 CTests passed (2.31 s); full pytest initially
reported 184 passes / 1 fixture failure (623.47 s, no skips). The partial-word test
fixture was replaced with a pinned complete EMA `Evet.`; all 3 packet-phase
variants passed (59.01 s). Final coverage is 184 unchanged cases plus 3 corrected
variants, not a second full-suite invocation. Ruff, clang-format, no-model build
and fail-closed opt-in checks passed. Real CPU/CUDA PCMA/PCMU interruption calls
passed separately; [the report](validation/linux-interruption-2026-10-23.md)
retains the failed attempt and precise limitations.


## Owner-authorized real-phone interruption follow-up

The explicit `interruption` carrier profile is now active after an idle-line
switch, rollback snapshot and updated loopback ASR readiness/coverage checks.
One PCMA call has both owner-confirmed sentence cutoff and server-recorded
invalidation/new-generation startup. Two preceding calls completed ordinary
ASR/EMA replies without interruption. A fourth call hit controlled incomplete-turn
fallback (error 8); keep this M3-01 calibration issue open without guessing its
cause or retaining private speech. No threshold/model changes were made.
The fixed response and uninterruptible opening remain development limitations;
full G4, 250 ms onset timing, broad echo/backchannel quality and M4 stay open.
See [the live report](validation/netgsm-interruption-2026-10-23.md).


## M4 owner-authorized continuation

On 2026-10-23 the owner prioritized M4, selected OpenRouter and then
`openai/gpt-6-luna-pro` (ADR 0005). Native M4 is implemented and active on the
carrier development line. The owner confirmed correct message readback after a
follow-up but still reported excessive waiting; full carrier acceptance is open.
See [implementation, tests and carrier evidence](validation/linux-agent-2026-10-23.md).

- M4-01: bounded SDK/Responses streaming, per-call context, native cancellation
  and phrase receipts implemented. Real API and synthetic CUDA/SIP dialogue passed.
  First substantive model response still takes several seconds.
- M4-02: idempotent local notes, delivered-readback confirmation and controlled
  closing implemented. Direct local confirmation removed repeated model waits.
  MCP policy boundary tested; full HTTP transport and live external tools pending.
- M4-03: utterances, durable summary jobs and schema validation implemented and
  tested with real PostgreSQL. Actual post-call summaries passed. Production
  lifecycle/retention/reconciliation remain open; M5 notification is not implemented.
- M2-01 follow-up: bounded same-call handoff waits for cancelled CUDA decoding to
  drain instead of rejecting the next recognition turn; isolation/cancellation
  regression tests pass.

Latest confirmation/handoff Linux checks: 48 focused pytest passed, no skips,
80.82 seconds; 8 CTests passed, 2.32 seconds. Two synthetic adaptive calls completed
with confirmed notes and summaries; confirmation half-close to output was
138/139 ms, versus 9059 ms in the preceding probe. These are not handset latency
or P95. Preserve the failed probes and owner-reported waiting in the evidence.
M3 calibration and M5 delivery remain separate unfinished work.

The owner then accepted correct readback but again rejected the waiting time.
A single cancellable waiting phrase is now emitted after 800 ms without a
complete response; it does not remove the measured 3–6 second substantive model
wait. Final focused checks: 28 passed in 76.98 seconds, no skips; unchanged ASR
handoff tests passed in the preceding 48-case run. A real adaptive CUDA/API call
passed with waiting text at 801 ms and closing output at 138 ms. Final carrier
listening/latency acceptance is pending. Do not mark G3/G4 or all of M4 accepted.

## Owner-prioritized performance review (2026-10-23)

The owner deferred M5-01 notification delivery and M5-02 owner API, then authorized
performance improvement, code review and research into Retell/ElevenLabs practices.
M5-03 measurement/performance subitems can proceed independently; the full M5-03
gate and its unfinished dependencies remain open.

Implemented: early natural-clause speech streaming, numeric/title boundary guards,
turn-scoped readback confirmation, recent/bounded summary input, consistent summary
retry updates, and separate waiting/substantive per-phrase timing. Same-model
routing and compact-prompt experiments did not establish reliable gains and were
not adopted. See [review, evidence and remaining findings](validation/performance-review-2026-10-23.md).

The main remaining delay is first substantive model output. Production lifecycle,
50+ timed Turkish turns, 30+ labeled scenarios, soak and human carrier quality
remain unaccepted. Existing fast local confirmation is preserved; no model or
architecture decision changed.

Final follow-up: native build and 8 CTests passed; 39 focused Linux checks passed,
then 35 agent/phrase/DB checks passed after the additional exact-goodbye path.
Real synthetic CUDA/API calls preserved note-confirmation rules and delivered
confirmation/goodbye closing at 138/139 ms after ASR half-close. Initial substantive
responses remained 3739/3499 ms. The idle development line was updated with
rollback snapshots; worker health and gateway readiness passed. Human carrier
retest, latency targets and full M5-03 acceptance remain open.

## Owner-selected quiet waiting music (2026-10-23)

M4-01/M5-03 follow-up: replace spoken waiting feedback with quiet original native
music. The final decision and 800 ms delay precede music; ready speech, valid
interruption, failure and hangup stop it. Music does not enter dialogue/confirmation
or substantive-response timing. [Evidence and limitations](validation/waiting-music-2026-10-23.md):
9 CTests and 44 focused Linux checks passed, plus a real synthetic adaptive
CUDA/API/DB call. Owner listening and handset-volume acceptance remain pending.
The updated gateway/agent are active on the idle-checked development line, with
rollback snapshots and passing ASR/EMA/agent health checks. Spoken waiting is off;
waiting music v1 is on. This deployment is separate from human carrier acceptance.

## Greeting opening-word follow-up (2026-10-23)

M1-03/M1-06, US-01: owner reported missing `Merhaba`. Stored audio and real CUDA
ASR confirm the word exists. Carrier-only v4 adds a 400 ms silent RTP lead-in while
preserving every original speech sample. Linux focused tests: 26 passed, including
both codecs with simulated loss of the first 300 ms. [Evidence](validation/greeting-start-2026-10-23.md).
Real handset confirmation remains pending; exact carrier clipping cause is unproven.

## Owner-requested ringing and dialogue follow-up (2026-10-23)

M1-03/M1-06 and M4-01/02, US-01/02/05: carrier answering now waits 3000 ms
from 180 Ringing. Agent commentary is separated from final speech/readback,
with a single fallback for commentary-only responses; prompt guidance avoids
repeated requests for supplied information. Last two actual calls were inspected:
one contained same-turn repeated questions, the other ended before any utterance.
Historical message phases are unavailable; the precise carrier cause is unproven.
See [evidence and validation](validation/ringing-dialogue-2026-10-23.md).
Human carrier retest remains pending; this does not close broad M4/G3/G4 acceptance.

Ringing/dialogue validation: Linux build, nine CTests and 62 focused checks
passed; two further streaming/cancellation cases passed separately. Three real
API dialogue checks and one adaptive CUDA/API/DB call passed. The idle-checked
development line is updated; active 3000 ms setting, v4 greeting and all worker
health checks verified. First substantive response remains several seconds.

## Owner-approved Kübra message flow (2026-10-23)

M1-03 and M4-01/02/03; US-01/02/05/07. [ADR 0006](ADR/0006-kubra-message-close.md)
records approved opening text, the Kübra name, no readback/confirmation and
closing three seconds after speech. Notes and summaries remain unconfirmed;
notification delivery is still deferred. Availability wording must not preempt
an already supplied message. [Validation](validation/kubra-message-2026-10-23.md).
The previous confirmation acceptance examples are historical, superseded by
this owner-selected behavior. Human carrier acceptance remains pending.

Kübra validation: Linux native build and nine CTests passed; 78 focused checks
passed with one SDK exception-type fixture failure, then all 40 final agent/phrase
cases passed after correcting that assertion. Both codec closing-pause checks,
v5 prompt transport and PostgreSQL checks passed. Real API availability/message
checks and a one-turn CUDA/API/DB call passed with an unconfirmed saved note.
The idle development line now runs v5 with healthy workers; handset retest pending.

## No-message farewell correction (2026-10-23)

M4-01/02, US-01/02: the latest real call spoke a farewell but returned finish=0
and reopened listening. Extend closing to a natural-language declined-message
exit without inventing a note. A complete standalone farewell also closes if
the model omits the tool. Keep actual message saving and continued questions
separate. [Evidence](validation/farewell-hangup-2026-10-23.md). Human retest pending.

Farewell regression validation: 49 Linux checks passed, three real model decision
cases passed, and a synthetic real-CUDA/API no-message exit reached local BYE.
The idle development line is updated and all worker health checks pass. Native
closing timer unchanged; new handset retest remains pending.

## Contextual call-center agent role (2026-10-23)

M4-01/02, US-02: the owner rejected the latest call's abrupt save-and-close and
requested a professional call-center role governed by context. ADR 0007 removes
automatic closing from take_note. The model now receives the save result, chooses
natural follow-up and supplies contextual farewell text through finish_call.
No readback confirmation is restored; the approved greeting and closing pause
remain. See [evidence](validation/natural-call-agent-2026-10-23.md).

Natural-agent validation: 53 Linux focused agent/DB/closing checks passed, with
50 final agent/phrase regressions also passing. Four real model scenarios (six
turns) passed, including message additions and contextual exits. A two-turn
CUDA/API/DB loopback saved the note, kept listening and closed after farewell.
The idle development line now runs natural-v1 with all workers healthy. Response
latency remains about 6 s on the measured first turn; human carrier retest is
pending. No notification delivery was added.

M4-01/02, US-02 wording refinement: unknown call purpose now gets one polite open
question after unavailability; a known purpose is never requested again. Two
synthetic real-model cases and 50 Linux regressions passed. natural-v2 is active
on the idle-tested development line with healthy workers; handset retest pending.

## Consolidated main publication (2026-10-23)

The owner authorized publishing all accumulated branch work as the current main
snapshot and explicitly required privacy checks. All pre-publication local branch
tips were contained in the working branch. A squash publication preserves their
combined source while excluding unpublished commit metadata and local session
refs. Private configurations, credentials, real recordings and transcripts stay
outside Git. See [publication evidence](validation/main-publication-2026-10-23.md).
This does not close deferred acceptance gates or enable notification delivery.

Publication validation: all 255 Linux pytest cases and nine CTests passed;
source formatting, lint and generated-binding reproducibility passed. Private
source and metadata checks completed; only a consolidated noreply commit is
published. Hosted CI remains absent, and handset acceptance remains separate.

## ASR spelling and CPU optimization (2026-10-23)

M2-01 / M5-03, §8.1 and US-02/04/06: preserve the pinned decoder and reduce ASR
OpenBLAS CPU work to one thread. Add a bounded private exact-phrase spelling
map for the owner-confirmed product. No denoiser or extra inference pass.
Text-only decoding and contextual hotwords were rejected after a phone-number
regression; noise filtering did not improve measured quality.

The final synthetic paired run kept median latency near 112 ms, reduced targeted
name misses from 24 to 12 across 240 speech decodes, and changed no numeric tokens.
CPU time for the same workload decreased approximately 92% versus the former
launcher. All seven real-CUDA service cases and both native PCMA/PCMU fixed-reply
loopbacks passed. The idle development line now uses ASR 15173; the replaced live
worker was stopped and GPU memory returned to its previous level. See
[evidence and limitations](validation/asr-quality-2026-10-23.md).
Human noisy-handset acceptance, broad WER and full conversational latency remain
open; no notification or recording feature was added.

Final focused validation: 44 Linux pytest cases passed in 3.11 s; Ruff lint and
format checks passed for six affected Python files; launcher syntax and diff
whitespace checks passed. The prior consolidated baseline had 255 passing tests;
that full suite was not rerun for this ASR-only change. Source synchronization
and final worker/gateway health were checked separately from human acceptance.

## Uncertain recognition clarification (2026-10-23)

M4-01/02 / M5-03, US-02/06: an owner-reported product inquiry was transcribed as a
stock outro and incorrectly ended the call. Add a local clarification guard for
known suspect ASR outputs and bare thanks after a pending question. Other unclear
or unrelated answers now require clarification in the agent role; remove the
instruction to close after two failed clarifications. Preserve actual exits,
existing notes, original stored recognition and bounded call resources.

Linux: 59 agent/phrase tests passed; six backend scenarios, six real CUDA speech
cases and a three-turn native CUDA/API/isolated-DB recovery call passed. Exact
product spelling still failed in one very quiet synthetic case; acoustic accuracy
is not declared solved. The development agent now uses natural-v3-clarification;
carrier retry remains pending. [Evidence](validation/clarification-recovery-2026-10-23.md).

## Skill Creator prompt review (2026-10-23)

M4-01/02, US-02/06: reorganize receptionist instructions around caller intent,
clarification, message saving and explicit completion. Distinguish a topic from
an actual message, callback requests from exits, and first-save invitations from
redundant follow-ups. Reinforce finish_call's description without changing its
contract. Align the stale two-retry requirement with the approved clarification
policy. Existing ASR guards and speech services are unchanged.

After rejecting failed draft behaviors, the final 16 synthetic scenarios passed
(14 real API, two local guards), along with 59 Linux agent/phrase tests. The idle
development agent now runs natural-v4-prompt-review. Human acceptance and model
behavior on unseen speech remain open. [Evidence](validation/prompt-review-2026-10-23.md).


## M3-01 silence recovery follow-up (2026-10-23)

Owner requested completion of M3-01 after reviewing the remaining-task list.
Maps to US-04/US-06 and requirements §7.2; no DEC or P0/P1 change.
The adaptive agent profile now reminds a silent caller once after seven seconds,
continues listening, and uses a polite silence-timeout farewell after the next
bounded 20-second capture has no confirmed speech. Incomplete endpoint evidence
requests repetition rather than the dependency-unavailable fallback. Actual
model/transport failures retain the controlled failure path. Call/turn limits,
three-second closing drain, recording policy and deferred notifications remain.

Recovery uses validated internal metadata, bypasses model/tools and never invents
caller utterances. Assistant delivery remains receipt-based. The existing monitor
handles echo/interruption; bounded pre-roll preserves speech beginning near the
end of the recovery prompt. Six validated runtime threshold flags retain the old
defaults and expose endpoint calibration without rebuilding.

Implementation and validation are recorded in
[the M3-01 recovery report](validation/silence-recovery-2026-10-23.md).
Full M3-01/G4 acceptance remains partial until real human/noisy pause calibration
and handset recovery acceptance are complete; synthetic model/transport checks
must not be presented as those gates. M3-02's 250 ms interruption target remains
separate. M5-01 notifications and M5-02 owner API remain owner-deferred.

M3-01 follow-up validation: final Linux build, nine CTests and 95 focused pytest
cases passed, with no skips; the separate prior 26-case turn/recovery run passed.
Five functional real-CUDA/DB synthetic calls passed. One stricter mid-prompt cutoff
attempt failed and remains documented; M3-02 timing acceptance stays open.
The idle carrier gateway and agent were updated to `natural-v5-silence-recovery`
with matching runtime arguments and healthy ASR/EMA/agent services. Handset
validation was requested and is pending. No push, PR, new recording or notification.

M3-01 handset follow-up: the owner heard the reminder and timeout farewell but
the line stayed open. Logs confirm `finish=1` followed by another recognition
turn without a confirmed interruption. This is a failed carrier closing check,
not a passed recovery gate. The gateway correction removes the unconfirmed
pre-roll override of the finish decision; confirmed interruption still resumes.
See the recovery report's handset failure section for regression and deployment
evidence. Broad M3/G4 calibration and carrier retest remain open.

Correction checks: Linux build, 9 CTests and all 8 recovery SIP tests passed;
the late-backchannel regression failed before and passed after the fix. A new
resident CUDA/isolated-DB silent PCMA call completed farewell and hangup without
fabricated caller text. `natural-v5.1-silence-close` is active after an idle
gateway-only restart with identical runtime arguments and healthy workers.
No push or raw recording. Human closing retest is pending.

## Owner-requested selectable ASR comparison (2026-10-23)

M2-01 / M5-03, §8.1 and US-02/04/06; [ADR 0008](ADR/0008-selectable-asr.md).
Implemented `ALOJAN_ASR_BACKEND=whisper|nemotron` with isolated frozen runtimes,
pinned/checksummed Nemotron weights, shared gRPC isolation/cancellation and
explicit offline evaluation tools. Whisper remains the active/default backend.

On the RTX 4080, 24 public human recordings plus 16 synthetic utterances across
four conditions produced 480 decodes in three profiles. Human PCMA WER was
11.40% for Whisper, 23.03% for Nemotron 320 ms and 23.46% for Nemotron 1120 ms.
Neither candidate justified promotion. Speaker identities are unavailable;
this is not balanced-speaker or handset acceptance.

Linux: 45 ASR tests and three evaluation checks passed. Both temporary real CUDA
workers passed seven transport/silence cases and cancellation/reuse. Nemotron
failed the existing name-spacing and spoken-number format checks; do not label
its quality validator a pass or infer incorrect numeric digits from that failure.
Whisper passed the entity checks. Temporary workers were stopped; live carrier
configuration was preserved. [Full evidence](validation/nemotron-asr-2026-10-23.md).
Persistent per-generation Nemotron caching, broader human speech, long-turn and
carrier acceptance remain open. No M5 notification work or publication occurred.

## Turkish-adapted Whisper evaluation (2026-10-24)

M2-01 / M5-03, §8.1 and US-02/04/06. Owner-requested TurkMedSTT general Turkish
large-v3 evaluation completed on Linux/RTX 4080: 320 paired decodes across the
same 24 human and 16 synthetic fixtures, plus eight silence/noise diagnostics.
Human PCMA WER tied Turbo at 11.40%; noisy/quiet PCMA improved to 22.15%/12.28%
from 24.56%/21.93%. Clean WER regressed to 7.89% from 7.24%; product-name misses
increased and human PCMA inference P50 rose from 142 to 368 ms. Synthetic literal
WER is confounded by written-number formatting. Three evaluation checks passed.
Keep the existing live/default model. No production source/configuration change
or carrier call occurred. [Evidence and reproduction](validation/turkmed-asr-2026-10-24.md).

## Response latency measurement and routing comparison (2026-10-24)

M4-01 / M5-03, requirements §3/7.4/9.1/10/12/15; US-02/05/06. Owner approved
plan items 1 and 4 only. Agent and native per-turn measurements now separate DB,
provider text, speakable phrase, model/tool steps, endpointing, ASR, TTS and output.
Failed/interrupted/disconnected turns and missing measurements remain visible;
waiting music and recovery prompts are excluded from successful response metrics.

All 72 synthetic API turns completed. Default/latency/sticky/combined median
first phrase times were 2904.5/2871.5/2907/2996.5 ms. All 96 model requests reported
cache hits. Candidate arms had 1/1/2 premature-close behavior failures; baseline
had none in this small sample. Retain default routing: no candidate met the
predeclared speed and behavior gates. No causal claim about routing and model
behavior is made. Optional routing profiles and a repeatable comparison/report
command are available. [Evidence](validation/latency-routing-2026-10-24.md).

Linux build, 9 CTests and 87 focused tests passed (86 plus one reporting test);
final affected Python recheck: 74 passed. A two-turn real CUDA/API/isolated-DB
loopback passed functional checks but measured 7238/5059 ms endpoint-to-output,
so G3 latency remains failed/open. The idle gateway and agent were updated to
`natural-v5.2-latency-observability`, retaining runtime arguments/default routing
and healthy ASR/EMA/agent workers. No ASR/EMA restart, raw recording or publication.
Full M5-03 hardening/soak and human/carrier timing acceptance remain open.

### DeepSeek model selection prepared (2026-10-24)

M4-01 / M5-03, DEC-11 and §9.1: the owner selected
`deepseek/deepseek-v4.1-flash`; see the accepted selection amendment in
[ADR 0005](ADR/0005-openrouter-agent.md). The local backend now selects that exact
model, preserves Responses streaming and reasoning `none`, and omits the
unadvertised verbosity parameter. Prompt, tools, routing and speech services are
unchanged. Mac checks: 74 agent/phrase/timing/report tests passed in 4.79 s;
Ruff lint/format and diff whitespace checks passed. These use simulated models.

Primary Linux SSH timed out repeatedly. Deployment, Linux tests, real OpenRouter
access/behavior/latency, structured summary and GPU call validation remain
pending. No live restart, new carrier acceptance or speed improvement is claimed.
The last verified live model is still the earlier Pro model; current service
health is unknown until connectivity returns. No push or publication performed.

### GPT-OSS 120B prompt evaluated; activation held (2026-10-24)

M4-01 / M5-03, DEC-11, §9.1–3, US-02/05/06: the owner superseded the undeployed
DeepSeek choice with `openai/gpt-oss-120b`, requested model-specific prompt research
and authorized activation if faster. Local source now pins Cerebras, uses supported
low reasoning and applies the provider pin to both conversation and summary.
The Hermes-informed prompt adds explicit decision rules, tool sequencing and
eight Turkish examples. Owner-authorized real Mac API evaluation measured mean
first text at 0.926–0.981 s for the revised candidate versus 4.399 s for Luna.
However, it passed only 14–15/18 automatic scenario checks versus Luna's 18/18;
novel paraphrases passed 6/8. Missing closing tools, repeated questions and some
reasoning/tool text leakage block activation. These are small configuration
comparisons, not handset or first-speakable-phrase latency measurements.
See [research, evidence and pending gates](validation/gpt-oss-120b-2026-10-24.md)
and ADR 0005. 77 Mac regression tests passed in 4.56 s. Linux remains unavailable;
Linux/DB/summary/GPU/carrier validation and deployment remain pending. No push.

### 120B reasoning and validated speech tools (2026-10-24)

M4-01 / M5-03, DEC-11, §7.4/9.1–3, US-02/05/06/08. The owner reaffirmed 120B,
allowed more reasoning below three seconds and restored Linux access. Medium
reasoning, temperature 0.2 and a 4096-token step bound are selected. Required
`respond`/`finish_call` speech tools prevent raw model reasoning or tool-shaped
text from reaching TTS. Existing-note state is explicit; identical durable notes
avoid repeated IO. Model-chosen natural closing and unconfirmed notes remain.

87 Linux regression tests passed. Real isolated DB/summary and CUDA/EMA/Whisper
PCMA loopback passed; first audio after endpointing was 1459/639 ms. Final
synthetic dialogue checks passed 37/38, with one adversarial early-close failure
still open; first usable phrase maximum was 2304 ms. The owner's development
model rollout does not close the zero-critical-failure, carrier, G3 or soak gates.
See [full evidence and rollout status](validation/gpt-oss-reasoning-2026-10-24.md).
The development-line agent now runs 120B with these settings on port 15073.
Only the idle agent was restarted; ASR/EMA/gateway were preserved and their health
checks passed. Prior live Luna source/logs remain available for rollback. Human
carrier acceptance and the recorded adversarial closing issue remain open.

## 2026-10-24 — Executive-assistant conversation repair (M4-01 / M5-03)

The owner rejected the latest carrier conversation's support dismissal and
repeated closing questions. Reviewed stored recognition/delivered speech and
sanitized timing, then refined ADR 0007 to a senior executive-assistant role.
Concrete problems now enter the note flow; contextual thanks can close a handled
request. Narrow intake recovery and bounded repair of observed generic invitations
and unsupported callback claims protect the speech boundary without extra repair
roundtrips after a durable save. Model/provider/reasoning remain 120B/Cerebras/medium.

Linux: 101 focused tests passed in 7.63 s; Ruff and diff whitespace checks passed.
Release replay: 33/33 note/completion states, not a full language-quality pass;
missing follow-up details and an overly generic answer remain documented. Real
CUDA ASR/EMA + OpenRouter + PostgreSQL native loopback passed, first audio 1,939 /
720 ms. The agent was reloaded on the idle development line; ASR/TTS/gateway kept
running. New carrier listening, general semantic validation, G3 and soak remain
open. See [evidence and limitations](validation/executive-assistant-2026-10-24.md).

## 2026-10-24 — Natural closing and researched conduct (M4-01 / M5-03)

Owner reported another storage acknowledgement after thanks. Latest carrier
records confirm one stored note but duplicate spoken acknowledgement. Added the
[researched conduct list](AGENT_CONDUCT.md) to the prompt and note-version-aware
completed-speech accounting to prevent that closing/repair repetition without
suppressing unheard or updated acknowledgements. No additional API roundtrip.

Linux: 108 focused tests passed in 7.71 s; Ruff/format/diff checks passed. Real-model
gRPC replay: 13/13 state checks, four eligible closings without repeated storage,
mean first phrase 1066 ms / max 1930 ms. Native real ASR/EMA/API/DB loopback passed,
first audio 1659 / 1540 ms. These do not close carrier listening or general
language-quality gates; see [evidence](validation/natural-closing-2026-10-24.md).
The natural-closing update is active on the development line after an idle-agent
reload. Agent/ASR/TTS health passed; the native gateway remained running. Previous
agent source/logs were retained for rollback. Owner listening remains pending.

## 2026-10-24 — One further-help question (M4-01 / M5-03)

The owner superseded the blanket invitation ban: ask once after the request is
handled, then never repeat after additions/corrections. Prompt/tool state and
completed-playback accounting implement this without another normal-path model
request. Explicit exits remain valid. Linux: 110 tests in 8.05 s; Ruff/whitespace
passed. Real-model replay: 19/19 state checks, seven conversations with one
invitation each, first phrase mean 998 ms / max 2442 ms. Missing-product elicitation
and occasional readback remain quality limitations. Development agent activated;
new carrier listening remains pending. See [evidence](validation/once-offer-2026-10-24.md).

## 2026-10-24 — Researched service practices (M4-01 / M5-03)

Owner requested international service guidance using the earlier research method.
Added six positive practices, primary-source mapping and consistent question
priority in prompt/tool descriptions; no runtime logic or media changes. Reviewed
ISO's public framework plus ICMI, Google and Retell guidance, without claiming
normative conformity. Final Linux checks: 110 passed in 7.59 s; Ruff/format and
whitespace passed. Real 120B replay: 14/14 note/finish states, mean first phrase
935 ms / maximum 1917 ms; a small sample, not a latency guarantee. Explicit empathy
and nonrepeating intention wording still need improvement. Agent activated after
idle checks; agent/ASR/TTS healthy and gateway unchanged. Private rollback snapshot:
`.local/rollbacks/service-conduct-20261024`. Carrier listening and general language
quality remain pending. See [evidence](validation/service-conduct-2026-10-24.md).

## 2026-10-24 — Adversarial dialogue review (M4-01 / M5-03)

Owner requested unusual questions, a findings-based improvement plan and reviewed
implementation. Added a reproducible real-model evaluator and 34 synthetic
conversations / 58 steps. Retained the existing prompt structure after rejecting
a broader compaction; clarified identity, complete-note updates, legitimate mixed
requests, credentials in generated notes and latest-intent closing. Narrow tool
checks prevent observed false storage acknowledgements, content-free note rewrites
and premature closing; malformed provider output recovers with clarification.

Linux: 126 focused tests passed in 8.03 s; Ruff/format/whitespace passed. Selected
real-120B evaluation: 45/46 main and 12/12 additional checks. Real-model steps
averaged 979 ms to first phrase, maximum 3208 ms; not phone first-audio latency or
a three-second guarantee. Same-turn day correction still preserves a discarded
word; mechanical acknowledgements and cold diversions remain language gaps.
The development agent was activated after idle checks; agent/ASR/TTS healthy,
gateway unchanged. Previous source/logs are in the private rollback directory
`.local/rollbacks/dialogue-review-20261024`. No new native/GPU/carrier acceptance;
M4/M5 quality gates remain open. See [review and evidence](validation/dialogue-review-2026-10-24.md).

## 2026-10-24 — Native denoising comparison (M2-01 / M5-03)

Owner authorized research of established open-source C++ options and a Linux
trial before enabling denoising. Built WebRTC AudioProcessing 2.1 (low/moderate),
RNNoise v0.2 and SpeexDSP 1.2.1 in an isolated private directory. Added a C++ probe,
pinned build recipe and paired evaluator using 24 public Turkish recordings and
16 EMA synthetic fixtures. Five speech conditions plus controls produced 1015
initial decodes; 92 additional decodes repeated the observed WebRTC-low regressions.

WebRTC low reduced white-noise human WER from 32.68% to 29.61%, but regressed fan
and quiet conditions. It worsened 23/120 human pairs; all 46 repeated comparisons
of those pairs reproduced the regression. RNNoise/Speex also failed the quality
preservation gate. Native CPU means were 0.0071/0.0070/0.1034/0.0093 ms per 10 ms
frame (WebRTC low/moderate, RNNoise, Speex); costs exclude initialization/I/O and
are not hard deadlines. Filter delay is separate. Noise-only hallucinations remain.

Decision: keep the live gateway/Whisper path unchanged. Reproducible isolated
Linux build succeeded; 14 evaluator/native-boundary checks passed in 0.11 s.
One existing Python 3.12 audioop deprecation warning remains; migrate the fixture
conversion before adopting Python 3.13. Ruff/format/clang-format/whitespace checks
passed. Agent/ASR/TTS health passed; no service restart or carrier test. Research,
limits, source pins and results are in [the report](validation/denoise-2026-10-24.md).

## 2026-10-24 — DTLN follow-up (M2-01 / M5-03)

Owner authorized DTLN after voice-agent source research. Added a pinned, verified
CPU ONNX probe and compared original full suppression, then an exploratory
time-aligned half-strength mix, against bypass on the same public/synthetic
corpus: 812 CUDA Whisper decodes. Full DTLN regressed all human conditions;
half improved white-noise WER 32.68% → 29.39% but worsened PCMA 11.84% → 12.28%,
fan/click conditions and a curated product name. Neither passes §8.1 / US-02/06.

Mean processing cost was ~0.127 ms per 8 ms hop (~1.59% of one CPU core), separate
from 24 ms overlap-add delay. This includes Python/NumPy and native ONNX inference,
not a standalone C++ gateway measurement. Original-reference parity was within
1.27e-7; 21 Linux checks passed in 0.23 s. Ruff/format/whitespace passed; existing
audioop deprecation remains. No live restart/default change, C++ port, recording
or carrier acceptance. [Evidence and limits](validation/dtln-2026-10-24.md).

## 2026-10-24 — M4-01/02 reviewed dialogue-quality candidate

The owner approved the independently reviewed plan, including limited M4-03
summary consistency. Skill Creator guided generalized prompt/tool revisions and
the natural executive-assistant tone; no case-specific correction recognizers
were added. Private speech-tool acknowledgement intent is now bound to durable
note versions and complete response playback, with partial/cancelled/late receipt
and failed-save regressions. Public contracts, storage schemas and normal-path
model request counts are unchanged.

**Release acceptance remains open; candidate not deployed.** Isolated Linux
regressions pass, but repeated real-model and independent language review expose
wrong corrected values, lost requests, closing mistakes and a synthetic credential
retention regression. Summary tests also fail semantic acceptance. The combined
candidate must not replace the live listener on this evidence. Current agent
source/runtime remains intact; no carrier acceptance or new notification is claimed.

See [complete method, results and limitations](validation/dialogue-quality-2026-10-24.md).
Further work must address general fact/correction handling with a fresh unseen
set, or evaluate the receipt repair separately. Do not mark M4 dialogue quality
complete based on deterministic tests or latency alone.


## 2026-10-24 — Real M3/M4 carrier validation

One owner-placed Netgsm call exercised pause, interruption, message correction
and closing on the existing live version. Four cancellation events and a correct
final note were observed; the system eventually initiated termination. Explicit
farewell handling failed (an optional question followed the recognized exit),
and the completed summary incorrectly marked the clear corrected date uncertain.
The owner subsequently confirmed disconnection and accepted the phone experience
as very good and comfortable. Summary improvement is deferred at the owner's
request; stored conversation text and the final message remain the review records.
The observed farewell deviation and ASR concerns remain documented. Broad M4
quality and quantitative M3 timing acceptance remain open. No candidate
deployment, restart, recording or notification occurred.
[Sanitized results and timing limits](validation/carrier-m3m4-2026-10-24.md).


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


## 2026-10-24 — Proposed endpoint-latency calibration

Owner requests a plan for reducing end-of-turn waiting and excludes LLM
optimization. A separate future Splash Engine Qwen 3.6 35B comparison is noted,
not verified or activated. The proposed M3-01 / M4-01 / M5-03 work first attributes
partial freshness, stability, detector and queue delays; then evaluates bounded
scheduling changes and, only if needed, a high-confidence faster endpoint path.
Preserve pause/recognition quality and resource cost. No implementation or live
configuration change is authorized by this planning step.
[Proposed sequence and acceptance gates](ENDPOINT_LATENCY_PLAN.md).

## 2026-10-24 — Qwen3-ASR-1.7B evaluation (M2-01 / M5-03)

Owner-requested conditional replacement evaluated under ADR 0008, §8.1 and
US-02/04/06. Real Ubuntu/RTX 4080 paired evaluation completed 320 decodes on
24 human and 16 synthetic fixtures across four conditions, plus eight controls.
Human PCMA WER regressed from Whisper's 11.40% to Qwen's 17.11%; clean/noisy
WER and product-name recognition also regressed. Quiet pooled WER improved,
but 15/24 quiet recordings worsened. PCMA human P50 was 142 versus 439 ms in
the tested Transformers runtime. Keep Whisper live/default; no promotion.

Four Linux evaluator/adapter tests, Ruff and whitespace checks passed. The
isolated Qwen evaluator reuses existing fixtures and scoring; no production
adapter, native build, carrier test or restart was needed. Qwen streaming,
lifecycle and concurrency gates remain untested; vLLM was not benchmarked.
[Full provenance, reproduction, results and limitations](validation/qwen-asr-2026-10-24.md).

## 2026-10-24 — Standard Whisper large-v3 evaluation (M2-01 / M5-03)

Owner-requested standard large-v3 test under §8.1 and US-02/04/06 completed on
Ubuntu/RTX 4080 using the existing paired evaluator and identical settings.
Human clean/PCMA/noisy/quiet WER improved to 6.14%/9.65%/24.12%/11.40% from
Turbo's 7.24%/11.40%/24.56%/21.93%. PCMA human P50 increased from about 142 to
360 ms; curated product-name misses rose from one to two. No automatic promotion:
keep the current live/default Turbo profile, with the accuracy/latency tradeoff
and broader human/service gates visible.

Three evaluator checks passed. No production source change, native build,
service restart or carrier call. Independent endpoint-latency work on the shared
host was preserved; the final report distinguishes its additional resident worker
from this evaluation's GPU allocations and timing limitations.
[Results, exact provenance and reproduction](validation/whisper-large-v3-2026-10-24.md).


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

## 2026-10-24 — Standard large-v3 speed study (M2-01 / M5-03)

Owner requested acceleration research under §3/8.1 and US-02/04/06. Seven real
CUDA decoder profiles, component timing and a targeted regression repeat produced
1,169 measured decodes. INT8/greedy reduced human PCMA P50 from 359 to 288 ms but
lost quality; plain INT8 retained PCMA/quiet pooled WER at 334 ms but regressed
clean WER. INT8/beam-three reached 320 ms but fabricated a subtitle-like phrase
in a quiet synthetic closing, reproduced three times. No profile passes all
quality-preservation conditions. FlashAttention failed as unsupported.

Three evaluator checks passed and the reference wrapper reproduced all 160 prior
transcripts. About 79% of human inference wall time was decoder generation.
Prioritize an isolated TensorRT-LLM engine experiment, followed by measured partial
coalescing and bounded cross-call batching; these are untested follow-up paths,
not delivered performance or capacity. No production source/runtime changes,
restart or carrier acceptance. [Measurements and plan](validation/whisper-large-v3-speed-2026-10-24.md).

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
