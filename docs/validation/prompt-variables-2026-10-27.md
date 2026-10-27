# Instruction variables and Nazlı analytics — 2026-10-27

AGP-06/07/09 and MCP-06, M4–M5, CFG-01, US-08, requirements §11.2–11.3/17.1,
ADR 0011–0013. The owner requested per-agent instruction variables while configuring
Nazlı's Deliver2.ai analytics role.

## Implemented and deployed

- Optional `prompt_template` stores version 1, an IANA timezone and at most 16
  literal variables (1,000 characters each; combined JSON at most 8 KiB).
- `{{name}}` expands once inside the agent-authored instructions JSON field.
  Nine reserved identity/time values come from pinned identity and one trusted
  UTC clock sample per model turn. Local day boundaries honor the configured zone.
- Reject invalid/undefined/duplicate/reserved names, malformed syntax, unsupported
  versions, invalid timezone and excessive expansion. Existing 20,000-character
  instruction and 32-KiB compiled-prompt limits remain. Inserted text cannot change
  JSON structure and is never recursively expanded or executed. No IO is added.
- No template preserves historical serialized content/digests and literal braces.
  Template-bearing releases require schema v10. Existing v1–9 support and no-answer
  action enqueueing remain intact. Values are business configuration, not secrets.
- UI under Instructions provides enablement, timezone, custom entries and insertion
  buttons. HTTP and public management MCP expose the same draft schema. Prepared
  audio, summary templates and tool guidance retain their existing contracts.
- The real-model check exposed U+00A0/U+202F currency spacing being rejected as
  nonprintable speech. Model response/closing text now converts exactly those two
  whitespace characters to ordinary spaces before existing speech validation;
  other controls, bidi marks and all speech budgets remain enforced.

No migration, new service, external write integration or added dependency.
[Authoring example](../../services/app-api/README.md#instruction-variables) and
[read-only SQL example](../../infra/examples/prompt-variables.sql).

## Primary Linux validation

- Core template/draft/release/runtime/lifecycle suite: **97 passed in 38.67s**.
- Management MCP/schema/Deliver2.ai/runtime/number-routing regressions:
  **114 passed in 81.90s**.
- Speech-space fix plus runtime/grounding/model/template suite:
  **111 passed in 4.42s**. These suites overlap; do not sum as unique tests.
- Real HTTPS isolated browser suite: **47 passed**. New scenario persists variables
  across reload, inserts builtins, rejects an undefined placeholder with HTTP 400,
  preserves the previous saved draft, and reports no browser exception. An initial
  ambiguous alert locator was corrected before the passing repeat.
- Ruff and `git diff --check` passed. Linux production frontend build passed.
- Three existing immutable releases compiled to identical voice/engine/instruction
  configuration in old agent and all candidate readers. Live source hashes and
  timezone support were checked in agent, worker and management containers.
- Rendering the saved analytics instructions 3,000 times measured approximately
  **0.08 ms/turn** on this host. This is CPU-only micro-measurement, not concurrent
  load, speech latency, GPU or carrier acceptance.

## Deployment and recovery

All v10 readers (agent, discovery, summary/delivery workers, management API) and
immutable host preparer were installed before publication resumed; web was updated
separately. Native admission acknowledged draining with zero calls before replacement.
One bound number became ready; admission reopened. Existing numbers, bindings,
publications and releases were unchanged. Eight unrelated containers were preserved.
The subsequent currency-space fix replaces only the agent after another idle drain.

Private rollback/source/image/test evidence remains under
`.local/prompt-variables-20261027/` on the primary Linux host. `result.json` records
initial images and `space-fix-result.json` the final agent image. Restore exact prior
compose/images/unit only during an acknowledged idle drain, then verify readiness
before reopening. Older readers cannot consume template-bearing v10 releases;
rollback after new publication requires compatible readers or deliberate route rollback.
Never copy private logs/configuration/credentials into Git.

## Nazlı configuration and evidence

Saved **draft v6** through public HTTPS management MCP, including the template,
Europe/Istanbul timezone, custom team name, concise analytics instructions and eight
exact reviewed/granted read tools. Replaced the skill-version comparison selection
with `mcp_sessions`; `pageSize=1` and `isSubAgent=false` are fixed. The list's `total`
is the filtered main-session count, not page length. Cost remains `task_tree` and
unknown actual totals are distinguished from known subtotal and estimated cost.
Named-user queries first resolve an actual developer ID; ambiguous matches require
clarification. Further-help invitation is disabled for concise analytics replies.
Temporary personal tokens were revoked and sessions logged out.

Real authenticated Deliver2.ai reads established bounded response shapes for session
count and cost summary (1,541 and 1,880 bytes respectively); private record values were
not included in maintained evidence. The currently selected tools do not expose an
all-developer aggregate. A partial page cannot support a complete user distribution;
Nazlı must explain that limitation and narrow the person/scope.

The selected real Cerebras model was tested with synthetic tool data and a frozen
local-midnight boundary. Initial trials exposed wrong person filters, incomplete
all-user answers, the currency whitespace bug and provider rate limiting. Instructions
and tool guidance were refined, fixed main-session filtering was added, and the
speech bug was corrected; pacing was reduced. These are semantic smoke checks,
not a statistical guarantee of conversational reliability.

Final semantic smoke checks passed for six scenarios on draft v6: main-session
count uses `total=12` despite one returned item; cost reports only the known 12.5 USD
subtotal; combined count/cost uses two matching-date tools; named-user count resolves
then reuses the returned UUID; ambiguous name asks for clarification; all-user
breakdown explicitly declines unsupported complete aggregation without inventing it.
Every lookup used the injected Turkey-local midnight/current-time range. The two
currency cases were repeated after the whitespace fix and each completed with one
speech attempt. Final successful request times ranged from 0.642 to 2.276 seconds
with synthetic zero-latency tool handlers; these exclude real MCP/network/audio
latency and are not production performance acceptance. Private evidence:
`.local/nazli-analytics-20261027/semantic-verification.json` and associated model logs.

Nazlı has **no publication or number binding**. No live carrier call, recording,
notification, summary-quality approval, new model qualification, concurrent load
acceptance, Git push or merge is claimed here. A real voice trial and broader
analytics paraphrase/evaluation coverage remain separate.
