"""Deny-by-default operation scopes for personal management tokens."""

from alojan.auth import AuthError


def required_permissions(resource, action, method):
    read = method == "GET"
    if resource == "connection-setups" and action != "complete":
        return frozenset({"connections:write"})
    if resource == "mcp-oauth" and read:
        return frozenset({"connections:read"})
    if resource in {"personal-tokens", "mcp-oauth"}:
        # Issuance and provider OAuth callbacks require a human browser session.
        raise AuthError("browser_session_required", 403)
    if resource in {
        "provider-connections",
        "telegram-connections",
        "http-connections",
        "mcp-connections",
    }:
        if action not in {None, "revoke", "discovery", "tools"}:
            raise AuthError("insufficient_scope", 403)
        return frozenset({"connections:read" if read else "connections:write"})
    if resource == "calls":
        return frozenset(
            {"calls:read", "transcripts:read"} if action == "transcript" else {"calls:read"}
        )
    if resource == "performance":
        return frozenset({"calls:read"})
    if resource in {"models", "agent-schema"} and read:
        return frozenset({"agents:read"})
    if resource == "numbers":
        return frozenset({"agents:read" if read else "numbers:manage"})
    if resource == "agents":
        if action in {"publish", "rollback"}:
            return frozenset({"releases:publish"})
        if action in {"action-grants", "mcp-grants", "revoke-action-grant", "revoke-mcp-grant"}:
            return frozenset({"agents:read" if read else "grants:manage"})
        if action in {"deliveries", "delivery", "retry-review", "retry-delivery"}:
            return frozenset({"calls:read" if read else "deliveries:retry"})
        if action in {
            None,
            "preview",
            "prepare",
            "voice-preparation",
            "voice-preview",
            "releases",
            "release-status",
            "action-review",
            "mcp-review",
        }:
            return frozenset({"agents:read" if read or action == "preview" else "agents:write"})
    raise AuthError("insufficient_scope", 403)
