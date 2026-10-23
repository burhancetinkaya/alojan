"""M4 adapter boundary only: no live MCP integration is enabled for callers."""

from agents.mcp import MCPServerStreamableHttp


def owner_read_adapter(url, allowed_urls, read_tools):
    """Only owner configuration can select an endpoint and its read-only tool names."""
    if url not in allowed_urls or not url.startswith("https://") or not read_tools:
        raise ValueError("owner allowlist required")
    return MCPServerStreamableHttp(
        params={"url": url},
        name="owner-approved-reads",
        client_session_timeout_seconds=3,
        max_retry_attempts=0,
        tool_filter={"allowed_tool_names": sorted(read_tools)},
        require_approval="always",
    )
