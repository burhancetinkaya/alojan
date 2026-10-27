# MCP selection and owner consent — 2026-10-26

AGP-07 / M4–M5, ADR 0011, requirements US-08, §9.3/12/14–16.
This is the reviewed authoring/permission stage, not an executable MCP release.

## Implemented behavior

- Migration 0021 adds operator-owned immutable `mcp_tool_reviews` and scoped
  `mcp_tool_grants`. Composite keys bind discovery/connection/workspace; forced RLS
  separates workspaces. Revoked records cannot be changed or re-enabled.
- The private CLI approves an exact currently discovered read capability only after
  implementation review. Remote hints never grant permissions. Management and
  discovery service provisioning rejects forged capability-review privileges.
- Existing draft APIs accept up to eight explicitly selected tools with distinct
  namespaced aliases, usage guidance and bounded nonsecret fixed parameters.
  Cross-workspace, revoked, unreviewed and changed selections are rejected.
- Closed, bounded schemas use the existing jsonschema 4.26.0 validator. Fixed
  properties are removed from the model schema; attempted overrides are rejected.
  Combined arguments receive full validation. Recursive references, regex,
  combinators and unbounded/open schemas remain unsupported.
- Owner consent reviews pin workspace, agent, immutable connection endpoint,
  capability-review identity, exact tool description/schemas, alias, fixed values,
  guidance and derived runtime schema. Draft version/digest checks reject stale
  requests. Concurrent identical consent is idempotent. Prompt text is never consent.
- A live grant lookup requires an enabled issuing owner; revocation does not allow
  old consent to be resurrected. New discovery cannot broaden selected tools. An
  unrelated tool addition leaves the selected tool intact; a selected change blocks it.
- Shared compilation explicitly rejects MCP selections until release/admission/
  invocation support is implemented. Preparation and publication therefore cannot
  advertise unusable MCP agents. No new release manifest version is emitted here.
- Empty MCP configuration is omitted from serialized drafts, preserving historical
  digests. No per-turn database or discovery work was added. Management validates
  schemas; voice-preparer imports retain their independent dependency environment.
- Repeatable PostgreSQL diagnostics show review/grant metadata without seeding
  permission, exposing fixed values or initiating a request.

## Linux checks

All DB tests used disposable schemas and restricted service roles on the authorized
Linux host. Synthetic manifests contain no credentials or caller content. No network
MCP discovery or tool invocation was performed.

1. Combined MCP discovery/selection, draft/release/runtime, action-consent, native
   account, number-routing and legacy migration suite: **171 passed in 58.59s**.
2. After isolating optional MCP imports from voice preparation: selection, draft,
   voice-job and voice-pack suite: **61 passed in 18.15s**. The actual frozen
   voice-preparer environment successfully imported `alojan.voice_worker` without
   adding jsonschema to that service.
3. Final selection tests, including real API catalog access, direct publication
   rejection and repeatable diagnostic SQL: **27 passed in 10.53s**.
4. Ruff check and format check: **12 files passed**. Local `git diff --check` passed.
5. Management production image built with the frozen isolated dependency lock and
   CPU/memory limits. Real restricted-container HTTP validation passed against the
   final image: registration, drafts, qualification/number guards, MCP queue and
   session revocation. Test container/roles/schemas were cleaned up by the validator.

These suites overlap; their counts must not be added together. No skipped tests
were reported. Existing HTTPS/browser journeys were not rerun: there is no UI edit.
Initial lint found two unused test imports; both were removed before validation.
Review found that fixed-parameter projection must reject root object enum constraints;
that case now has a regression test. Optional management imports were also separated
from the voice-preparer dependency set and verified in its actual frozen environment.

Final candidate image (not serving):

```text
alojan-management:mcp-selection-20261026
sha256:8d9769c5d7b992c342efb45a59bc14275722043040b827468b2f90ad1aaba9fb
```

The earlier image `7b9654bf466627b9c30835bcd07dd6cda9531b7228e44c0c73b2a21c6cf76c90`
passed container checks before the optional-import change; final checks used the
identity above. Source transfers were selective and compared before edits. No
production schema migration, service restart, route change or external send occurred.
Migrations 0020/0021 remain candidate-only. Existing Kübra and disabled second-number
configuration were not activated or altered by this work.

## Remaining gates

Next AGP-07 work is immutable MCP release pinning, call admission/readiness and
schema-drift handling, bounded execution/output filtering, cancellation and live
revocation fencing. Only then remove the compiler gate and expose the builder UI.
OAuth, external write tools, real approved-server/TLS acceptance and carrier/load/
latency evidence remain separate. This stage does not certify runtime performance
or authorize any external request. AGP-08 HTTP actions and public launch remain open.
