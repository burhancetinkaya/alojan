# ADR 0011: User-managed voice agents, tools and post-call actions

Date: 2026-10-25.
Status: Scope and design direction accepted by the owner's explicit request;
implementation and eventual tested Linux migration authorized by the owner;
frontend and live activation pending acceptance gates.
Supersedes ADR 0010's administrator-only scope, single Telegram target requirement,
and global agent-model/runtime settings. Extends DEC-11 configuration and §1–2,
9–12,14–15; preserves DEC-01–10/12–15 boundaries and ADR 0009 capacity gates.

## Decision

Users manage agents within an authenticated workspace. They register and verify
ownership/routing of a Netgsm DID, write instructions, select system-defined tools,
configure each tool for their agent, select an eligible model/provider and runtime
settings, and configure deterministic post-call actions. Telegram is the first
post-call adapter; HTTP webhook and remote MCP connections are subsequent stages
of the same design. Shared EMA remains the approved voice; no voice cloning.

An immutable agent release binds prompt, profile, model/runtime configuration,
tool configuration, MCP tool manifest, post-call action configuration and audio
assets. A call pins one release. Number routing, credentials and record access
are workspace-scoped and checked server-side. Instructions describe when to use
a tool but never confer permission or override fixed configuration.

Keep system-defined executable handlers; users configure schema-validated data,
not Python, JavaScript, SQL, shell commands or arbitrary code plugins. Selectable
remote MCP tools pass capability/schema review and explicit grants. They do not
expand agent permissions automatically when discovery results change.

Agent-specific settings include model/provider/credentials reference, reasoning,
temperature, output/context budgets, call/turn limits, timeouts, greeting/ringing,
closing and supported conversational calibration. Global settings retain only
infrastructure, supported capability catalog, default templates and hard safety/
resource ceilings. Existing `system_settings` agent fields are a migration source,
not the final ownership model. Agent publication must reject unsupported options
rather than silently changing model/settings. No model switch occurs in this task.

External operations require an authorized workspace owner's grant. Explicit
publication of a bounded tool/action configuration may record a standing grant;
merely naming a tool in the prompt is not approval. Operations without a standing
grant require a separate authorized approval or must not execute. Callers and
model outputs cannot approve. Mandatory disclosure/isolation/recording policies
remain non-overridable. Platform operators can revoke execution with bounded propagation; strict immediate revocation requires acknowledged fencing as defined by the performance plan.

Use existing app-api, agent service, PostgreSQL and a separate background action
worker. Preserve C++ SIP/RTP and call-local cancellation. No separate stack/model
per agent, new broker, general workflow engine or hosted voice orchestration.

## Consequences and migration

[VOICE_AGENT_PLATFORM](../VOICE_AGENT_PLATFORM.md) defines the authoritative new
schema, UI/API, permission, execution, delivery and rollout contracts. The earlier
profile plan remains a historical lower-level reference only where compatible.
Do not rewrite migrations 0001–0003. Add workspace membership and configuration
relations, retain existing UUIDs/revisions, snapshot old system defaults into
agent settings, and quarantine legacy data with unknown ownership. Migrate a
legacy Telegram target into one post-call action; do not send historical results.

Workspace isolation and verified DID possession are prerequisites for self-service;
an entered number is not a right to receive its calls or records. Authentication,
MCP transport and provider implementation versions must be selected/pinned and
validated during implementation. Research links do not authorize installation.
This design does not deliver customer accounts, change live runtime or certify
simultaneous-call capacity. Existing model/carrier/latency limitations stay open.


## Owner follow-up: Netgsm scope and performance isolation

Netgsm IP-directed inbound is the only carrier integration. Keep SIP addresses,
ports, source allowlists and prefix rules in private deployment configuration;
no user-facing generic trunk catalog or REGISTER credential flow is needed.

