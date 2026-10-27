# Interruption evidence and recovery trial — 2026-10-27

M3-02/M5-03/VXP-06; US-05/06; ADR 0003/0014. The owner authorized an isolated
trial and conditional deployment only if results were satisfactory. Preserve
Silero and its thresholds. No live deployment, number change or carrier call.

## Decision

The first candidate does **not** qualify for live activation. Requiring fresh ASR
text avoids the no-transcript sustained interruption, but also misses callers when
ASR is empty and delays them when ASR is late. Fresh background-speaker words
still trigger an interruption. Do not confuse successful test assertions that
reproduce these limitations with passing acoustic acceptance.

Post-interruption recovery is promising separately: a capture that previously
ended with `incomplete_turn` instead requests clarification, then accepts a new
caller turn. It does not establish speaker identity or fix the false interruption.
It currently retains the existing 20-second capture limit; recovery latency is
not improved. No automatic replay or regeneration of interrupted answers is added.

On 2026-10-27 the owner ended this experiment. Its source and test harness were
archived under ignored `.local/`; the publication tree restores the previously
qualified default implementation. The following describes the archived trial.

## Candidate and isolation

`--interruption-evidence-trial 1` is off by default and rejected outside unmanaged
loopback tests, including managed service routing. The SpeechBridge constructor
also rejects the trial for managed calls. No database, release schema, user-facing
setting, external API, model, paid dependency or media-callback work is added.

The candidate reuses existing echo rejection and 192 ms VAD evidence, then
requires fresh, nonempty, non-backchannel ASR text. The existing 640 ms no-text
fallback is disabled **only inside the trial**. This intentionally simple first
candidate tests whether text corroboration is enough; energy/onset fusion, AEC
and speaker-conditioned models have not been implemented or measured here.

If the immediately preceding response was interrupted and capture reaches its
limit without an accepted turn, the trial emits the existing `clarification`
control event once per call. A repeated occurrence uses `silence_timeout` for a
polite ending. Protocol errors, cancellation and queue overflow remain failures;
the recovery does not fabricate caller text or dispatch business tools. Speech
uses a fresh generation, with existing cancellation and sent-audio accounting.

## Experiment design

Primary Linux host, real native Silero/Smart Turn, loopback SIP/RTP PCMA, real
gRPC with **explicitly scripted ASR/TTS and agent inference**. Known synthetic
telephone speech is reused. Tests control whether monitor ASR returns empty text,
fresh background words, a fresh correction or a correction delayed to 1.5 s.
These are protocol/decision counterexamples, not real room-noise recognition
accuracy, production failure rates or a CUDA benchmark. No private recording.

Identical audio can represent a caller or another person; the input contains no
speaker ownership reference. Reporting both interpretations prevents falsely
crediting a rejected caller as successful background suppression.

| Controlled case | Current behavior | Candidate |
|---|---|---|
| Sustained speech, empty ASR | Interrupt at 701 ms | No interruption in 4 s; also misses a real caller |
| Fresh background words | Interrupt at 271 ms | Still interrupts at 276 ms |
| ASR text delayed to 1.5 s | Interrupt at 705 ms | Interrupt at 1550 ms, about 845 ms later |
| Post-interruption capture limit | Error fallback | Clarification, listening, then valid caller turn |

The complete 760 ms EMA "Bir dakika" fixture was additionally tested at original
and quarter amplitude. With scripted fresh text, decisions were at 271/311 ms;
with text delayed to 1.5 s they were at 1506/1510 ms. All four were detected,
but the delayed cases respond after the short phrase has already finished.
Fixture SHA-256:
`e58d0de363b4b17f85eb74c55571dee8a927ad3bc3933760528593b4836fdd67`.
These runs use the fixture's original amplitude, unlike the peak-normalized
offline filter sweeps; do not compare absolute times across those experiments.

Times start at synthetic clip injection, not hand-annotated speech onset. Single
paired runs are diagnostic observations, not latency percentiles. The fast-ASR
stub can emit every 20 ms, so its performance is not a serving-ASR claim.

## Verification

- Linux native build: passed with four jobs; serving containers untouched.
- CTest: 11/11 passed, 3.82 s, including default-policy and trial boundary checks.
- Initial loopback trial: 10/10 passed, 172.37 s, no skips. Includes CLI serving
  restrictions and the failed quality hypotheses above.
- Short/quiet correction and repeated-recovery checks: 5/5 passed, 128.85 s,
  10 deliberately deselected, no skips. The repeated failure requested clarification
  exactly once, then completed the existing polite timeout farewell without fallback.
- Default cancellation/monitor regression: 8/8 passed, 166.32 s, 7 deliberately
  deselected, no skips. Includes PCMA/PCMU cancellation and old-output fencing,
  short/repeated acknowledgments, monitor hangup/service reuse and invalid ASR
  coverage rejection. The last received old-tone packet was 1.31/0.14 ms before
  the recorded decision in these runs; this is not end-to-end interruption latency.
- Linux clang-format dry run and Ruff lint/format: passed for changed sources.
- Task diff reviewed; whitespace check passed; Mac/Linux source hashes matched.
- The existing Python 3.12 `audioop` deprecation warning remains.
- Knowledge-graph refresh attempted twice; tool transport closed, refresh pending.

Private evidence is under `.local/evidence-trial-20261027/` on Linux. The original
development gateway binary is saved separately; the serving binary was never
replaced. Scripts, source and reports are retained for reproducibility. Real ASR,
EMA, native load/soak and handset qualification were not attempted after the
candidate failed the early decision-quality gate.

## Reproduction status

The rejected candidate and its harness are retained only in private development
snapshots; they are not part of the published or serving source. The measurements
above are historical evidence, not a reproduction command for the release tree.
