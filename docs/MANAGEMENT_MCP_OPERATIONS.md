# Management MCP operation matrix

MCP-01–05; ADR 0012; requirements §11.3. Generated from the explicit tool catalog.
All writes require an operation key; underlying API business authorization still applies.

| Tool | API operation | Required token permissions |
|---|---|---|
| `alojan_get_context` | `GET @context` | Authenticated token |
| `alojan_list_oauth_providers` | `GET mcp-oauth` | connections:read |
| `alojan_open_oauth_setup` | `GET @oauth` | connections:write |
| `alojan_get_agent_schema` | `GET agent-schema` | agents:read |
| `alojan_list_models` | `GET models` | agents:read |
| `alojan_list_agents` | `GET agents` | agents:read |
| `alojan_get_agent` | `GET agents/{agent_id}` | agents:read |
| `alojan_create_agent` | `POST agents` | agents:write |
| `alojan_update_agent` | `PUT agents/{agent_id}` | agents:write |
| `alojan_preview_agent` | `POST agents/{agent_id}/preview` | agents:read |
| `alojan_prepare_voice` | `POST agents/{agent_id}/voice-preparation` | agents:write |
| `alojan_get_voice_status` | `GET agents/{agent_id}/voice-preparation` | agents:read |
| `alojan_preview_voice` | `GET agents/{agent_id}/voice-preview/{clip}` | agents:read |
| `alojan_prepare_release` | `POST agents/{agent_id}/prepare` | agents:write |
| `alojan_list_releases` | `GET agents/{agent_id}/releases` | agents:read |
| `alojan_get_release_status` | `GET agents/{agent_id}/releases/{release_id}/status` | agents:read |
| `alojan_publish_agent` | `POST agents/{agent_id}/publish` | releases:publish |
| `alojan_rollback_release` | `POST agents/{agent_id}/rollback` | releases:publish |
| `alojan_list_numbers` | `GET numbers` | agents:read |
| `alojan_register_number` | `POST numbers` | numbers:manage |
| `alojan_activate_number` | `PUT numbers/{number_id}/binding` | numbers:manage |
| `alojan_deactivate_number` | `POST numbers/{number_id}/deactivate` | numbers:manage |
| `alojan_list_calls` | `GET calls` | calls:read |
| `alojan_get_call` | `GET calls/{call_id}` | calls:read |
| `alojan_get_transcript` | `GET calls/{call_id}/transcript` | transcripts:read, calls:read |
| `alojan_get_performance` | `GET performance` | calls:read |
| `alojan_list_deliveries` | `GET agents/{agent_id}/deliveries` | calls:read |
| `alojan_get_delivery` | `GET agents/{agent_id}/deliveries/{job_id}` | calls:read |
| `alojan_review_delivery_retry` | `GET agents/{agent_id}/deliveries/{job_id}/retry-review` | calls:read |
| `alojan_retry_delivery` | `POST agents/{agent_id}/deliveries/{job_id}/retry` | deliveries:retry |
| `alojan_review_action_grants` | `GET agents/{agent_id}/action-review` | agents:read |
| `alojan_list_action_grants` | `GET agents/{agent_id}/action-grants` | agents:read |
| `alojan_authorize_action_grant` | `POST agents/{agent_id}/action-grants` | grants:manage |
| `alojan_revoke_action_grant` | `POST agents/{agent_id}/action-grants/{grant_id}/revoke` | grants:manage |
| `alojan_review_mcp_grants` | `GET agents/{agent_id}/mcp-review` | agents:read |
| `alojan_list_mcp_grants` | `GET agents/{agent_id}/mcp-grants` | agents:read |
| `alojan_authorize_mcp_grant` | `POST agents/{agent_id}/mcp-grants` | grants:manage |
| `alojan_revoke_mcp_grant` | `POST agents/{agent_id}/mcp-grants/{grant_id}/revoke` | grants:manage |
| `alojan_list_provider_connections` | `GET provider-connections` | connections:read |
| `alojan_revoke_provider_connection` | `POST provider-connections/{connection_id}/revoke` | connections:write |
| `alojan_list_telegram_connections` | `GET telegram-connections` | connections:read |
| `alojan_revoke_telegram_connection` | `POST telegram-connections/{connection_id}/revoke` | connections:write |
| `alojan_list_http_connections` | `GET http-connections` | connections:read |
| `alojan_revoke_http_connection` | `POST http-connections/{connection_id}/revoke` | connections:write |
| `alojan_list_mcp_connections` | `GET mcp-connections` | connections:read |
| `alojan_revoke_mcp_connection` | `POST mcp-connections/{connection_id}/revoke` | connections:write |
| `alojan_discover_mcp_tools` | `POST mcp-connections/{connection_id}/discovery` | connections:write |
| `alojan_get_mcp_discovery` | `GET mcp-connections/{connection_id}/discovery` | connections:read |
| `alojan_list_mcp_tools` | `GET mcp-connections/{connection_id}/tools` | connections:read |
| `alojan_begin_connection_setup` | `POST connection-setups` | connections:write |
| `alojan_get_connection_setup` | `GET connection-setups/{setup_id}` | connections:write |

`@context` returns authenticated identity; `@oauth` returns the same-user browser
handoff. Other paths are scoped under `/v1/workspaces/{authenticated_scope}/`.
Token issuance/revocation, account changes and operator-only verification are intentionally
browser/operator controls. Audio preview returns MCP audio content.
Transcript search in `list_calls` also requires `transcripts:read`.

Coverage: `test_personal_tokens.py` verifies authority/CSRF/revocation;
`test_management_mcp.py` exercises SDK transport, atomic retries and the synthetic
create/prepare/publish/activate/audio flow; `test_call_search.py` checks search
bounds/visibility/isolation; `test_connection_setups.py` checks human handoff.
Existing agent/grant/number/delivery business suites remain required Linux regressions.
A catalog entry alone does not prove real client interoperability or carrier acceptance.
