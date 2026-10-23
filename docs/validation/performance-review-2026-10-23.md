# Voice performance and correctness review

Date: 2026-10-23. Branch: `codex/performance-review`.
Scope: owner-authorized M5-03 observability/performance work, M4-01/02/03 fixes.
Acceptance: requirements §3, §7.3–4, §9–11, §14–15; US-02/05/08.
M5-01 notifications and M5-02 owner API remain deferred by the owner. This review
covers the agent, its database writes and the native speech path, not a security
certification or the entire repository. Existing M3/M4 work remains uncommitted.

## Findings and changes

| Priority | Finding | Resolution / remaining work |
|---|---|---|
| P1 | A delivered readback could remain eligible for confirmation after an intervening unrelated caller turn. A late playback receipt could re-arm it. | Confirmation now requires the immediately following turn and the unchanged note version. Receipts are tied to the turn that generated them. Regression covers unrelated turns and late receipts. |
| P1 | Summary input selected the earliest 100 utterances, losing later corrections. A summary retry could update JSON but leave indexed subject/action/urgency stale. | Select recent utterances under a 12,000 UTF-8 byte cap, restore chronological order, and update summary columns consistently. Real PostgreSQL regressions cover both. |
| P2 | Streaming waited for sentence punctuation or 240 characters, even when a complete long clause was ready. Periods in numbers/titles could split speech incorrectly. | Start at sufficiently long comma/semicolon boundaries (40 characters and four words). Preserve common Turkish titles, decimals and ordinals; retain the 240-character bound and immediate ordinary sentence endings. |
| P2 | Aggregate last-turn timing concealed the distinction between waiting audio and the actual answer. | Add per-phrase kind, ASR-finalization, endpoint-to-output, phrase-ready-to-output and TTS-first-chunk timings. Native tests verify both codecs and distinguish waiting audio. |
| P1, open | Agent call state stops admitting new calls at 128 retained calls; speech generation tombstones stop at 4096 identities. | Safe lifecycle/restart reconciliation remains required for continuous operation. Do not simply evict cancellation records and allow stale generations to revive. |
| P2, open | Input admission pauses while final ASR completes; continued speech in that interval may be lost. | Needs a bounded handoff regression with resumed caller speech before changing the media ownership rules. |
| P2, open | TTS phrases are synthesized sequentially after previous playout/receipt completes. | New timings expose the queue/transport cost. Prefetch requires cancellation and exact sent-audio accounting tests before adoption. |

ASR still decodes a bounded full prefix every second with beam size five. This
is a potential long-utterance cost, not a proven dominant cause in these calls.
Changing decode quality or endpointing without Turkish pause/noise evaluation
would trade correctness for an unmeasured speed claim.

## Research and decisions

