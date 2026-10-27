# OpenRouter Jev access qualification

Date: 2026-10-27. Environment: authorized primary Linux host.
Task: VXP-04 prerequisite; AGP-06/07/09, PERF-02/03, M2/M4/M5,
US-04/05/06/08. Current outcome: access verified; six synthetic decisions passed.
The earlier blocked attempt is preserved below as historical evidence.

## Initial attempt before owner permission update

Used the owner's existing enabled OpenRouter connection with read-only database
access and in-memory credential decryption. No key, headers, private call input,
recording or user conversation was logged or sent to the model. Requests used
synthetic Turkish text, an eight-second deadline, no automatic retries, no proxy
inheritance and no redirects. No tool execution or agent mutation was permitted.

| Check | Observed result |
| --- | --- |
| Initial `POST /api/alpha/decisions`, `typesafe/jev-1.14` | HTTP 404 in 375.7 ms; smoke stopped at case one |
| `GET /api/v1/key` | HTTP 200; existing credential valid |
| `GET /api/v1/models` | HTTP 200; Jev-filtered result contained `typesafe/jev-router`; catalog listing alone does not prove inference permission |
| One diagnostic Decisions request with the same synthetic case | HTTP 404; provider explicitly reported `Model blocked by guardrail: 1 endpoint excluded` |

Two Decisions requests were made in the initial attempt; neither produced an answer. The initial
375.7 ms measures a rejected HTTP request, not model inference or useful-answer
latency. Zero of six planned Turkish cases were evaluated successfully; the other
five were not run. No P50/P95/P99 or quality qualification can be inferred.

## Integration decision and next gate

The [official OpenRouter example](https://openrouter.ai/blog/insights/what-is-jev/)
documents the typed Decisions API. The separately documented
[Jev Router](https://openrouter.ai/typesafe/jev-router/api) routes generative-model
requests and cannot establish direct Jev decision performance for this plan.
Use the existing authorized workspace connection through the common runtime
capability; keep model version, deadlines and fallback as platform presets.

After the owner reported enabling the model, reran the same six-case smoke without
changing the key, endpoint, model, instructions or criteria. No provider policy was
changed by the assistant. All six responses passed choice, probability distribution,
confidence and model-family validation. Resolved model for every response:
`typesafe/jev-1.14-20261014`.

| Synthetic case | Expected and returned choice | Total HTTP ms | Confidence |
| --- | --- | ---: | ---: |
| count | `count_today` | 605.5 | 0.98 |
| cost | `cost_today` | 224.0 | 0.95 |
| correction | `general` | 224.6 | 0.98 |
| ambiguous | `general` | 210.5 | 0.98 |
| continuation | `general` | 222.5 | 1 |
| combined | `general` | 204.9 | 1 |

Cases cover today's total session count, today's total cost, a correction to
yesterday, an ambiguous pronoun, a conversational continuation, and a combined
count/cost question. The last four deliberately select the normal conversational
agent (`general`), not a fast route. No real external tool was dispatched.

English decision instructions and choice descriptions were used from the first
attempt; caller inputs remain Turkish. The owner explicitly requested English Jev
instructions after the successful probe. This becomes the shared platform policy,
with no automatic translation of caller text or user-authored agent prompts.

Eight Decisions requests across both attempts: two rejected and six successful.
Durations include network/provider overhead. The first request may include connection
setup; this measurement does not isolate model cold start. No percentile or
production error-rate claim is justified by six observations. There was no baseline
comparison, so no conversation-speed improvement is established. Held-out Turkish
quality, cancellation/failure handling, matched latency and audio testing remain
required before any live activation.

Private sanitized probe outputs are under `.local/jev-openrouter-20261027/` on the
Linux host and Mac checkout. No runtime source, live agent, release, routing,
service or provider settings changed. No carrier, SIP/RTP, GPU or TTS test ran.
