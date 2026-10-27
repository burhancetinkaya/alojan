# M3-01 silence and incomplete-input recovery

Date: 2026-10-23. Tasks: M3-01, M4-01 transport integration.
Acceptance mapping: US-04/US-06, requirements §7.2; ADR 0003/0007.
Branch: `codex/silence-recovery`, preserving earlier uncommitted ASR/prompt work.
Primary environment: authorized Ubuntu host, native gateway and resident CUDA
speech workers. No carrier calls are placed by these validators.

## Behavior and boundaries

- One reminder per call after seven seconds of quiet listening, excluding
  greeting, model processing, waiting music and assistant playback. Low-confidence
  voice activity postpones it. Confirmed speech uses normal endpoint decisions.
- “Buradayım, sizi dinliyorum.” is an internal control response, not caller text.
  It bypasses the LLM/tools, uses normal EMA playback/receipts and then listens.
- The next no-speech capture retains the existing 20-second bound. Continuing
  silence produces a polite farewell, followed by the existing three-second
  closing drain. Overall call and 16-turn resource bounds are unchanged.
- Incomplete acoustic/partial evidence requests repetition and continues. Real
  model, malformed transport, overflow and dependency failures retain fallback.
- The existing echo monitor/cancellation runs during recovery speech. Bounded
  pre-roll preserves speech beginning near its end; input remains queued during
  the ASR-to-monitor handoff. No model/frontend/codec or recording-policy change.
- Runtime endpoint configuration adds six validated integer options, retaining
  all previous defaults. Invalid bounds/order fail before SIP readiness. These
  options do not change the separate interruption classifier.
- `input_event` is optional additive v1 metadata; event requests require empty
  text and a fixed enum. Ordinary caller requests still require nonempty text.
  Upgrade agent before gateway; old agents fail closed on this new metadata.

## Checks

Initial implementation on Linux:

- Native build passed; nine CTests passed (2.34 s).
- Agent/phrase tests: 66 passed (4.86 s).
- Silence plus existing turn suites: 26 passed (340.88 s), no skips, one known
  Python `audioop` deprecation warning. This includes both G.711 codecs, one
  reminder followed by continued listening/timeout, mid-prompt interruption,
  late speech handoff, incomplete-input clarification, hangup/reuse, 0.5–2 second
  labeled pauses, malformed coverage and invalid settings.

Initial verification added a guard against masking detector failures and retained
queued input during recovery cancellation. It also let preserved pre-roll veto
a recovery farewell; the handset failure below supersedes that behavior.
Final Linux checks on the source/binary used for CUDA validation:

- Native rebuild and all nine CTests passed (2.34 s).
- 95 pytest cases passed (542.86 s), no skips, one known `audioop` warning:
  agent/phrase/database, six recovery SIP cases, configured endpoint timing,
  existing interruption and agent-dialogue suites. Earlier unchanged turn/pause
  cases are covered by the separate 26-case run above, not a claimed full-suite
  rerun.
- Linux Ruff lint/format (11 files), native clang-format, and local `git diff
  --check` passed. The code graph was refreshed. Target source hashes match
  between Mac and Linux. No Mac build, hosted CI or clang-tidy run is claimed.
- Diff credential-pattern review found only existing synthetic test API-key
  placeholders. Private runtime configuration and diagnostics remain ignored.

Activation: after confirming the listener was idle, the agent and native gateway
were restarted into `natural-v5-silence-recovery`. All gateway arguments matched
the previous profile; the approved greeting, ringing delay, ASR endpoint and
closing delay were preserved. ASR/EMA were not restarted. Agent, recognition and
synthesis health passed. Previous binary, agent source and private runtime profile
remain in ignored `.local/before-m3-silence` for rollback. Human handset acceptance
is pending; this activation does not close G3/G4 or publish any Git changes.

## Evidence limits

Synthetic service tests use real SIP/RTP, native Silero/Smart Turn and real gRPC,
but fake ASR/TTS/agent inference. The CUDA check uses synthetic input and real
resident ASR/EMA with an isolated database. Neither proves handset audibility,
human/noisy pause accuracy, full G3/G4 acceptance or the 250 ms interruption goal.
Recovery response timing must be excluded from substantive LLM latency metrics;
these are control prompts, not ordinary user/model turns. No new ordinary-turn
inference pass or GPU model is introduced. Raw caller recording remains off.

The standalone adaptive profile without an agent retains its old fallback
behavior. Call/turn/capture ceilings still apply; prolonged continuous speech,
repeated ambiguity and wider noise calibration remain acceptance limitations.


