# ADR 0003: Use the owner's Linux GPU server for development

Date: 2026-10-23 (Europe/Istanbul).
Status: Accepted by the owner's explicit chat request to connect to the supplied
Linux server, copy code there, and build/test there; the follow-up selects `ai/alojan`.
Amends DEC-01 and ADR 0002's primary development environment. DEC-02–15 and product scope remain unchanged.

## Decision

Use the owner's Ubuntu server and `~/ai/alojan` as the primary execution workspace.
The Mac checkout remains available for editing and review. Copy source changes over
SSH before building and testing on Linux. Never transfer Mac virtual environments,
compiled dependencies, secrets, private captures, or knowledge-graph caches.
Keep connection details in ignored local configuration and use existing SSH authentication.

Continue the native C++/Python foundation with an isolated PostgreSQL Compose
project. Keep development SIP, RTP and HTTP on loopback. Use the actual RTX 4080
for hardware checks; inference readiness still requires real pinned models and
their own acceptance evidence. Do not expose services or alter other applications.

This is task U0-01 / M0-08, requirements DEC-01–03 and sections 12, 15–16.
It does not authorize publication, merging, a project license, carrier calls or
unrelated host upgrades. Retain focused `codex/` branches and existing uncommitted work.

## Gates and alternatives

Record Linux results separately from historical Mac evidence. The existing real
SIP/RTP G1 scenario set must still complete before M2–M5 implementation; it may now
complete on the primary Linux development host. A passed subset is not a full gate.
G2 remains a real Netgsm gate, and G3 still requires real inference/API validation.

Remaining exclusively on Mac would not satisfy the owner's request. Making the
remote host the only source copy would weaken local review and recovery, so retain
both source workspaces with explicit synchronization. Do not use destructive mirror
deletion; review remote differences and apply intended removals explicitly.

## Consequences

Build artifacts and private database configuration stay on the Linux host. Model,
network and carrier limitations remain visible in PLAN.md and CALL_TEST_PLAN.md.
The shared server already runs other applications: bound build parallelism and
avoid daemon restarts where a documented reload can apply a configuration change.
See [development setup](../DEV_SETUP.md) for synchronization and execution commands.
