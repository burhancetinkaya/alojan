# Declared post-call outputs candidate — 2026-10-26

AGP-08 / M4–M5, ADR 0011, US-07/08 and requirements §9.3–4/12/14–16.
Ponytail full: reuse the existing summary request, scoped tool execution storage,
immutable releases/events/grants, independent delivery worker and Next/shadcn UI.
No new dependency, service, migration, model request or tool invocation.

## Result and review

Agents can declare up to eight typed conversation or reviewed selected MCP output
fields. Conversation extraction shares the existing bounded summary request with
no tools. Tool fields project explicit object properties from the highest successful
invocation ordinal completed before call end, restricted to the exact workspace,
call, release and selected aliases. Raw tool results never enter delivery projections.

Release v4 pins definitions. Review v3 additionally pins selected tool bindings,
including fixed parameters, so changes require new owner consent. Final event v2
records bounded values and done/missing/failed/unavailable states. Existing empty
output drafts and historical releases/reviews retain their schema and digest.
Values can be mapped only into the HTTP JSON body alongside their status. Synthetic
previews preserve scalar/list types; saving or reviewing cannot send a request.
Call details show escaped outputs under the existing workspace access policy.

The UI supports declaration, selected tool properties, exact consent and mapping.
All limits remain enforced server-side: four object path segments, no arrays or
wildcards in paths, 512 characters per string, eight array items, 1 KiB per value,
finite bounded numbers and existing request/review budgets. Null does not invent data.
Summary failure does not discard independent selected tool results; invalid output
values do not discard a valid summary. Existing calls are not re-finalized or replayed.

Reviewed affected contracts, runtime consumers, scoped SQL/roles, grants, callers,
fixtures, frontend controls and the full task delta including new files. The summary
role alone gains bounded-column SELECT access to tool execution rows under RLS;
management/actions/records cannot read raw output, and summaries cannot update it.
A huge integer guard now checks the numeric bound before finite conversion; regression
coverage prevents OverflowError. The new PostgreSQL example is read-only and does
not create agents, permissions, jobs or network requests.

## Primary Linux evidence

- Broad compatibility: **234 passed in 183.25s**, including the initial eight output
  cases, HTTP/actions/grants/delivery, summaries, scoped records, releases/preparation,
  agent runtime, MCP and call management.
- Expanded output checks: **11 passed in 9.29s**, including least-privilege/RLS,
  fixed-tool-parameter consent invalidation and executable read-only SQL example.
  These overlap the broad suite and are not additive.
- The installed real Agents SDK with a scripted model validates the dynamic structured
  schema, one request and no tools. This is simulated inference, not model quality.
- Final HTTPS browser harness: **33 passed in 57.5s**, followed by all database
  invariants passing. Real restricted-API journeys plus intercepted UI contracts;
  synthetic external transports only. Evidence on Linux:
  `.local/web-validation-ae1d91a67b944d8483fa3f15ea9580b0`.
  Harness reports zero production writes and zero external sends.
- Pinned Linux Node TypeScript and Next production build passed. Separate management,
  worker and web images built. Restricted management container checks passed with
  actual limited database roles. Frozen action/summary imports passed with network
  disabled; independent voice-preparer imports passed without dependency changes.
- Final Ruff check/format passed for 17 Python files; pinned Prettier 3.8.3 and
  TypeScript passed for eight affected UI/test files. Screenshot review confirms the
  declared-output editor and typed mapping fit the existing flat design.
- All 26 source-manifest hashes match Mac/Linux.
- Graph refreshed without persistence: 6,794 nodes / 24,372 edges. No graph artifacts,
  secrets, recordings, full numbers or caller transcripts are included.

Earlier diagnostic failures are not acceptance. Test scaffolding initially needed
corrections to exception expectations, prepared-version fixtures and the scripted
backend/client setup. A frontend formatter started before file transfer completed;
the corrected check passed. Three browser runs passed 31 tests and failed one existing
HTTP test because its selectors assumed a single connection. The test now explicitly
selects and scopes review/revocation to Synthetic CRM when another connection exists.
The new declared-output journey passed throughout. Final results above supersede
these failed runs; no failed/skipped check is counted as successful.

## Candidate identities and activation

| Application | Candidate image |
| --- | --- |
| Management | `sha256:cb001b80b125ed883f24ffe0dcbf248ed40045f93495753074538dde01c3be06` |
| Action/summary worker | `sha256:ba99ed19f6218a342b3726a5b33c898060b745de1ad545a993039354641b0483` |
| Web | `sha256:381e69214afb72156245b1b1575d0129daa744fc42d2fb1748813ba2fb6e8e1c` |

Sources are copied to the authorized Linux checkout; maintained documentation is
staged separately under `.local/agent-platform-design-review/implementation/`.
No serving migration/restart, ingress/environment replacement, real model/provider,
MCP/webhook/Telegram send, synthesis or SIP/RTP call occurred. Kübra/EMA and the disabled
second mapping retain their prior state. No commit, push, PR or merge was performed.
The preceding HTTP candidate migrations and scoped-role provisioning plus all v4
consumers require coordinated activation before publishing declared-output agents.

## Remaining acceptance

Additional event filters and explicit optional transcript policy remain AGP-08 work.
Nested mapping and dynamic paths remain unsupported. Real model extraction accuracy,
receiver TLS/authentication/idempotency, approved MCP/provider behavior, load/latency,
concurrent-call capacity and carrier/public-launch gates are not established by these
synthetic tests. No claim of zero extra summary latency or real model readiness.
