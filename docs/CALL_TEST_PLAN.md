# Call acceptance and external validation

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
