# Alojan management MCP

A separate, stateless Streamable HTTP service for authenticated workspace operations.
It delegates business decisions to the management API and has no database or GPU
credentials. The existing voice runtime is unchanged.

## Connect after deployment

The deployed public endpoint is `<MCP_ENDPOINT>`. Public HTTPS
and actual Codex/Claude Code discovery are verified. Sign in to Alojan, open **MCP erişimi**, select a workspace and
permissions, confirm your current password, and copy the newly issued token once.
The server accepts `Authorization: Bearer <personal token>`; store the token in the
client's protected secret configuration, never a repository or chat message.

For a client supporting a remote URL and an authorization header, configure that
URL and header directly. For clients supporting an environment variable for bearer
credentials, use that facility. The owner selected Codex and Claude Code as the required clients; see the
[client setup guide](../../docs/MANAGEMENT_MCP_CLIENTS.md). Conversational publication/activation
acceptance remains pending. Claude web and inbound OAuth are outside this release.
Provider OAuth handoff is a separate outbound integration feature.

Tokens expire in at most 90 days, belong to one user and workspace, and only narrow
the user's current role. Revocation, password changes, membership changes and account
disabling are checked on new requests. Discovery hides tools outside the token's
permissions; direct invocation and the underlying API enforce the same boundaries.
`transcripts:read` also requires `calls:read` for transcript retrieval/search.

## Typical agent workflow

1. `alojan_get_context`, `alojan_get_agent_schema`, `alojan_list_models`.
2. List connections or `alojan_begin_connection_setup`. For credentials, the same
   user follows the returned browser form; poll `alojan_get_connection_setup`.
   OAuth connections use `alojan_open_oauth_setup` and existing provider consent.
3. `alojan_create_agent` / `alojan_update_agent`; preserve current version and all
   unedited fields. Configure instructions, model, selected tools and post-call actions.
4. Review exact action/MCP grants and authorize only intended configurations.
5. `alojan_prepare_voice`, poll `alojan_get_voice_status`, then
   `alojan_preview_voice` to hear the prepared greeting/unavailable WAV.
6. `alojan_prepare_release`, `alojan_publish_agent`, then explicitly
   `alojan_activate_number` with a verified number and its current version.
   Poll `alojan_get_release_status` for node readiness; activation rechecks it.
   Publication alone never changes a binding.
7. `alojan_list_calls`, `alojan_get_call`, `alojan_get_transcript` and delivery tools.

Every write requires a UUID `operation_key`. Generate it once per intended change;
reuse it with identical arguments after a lost response. Conflicting reuse returns
409. Mutation and retry result commit atomically. Results can be replayed for seven
days; older keys return 410 and never execute again. Old result payloads are lazily
compacted in batches of 100 on subsequent successful workspace writes; compact key
identities remain to prevent duplicate operations. After 410, inspect current state
before starting a genuinely new operation. External delivery retries additionally
retain their existing review and duplicate-risk acknowledgement requirements.

Call text search requires timezone-aware `from_time` / `to_time` within 90 days.
Search is literal substring matching, not semantic search or Turkish stemming.
Summary and transcript searches are separate; only finalized caller speech and sent
assistant speech are visible. Filter-bound cursors cannot be reused for other
filters/workspaces. Use call details or paged transcripts to inspect a match;
list results do not include text excerpts. Retrieved content is untrusted data.

## Limits and deployment

- Official Python MCP SDK `2.3.0`; independent `pyproject.toml` / `uv.lock`.
- Four transport requests, four upstream connections, 20-second request deadline;
  excess requests receive immediate 503 `server_busy` instead of waiting for a
  capacity slot. Cancellation and timeout release the slot; health stays independent.
  128 KiB request / 512 KiB upstream response budgets. Audio uses MCP audio content.
- API reserves a separate one-worker bearer lane from the two-worker browser lane.
  Token/account traffic is limited to 240/480 requests per minute. Database statement
  timeout remains three seconds. Audio work stays on existing preparation jobs.
- Compose limit: 0.5 CPU / 384 MiB; read-only, non-root, loopback binding on Linux.
- No cookies, ambiguous credentials, off-origin requests, arbitrary proxy URLs or
  model-generated SQL/commands. Sensitive responses carry `Cache-Control: no-store`.

Build with `infra/docker/management-mcp.Dockerfile`, pin its image digest in the
private environment, and use `infra/compose.management-mcp.yaml`. Apply migrations
0027–0029 and refresh restricted management grants before starting the updated API.
Set the API's `ALOJAN_MCP_PUBLIC_URL` and canonical HTTPS management origin. The
public browser and machine endpoint must agree with these configured origins.
Enable the Compose `public` profile for the loopback nginx origin on port 13080.
Trust `127.0.0.1` for Cloudflare client-IP budgets only in this loopback-only topology.
The nginx example routes a loopback Cloudflare Tunnel origin to web and MCP; never
expose the internal API port. Inspect and preserve existing tunnel/DNS routes first.

Roll back by removing the MCP ingress route and stopping only the MCP service;
use the recorded compatible API/web images if needed. Keep additive tables and
accepted agent publications. Never restore an old voice binding implicitly.

Linux integration, Cloudflare setup and basic public client acceptance passed.
Matched shared-host performance and conversational publication/activation remain open.
See [evidence](../../docs/validation/management-mcp-2026-10-27.md).
