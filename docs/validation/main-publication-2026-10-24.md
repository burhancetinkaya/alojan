# Consolidated development publication — 2026-10-24

The owner explicitly requested all accumulated development to be pushed to main.
This integrates M2-01 ASR experiments, M3-01 recovery, M4-01/02 dialogue work and
M5-03 latency instrumentation under US-01/02/04/05/06/07/08. Capacity targets stay
planning-only under ADR 0009; rejected ASR/denoise comparisons remain optional.
Publication is not live deployment or acceptance of the documented quality gates.

## Source reconciliation

A separate `codex/consolidate-main-20261024` branch starts from `18e6215`.
The primary working checkout supplies accumulated ASR studies, dialogue correction
and semantic acknowledgement tracking. The endpoint worktree supplies its additive
protobuf hint, native scheduling/diagnostics, replay probe and matching tests.
The grounded-dialogue worktree supplies verified-knowledge/repetition guidance,
bounded repair, evaluator changes and fixtures. Existing branches and dirty source
checkouts are preserved; old local session checkpoints are not published.
The Linux-only stale CI file remains excluded as previously removed on main; its
duplicate Nemotron pin is already represented by `services/asr/nemotron.json`.

Three backend overlaps were resolved by retaining both semantic acknowledgement
intent and explicit-repeat intent, complete-note correction rules, natural tone
and knowledge boundaries. The unchanged-note guard uses semantic intent as well
as the legacy phrase fallback. Three additional regression combinations verify
that unusual acknowledgement wording, explicit repeats and unheard notes retain
their intended interaction. Skill Creator principles guide the merged instructions;
no new caller-specific exception or model/provider change was introduced.

## Privacy checks

Only nonignored source, documentation and existing synthetic assets are included.
Private configuration, raw caller recordings/transcripts, downloads, caches,
model weights and build outputs remain excluded. Three product-name references in
new validation prose were anonymized. Existing approved generated greeting assets
are product content, not caller recordings.

Detect-secrets 1.5.0 with network verification disabled reported 84 findings:
82 public file/model hashes, one existing example database credential placeholder,
and one explicitly synthetic test API key. No live secret was identified.
A read-only Linux comparison against four distinct private configuration/number
values and 32 caller utterances of at least 40 characters found zero source matches.
Both Mac private connection values also had zero matches.
Additional credential, host/path and phone-pattern inspection found only public
attribution, approved greeting content, synthetic numbers and numeric metrics.
These checks reduce disclosure risk; they are not a universal privacy guarantee.

## Validation

The isolated Linux workspace is `.local/consolidate-main-20261024/` beneath the
authorized project. It reuses installed native dependencies without changing the
live source, gateway, ASR, EMA or agent processes. Linux native build passed and
all nine CTests passed in 2.50 seconds. All six generated protobuf bindings were
byte-identical after regeneration. Ruff lint/format, C++ formatting, whitespace
and local documentation-link checks passed.

The initial Mac agent/ASR/latency subset passed 188 tests with 19 skips (database
and explicit real-summary opt-in). The expanded merged repetition suite passed
all ten cases on Linux. Optional ASR/denoise tooling passed all 25 checks using
the installed private DTLN models/native probe. Its first attempt lacked ONNX
Runtime and failed one test with 17 skips; the documented runtime and model/probe
paths were supplied before the successful rerun. No runtime dependency pin was
changed by this test setup.

The full Linux pytest run completed in 1099.08 seconds: **385 passed, one failed,
18 skipped**. The sole failure was the old exact AudioFrame descriptor expectation,
which omitted the documented additive `partial_hint` field. The contract test now
checks field 9/type bool and verifies that absent/false hints preserve the previous
wire payload/default. The protocol/gRPC/ASR rerun passed **76 tests in 3.99 seconds**,
with no skips. The expanded acknowledgement/repetition tests separately passed
**17 tests on Mac** and **ten repetition tests on Linux**. The complete long suite
was not repeated after this test-only correction; runtime source was unchanged.
The 18 skipped real-summary API cases require a separate explicit opt-in and are
not counted as passed. The known Python `audioop` deprecation warning remains.

The merged prompt's real OpenRouter grounding evaluation passed 27/30 mechanical
checks. The three failures concern owning an earlier unsupported statement,
unnecessary recognition clarification and availability wording. First emitted
phrase median was 1073.5 ms, nearest-rank P95 4686 ms and maximum 4695 ms. These
are synthetic agent-only measurements under concurrent integration-test load,
not an isolated performance comparison or telephone latency acceptance. The
quality gate remains open; publication must not be interpreted as a rollout.

No new GPU ASR-quality benchmark, real phone call, hosted CI or clang-tidy run is
claimed. Historical candidate failures remain documented instead of being promoted
to passes by this consolidation.
