# Voice response plan review — 2026-10-27

Scope: proposed VXP-01–06 under AGP-06/07/09, PERF-02/03, M2/M4/M5,
US-04/05/06/08. The owner requested independent subagent review of a natural
telephone experience plan including Jev. This records design review, not runtime
validation or implementation approval.

An independent review agent read the proposal and relevant implementation and
requirements. The parent accepted these findings and revised
[the plan](../VOICE_RESPONSE_EXPERIENCE_PLAN.md):

| Finding | Disposition |
| --- | --- |
| P1: Existing waiting music updates audio timestamps and could permanently suppress a naive quiet watchdog. Existing waiting-phrase/receipt contracts were omitted. | Reuse the existing contracts; distinguish music from speech; define music suppression and no resumption after first spoken interim in v1. Feature-off behavior stays unchanged. |
| P1: Finishing a filler sentence before the actual answer can violate the existing P95 <=50 ms non-regression bound. | Add segment-level preemption experiment, initial <=40 ms fade budget, actual final-ready-to-useful-RTP measurement and audible-quality gate. Disable failing policies rather than relax the gate silently. |
| P1: Generating metadata in the same model call still delays complete tool arguments. | Add paired dispatch P50/P95 measurements, no incomplete-JSON dispatch, no repair round trip for optional metadata and feature disablement on regression. |
| Speculative Jev/primary planner race adds ownership and duplicate-effect complexity. | Remove it from first delivery. Fast routing remains a narrow decision-first experiment with explicit fallback-delay measurement. Any later race needs a separate all-effects ownership design. |
| Jev may add an unnecessary remote decision when tool state is already known. | Begin with synthetic Turkish shadow evaluation; deterministic category selection is the comparator; do not call Jev on every turn merely to pick a filler. |

The same reviewer rechecked the revised plan and reported no remaining P1 planning
ambiguity in first-delivery scope. Its final wording note was applied: Jev may improve
responsiveness only if evaluation passes. This is not runtime approval or evidence
that the proposed audio preemption budget is feasible.

The resulting delivery order is lifecycle/prepared speech, conditional same-model
dynamic speech, Jev shadow evaluation, then optional proven read-only fast routing.
AI disclosure remains; natural conversation does not imply human impersonation.

Checks: primary official Jev/API/platform documentation reviewed; current source
paths inspected through the knowledge graph and targeted literal searches. No live
Jev request, GPU benchmark, generated voice asset, carrier call, tool execution,
deployment or agent setting change was performed. Documentation formatting checks
are separate from performance, semantic quality and handset acceptance.