The HTTP management application must run independently in its own Docker service,
with a separate background worker service. Never embed HTTP management in the
voice process or add it to the live turn path. Per-agent settings are prepared and
pinned at release/call initialization; management outages do not interrupt calls.
The [performance plan](../AGENT_PLATFORM_PERFORMANCE_PLAN.md) defines isolated
resource budgets, explicit GPU preparation windows, measured non-regression gates,
and controlled rollout. These are required implementation gates, not completed
measurements. Native voice deployment remains unchanged during this planning task.


## Owner clarification: automatic technical optimization

The later request supersedes user-editable low-level runtime tuning above. Users
own identity, instructions, business vocabulary, approved model selection, tool/
connection configuration and post-call outputs. Platform-owned immutable engine
presets own model generation defaults, audio/turn calibration, technical budgets,
timeouts and retry policies. The agent release references the selected model's
qualified preset automatically. No per-agent advanced engine override is exposed.
Compatible agents share a preset; different model capabilities may require different
presets. Rollout is benchmarked/canaried and never mutates active calls. Preserve
configuration completeness tests and independent HTTP Docker deployment.

## Owner clarification: native authentication

The owner explicitly selects Alojan's own authentication. Replace the proposed
OIDC dependency with local accounts, adaptive password hashing, opaque revocable
server-side sessions and workspace memberships. Preserve origin/CSRF protection,
bounded login work, privilege checks and audit. Anyone may register and receive
their own workspace with owner rights to create and publish agents. Number ownership
verification remains mandatory before routing. Never ship default credentials.
External identity-provider setup is not a blocker.

## Owner clarification: in-place line testing

On 2026-10-26 the owner confirmed that the existing line is unused and explicitly
authorized tests on that line, without creating another environment or reopening
the old runtime between migration steps. Apply the additive migration to the
backed-up existing database and continue the managed trial on the existing Linux
host/workers. Retain known quality/performance failures and distinguish functional
trial readiness from completed carrier, load and performance acceptance. This
changes the rollout sequence, not number ownership checks, tenant isolation or
external-action approval boundaries. See the [in-place evidence](../validation/in-place-platform-2026-10-26.md).


## Owner clarification: defer post-call summary quality

On 2026-10-27 the owner explicitly asked to skip further summary quality improvement
for now and resume the remaining rollout work. Retain summary generation and all
known failed evidence, but remove post-call semantic/wording quality qualification
from the current owner-directed rollout gate. Revisit it later as deferred AGP-08
work; this is not a pass or a claim of accurate summaries. Durable persistence,
workspace isolation, typed-output validation, action grants and delivery behavior
remain required. Live conversation quality and voice performance are unchanged.
No model switch or production setting change follows from this prioritization.

## Owner clarification: password minimum

On 2026-10-27 the owner explicitly requested an eight-character password minimum.
Registration, password change and private operator recovery accept 8–128 Unicode
characters. Existing scrypt parameters, login rate limits, session/token invalidation,
origin/CSRF checks and audit remain unchanged. No existing password is rehashed or
reset automatically; account recovery requires an explicit owner request.

## Owner clarification: agent instruction variables

On 2026-10-27 the owner requested variables defined on each agent and automatically
injected into its instructions. An optional versioned `prompt_template` holds
bounded literal name/value pairs and an IANA timezone. Reserved platform variables
provide agent/owner names, current local date/time and local day boundaries.
Substitution is one pass in the agent-authored instructions field, on each model
turn, using one trusted UTC clock sample. It never executes expressions, reads
secrets, performs IO or replaces platform policy. Values and timezone are pinned
to the immutable release; published calls do not read mutable drafts.

Absent templates preserve legacy prompt bytes and literal braces. Undefined,
malformed, duplicate and reserved user names are rejected before saving; expansion
must fit the existing prompt budget. UI and management MCP use the same draft
contract. Template-bearing releases require reader version 10; deploy all readers
and the host preparer before enabling publication. No database migration or new
service is needed. Existing audio preparation/publication rules remain unchanged.
