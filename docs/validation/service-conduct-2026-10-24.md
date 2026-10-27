# Researched service practices — 2026-10-24

Scope: M4-01 / M5-03, US-02/06/08, requirements §9.2, ADR 0007 owner refinement.

## Research and adaptation

Followed the same method as the earlier conduct list: inspect primary sources,
separate general guidance from product permissions, paraphrase applicable rules,
review conflicting instructions, then evaluate synthetic Turkish dialogues on Linux.
The [source mapping](../AGENT_CONDUCT.md) records ISO's public overview, ICMI's
training guide, Google conversation/error guidance and Retell prompt guidance.
No paid ISO normative text was reviewed and no conformity claim is made.

Added six positive service practices alongside the existing conduct boundaries:
contextual listening, concrete empathy, plain language, targeted recovery, truthful
available next steps and faithful corrections. Clarified the distinction between
a request to speak now and an actionable callback/message. Essential product
identification precedes further-help offers. Tool descriptions now use the same
question priority as the system prompt. Existing once-per-call invitation, no-readback,
explicit exit, local-storage permissions and media controls remain unchanged.
AST comparison confirms only system-prompt text and tool descriptions changed.

## Evaluation

Real OpenRouter GPT-OSS 120B / Cerebras / medium, Linux loopback gRPC, synthetic
caller text, in-memory note store and simulated completed playback receipts.
Five conversations / 14 turns: frustration with unknown product, contextual
correction, unclear purpose, requested resolution deadline and plain-language need.
Each step checked expected note presence and finish state; replies and stored note
content were also inspected. These checks are not an exhaustive semantic score.

| Prompt | Note/finish checks | Mean first phrase | Maximum first phrase |
|---|---:|---:|---:|
| Previous active prompt | 14/14 | 1208 ms | 2832 ms |
| Initial candidate | 12/14 | 1208 ms | 2724 ms |
| Revised candidate | 14/14 | 935 ms | 1917 ms |

The previous prompt and initial candidate skipped the missing-product question.
The initial candidate also incorrectly saved a simple request to speak now. The
revised candidate asked for the product before inviting another topic and kept the
vague speaking request out of notes. It preserved the address correction and the
requested deadline without guaranteeing a resolution. Explicit exits closed.
Handled message scenarios each had one invitation, with none repeated on updates.
The short sample does not establish a latency percentile, causal speedup or SLA.

Language limitations remain: the frustrated-caller response asked the right
question but did not include the desired explicit empathy; the deadline answer
repeated an intention to pass on the request. No claim of fully natural or
universally nonrepeating conversation follows from the state checks. Broader
language review and actual carrier listening remain pending.

Focused Linux regression tests, Ruff/format and whitespace checks are recorded
in PLAN.md. No new GPU/native-media test was run for this prompt-only update.
The previous source/log snapshot is privately retained for readiness rollback.
No private caller transcript, phone number, credential or recording is in this report.
