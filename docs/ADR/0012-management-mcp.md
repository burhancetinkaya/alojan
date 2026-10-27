# ADR 0012: User-scoped management MCP server

Date: 2026-10-27.
Status: Accepted by the owner's 2026-10-27 instruction to start development and
continue until ready for a live MCP test. Public ingress remains a verified deployment gate.
Extends ADR 0011, requirements §11.2 and US-07/08; preserves DEC-01–15.

## Decision

Provide a separate Streamable HTTP management MCP application and Docker service.
Authenticated users create revocable, expiring, workspace-scoped personal access
tokens in the existing frontend. The owner subsequently clarified that Codex and
Claude Code are the required clients. These clients use the
tokens to manage agents and retrieve scoped call records.

The MCP service translates named tools to the existing management API. It has no
direct database, provider-secret or voice-runtime access. The management API gains
explicit bearer authentication and centralized operation scopes, using the same
membership, version, grant, preparation and number-binding rules as browser users.
Cookie/CSRF protections stay intact. No fabricated browser sessions or privileged
shared service account impersonation is allowed.

Agent publication and number activation remain separate versioned operations. Token
permissions can explicitly delegate publication and bounded external-action grant
management; general edit permission does not confer those powers. Client approval
dialogs and model-supplied confirmation flags are not server authorization proofs.

Deliver full operational UI parity, including connections, tool/action configuration,
voice preparation, releases, number routing, call queries and delivery status/retry.
Account login/password/token issuance remain human account controls. Provider OAuth
and secret entry may require a secure browser handoff; raw credentials are never
returned to the model. Operator-only number verification and tool qualification
remain operator responsibilities.

## Consequences

Use additive token/idempotency persistence and extend the shared call-query API.
No new speech model, broker or orchestration engine. Preserve measured performance
gates and existing voice preparation resource controls. A stable externally reachable
HTTPS endpoint is necessary for cloud clients; the current private preview alone is
insufficient. Personal-token compatibility is validated separately in Codex and Claude Code.
Claude web/Desktop remote connectors and inbound OAuth are outside this release
following the owner's explicit client-scope clarification.

The detailed scope, acceptance criteria and rollout gates are in
[the management MCP plan](../MANAGEMENT_MCP_PLAN.md).
