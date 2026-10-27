# Owner-provided external integration checks — 2026-10-26

AGP-07/08 / M4–M5, ADR 0011, US-07/08 and requirements §9.3–4/12/14–16.
Owner supplied and corrected the MCP endpoint to
`<MCP_ENDPOINT>`, and authorized a Google GET for connectivity.
The earlier `<DEPLOYMENT_HOST>` address was not contacted.

## Observed primary Linux results

The production `discover` implementation, pinned SDK/protocol, public-address validation,
DNS-pinned TLS and bounded response handling discovered **39 tools in 1.241 seconds**.
No bearer credential was supplied. The exact manifest is retained privately under
`.local/real-integration-20261026/hindsight-manifest.json` on Linux. Discovery is not
tool execution, operator qualification, owner grant or permission to run write tools.
No Hindsight bank, memory, directive, document or other data was created/changed/deleted.

One GET to `https://google.com/`, using the delivery destination resolver and the same
vetted literal/TLS hostname connection boundary, returned **HTTP 301 in 0.536 seconds**.
TLS validation succeeded, redirects were not followed, and no call data, credentials,
request body or personal data was sent. This proves external HTTPS connectivity only.
It is not a passing post-call POST/PUT/PATCH receiver, authenticated webhook,
idempotency, callback or payload-delivery acceptance check. HTTP action methods remain
POST/PUT/PATCH; this diagnostic GET did not change the public action contract.

The first diagnostic command failed before network access because its explicit source
PYTHONPATH was missing. The corrected invocation produced the results above.

## Initial incompatibility (resolved by the following candidate)

The real discovered `list_banks` schema has optional nullable string/default fields,
unbounded integer fields and a FastMCP wrapped string output. `get_bank_stats` likewise
uses a nullable optional bank ID and wrapped string output. The existing production
`validate_tool` rejects them with `MCP schema keyword unsupported` and
`MCP schema type unsupported`, respectively. This is not a network/authentication failure.
No operator review, release, grant or remote tool invocation was attempted after rejection.

Next implement a bounded qualification path for this common schema subset, preserving
raw schema/digest pinning and strict fixed-argument ownership. Review every schema
consumer, preserve existing historical semantics, and retain finite depth/item/string/
byte ceilings, closed objects, local-reference restrictions and output validation.
Do not simply disable the validator, trust readOnlyHint as permission, silently expose
write tools, or advertise unsupported controls. Add Hindsight-shaped synthetic regressions
before rerunning compatibility/browser checks. Then qualify only the inspected read
operation `list_banks`, with an opaque synthetic unmatched query, limit 1 and offset 0,
in an isolated disposable owner workspace; exercise the actual granted executor and
revocation. No real bank content or write operation is needed for that acceptance.

Real structured model extraction, full receiver acceptance, coordinated activation,
matched voice/load/rollback acceptance and separate public-launch/carrier gates remain
open. These connectivity observations do not make the goal complete.


## Follow-up: granted read acceptance completed

The bounded qualification candidate resolves the recorded schema rejection. A fresh
production discovery in an isolated workspace found 39 tools in 1.277s. Exactly one
inspected `list_banks` operation, pinned to the original digest and an unmatched random
query/limit 1/offset 0, succeeded through the restricted real executor in 0.794s. The
wrapped result contained an empty bank list and total zero. Fixed-argument override
and post-revocation attempts made no remote tool call. Disposable DB state was removed;
no production agent/profile/grant or remote memory data changed. See
[complete candidate evidence](mcp-schema-2026-10-26.md).

Read semantics were checked against the official
[Hindsight MCP reference](https://github.com/vectorize-io/hindsight/blob/main/skills/hindsight-docs/references/developer/mcp-server.md).
That reference is not an attestation of the deployed server's binary/source revision.
This proves one none-auth read integration, not all 39 tools or external write acceptance.
The earlier Google 301 observation remains connectivity-only.
