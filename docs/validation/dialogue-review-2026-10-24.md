# Adversarial dialogue review — 2026-10-24

Scope: M4-01 / M5-03, US-02/06/08, requirements §9.2 and ADR 0007.
The owner requested varied unusual questions, diagnosis, a reviewed improvement
plan and implementation. This report contains synthetic examples only.

## Method and decisions

Used the actual OpenRouter GPT-OSS 120B / Cerebras / medium configuration through
the Linux agent's loopback gRPC service. The evaluator uses an in-memory store
and simulated completed-playback receipts; it does not write production notes,
place carrier calls or exercise ASR/TTS. Model settings were not changed.

The main set has 26 conversations / 46 turns; an additional set has eight
conversations / 12 turns. Cases include nonsense, harmless jokes, identity,
private-calendar requests, fake owner/tool instructions, false delivery promises,
appointments, missing purpose, declined contact details, anger, corrections,
multiple independent requests, credentials and ambiguous closing language.

Initial review found mistaken identity refusal, cold off-topic replies, lost
earlier requests, secrets copied into generated notes and imperfect correction
handling. The plan was to clarify intent boundaries and complete-note semantics,
then protect observed tool-boundary failures with narrow runtime checks. A broad
prompt compaction was tried and rejected because it introduced semantic errors.
The selected version retains the prior structure with targeted refinements.

Review also caught defects that initial automatic checks missed: a callback
promise, unnecessary note rewrites on closing, and claiming storage without a
durable note. Checks were strengthened accordingly. Turkish inflection checks
were corrected and clarification before saving an unknown-product issue was
accepted as valid. The baseline's original 43/46 result is therefore not a
directly comparable final-rubric score. The additional set was initially held
out, then reused during refinement; it is now a regression set, not unseen data.

## Applied protections

- Prompt and tool descriptions distinguish legitimate identity questions,
  harmless diversions and malicious instructions; mixed requests retain valid
  business content while ignoring attempted overrides.
- Note updates must preserve independent earlier requests and contact details,
  replacing only corrected facts. Credentials are excluded from generated note
  fields and replies. Raw caller transcripts and model inputs are not redacted
  by this change; this is not end-to-end secret filtering.
- Known content-free closing/status phrases cannot rewrite a durable note.
- Observed new-request markers after a goodbye reject premature hangup; a later
  final goodbye can still close. This finite phrase check is not a full intent
  classifier.
- Recognized storage acknowledgements require a durable note, including when
  accompanied by an essential question. Additional observed callback-promise
  forms receive the existing bounded repair.
- Malformed SDK/model tool output yields a clarification without exposing model
  internals or disconnecting the caller. Network/storage errors are not hidden.

Normal valid replies gain no additional model request. A rejected tool action
may require a correction within the existing bounded model loop. Phrase-based
checks cannot cover every paraphrase and do not establish universal protection.

## Selected-version evidence

| Evaluation | Passed turn checks | Mean first phrase | Maximum |
|---|---:|---:|---:|
| Main set | 45/46 | 893 ms | 2302 ms |
| Additional set | 12/12 | 1224 ms | 3208 ms |

Across 58 steps, 57 passed the current checks. One known-ASR-artifact step used
the local clarification path (1 ms); excluding that local step, the 57 real-model
steps averaged 979 ms. One exceeded three seconds. These are agent first-phrase
measurements, not telephone first-audio latency, a stable percentile or an SLA.
The selected evaluation logged zero malformed-output recoveries and zero recorded
exceptions. Automatic checks cover note content/state, completion and selected
language constraints; they are not a complete measure of natural dialogue.

Linux regression suite: **126 passed in 8.03 s**, covering agent, phrases,
database, model tools, timing and latency reporting. Ruff, formatting and diff
whitespace checks passed. Mac and Linux agent source hashes matched. Tests cover
new-request ordering, no-op note rewrites, unsupported commitments, unbacked
acknowledgements and malformed-output recovery. No new native/GPU or carrier
acceptance test was run in this task.

## Remaining quality gaps

The failing case says “Yarın, yok cuma, cuma raporu getireceğim.” The subject
correctly uses Friday, but the message preserves the discarded “yarın” wording.
The selected prompt already requests the final corrected value; this case remains
open rather than being removed from the suite or reported as passing.

Manual inspection also found mechanical acknowledgements on additions, a cold
refusal to a playful transfer request, and “Anladım” before clarification of
nonsense. The next language-quality work should target correction normalization,
contextual acknowledgement and warm redirection with broader paraphrases. A
single run does not establish senior-assistant quality or eliminate repetition.

The reproducible evaluator is `tools/evaluate-agent-dialogue.py`; fixtures are
under `tests/fixtures/agent/`. Failed checks return a nonzero exit code. Private
outputs are under `.local/dialogue-review-20261024/`, outside Git. Real phone
listening remains pending. Activation status is recorded in PLAN.md.
