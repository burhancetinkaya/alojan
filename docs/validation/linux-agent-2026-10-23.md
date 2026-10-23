# Linux M4 agent and carrier follow-up

Date: 2026-10-23. Branch: `codex/agent-dialogue`.
Tasks: M4-01–03, with an M2-01 cancellation handoff correction.
Acceptance: US-02/05/07/08; requirements §7.3–4, §9–11; ADR 0005.

## Implemented boundary

The private agent uses the pinned Agents SDK and owner-selected OpenRouter
`openai/gpt-6-luna-pro` Responses model. Bounded phrase streaming, per-call
context, cancellation, complete-phrase playback receipts, local idempotent notes,
controlled closing and durable post-call summary jobs are integrated with the
native gateway. No live external MCP tool or notification is enabled.

A successful draft tool renders the saved message and confirmation question
directly, avoiding another model request to rewrite the tool result. A plain
affirmative to a completely delivered, unchanged readback uses the same local
confirmation policy and durable save before producing closing text. Corrections,
missing receipts and failed writes cannot take that path. Explicit stop requests
and other dialogue still use the agent/tool policy.

A cancelled ASR monitor can retain a non-preemptible native CUDA decode. A new
generation of the same call now reserves the single admission slot and waits at
most 1.5 seconds for that decode to drain. It never queues another native decode;
other calls remain rejected while busy. Successor cancellation and timeout keep
the old native slot occupied until it actually finishes.

## Linux checks

- Native build and 8 CTests passed; latest CTest run: 2.32 seconds.
- Earlier broad pytest run: 205 passed, no skips, 696.75 seconds, one `audioop`
  deprecation warning. Source evolved during that run; it is not a clean full
  suite for the final revision.
- Subsequent pre-follow-up M4 run: 21 passed in 75.31 seconds, no skips.
- Confirmation/handoff follow-up: 48 passed in 80.82 seconds, no skips, one
  `audioop` warning. This covers ASR lifecycle, agent policy/SDK, actual isolated
  PostgreSQL and six native SIP/RTP scenarios. It is a focused run, not the full
  suite. Cases include cancellation, stale/missing terminal events, both codecs,
  partial playback, correction, failed note save, and bounded same-call handoff.
- Ruff check/format and affected C++ clang-format checks passed. Bindings were
  regenerated on Linux with unchanged hashes before this follow-up; no protocol
  edit was needed for the latency/handoff changes.
- Mac fallback checks are separate: latest ASR/agent unit run 41 passed in 4.64
  seconds. These are not CUDA or carrier evidence.

## Real provider and GPU observations

Original Luna was denied by an account guardrail. The owner explicitly selected
Pro; no account guardrail or fallback model was changed. The first Pro streaming
smoke completed in 3460 ms. A later actual SDK/DB test with simulated playback
receipts passed note confirmation and schema-validated summary; its initial
response took 11744 ms and confirmation response 18323 ms before optimization.

Real local SIP/RTP checks used synthetic EMA-generated caller speech, resident
EMA, real CUDA ASR, the selected API model and isolated disposable PostgreSQL
schemas. Caller audio was kept in memory. They are not human/carrier acceptance.

| Probe | Result | Confirmation half-close to first output-port audio |
|---|---|---:|
| Initial fixed capture | Passed | 16734 ms |
| Initial adaptive | Failed: agent timeout | No valid closing |
| Optimized finish tool | Passed | 9059 ms |
| Direct readback/confirmation, old ASR | Failed: next recognition ended after one frame | No valid closing |
| Direct readback/confirmation, handoff ASR, run 1 | Passed | 138 ms |
| Same path, run 2 | Passed | 139 ms |

The last two calls completed two turns, confirmed one note and generated a valid
post-call summary. First substantive agent phrases took 4058/3322 ms; confirmation
text took 20/21 ms. Calls lasted 22383/17693 ms. Both had no RTP loss, reorder,
duplicates or malformed PCM; maximum jitter was 10500/8875 microseconds. These
are individual observations, not P95, handset latency or full quality acceptance.
An independent API/DB probe with simulated audio receipts measured first phrases
at 5097 ms and confirmation at 60 ms.

## Actual carrier observations

The first M4 carrier call saved a confirmed note after a fully delivered readback
and an affirmative caller turn, but closing was interrupted before audio and a
later listening turn reached incomplete-turn fallback. A second call ended
remotely before any assistant phrase completed. The owner reported an incorrect
or missing confirmation and excessive waiting. This is failed experience evidence;
the stored confirmation does not override the owner's assessment.

After the first follow-up activation, the owner confirmed the message was correct
but still reported excessive waiting. The corresponding PCMA call completed its
readback, confirmation and closing. Agent response preparation took 3102/3824 ms
on the first two turns and 21 ms on confirmation; closing half-close to output was
139 ms. One interruption invalidated the first response after 80 ms of audio.
The call lasted 36466 ms, with one lost RTP packet and no malformed PCM. No private
transcript, caller number or recording is included here.

Carrier latency acceptance remains open. The remaining 3–4 second model wait is
distinct from the corrected confirmation path. Generation diagnostics now report
the actual interrupted turn instead of the interruption count.

## Waiting-phrase follow-up

The owner's second latency report prompted a bounded waiting phrase: when no
complete answer phrase is ready after 800 ms, emit one Turkish acknowledgement
through the existing EMA/receipt/cancellation path while inference continues.
Fast confirmations bypass it. It cannot replace a real response, establish note
confirmation or extend the 20-second turn deadline. Pending reads are cancelled
and joined before the stream closes. Logs separate first audible-content-ready
text from the substantive response with `first_phrase_ms`/`first_content_ms`;
neither is a handset-audio timestamp.

Final focused Linux checks: 28 passed in 76.98 seconds, no skips, one `audioop`
warning (agent, PostgreSQL and six native dialogue scenarios). This supplements
the unchanged 22 ASR tests from the 48-case run. Mac agent checks: 21 passed in
3.29 seconds. New regressions cover a single waiting phrase followed by real
content, cancellation of its pending model read and no confirmation from it.

A real CUDA/EMA/OpenRouter adaptive call passed with one fully delivered 1680 ms
waiting phrase, two turns, confirmed note, complete closing and valid summary.
Waiting text was ready at 801 ms; substantive content took 6315 ms. Confirmation
text took 21 ms and first closing output 138 ms after ASR half-close. Total call
was 24722 ms, no RTP loss/reorder/duplicates or malformed PCM, maximum jitter
8500 microseconds. This explicitly does **not** prove faster model inference;
the observed substantive API wait now spans roughly 3–6 seconds. This final
waiting-phrase version still requires owner listening acceptance.

## Limitations

Human latency/turn quality, broad/noisy Turkish ASR, M3 reminders and 250 ms
interruption acceptance remain open. Readiness is separate from provider access.
Exact affirmative matching is conservative. The MCP allowlist/approval boundary
is unit-tested; full HTTP transport integration is not. M5 notification is absent.
Production supervision, call-state reclamation, runtime DB roles, retention and
crash/orphan reconciliation remain pending. Playback receipt offsets are relative
to each phrase, not a full call timeline. Summary input currently takes at most
100 utterances; long-call truncation needs further hardening. Hosted CI and
clang-tidy are unverified. No publication, merge or license decision was made.
