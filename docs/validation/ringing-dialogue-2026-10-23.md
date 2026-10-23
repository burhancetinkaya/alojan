# Ringing delay and duplicate-question follow-up

Date: 2026-10-23. Tasks M1-03/M1-06 and M4-01/02; US-01/02/05.
Owner request: ring for at least three seconds before answering, and investigate
repeated questions in the latest two carrier calls. No model/provider change.

## Carrier evidence before the change

Read-only PostgreSQL and current gateway-log inspection covered the two latest
real calls. No raw recording was enabled. No private transcript is copied here.

- Earlier call: seven caller turns, one confirmed note, normal closing after
  approximately 72 seconds. In turns 3 and 4, two differently worded requests for
  the same missing information were fully sent within each single response.
  This is not duplicate delivery of an identical database row. Several ASR texts
  were unclear; without a consented source recording their accuracy is unknown.
  Two interruptions were also recorded.
- Latest call: remote disconnect after approximately five seconds, no utterances
  or note. It cannot provide evidence about question repetition.
- Both calls entered 180 and 200 at zero milliseconds in gateway timing.

## Changes and diagnosis limits

The carrier launcher now selects 3000 ms. The native timer starts after sending
180 Ringing, preserving cancellation, admission policy and immediate answering
for explicit zero-delay local profiles. The existing 400 ms greeting lead-in is
separate from the pre-answer ringing interval.

The agent previously forwarded every output-text delta, including commentary
and final-answer messages. This permits draft and final versions of a question
to be spoken together. Real synthetic API probes confirmed that the selected
provider returns both commentary-only and final-answer-only responses. Eight
pre-change probes did not reproduce a mixed response. Historical carrier data
has no message-phase metadata, so this path is a demonstrated code defect and
plausible cause, not a proven reconstruction of those calls.

Commentary is now buffered and discarded when a final answer or successful tool
readback exists. Final-answer and legacy phase-less deltas still stream without
waiting for completion. A commentary-only response uses its last message once,
after successful completion; cancellation/failure never flushes that buffer.
The prompt explicitly requires one final spoken response, waiting after a
question, and using already supplied information. No fuzzy text deduplication
or suppression of legitimate correction/readback is introduced.

## Validation

- Mac: initial focused run had 38 passes and one test-fixture error (missing SDK
  function-call ID); the fixture was corrected before Linux validation.
- Linux native build and nine CTests passed (2.30 s).
- Linux focused agent, PostgreSQL, SIP and dialogue suite: 62 passed, no skips,
  145.14 s, one known Python 3.12 audioop deprecation warning. Two additional
  streaming/cancellation cases passed separately (0.81 s); final answers arrive
  before model completion and cancellation does not leak buffered commentary.
- Ruff, clang-format, shell syntax and diff whitespace checks passed. Source
  changes were synchronized to Linux; no secrets or host artifacts were copied.
- Real OpenRouter, selected Pro model: three synthetic checks passed for one
  question, reuse of a known name, and a corrected day requiring new readback.
  These checks use in-memory synthetic notes and make no external writes.
- Synthetic adaptive PCMA call with real CUDA ASR/EMA, OpenRouter and isolated
  PostgreSQL passed: two turns, confirmed note and post-call summary. First
  response output was 4379 ms after ASR half-close, confirmation 140 ms; waiting
  music 3420 ms. These are not handset timings or improved latency claims.
- Idle-line activation passed with previous binary, arguments, agent backend
  and logs backed up privately. Gateway PID 1911306, agent launcher PID 1911242.
  Active arguments verified 3000 ms and v4 greeting; all three worker health
  checks passed. Binary SHA256:
  `a1cd64fb8d1b8ab1c93f73fa3b0035521908adf246ef05a26b5485a4584b32aa`.

Handset ringing duration and dialogue acceptance require a new human call.
No claim that all repetition, ASR accuracy or latency targets are solved.
