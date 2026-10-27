# Jev recent dialogue and primary-model history — 2026-10-27

Scope: VXP-04/06, PERF-02/03, M2/M4/M5, US-04/05/06/08; ADR 0014.
The owner requested implementing recent dialogue for Jev first, and checking
whether the primary LLM already receives earlier conversation.

## Behavior

Jev snapshots up to three preceding caller-led turns from the call-local history.
The current utterance is separate. History has independent caps of 12 messages
and 4096 UTF-8 content bytes; the current utterance retains its 4096-byte limit.
Oldest messages are omitted whole, with orphan answers removed. No clipping of
words or generated summary is introduced. The copy is taken before scheduling,
so subsequent mutation cannot change the request's question or dialogue.

Only fully played substantive phrases enter the existing assistant history.
Partial/unsent speech and waiting receipts do not fabricate spoken text; remote
tool result bodies are not conversation history. Known suspect ASR is marked
unreliable in the copied context. Provider input validation rejects invalid roles,
extra fields, malformed text and excess bytes/messages/turns. History is data,
never instructions or permission. Logs retain only category/status/timing.

When context resolves exactly one request, an explicit correction/follow-up can
inherit its intent. Unresolved references remain unknown. Empty history uses the
previous English instructions, criteria and request shape unchanged. Existing
750 ms deadline, no retry, two-request limit, scoped credential and stale-result
checks remain authoritative. No new database access or service is introduced.
This is a shared capability for all managed agents, still shadow-only.

## Primary model finding

`Backend.stream` already passes the call's bounded messages to the SDK, together
with current call data and applicable instructions. `Call.add_message` enforces
the engine's byte budget (12000 bytes in the legacy fallback). `ReportPlayback`
adds only completed substantive phrases. The primary model is not reduced to
three turns; doing so would unnecessarily discard earlier details. Added an SDK
input regression for three prior exchanges plus the latest correction. Existing
real-loopback gRPC tests verify receipt handling, partial output exclusion and
call isolation. This verifies context delivery, not semantic model perfection.

## Linux validation

- **132 tests passed in 5.65 s**: decisions, shadow isolation/cancellation,
  agent runtime, agent service and response experience suites.
- Ruff lint and formatting passed for all six changed Python files.
- Initial new snapshot test lacked a scoped synthetic provider identity; corrected
  that fixture before the final passing run. No live configuration was involved.
- The task diff was reviewed against saved pre-change files; whitespace checks
  passed. No native/GPU/media code changed or needed rebuilding.

## Real OpenRouter synthetic evaluation

Pinned `typesafe/jev-1.14-20261014`, existing authorized workspace credential,
primary Linux host, production 750 ms deadline. Synthetic dialogue only; no real
call content, tools, actions or telephone calls. The evaluator alternates variant
order per case. Expected no-history outcomes are specified separately when
missing context makes unknown the appropriate answer.

| Final candidate cohort | Observed | Expected choices | Unknown choices | Median HTTP duration | Maximum |
|---|---:|---:|---:|---:|---:|
| Context scenarios with available history | 16/16 | 16/16 | 6 | 229 ms | 309 ms |
| Same final utterances without history | 16/16 | 15/16 | 10 | 218 ms | 311 ms |
| Original calibration regression | 20/20 | 19/20 | 6 | 221.5 ms | 292 ms |
| Original held-out regression | 40/40 | 39/40 | 11 | 227.5 ms | 338 ms |

The two date-correction cases resolve to lookup with the preceding question,
including when no assistant phrase completed. Both remain unknown without context.
Ambiguous people, incomplete/mixed requests and adversarial instructions stay
unknown where expected with context. One no-history pronoun explanation was
classified explanation despite the conservative expected unknown. The old corpus
retains its prior total 58/60, with both misses conservative unknown.

These are 32 paired requests plus 60 existing regression requests. Two context
scenarios intentionally have no preceding history even in the context variant.
The 11 ms difference of medians is not a paired per-request latency penalty,
whole-call latency result or statistical non-regression guarantee. The small
context set is a development/regression set, not a new blind held-out benchmark;
the previously named held-out corpus is reused here as a regression set.

An earlier candidate applied expanded instructions even without history: context
15/16, original regression 43/60 (one nonunknown where unknown was expected).
It was rejected. Preserving the exact old no-history contract and shortening the
context policy produced the final results above. Both runs are retained privately;
no failed candidate was installed in the serving agent.

Reproduce with the existing evaluation command and scoped environment credential:

```sh
uv run --frozen python tools/evaluate-response-decisions.py \
  --cases tests/fixtures/response-experience/decisions-context-tr.json \
  --compare-history --output .local/jev-context-paired.json
uv run --frozen python tools/evaluate-response-decisions.py \
  --output .local/jev-context-regression.json
```

## Delivery and limits

Source, tests and evidence are synchronized to the primary Linux development
checkout. Serving containers were not restarted or upgraded in this task; live
Jev remains disabled and the restored Kübra binding is not changed. This is tested
candidate code, not live activation. No prompt/person-lookup edits, number binding
change, new recordings or external notifications. No claim that contextual intent
fixes the noisy-speakerphone false interruptions; that acoustic issue remains open.
Private measurements stay under `.local/jev-history-20261027/`.
