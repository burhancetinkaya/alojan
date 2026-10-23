# Linux native turn detection — 2026-10-23

Task M3-01, US-04/06, requirements §7.2; branch `codex/turn-detection`.
Primary development/build/test host: authorized Ubuntu GPU server under ADR 0003.
The owner requested continuation after accepting the live carrier greeting.
No publication, merge, new external service or live adaptive carrier change occurred.

## Delivered behavior and boundaries

An opt-in C++ adaptive single-turn profile now combines real Silero v6.2 ONNX VAD,
Smart Turn v3.2 CPU completion, a bounded current ASR partial and explicit last-question
context. Speech/end decisions stay in the native bridge; media callbacks only enqueue
PCM. Eight seconds of in-memory history, one pending Smart Turn job per call, stale
candidate epochs, a one-second score age bound, a model watchdog and existing
RPC deadlines/cancellation preserve the stream boundaries. The default accepted
AI greeting/fallback process remains running on its original binary.

The additive `RecognitionEvent.processed_audio_ms` field distinguishes decoded
coverage from result arrival time. Old fixed-capture clients remain compatible;
adaptive clients require updated ASR coverage and a final matching the half-close.
No transcript or caller audio is stored. All audio used in this report is synthetic.
The response is still the approved fixed EMA unavailable closing, not a GPT answer.

## CPU numerical calibration

All six cases passed against pinned Python reference interfaces: digital silence,
seeded low-level noise, impulse, synthetic Turkish phone fixture, that fixture plus
500 ms silence, and a short fragment. Native Whisper feature max error stayed below
`7.69e-6`; Silero stateful outputs matched exactly in these cases. Smart Turn native
inference matched Python on the *same* features within `1e-5`. Dynamic int8
quantization amplified the tiny native/reference FFT difference to approximately
0.00744 probability on one case; all 0.50/0.75 threshold decisions agreed. The
separate allowed drift bound is 0.02, not a claim of bit-identical preprocessing.

Full native feature extraction plus completion inference took 64.8–66.8 ms in the
Debug build on this host. Python reference VAD averaged 0.069–0.103 ms per 32 ms
block; this is not a native VAD P95. Silence/noise can receive high Smart Turn
completion probabilities, so a real VAD speech gate and current nonempty transcript
are required. These numerical fixtures do not establish real human turn accuracy.

Ignored evidence: `.local/turn-calibration-2/result.json`; source/reference pins
and license limitations are in [DEPENDENCIES](../DEPENDENCIES.md).

## Regression found and corrected

The first labeled two-second pause failed: the test call closed before resumed
speech crossed Silero's 0.50 confidence. Adding the 200 ms endpoint pad alone was
insufficient. A separate G.711 reference check showed confidence remained below
0.50 for about 216 ms after audio resumed, with lower-confidence onset already
present. The detector now also invalidates stale scores at probability 0.10 and
holds decisions until 200 ms without that candidate. This hint cannot create a
turn or establish transcript coverage. The failing two-second scenario then
passed; a deterministic native test separately guards low-confidence resumption.

The incomplete-phrase wait remains two seconds plus 200 ms endpoint pad. A phrase
that remains incomplete/unknown uses the existing local unavailable fallback;
it is never silently promoted to a complete user instruction. A continuous
low-confidence/noisy candidate may delay decisions until the 20-second test capture
ceiling. Broader noise calibration remains open.

## Verification

The full frozen Linux suite passed **175 pytest tests**, with no skips, in
434.96 seconds; its only warning is the known Python 3.12 `audioop` deprecation.
All **7 CTests** passed in 2.31 seconds. Native compilation, Ruff check and format
check passed (36 Python files). The two new CTests exercise adaptive policy and
deterministic model timing/fault behavior without claiming real-model readiness.