## Resident CUDA/DB evidence

Four synthetic loopback calls passed on the final binary: PCMA and PCMU, each
with continued silence and with a caller speaking after the reminder. The
resident ASR port was 15173; the single resident EMA worker remained on 15072.
No new model process was launched. Each call used an isolated PostgreSQL schema,
removed afterward. Raw caller recording was not enabled.

- First reminder PCM reached the output port 38–59 ms after the seven-second
  control boundary. Complete reminder plus return to listening took 8.401–8.426 s
  from capture start; this includes the 1360 ms reminder itself.
- Silent calls stored zero caller utterances. Resumed calls stored exactly one
  synthetic caller utterance, with no fabricated silence transcript or note.
  Delivered assistant receipts and pending durable post-call jobs were checked.
- These four paths use local recovery/explicit-exit responses; they do not measure
  substantive LLM response latency. GPU allocation remained 6626/16376 MiB before
  and after validation, including the already resident rollback ASR workers.

An additional real-CUDA speaking-over-reminder attempt completed the conversation
but **failed its stricter mid-sentence-cutoff assertion**: the short 1360 ms
reminder finished before an interruption was observed. Its private failure log
is retained; this is not a passed interruption case. A follow-up checked the
actual M3-01 criterion (preserved caller exit intent and continued recognition),
passed and also observed cutoff after 840 ms of reminder PCM. The interrupted
phrase had empty aligned text; the subsequent caller utterance and assistant
farewell were stored. That follow-up used a real OpenRouter response (first agent
phrase 3364 ms), so no ordinary-turn latency improvement is claimed.

Five functional CUDA/DB cases passed plus one stricter failed interruption
attempt. This does not establish deterministic prompt cutoff or M3-02's 250 ms
target. Human/carrier validation remains separate.

Private evidence stays under `.local/m3-silence-cuda*` and `.local/m3-*-*.log` on
the Linux host. Native binary SHA-256:
`644353b9a525fa4391855c19aeb1de957b6b68aa96eecb54bb0dabb192250dd0`.

## Handset farewell failure and correction

The owner heard the reminder and subsequent silence-timeout farewell, but the
line remained open. Sanitized carrier events confirm that agent turn 5 returned
`finish=1` and the gateway nevertheless started recognition turn 6. No confirmed
interruption was logged. Raw recording remained off; the precise acoustic trigger
is not known.

The monitor retains low-confidence recent activity in bounded pre-roll. The
recovery synthesis path incorrectly cleared `finish_call` whenever this buffer
was nonempty, even without a confirmed interruption. Remove that override:
the agent finish decision survives unconfirmed activity, while the existing
`interrupted` branch still resumes recognition on a valid interruption. Reminder
and clarification handoff, echo filtering and the three-second closing delay
are unchanged. This adds no inference, model or audio processing.

A real Linux SIP/RTP regression using a late synthetic backchannel reproduced
the old bug: the gateway entered turn 3 after the timeout farewell despite zero
interruptions. The pre-fix run failed as expected (45.93 s). The companion case
checks that actual speech interrupting the timeout farewell still resumes and
reaches the agent. These use native CPU detection and synthetic speech services;
they do not establish carrier acoustic accuracy.

Correction validation on Linux:

- Native build and all nine CTests passed (2.41 s).
- All eight recovery SIP cases passed (266.51 s), no skips, one known `audioop`
  warning. This includes the failing-before/passing-after late backchannel case,
  confirmed interruption of the timeout farewell, both G.711 silence paths,
  reminder interruption/late handoff, clarification and hangup/session reuse.
- A fresh PCMA loopback with resident CUDA ASR/EMA and an isolated PostgreSQL
  schema completed the reminder, timeout farewell and SIP hangup. It stored zero
  caller utterances and verified durable assistant receipts and a post-call job.
  The schema was removed afterward. No new model or raw recording was created.
- Targeted Ruff lint/format, clang-format and `git diff --check` passed. Changed
  source/test hashes match Mac and Linux; the code graph was refreshed. Hosted
  CI, clang-tidy and a new human handset call were not performed.

Activated `natural-v5.1-silence-close` on an idle carrier listener. Only the
gateway restarted; all runtime arguments and its environment were preserved.
Agent/ASR/EMA health passed. The old binary/profile/private logs are retained in
ignored `.local/before-m3-farewell-fix`; no Git publication occurred. Fixed binary:
`2615acb21b42c3c737b0fa7894f8ab85e0cbcbc5edb7cb78dc508b6dfb5beb8f`.
Human carrier closing revalidation remains pending.
