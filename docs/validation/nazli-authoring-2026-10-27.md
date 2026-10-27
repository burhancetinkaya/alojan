# Owner-requested Nazli authoring through management MCP

MCP-06 / AGP-06–07, M4–M5, requirements §11.3 and ADR 0012.

The owner requested Nazlı, Burhan's assistant for questions about the team's agentic
development processes, using deliver2.ai. The draft was created, read back and updated
through the public HTTPS management MCP with the official SDK. Version 2 contains
Turkish evidence-based instructions, the existing qualified model connection and EMA
voice. It has no publication, number binding, post-call action or selected outbound tool.
No publication or number activation was requested. Temporary personal tokens were
revoked and verification browser sessions logged out after operations.

The owner saved a bearer connection to `<MCP_ENDPOINT>` in the workspace.
It is not an OAuth connection. The requested endpoint was added to the private approved
endpoint list, retaining Hindsight; only the independent discovery worker was restarted.
The initial discovery failed with `endpoint_not_approved`; retry after the update failed
with `discovery_failed`. A diagnostic using the same saved encrypted credential and
DNS-pinned bounded transport isolated the following compatibility prerequisites:

- The server negotiates MCP `2025-06-18`; Alojan's discovery and execution currently
  require `2025-11-25` exactly. The official SDK completed initialization successfully.
- Read-only diagnostic tool discovery returned 19 tools. Their current schemas do not
  pass Alojan's reviewed bounded subset. Examples include UUID `format` keywords and
  absent optional output schemas. No unsafe fallback or schema-validation bypass was
  applied, and no tool was approved or executed.

Nazlı remains a saved draft while protocol compatibility and safe schema qualification
are developed and tested. Connection authentication succeeded; this is not successful
runtime tool-call, model, voice, publication or carrier acceptance. Credentials and
remote team records are not included in this evidence. No deliver2.ai business query
was executed. Private operational receipts are under `.local/nazli-mcp-20261027/`.
