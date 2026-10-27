# Codex and Claude Code setup

MCP-01/06, ADR 0012, requirements §11.3. The owner clarified that **Codex and
Claude Code are sufficient**. Claude web/Desktop remote connectors, inbound OAuth
and general cloud-client compatibility are outside this release's acceptance scope.
Obtain the deployed endpoint from the authenticated MCP access screen. Both installed clients
passed public HTTPS discovery; SDK draft mutations/retries/revocation also passed.
Conversational publication/activation and matched voice performance remain pending.

## Personal access

Sign in to Alojan, open **MCP erişimi**, choose permissions and create a token.
Save the copy-once value in a protected local secret store or environment variable
named `ALOJAN_MCP_TOKEN`. Set `ALOJAN_MCP_PUBLIC_URL` privately to the endpoint
shown in Alojan. The client process must inherit both variables. Do not put
the token in a prompt, repository, command argument or shared connector. After
changing a desktop process environment, restart that client.

Use read permissions for initial discovery. To configure and activate agents,
explicitly add agent/connection writes, publication and number management. External
write grants and delivery retries are separate delegations. Full transcript access
requires both `calls:read` and `transcripts:read`. Every token belongs to one account
and workspace; disabling it in Alojan invalidates subsequent requests.

## Codex

The installed Codex CLI exposes a Streamable HTTP URL and bearer-token environment
variable option. Configure once:

```sh
codex mcp add alojan --url "$ALOJAN_MCP_PUBLIC_URL" --bearer-token-env-var ALOJAN_MCP_TOKEN
```

The command writes the resolved endpoint to your private Codex configuration.
Do not commit that generated configuration.

These instructions were checked against installed `codex-cli 0.163.0-alpha.10.2`
help and generated local app-server schemas. They do not install anything into the
user's existing configuration as part of development.

## Claude Code

Merge the following entry into the project's `.mcp.json`, preserving other entries.
The ignored file references environment variables and contains no endpoint or token value:

```json
{
  "mcpServers": {
    "alojan": {
      "type": "http",
      "url": "${ALOJAN_MCP_PUBLIC_URL}",
      "headers": {
        "Authorization": "Bearer ${ALOJAN_MCP_TOKEN}"
      }
    }
  }
}
```

Launch Claude Code from an environment containing both variables, approve the
project's MCP configuration when prompted, and check the server in `/mcp`.
Claude Code documents HTTP headers and variable expansion in MCP configuration;
installed `claude 2.1.87` help also exposes HTTP/header configuration.
[Official Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).

## Live acceptance sequence

1. Ask the client to read `alojan_get_context` and list agents. Confirm the intended
   workspace and permissions; do not rely on a successful TCP connection alone.
2. Create a synthetic draft through the client, repeat the same operation key and
   confirm there is one draft. Edit with its current version.
3. Configure intended connections, tools and post-call actions. Enter any new
   secrets through the authenticated Alojan browser handoff, never the conversation.
4. Prepare voice assets, preview them, prepare and publish the exact draft.
   Poll `alojan_get_release_status` at its returned interval. Readiness is an
   expiring observation; activation always rechecks it.
5. Explicitly activate an authorized verified test number. Confirm the binding with
   `alojan_list_numbers`. Inspect a real call and its summary/transcript as permitted.
6. Revoke the test token and confirm the next protected request fails.

Run this sequence separately for Codex and Claude Code. The SDK, ASGI tests and
local discovery checks support the implementation but do not replace public HTTPS,
real-client mutation and primary-host performance acceptance.
