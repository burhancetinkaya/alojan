# Receptionist prompt review — 2026-10-23

Scope: M4-01/02, US-02/06, ADR 0007. The owner requested use of Skill Creator to
revise the current LLM prompt. Its instruction-design principles were applied to
the existing runtime instructions: preserve scope, remove ambiguous repetition,
make consequential decisions explicit, and validate observable behavior. No new
Codex skill package, plugin, dependency or alternate model was created.

## Resulting decision rules

- Separate a topic announcement from an actual question/message. Naming a product
  or asking to speak to the owner does not itself constitute a message to save.
- Distinguish a callback request from the caller saying they will call later.
  A callback request is saved, then acknowledged with one invitation to add more;
  it is not evidence that the caller is finished.
- Repeat/simplify unanswered questions, but do not request known information or
  insist on a stale question after a clear topic change. Ask at most one question
  in a response. An informational answer does not start another generic invitation.
- Preserve additions/corrections, acknowledge an update and listen. If the final
  utterance also contains a message/correction, save before a justified farewell.
- Find completion in the caller's expressed intent, not the successful note tool
  result. The finish_call tool description reinforces this precondition.
- Keep AI identity, configured availability wording, no readback confirmation,
  local-only storage, privacy/tool boundaries and three-second closing behavior.

The source remains `services/agent/alojan_agent/backend.py`. The known suspect-ASR
and bare-thanks guards are unchanged. No acoustic accuracy or end-to-end speed
improvement is claimed. The stale requirements sentence allowing closure after
two failed clarifications was aligned with the already approved ADR 0007 follow-up.

## Behavioral review

The initial rewrite failed three synthetic cases: saving only a topic, closing
on a standalone callback request, and repeating the invitation after an addition.
It was not activated. Concrete decision examples and a clearer finish tool
description resolved those observed cases on the next run. Reading the actual
answers then found a two-question clarification and an unnecessary generic
invitation after answering; these style rules were tightened.

A subsequent run still closed a callback request, exposing ambiguity between a
generic stop-speaking rule and the first-save follow-up. The final wording makes
the informational-answer rule distinct from the required first-save invitation,
and identifies caller words as the source of completion. No failed candidate was
activated. Prompt-only compliance remains probabilistic; passing a small synthetic
set is not a guarantee for unseen caller speech.

Validation uses the pinned OpenRouter model with synthetic caller turns, an
in-memory note callback, and asserted save/finish/question behavior. Notes are
checked for retained details, corrected dates and supplied callback number.
Actual answer text is also reviewed. This is model behavior testing, not phone
or human intelligibility acceptance; detailed synthetic outputs stay in `.local/`.

## Final validation and activation

The final run passed all 16 scenarios: 12 review cases, three previously unused
variations (topic change, nothing else, differently worded callback), and a repeat
of the callback case that had failed earlier. Fourteen exercised real OpenRouter;
two used the unchanged local clarification guards. The checks covered save/finish
choices, at most one question, required/forbidden invitations, retained note
content, supplied number, no readback confirmation and the 400-character limit.
All final answers were inspected as well. API cases took 2004–5544 ms total in
this run; no speed improvement or stability guarantee follows from that sample.

Final Linux regression: 59 agent/phrase tests passed in 4.78 s. Ruff lint/format
and diff whitespace checks passed. No native build, CUDA/audio test or full test
suite was repeated for this instruction/tool-description-only change.

The idle development agent was restarted with a private rollback copy and active
policy `natural-v4-prompt-review`. Gateway and speech workers were not restarted.
Handset acceptance remains pending. No Git push or publication was performed.
