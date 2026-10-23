# ADR 0005: OpenRouter-hosted phone agent

Date: 2026-10-23
Status: Accepted by explicit owner instructions in the M4 continuation.
Amends: DEC-11 provider/model selection only.

## Decision and authorization

The owner requested OpenRouter's OpenAI-compatible API, then explicitly selected
`openai/gpt-6-luna-pro` after the original Luna model was denied by an account
model guardrail. Preserve the OpenAI Agents SDK, `Runner.run_streamed`, Responses
API, `reasoning.effort=none`, low verbosity and the existing native audio boundary.
Use `https://openrouter.ai/api/v1` with `OPENROUTER_API_KEY` in the ignored server
`.local/agent.env`. No fallback to another model/provider endpoint is configured
in Alojan. OpenRouter may perform its own provider routing under account policy.

The owner also chose to start M4 before remaining M3 calibration improvements.
M3's incomplete-turn behavior, silent reminder and latency targets stay open;
this scheduling decision does not mark those acceptance criteria passed.

## Evidence and alternatives

A real Linux Responses streaming request to the selected Pro model completed,
returned text, and accepted the requested settings (one synthetic observation:
3460 ms total). The original `openai/gpt-6-luna` returned HTTP 404 with the explicit
reason `Model blocked by guardrail`; no account guardrail was changed by the agent.
This smoke check is not full tool/dialogue quality or latency acceptance.

Direct OpenAI would violate the owner's provider preference. Silently changing
models would violate DEC-11; the explicit Pro choice authorizes this amendment.

## Consequences

Caller text and minimal call context pass through OpenRouter and its upstream
provider. OpenAI SDK tracing and response storage are disabled in application
requests; this is not a claim about provider-side retention. Keep API keys out
of commands/logs/Git. Terms, provider data policies and redistribution notices
remain review items. No external message/calendar tool is enabled by this change.
The durable notification milestone remains M5.
