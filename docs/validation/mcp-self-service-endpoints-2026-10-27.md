# Self-service MCP endpoints deployed

AGP-07/09 / M4–M5, US-08, requirements §11.2–11.3 and ADR 0013.
The owner explicitly requested removal of manual server address preapproval.

## Implementation

Removed the operator URL allowlist from discovery, execution preparation and the
managed launcher. Canonical public HTTPS URLs saved by workspace owners no longer
need a second file entry or a service restart. Retired the environment variable,
secret mounts and Compose example requirement. Existing endpoint parsing and the
DNS-pinned transport remain unchanged, including private/reserved-address rejection,
TLS hostname verification, exact destination, no redirects/proxies/compression and
bounded time/body/concurrency. Workspace membership, revoked-credential handling,
reviewed tool schemas and agent grants remain required.

Historical discovery failure rows are retained without migration. Failed discoveries
can be retried normally. This does not implement OAuth dynamic client registration,
new protocol versions, new schema forms or unrestricted remote execution.

## Verification

Primary Linux: **147 passed in 84.39s** across MCP discovery, runtime, OAuth, tool
selection and managed startup. Regression coverage exercises credential-bound saved
endpoints without an operator list, actual scoped worker/executor roles, revocation,
private-address/transport rejection, cancellation, failures and secret redaction.
External servers and speech inference are synthetic in these tests. An initial test
command named a nonexistent test file; zero tests ran and it was corrected before
qualification. Mac Ruff, task-diff review and whitespace checks passed.

Built minimal source derivatives of the exact running images without dependency
updates or network access during build. Each copied source file was checked against
its pre-edit running-container bytes. Deployment initially stopped before mutation
because the helper lacked the generated-protobuf import path; corrected and rerun.

## Deployment

Paused the idle host voice-preparer and acquired its existing coordinator/advisory
locks. Closed native admission, received a fresh drained acknowledgement and checked
zero active/initializing calls before replacing the agent. Replaced only agent and
MCP-discovery containers. Removed both consumers' obsolete environment variables and
endpoint-secret mounts. Twelve other Alojan container identities/start times were
preserved. Existing publications, releases and number bindings were unchanged.

- Agent: `sha256:28d6f400731e319bd158bcb814d04640078438ca150a7e31ca36c1ab1cb15420`.
- Discovery: `sha256:653ed7e43a964f923d5ace47f206683e4e96781c6678495374fc69c879ab12d8`.
- Agent healthy; discovery running; both have zero restarts.
- One bound number has fresh release readiness; native admission reopened and the
  host preparer is active. No new handset call or external business tool was invoked.
- Nazlı remains a draft. Deliver2.ai protocol/schema compatibility is still pending;
  removing address preapproval does not establish tool-call readiness.

Private source/config backups, base-image references and rollback receipts are under
`.local/mcp-self-service-20261027/`. Rollback restores the two recorded image/config
pairs under the same drain procedure; never restore database data or old bindings.
No load/soak, new GPU calibration or carrier acceptance is claimed.
