# Summary model access recovery and private qualification

Task AGP-08; milestones M4–M5; ADR 0011; US-07/08; requirements §9.3–4/11.2/12/14–16.

## Restored primary environment

The owner confirmed Linux availability on 2026-10-27. Bounded SSH succeeded.
SHA-256 comparison matched `backend.py`, `models.py`, shared `runtime.py`, the
legacy summary live test and managed summary live test between both checkouts.
The check did not overwrite source. Read-only key status returned HTTP 200 with
a configured, non-exhausted limit. An in-memory fingerprint comparison established
that Linux uses a different key from the exhausted local key. Only equality/quota
flags were emitted; no key, fingerprint, balance or label was disclosed. Account-
filtered model discovery returned 21 eligible identifiers. Eligibility is not
inference, quality, provider-policy or latency acceptance.

The existing Alojan Docker services remained running. Configured health checks
reported healthy; the two worker containers do not expose the same health status.
Container status alone is not a call, inference or end-to-end delivery check.
Pending Mac documentation was staged into the private design-review directory,
preserving Linux's maintained root documents.

## Initial real-model diagnostic

A private test-only `openai/gpt-6-luna-pro` override used canonical `openai`, excluded
flex/fast routes and disabled fallbacks. It preserved medium reasoning, 4096 output
tokens, the current summary policy/schema, 15-second client and 20-second outer
limits, and omitted unsupported temperature. No live configuration changed.

Three synthetic cases passed the strengthened shared assertions:

| Case | Result | Model operation seconds |
|---|---|---:|
| Ambiguous report/contract correction | Passed | 11.072 |
| Product name correction | Passed | 9.843 |
| Ambiguous document deferral | Passed | 13.170 |

Manual review confirmed that outputs retain current facts, omit superseded product
names, keep recipient action empty for caller-owned plans, and quote the entire
ambiguous sentence without inventing people. This is a tiny semantic screen, not
statistical reliability or voice-latency qualification. Durations exclude the
six-second test-only spacing. It used no database, tools or external deliveries.

## Scoped diagnostic and test-harness corrections

A private pytest plugin reuses each production-selected client (including scoped
credential resolution) and replaces only the test Agent's model/settings before
inference. Published release/catalog records are not changed; this override cannot
prove correct model selection through a qualified release.

The first scoped screen ended **8 passed, 5 failed, 26 deselected in 199.34s**.
Eight managed summaries passed; the real-person choice case described the uncertainty
accurately but omitted its required unresolved quote. Four extraction cases failed
because the launcher omitted `ALOJAN_OUTPUTS_EVIDENCE_DIR`, before their final semantic
assertions. Those are harness failures, not model-quality results or passes.

A private instruction clarification treats an unselected choice among known alternatives
as unresolved even when its category is known. With both evidence directories supplied,
the next screen ended **12 passed, 1 failed, 26 deselected in 224.93s**. All four typed
extraction cases passed. One managed summary finalized as failed rather than done;
its approximately 20-second test call is consistent with the worker deadline, but the
available report does not identify the underlying exception. Do not classify this as
a proved provider timeout or semantic failure.

Inspection found that the existing six-second test-only request spacing ran inside
`Runner.run`, consuming the worker's production timeout. That spacing is now done once
in test setup, before entering the worker. Production timeout/client limits and retry
behavior are unchanged. All three live suites now validate/create their evidence
directories before setting up call records or making inference requests; disposable
pytest database fixtures may still run before the test body.

Primary Linux checks: **4 passed in 0.83s**, covering all three suites' missing/invalid
paths and ensuring the request wrapper does not spend an artificial six seconds inside
a bounded worker operation. Ruff lint and formatting passed for all four affected
files. A preliminary Mac-only helper import lacked `httpx`; no local test result is
counted. Linux used the existing pinned `httpx==0.28.1` test dependency.

## Existing-model control and rejected shared-policy candidate

With corrected pacing and the same private instruction clarification, the existing
model/provider screen passed **13 tests, 26 deselected in 105.42s**: nine managed
summaries and four typed-output cases. No model override was used in this control.
This single repeat was insufficient to qualify a production change.

The clarification was then placed in the shared summary policy and a 66-case legacy,
managed and extraction run was started without private plugins. Fail-fast stopped at
the first legacy case: **1 failed in 8.43s**, with 65 intended cases unexecuted. The
caller corrected Monday to Thursday; the output incorrectly said the Thursday report
would be sent on Monday. This is a substantive semantic failure, not formatting or
pacing. No assertion was weakened. The exact candidate placement differed from the
private append-only screen, and stochastic variation is also possible; these runs do
not isolate a single cause.

The candidate policy was rejected. After verifying the remote candidate fingerprint,
shared `runtime.py` was restored to its pre-experiment bytes on Mac and Linux. Only
test harness changes are retained. Final primary Linux regression checks:
**29 passed in 1.10s** (`test_live_summary_configuration.py` and `test_agent_runtime.py`),
with Ruff lint/format passing for four changed test files. This includes the earlier
four checks; the counts are not additive. Git whitespace checks passed. The code graph
was refreshed without publishing an artifact.

The initial model-quality gate remains open. Neither model switching nor the prompt
candidate is accepted. The alternative model is not a qualified catalog entry, and
no voice-speed, GPU, carrier or capacity acceptance follows. Next work must establish
source-faithful summaries in the full legacy/managed/extraction corpus before promoting
a configuration, then complete coordinated activation and matched voice/load/rollback
checks. No proof follows from small screens, container health, metadata or skipped tests.

Private evidence is under `.local/final-facts-20261026/` on Linux:
`linux-model-screen-20261027/`, `linux-managed-screen-20261027.log`,
`linux-choice-screen-20261027.log` and `linux-current-choice-20261027.log`.
No candidate production policy was retained; no preset/model change, service restart, migration, deployment,
external message, spending-limit change, commit or push occurred.
