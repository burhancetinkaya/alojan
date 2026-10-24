# Implementation plan

## 2026-10-24 — Configurable capacity: five per host, fifty total

The owner superseded the two-call proposal with a 50-concurrent-call architecture
and per-server limits; the current Linux target is `max_calls = 5`, with excess
calls rejected busy. [CAP-01–09](CALL_CAPACITY_PLAN.md) replaces C2-01–08 and maps
implementation, infrastructure sizing, load tests and rollout to M0–M6 / US-01–08.
[ADR 0009](ADR/0009-call-capacity.md) records the accepted target and proposed
Kamailio/RTPengine plus complete-call-server topology. Primary-source research and
planning are complete. Five/50-call GPU/API/carrier acceptance, implementation and
activation remain pending; current live configuration is unchanged.

Updated: 2026-10-24. Status: **Linux GPU server development/build/test authorized and in progress**.

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
| M5-01 | Durable private Telegram outbox; owner-selected 2026-10-24. Bot pairing and real delivery acceptance required. | M4-03 local checks; EXT-08 for actual delivery | US-07; §10,11 | macOS; later Ubuntu + endpoint | Retry/restart/deduplication locally; actual notification pending G5; no exactly-once claim |
| M5-02 | Private REST endpoints and HTTP-only Cloudflare Access guide | M4-03 | §10,12; P0 API | macOS; later Ubuntu | Auth/owner-only retry enforced; live/ready distinct; no dashboard required |
| M5-03 | Observability, retention/backup restore, failure injection and soak | M5-01,02 | §3,12,14,15; G4,5,7 | Ubuntu GPU/phone | 30+ labeled scenarios, 50+ timed turns, two-call isolation and 30-minute soak; report targets versus measured values |
| M6-01 | Compare direct, forwarded and withheld caller identity | M1-07; EXT-03 | US-03; §13; G6 | Phone + carrier | Sanitized header comparison; no caller identity guarantee |
| M6-02 | Test manual/assisted iOS Focus forwarding and document limitations | M6-01; EXT-04 | US-09; §13; P1 | Owner iPhone | Owner-authorized enable/status/disable tests; no assumed unattended USSD support |

The owner selected private Telegram notifications on 2026-10-24, replacing the generic-webhook default. Bot credentials and paired recipient stay private; see [setup and delivery policy](TELEGRAM.md). P1 dashboard, contacts and live MCP integrations remain deferred. M6 is a separate carrier/device feasibility report and must not conceal an otherwise functional P0 as either proven or broken without evidence.

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


## 2026-10-24 — Owner-authorized main consolidation

M2-01, M3-01, M4-01/02 and M5-03 accumulated source/evidence from the three working
checkouts is consolidated on a separate publication branch. Merge regressions
cover semantic acknowledgements together with explicit repetition. ASR/denoise
experiments and the capacity design retain their documented acceptance limits.
See [publication checks and unresolved quality gates](validation/main-publication-2026-10-24.md).
The owner requested main publication; this action does not restart live services.


## 2026-10-24 — Private Telegram notifications (M5-01)

The owner requested automatic post-call messages to their own Telegram bot,
superseding the historical notification deferral. US-07/08 and §9.4/11/12: an
independent worker uses finalized summaries, queues one frozen payload per call
and configured target, and preserves retries across process restarts. Failed or
stalled summaries produce a status-only message. Activation excludes historical
calls; recipient pairing requires a fresh challenge in a private chat. No voice
prompt, model, media code or running voice process is changed.

Isolated Linux validation passed: 22 tests, zero failures/skips, 4.56 seconds;
Ruff lint/format checks and the systemd user-unit verifier passed. Coverage includes
the real Store end/summary lifecycle with synthetic Telegram transport, restart,
concurrent enqueue/delivery, 429 backoff, exhausted/permanent errors, summary
failure, message bounds and private-chat pairing. The owner subsequently supplied
bot credentials: real getMe identity verification passed, the additive live DB
migration applied, and private-chat challenge pairing completed. The labeled
Telegram test received a provider receipt and owner confirmation. The independent
user service is enabled and active/running with zero restarts; linger is enabled.
A first check found no calls ending after activation and no outbox rows, so a fresh
phone call with a correlated delivery receipt is still required for G5.
See [Telegram setup](TELEGRAM.md) and [validation](validation/telegram-2026-10-24.md);
no publication or real post-call acceptance is claimed; the labeled setup test was delivered.


### Telegram display name follow-up

M5-01 / US-07: the owner selected Alojan as the Telegram notification name.
Both the call title and setup-test message now use Alojan. The isolated release
passed all 17 notification tests on Linux (1.61 seconds); Ruff and diff checks
passed. The notification worker was restarted and verified active. No pending
messages required a title update. Voice services and prompts were not modified.
