# Deliver2.ai MCP schema compatibility — 2026-10-27

AGP-07/09 and MCP-06, M4–M5, US-08, requirements §11.2–11.3;
ADR 0011–0013. Owner requested deliver2.ai tool-schema compatibility for Nazlı.

## Behavior and boundaries

Accept negotiated MCP `2025-06-18` and `2025-11-25`, recording the actual version
in discovery. The SDK sends the negotiated HTTP version on subsequent requests.
`outputSchema` is optional in the [MCP tool contract](https://modelcontextprotocol.io/specification/2025-06-18/server/tools);
version negotiation follows the [lifecycle contract](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle).

New `bounded.v2` qualification preserves UUID and date-time constraints, checks
formats for fixed and runtime parameters, and retains existing schema limits.
Date-time accepts explicit-offset RFC3339 timestamps with ordinary seconds; leap
seconds are intentionally unsupported. No dependency was added. Defaults remain
server-side; omission is distinct from null. Unknown schema keywords still fail.

A tool without an output schema pins `output_schema:null`. Accept an object from
`structuredContent`, or one JSON-object text block if structured content is absent.
Do not accept arbitrary text, lists as the root, images/resources, multiple text
blocks, non-finite numbers, null characters or results beyond 8 KiB / eight levels.
Schema-less results cannot supply typed post-call output paths. A declared schema
still requires structured content and validation against the exact qualified schema.
Results remain untrusted data, never instructions. Existing secret-echo, workspace,
revocation, cancellation, concurrency, deadlines and network controls are unchanged.

MCP grant v3 / release v9 distinguish the new semantics. Older grants, `bounded.v1`
and release digests are unchanged; downgrade attempts fail. The no-answer enqueue
path accepts v9. API, agent, background workers and host voice preparer must support
v9 before publication. No migration or automatic grant for arbitrary servers.

## Primary Linux verification

- Core discovery/runtime/schema/Deliver2.ai tests: **135 passed in 63.13s**.
- Additional new-policy, grant/OAuth, releases/lifecycle/readiness group:
  **110 passed in 50.92s**. These groups overlap; counts are not unique totals.
- Real HTTPS browser harness: **46 passed in 1.3m**, disposable schema, no
  production writes or external sends. Includes schema-less save/consent and
  existing schema-qualified editing; production Next build/TypeScript passed.
- Ruff check passed. Real catalog fixture contains all 19 tool definitions and
  no team records or credentials; all qualify under bounded.v2.
- Three existing releases compile identically across old/new agent, API and worker
  images for their model, speech, instructions and voice configuration.
- Real authenticated Deliver2.ai discovery negotiates June 2025 and exposes 19 tools.
  One bounded task-outcome query through the runtime transport completed in **2.077s**
  including handshake; validated JSON was **1811 bytes**. No private response body
  was logged or retained. This is one observation, not a latency/load qualification.

## Deployment

Linux admission was drained and zero active/initializing calls verified. Idle
preparer was stopped under its file/advisory locks. API publication was briefly
stopped while compatible consumers were replaced. API/web, agent, discovery,
summary/delivery workers and immutable host preparer were activated. Eight other
containers (including speech peers and public management MCP) remained unchanged.
Existing routes, releases and publications were preserved; one bound number is
fresh-ready, native admission is open and preparer is active.

Images:

- Agent: `sha256:5c3ecffd194a525b259033be0610cccc3e4004025960bacd117e7a1091b30c59`.
- Background workers: `sha256:d4756b3840de8b12c0c8a9b59c83031417f07b2459ef274243b4fb7503a067d6`.
- API: `sha256:4af88522752ab80c3ecf09526d0fc30721a6075b4d6e57b116ffae5e1c2186a3`.
- Web: `sha256:87406a105c002dec095e8861ea82d233467167112c64096f83a858e6ef60c8bf`.
- Host preparer source: `33cbf372b9f2553f1ae2e5a164e79e6a0beeaaad0ce0c9d5d7e010c3bf2ab831`.

Private reproducible logs/config backups are under `.local/mcp-deliver2ai-20261027/`.
The first image-build guard correctly stopped on the older unused runtime module
inside the discovery image; its exact bytes were checked against the previous
rollout backup before updating. A private review helper initially referenced an
incorrect table name; it failed before writes and was corrected. Neither failure
was counted as a test pass. Local and Linux pre-edit source hashes matched.

No real phone conversation, eight-tool live workload, GPU throughput or matched
voice-latency benchmark was run. Oversized results fail rather than being silently
truncated; agents should narrow filters and use small pages. Nazlı remains a draft.


## Nazlı authoring outcome

Used an ephemeral owner-scoped public management MCP token, then revoked it and
logged out. Live discovery completed with all 19 schemas; eight exact read-only
analytics tools were qualified using the trusted connected deliver2.ai contract,
not annotations alone. Public MCP updated Nazlı to draft v3, reviewed/authorized
the exact grant v3 (31,048 JSON bytes), and read back preview/releases/grants.

Selected task outcomes, cost summary, evaluation scorecard, skill-version comparison,
efficiency reasons/evidence, session analysis context and evaluation coverage.
Task pages are fixed to one; reason groups to five; evidence to one session/turn
without turn text; session trace to one event. Guidance requests narrow cohorts
and explicitly handles missing or oversized results. None of these limits claim
that every possible server response will fit.

No release, voice preparation, number binding, Telegram send or webhook was created
for Nazlı. Public MCP reports publication version zero and no releases. An initial
preview request without its required operation key returned `invalid_arguments`;
the corrected keyed preview succeeded. The authoring helper was corrected to accept
omitted default `mcp_tools` before making its first update. These were operator input
errors, not successful test runs or repeated mutations.

Final read-back validated the exact stored grant with the shared release contract,
confirmed no Nazlı publication, healthy API/web/voice/MCP services, active preparer
and open admission. The health helper's initial incorrect container name was
corrected from Docker inventory before the successful check. Full changed-Python
Ruff and `git diff --check` passed; the local code graph was refreshed.
