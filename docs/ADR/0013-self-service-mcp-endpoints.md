# ADR 0013: Self-service MCP endpoint registration

Date: 2026-10-27.
Status: Accepted by the owner's explicit request to remove the server address
allowlist and allow users to add MCP servers without prior operator approval.
Extends ADR 0011; AGP-07/09, M4–M5, requirements §11.2–11.3, US-08.

## Decision

Remove the manual exact-URL allowlist from outbound MCP discovery and execution.
A workspace owner can save any canonical public HTTPS MCP endpoint accepted by the
existing URL parser and initiate discovery. Adding a new hostname needs no private
configuration file or service restart. `ALOJAN_MCP_APPROVED_ENDPOINTS_FILE` is retired.
Enable the optional executor through its dedicated database credential alone; its
purpose-bound secret key remains required for encrypted credentials.

Preserve authentication, workspace isolation, immutable connection identity, scoped
per-agent tool grants and revocation. Every outbound request still validates its
exact saved destination, resolves and rejects non-public addresses, pins the socket
address and verifies the original TLS hostname. Redirects/proxies/compression remain
disallowed; timeouts, concurrency and size limits stay bounded.

## Consequences

Users no longer depend on an operator to register a server URL. Network capability
is broader across public hosts, while internal services and arbitrary destinations
remain inaccessible. This removes an administrative address gate, not technical
protocol/schema compatibility checks or the existing tool qualification/grant model.
No tool is auto-approved, no credential is shared between connections, and no agent
is published or rebound. OAuth issuer/client registration remains a separate
compatibility concern. Historical `endpoint_not_approved` failures are retained;
retry uses normal discovery rather than mutating historical job results.

No database migration is needed. Deploy compatible discovery and agent runtime
consumers together; remove obsolete environment variables and secret mounts. Retain
the prior private config only as rollback evidence. Existing releases and voice assets
remain byte-for-byte unchanged.
