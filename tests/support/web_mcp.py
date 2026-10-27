"""Synthetic MCP authoring fixtures for the isolated HTTPS browser harness."""

from test_mcp_schema import TOOL as QUALIFIED_TOOL
from test_mcp_deliver2ai import TOOL as JSON_TOOL
from alojan.profiles import Profiles
from test_agent_drafts import content
from test_mcp_tools import TOOL, discovered, operator_review, rediscover


def setup_mcp(accounts, password):
    login = "mcp.owner@example.test"
    token = accounts.register(login, password, "MCP Test Owner", peer="fixture")
    scope = accounts.session(token)["workspaces"][0]["id"]
    who = token, scope
    reference = discovered(accounts, who)
    # Metadata stays untrusted; only exact read tools receive operator review.
    rediscover(
        accounts,
        who,
        reference,
        [TOOL, TOOL | {"name": "unreviewed"}, QUALIFIED_TOOL, JSON_TOOL | {"name": "json_lookup"}],
    )
    review = operator_review(accounts, scope, reference)
    qualified_review = operator_review(accounts, scope, reference, QUALIFIED_TOOL)
    json_review = operator_review(accounts, scope, reference, JSON_TOOL | {"name": "json_lookup"})
    json_agent = Profiles(accounts).create(*who, content("MCP JSON Asistanı"))["id"]
    qualified_agent = Profiles(accounts).create(*who, content("MCP Şema Asistanı"))["id"]
    agent = Profiles(accounts).create(*who, content("MCP Asistanı"))["id"]
    return dict(
        login=login,
        scope=scope,
        agent=agent,
        connection=reference,
        review=review,
        qualified_review=qualified_review,
        json_review=json_review,
        json_agent=json_agent,
        qualified_agent=qualified_agent,
    )
