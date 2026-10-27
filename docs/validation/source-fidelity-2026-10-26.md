# Source-fidelity experiment and managed summary acceptance — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08, requirements §9.3–4/11.2/12/14–16.
Ponytail full: qualify changes against actual provider behavior before retaining them.
This work continues the live-readiness goal; it does not establish readiness.

## Rejected experiment

A private candidate offered a bounded set of exact caller quotes in the structured
summary schema, then merged selected quotes into the public unresolved questions.
Bounds, call isolation, sensitive-marker exclusion, strict parsing and one-request
SDK behavior passed **30 offline tests in 9.44s**. That did not prove meaning fidelity:
the real model screen produced **7 passed, 5 failed in 88.52s** (15 deselected).
It still invented person references, retold superseded product names and sometimes
omitted the exact ambiguous phrase. No assertions were weakened to accept this.

A diagnostic kept local strict parsing but moved the schema from provider constrained
generation into untrusted user input. It produced **5 passed, 1 failed in 43.75s**
(21 deselected, two pytest import/rewrite warnings). The remaining failure still
invented a person reference. This alternate transport was never applied to source.

Both experiments were rejected. The bounded quote schema, merge helper, its dedicated
tests and protocol-specific prompt changes were removed from the development checkout;
private snapshots retain the experiment. Backend/models/runtime/declared-output test
files were restored exactly to the pre-experiment snapshots, preserving the earlier
bounded 429 recovery and shared summary policy. No model/preset/transport/dependency,
public Summary schema, serving process or database migration changed in this step.

## Managed acceptance coverage

`tests/test_managed_summary_live.py` now applies the same nine-case, three-repeat
correction/ambiguity corpus used by the legacy/shared-policy tests to real scoped
records and the separate summary worker. It creates a disposable workspace, encrypted
provider connection, synthetic agent/audio preparation and published immutable release.
After call initialization it changes the authoring draft, then exercises the pinned
release through restricted record/summary/credential roles. It uses real model inference;
synthetic audio preparation does not prove EMA/GPU readiness.

The assertions require a completed finalization and one completed summary attempt,
correct final facts, no invented confirmation/commitment and the exact uncertain
phrase. Tests fail on a deferred/missing/failed finalization; those states are never
counted as success. They also require no action jobs, Telegram outbox entries or MCP
executions. The common meaning assertions were extracted without weakening them.

Provider pacing remains six seconds per request in the test only. These durations
are not production summary or voice latency measurements. The opt-in suite uses only
synthetic conversation content and private artifact files; routine runs skip it.

## Final primary Linux results

The retained production implementation was evaluated through all **27 managed cases**
without repeating any completed case: the fail-fast segment was **16 passed, 1 failed
in 138.33s**; the remaining segment was **9 passed, 1 failed in 81.05s** (17 deselected).
Total: **25 passed, 2 failed**. One result narrated the superseded product name; another
invented a person in a conversation about two documents. Every exact uncertainty quote
in these managed cases passed; that alone did not prevent a contradictory summary.
All 27 reached a completed, single-attempt finalization with zero action/outbox/MCP rows
before the meaning assertions. This proves plumbing, not acceptable summary quality.

Manual review also observed arrival being paraphrased as preparation in some report
summaries. Current lexical assertions are a bounded regression corpus, not a complete
semantic oracle. These observations remain quality follow-up work; no failing assertion
was removed or relabeled as infrastructure failure.

Final restored consumer boundaries: **60 passed in 21.50s**, covering summary recovery,
declared outputs and runtime compilation. Ruff lint/format passed for six affected
Python files. The full Git whitespace check passed; six final source hashes match
Mac/Linux and four reverted files exactly match their pre-experiment snapshots.
The common assertion extraction and new managed harness were reviewed. The graph was
refreshed without a persisted artifact: 7,022 nodes / 25,571 edges. Existing unrelated
working-tree changes were preserved. No image rebuild is claimed for these test changes.

## Limits and next step

No live restart, new external notification, webhook POST, Hindsight write, raw recording,
historical replay, production agent/grant change, commit, push or PR. The corrected
Hindsight endpoint and previous successful bounded read remain documented in
[mcp-schema-2026-10-26.md](mcp-schema-2026-10-26.md); they were not retested here.

Do not promote the failed quote-schema experiment. Finish final-meaning qualification
on the retained policy, then coordinated activation and matched voice/load/rollback
acceptance. Exact structured syntax alone cannot guarantee semantic accuracy or
arbitrary-secret redaction. Five/50-call capacity and carrier acceptance remain separate.

Private Linux evidence: `.local/source-quotes-20261026/{boundaries,screen,json-screen,
managed-baseline,managed-remaining,final-boundaries}.log` and synthetic `baseline/managed/` artifacts.


## Follow-up: stronger fact checks

Manual-review findings are now enforced by the shared acceptance helper. Replaying
the same managed outputs passes 19/27 under those stronger assertions. New prompt
and review controls did not qualify; no production change was adopted. See
[fact-boundary evidence and connection handoff](summary-fact-boundaries-2026-10-26.md).
