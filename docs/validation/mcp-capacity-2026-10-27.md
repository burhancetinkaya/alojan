# Bounded MCP admission deployment

MCP-06 / AGP-09, M4–M5, requirements §11.3 and ADR 0012.
The owner explicitly authorized deployment of the pending capacity fix before
creating a new agent through MCP.

## Change

The four-slot transport limiter now acquires without waiting and returns HTTP 503
with `server_busy` when full. Accepted work retains the 20-second deadline.
Cancellation and timeout always release acquired capacity. Health requests are
independent of these slots. No API, database migration, ingress, web or voice
configuration changes are required.

## Verification

- Primary Linux: **11 passed in 8.03s**, covering transport/API integration plus
  overload, immediate rejection, no extra upstream call while full, health during
  saturation, cancelled-slot reuse, deadline cleanup and subsequent success.
- The pressure tests use synthetic upstreams in-process, not production saturation.
- Frozen independent MCP Docker build passed. Mac Ruff and whitespace passed.
- Only the MCP container was replaced; thirteen other Alojan container identities
  were preserved. API, web and MCP health returned 200. Live source hash matches
  the tested source. Public HTTPS `/mcp` correctly returns 401 without credentials.
- Image: `sha256:b059df5400024521c45bd40ecd0f8a9d47cfb2004909a2385532803dcac82843`.
- Previous image: `sha256:8c8e61102ca1835b26ea6f5818581ceb48f92b9e053e8825ac874299eb359312`.
- Private rollout receipts and previous Compose environment are under
  `.local/mcp-capacity-20261027/`. Restore that image reference and recreate only
  `management-mcp` for rollback; no database or voice-state restoration.

No live handset call, shared-host saturation or matched voice/load/soak acceptance
was performed. These remain separate outstanding gates. New-agent authoring awaits
the owner's requested identity and instructions; this deployment created no agent
and changed no number binding.