Fourteen new pytest cases cover real CPU detectors over SIP/RTP: both codecs,
labeled 500/1000/1500/2000 ms inserted pauses with an explicitly incomplete fake
ASR hypothesis, unresolved/invalid text, silent input, hangup/reuse and invalid
configuration. Existing M0/M1/M2 regression tests remain in the full total.
The strengthened hangup test separately waits for the second call's own capture
event so it cannot consume its synthetic phrase during the earlier greeting.
That final strengthened case passed separately in 23.57 s (13 unrelated cases
deselected, not skipped).

The final actual CUDA run used a temporary updated ASR worker on a separate
loopback port, the resident EMA worker and real native CPU detectors. Both local
SIP calls passed complete output-reference matching, monotonic RTP timestamps
and 20 ms pacing. Each returned seven partials and a nonempty final before all
200 EMA frames (four seconds) were sent. Transcript content/accuracy is not an
acceptance assertion in this timing test.

| Metric | PCMA | PCMU |
|---|---:|---:|
| Input frames (20 ms each) | 356 | 357 |
| VAD-last-speech to accepted boundary | 1104 ms | 1124 ms |
| Half-close to first EMA PCM | 126 ms | 133 ms |
| Half-close to first output-port PCM | 139 ms | 138 ms |
| VAD-last-speech to first output-port PCM | 1243 ms | 1262 ms |
| Last observed background detector duration | 98 ms | 98 ms |
| Mean RTP packet interval | 20.001 ms | 20.001 ms |
| Closing reference relative RMS error | 0.01338 | 0.01402 |

The roughly 1.25 s response observation includes waiting for the ASR worker's
one-second partial cadence and stability check. It is not handset latency,
P95 or GPT response time. Host GPU peak during these calls was **4,995 MiB**,
including both the preserved resident ASR and the temporary updated ASR plus EMA;
this is not the normal single-ASR deployment footprint or a warm-up maximum.
Only the temporary ASR process group was stopped afterward.

Ignored final evidence: `.local/turn-cuda-final/result.json`,
`.local/m3-pytest-final.log`. No real carrier audio or transcripts were captured.
Tests using fake ASR/TTS are not interchangeable with these real-model calls.

## Final artifact and compatibility checks

- The native build with `ALOJAN_TURN_MODELS=OFF` succeeded separately; both
  deterministic turn executables passed and adaptive CLI activation was rejected
  before readiness. The normal feature-enabled binary was not replaced by this check.
- Regenerating Python/C++ protobuf bindings with the pinned tools left every
  generated source hash unchanged.
- Final whole-project Ruff check/format passed (36 files); changed C++ sources and
  tests passed clang-format. A docstring-only formatting mismatch found during the
  final audit was corrected and the checks rerun successfully.
- Feature-enabled gateway SHA-256:
  `66e6cf42117048fbd267fb3e1277789fe15f7dcbb845cbe252ad4ae55349cf6d`.
- The running carrier gateway still mapped the original binary SHA-256
  `624ed461fce0832c89da2e3cbee5c97ecdc10a73377261417ec0f1948238036c`.
  Both resident recognition and synthesis health endpoints reported `SERVING`.
- Source and documentation were copied to the authorized Linux project; private
  artifacts, model files, environments and graph caches stayed excluded. Existing
  uncommitted foundation work was preserved. No commit, push or PR was created.

## Remaining acceptance

The native single-turn core is implemented; parent M3-01 acceptance is partial.
Human/spontaneous/noisy Turkish pause testing, runtime threshold configuration,
and the once-at-seven-seconds silent-caller reminder remain open. The reminder
needs the upcoming outbound-reference/echo policy to preserve safe listening.
M3-02 barge-in/backchannel and aligned sent-text accounting, M4 dialogue, full G3/G4,
carrier adaptive tests, production supervision, soak, Mac model verification,
clang-tidy and hosted CI have not been completed here. The ONNX watchdog rejects
late output but cannot preempt a stuck native call; cleanup can wait for it.
