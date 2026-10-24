# Call acceptance and external validation

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
| EXT-08 | Owner Telegram bot token and verified private chat | M5-01 | Verified 2026-10-24: owner private chat paired, labeled test delivered; real post-call receipt pending |

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


## 2026-10-24 — Reported recovery and source consolidation

The owner subsequently reported the direct carrier line working again and
suspected a provider incident. This is owner-reported recovery; the upstream
cause was not independently established and no new scripted carrier acceptance
was completed. The subsequent main-publication request consolidates source only.
Linux loopback checks and the merged agent's synthetic API results are recorded
in [the publication report](validation/main-publication-2026-10-24.md); they do
not replace handset acceptance. Live services were not restarted for publication.


## M5-01 Telegram preparation — 2026-10-24

[Isolated Linux evidence](validation/telegram-2026-10-24.md): 22 tests passed with
synthetic Telegram transport and real PostgreSQL in disposable schemas. No live
voice process was restarted. The real owner private chat is now paired and a
labeled Telegram test was delivered and owner-confirmed. The independent worker
is enabled/running. G5 still needs a fresh completed phone call correlated with
one delivered outbox receipt and the owner's received notification; the first
check found no calls ending after activation. Include a failed summary case;
verify that no message is sent before the persisted call end.


M5-01 display-name follow-up: Telegram call and setup-test titles now use Alojan,
as requested by the owner. Linux notification tests: 17 passed in 1.61 seconds.
Notification worker active after restart; no new handset acceptance is claimed.


M5-01 dialogue follow-up (ADR 0010): 33 Linux tests passed (5.42 seconds, no skips).
The live worker now includes number, stored call time, summary and final dialogue.
Long recordings here mean text records, not audio: numbered text parts resume from
the last stored receipt. Real phone acceptance must compare all recorded turns
and speaker labels with the delivered parts; no new-format carrier pass is claimed.


## M1-04 caller identity / M5-01 notification follow-up — 2026-10-24

Private SIP-only observation of an owner test call found a national-format caller
number in `From`; no asserted-identity header was present in that observed INVITE.
The live gateway rejected the number because national conversion was disabled.
The Netgsm launcher now enables the existing Turkish normalization policy, with
an explicit opt-out. Linux launcher tests: 2 passed (0.04 seconds); existing native
caller-identity suite: 1/1 passed (1.04 seconds). The gateway was restarted while
no database calls were active; other launch arguments were preserved.

Pending handset check: place a fresh direct call, verify the persisted normalized
caller number and identity source, then correlate its Telegram delivery receipt
and owner-visible number. This finding does not establish forwarded or withheld
caller behavior. Raw signaling capture is stopped and stored only in private
ignored files; no raw audio capture was enabled.


## Standard large-v3 carrier ASR activation — 2026-10-24

M2-01 / M5-03: the owner requested standard Whisper large-v3. The live ASR worker
now uses the verified standard model with unchanged FP16/beam-five settings.
45 Linux regression tests and seven synthetic real-GPU gRPC cases on the live
worker passed; cancellation, recovery and model readiness passed separately from
phone acceptance. See [activation evidence](validation/whisper-large-v3-live-2026-10-24.md).
Next handset validation should cover quiet speech, names, dates, phone numbers,
turn pauses and interruption, and compare transcript accuracy and response delay.
Do not infer a handset pass from synthetic checks or the earlier pooled WER study.


Standard large-v3 owner follow-up: the owner reported a successful live call after
activation. The latest persisted call was ended, with caller number present
(`gateway_hint`); ASR, TTS and agent remained SERVING. This is one-call subjective
acceptance, not a transcript WER or latency-target pass. Telegram number display,
noisy cases, concurrency and soak checks are not established by this report.
