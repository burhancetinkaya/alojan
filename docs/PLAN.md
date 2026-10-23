# Implementation plan

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
| M3-01 | Native adaptive single-turn core implemented; full acceptance partial | Pinned Silero/Smart Turn CPU inference, fresh ASR coverage, contextual timing and bounded background decisions. [Turn evidence](validation/linux-turn-detection-2026-10-23.md). Synthetic 0.5–2 s pause/failure checks and real CUDA local calls are separate from human/carrier quality. Silent-caller reminder, runtime threshold configuration and broader human/noisy calibration remain open; M3-02 now has a separately validated native interruption core; M4 dialogue is now implemented separately; carrier latency acceptance remains open |
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

## M3-01 continuation boundaries

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
