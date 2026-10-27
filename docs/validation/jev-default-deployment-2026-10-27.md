# Default-on MCP-scoped Jev deployment — 2026-10-27

Scope: VXP-04/06, AGP-06/07/09, PERF-02/03, M2/M4/M5, US-04/05/06/08;
ADR 0014. The owner explicitly requested deploying the recent-context candidate,
enabling Jev by default and running it automatically for MCP-tool agents.

## Implemented behavior

Managed startup now defaults `ALOJAN_JEV_SHADOW` to `1`; an explicit `0` disables
it. Other values still fail startup. Before accessing provider credentials or
creating an observation task, the backend requires a compiled runtime with a
published MCP tool grant. Compilation creates that grant only for selected,
authorized conversational MCP tools. A connection by itself, a Telegram action,
or other non-MCP capability does not qualify. Existing tool preparation/validation
runs before the primary model and shadow are dispatched.

Eligible final model turns receive the last three bounded call-local dialogue
turns from the [context change](jev-dialogue-context-2026-10-27.md). Recovery and
local closing shortcuts, existing capacity/deadline/breaker controls and explicit
operator disable still suppress observations as applicable. Jev remains purely
observational: it cannot choose/execute tools, change permissions, produce speech,
or interrupt playback. No agent instruction, release or number binding is edited.

## Tests and image qualification

Primary Linux host: **154 tests passed in 17.08 s**, including decisions, shadow,
agent/runtime, response experience and actual managed-startup process/DB suites.
Coverage includes enabled default, explicit enable/disable, invalid flag rejection,
non-MCP skipping before credential access, scoped context, cancellation and stale
results. Ruff lint/format checks passed for changed executable code. A subsequent
Decisions docstring update was included in the final image; no behavior changed.

Built a source-only image layer on the exact serving image; only `backend.py`,
`managed.py`, and `decisions.py` changed. Installed dependency/model versions,
other services and native media binaries were retained. The final image passed
an isolated network-disabled smoke using synthetic HTTP: non-MCP skipped,
MCP history observation accepted, only one synthetic request sent.

- Previous image: `sha256:93758d5e26f05c2fde038f665e4eac35d79ad5aca781213bc00e725f031001c3`.
- Installed image: `sha256:e0ae416f62188bea3b12b3f0ac398670b99d0d419d852222b9816f20da911632`.

## Serving deployment

Verified no active/initializing calls and no preparation job. Held the existing
PostgreSQL preparation advisory lock, stopped the idle voice preparer, acquired
its file lock, and received fresh native gateway draining/drained acknowledgements.
Saved the prior private Compose config for rollback, switched only the agent image
and explicitly enabled Jev. Recreated only the agent, waited for health and bound
route readiness, then reopened native admission and restarted the preparer.

Read-only post-deployment verification confirmed:

- Running image and all three source-file hashes match the qualified candidate.
- The actual managed process environment contains `ALOJAN_JEV_SHADOW=1`.
- Agent healthy, gateway admission open, bound routes ready, preparer active.
- Number IDs/versions/active bindings/enabled state are unchanged across deployment.
- Published Kübra has no MCP tool grant and retains one active number binding;
  it does not dispatch Jev. Published Nazlı has an MCP tool grant and no active
  number binding; it will be eligible when used on an authorized call.

No extra message, handset test, call recording or remote MCP tool execution was
performed. The earlier real Jev contextual synthetic measurements remain the
model evidence; this deployment smoke uses a synthetic provider response and is
not another real-model/handset test. No GPU or full-path latency acceptance is
claimed. Noisy-speakerphone false interruptions remain open.

## Tool selection discussion and rollback

The current classifier does not receive tool candidates and cannot rank them.
A proposed future adviser could rank a bounded set of already-authorized tool
aliases using the question/history and tool descriptions; it must not fabricate
IDs/arguments, enlarge grants or execute tools. Measure against the primary model's
selection first. Waiting for advice before initial model dispatch adds a serial
latency cost; a parallel shadow cannot retroactively change that first selection.
This proposal is not implemented or activated by the present deployment.

Rollback uses the saved private prior image/config under the same maintenance
fences; `ALOJAN_JEV_SHADOW=0` also disables requests without changing releases.
Private build, rollback and verification artifacts are kept in
`.local/jev-default-20261027/`. No credentials are included in this report.