Retell recommends diagnosing per-call components before changing model, prompt,
provider or endpointing. Its metric separates LLM first speakable chunk from
TTS first byte; server metrics exclude the final network trip. We applied that
measurement discipline and compared the selected model's routing and prompt.
Sources: [latency troubleshooting](https://docs.retellai.com/reliability/troubleshoot-latency),
[actual latency definitions](https://docs.retellai.com/reliability/check-actual-latency).

ElevenLabs describes starting speech from sufficiently long clauses and emitting
at most one filler on a soft timeout. Filler changes perceived silence, not the
model's completion time. We adopted clause boundaries and explicitly classify
the existing waiting phrase separately. Their suggested three-second soft timeout
is not automatically a good calibration for this Turkish phone workflow.
Source: [conversation flow](https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow).

OpenRouter supports latency-based provider sorting, but lower provider time to
first token does not guarantee faster usable tool output. The actual experiment
below did not justify changing production routing. Source:
[provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

No hosted orchestration platform, dependency, model, voice or provider default
was substituted. Speculative LLM work is not enabled; partial ASR must never
commit a note or produce unconfirmed response audio.

## Controlled experiments

Actual SDK/OpenRouter requests used the same `openai/gpt-6-luna-pro`, two synthetic
note requests, three repetitions per case and alternating variant order. Each
variant had six samples, all with an unconfirmed draft, exact readback and
confirmation question. These boolean checks are not a full semantic evaluation.
No carrier call or notification was made.

| Comparison | Baseline median / maximum | Candidate median / maximum | Decision |
|---|---:|---:|---|
| Default vs `provider.sort=latency` | 2795.5 / 2914 ms | 2635.5 / 5548 ms | Retain default; tail became worse |
| Current vs compact system instructions | 3006 / 3874 ms | 2859.5 / 4623 ms | Retain current; small sample and worse maximum do not establish a reliable gain |

These are time to the first usable backend reply, including local tool execution
with a synthetic in-memory save. They exclude ASR, durable database latency and
audio. The two baselines were collected at different times. Six samples cannot
establish production P95 or causality under variable provider load.

A separate controlled stream supplied a complete Turkish clause immediately and
the remainder 1.1 seconds later. The unchanged baseline service waited 1103–1105 ms
for meaningful text; the clause version emitted it in 1 ms. With the resident
CUDA EMA worker, first meaningful PCM arrived at 1111–1125 ms versus 7–8 ms
(three samples each). This isolates approximately 1.1 seconds of avoidable text
buffering **in that fixture**, not faster model inference. It has no ASR, paced
RTP, waiting-phrase playback or handset network. Short replies that already end
with punctuation do not gain this amount. Caller fixtures are synthetic.

## Measurement contract

`AgentEvent.detail_json.kind` is additive: `response` or `waiting`; omitted means
`response` to preserve compatibility. Unknown kinds fail closed in the native
consumer. Existing phrase index, byte, queue, generation and deadline limits stay.

Native `sent_speech` records now include:

- `endpoint_to_audio_ms`: ASR half-close to the first PCM frame handed to the
  output port for this phrase, including any earlier phrase playback.
- `asr_finalize_ms`: ASR half-close through final stream completion.
- `phrase_ready_to_audio_ms`: receipt of this phrase from the agent through its
  first output-port frame, including queued playback and TTS work.
- `tts_first_chunk_ms`: synthesis request to first valid PCM frame.
- `kind`: waiting or substantive response; no audio means a timing of `-1`.

These are server-side monotonic timings. Endpointing silence precedes half-close;
handset/network playback follows the output port. They are not full caller-stop
to-ear latency. Sent-history logs currently appear on successful dialogue completion;
failed/disconnected calls need additional lifecycle telemetry. Agent logs retain
first phrase versus first substantive text timings. Never treat filler as a
successful substantive-latency sample.

## Validation and delivery

Validation results and activation are recorded below after final Linux checks.
The full acceptance target remains 50+ timed Turkish turns, P50 below 1000 ms,
P95 below 1800 ms, labeled interruption/pause/noise cases and a 30-minute soak.
No ElevenLabs/Retell parity is claimed. Existing owner-reported waiting remains
failed experience evidence until a new human carrier test succeeds.

Final Linux results:

- Native build succeeded; 8 CTests passed in 2.31 seconds.
- Agent/phrase/PostgreSQL/native dialogue suite: 39 passed in 107.67 seconds,
  no skips, one known `audioop` deprecation warning. Earlier run: 39 passed in
  107.94 seconds. The later exact-goodbye change touched Python only; its final
  agent/phrase/PostgreSQL run passed 35 cases in 6.94 seconds. The unchanged eight
  native dialogue cases remain covered by the preceding run.
- Mac final agent/phrase checks: 34 passed in 4.49 seconds. Ruff check/format,
  affected native clang-format and `git diff --check` passed separately. One
  intermediate test had an incorrect expected character count (18 instead of
  19); the assertion was corrected before final passing runs.
- Real adaptive PCMA loopback with CUDA ASR, resident CUDA EMA, actual OpenRouter
  and isolated PostgreSQL passed a two-turn confirmation and post-call summary.
  First substantive output: 3739 ms after ASR half-close; ASR finalization:
  138 ms; agent substantive text: 3581 ms; first response TTS chunk: 7 ms.
  Waiting audio began at 960 ms and is excluded from the substantive result.
  Confirmation closing began at 138 ms (agent text 18 ms).
- An additional exact-goodbye fast path now closes without an unnecessary model
  request. It does not confirm a draft. Exact phrases use the existing stop
  policy; negated/expanded utterances continue through the model. Four regression
  cases cover stopping, unchanged unconfirmed notes and a negated stop.
- A second real adaptive GPU/API/DB call ended with the synthetic phrase
  `Aramayı bitir.`. Closing output began at 139 ms after ASR half-close (ASR
  107 ms, agent 15 ms, TTS first chunk 5 ms). The draft remained unconfirmed;
  the post-call summary succeeded. Its first substantive response still took
  3499 ms. The validator's `--goodbye` flag reproduces this alternative outcome.

The real checks use synthetic caller speech and loopback SIP/RTP; they are not
new carrier or human-quality acceptance. The first substantive response remains
too slow for the stated target. Clause streaming and explicit-stop routing remove
specific unnecessary waits; neither makes the selected model consistently fast.

After the checks, the idle development listener and agent were restarted with the
reviewed source. ASR/EMA/agent health checks and gateway readiness passed. Gateway
binary SHA-256: `8487fd16f3d26836c6538735d8d58977601af7e3e4511f991f7d21390f319a7b`.
Private previous-runtime snapshots are in `.local/carrier-before-performance-agent`
and `.local/performance-baseline`; the existing M3 emergency rollback remains
available. Source checksum comparison between Mac and Linux was clean. No secrets,
recordings, virtual environments or binaries were synchronized into source control.
No commit, push, PR, merge or notification was performed.
