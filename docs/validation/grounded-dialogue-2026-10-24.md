# Grounded dialogue and repetition investigation — 2026-10-24

Status: owner-authorized live trial; quality acceptance remains pending. Tasks M4-01/02, supporting
M5-03; requirements US-02/06/08 and section 9.2, under ADR 0007.

## Problem and retained candidate

The owner reported invented business information and repeated responses in a
carrier call. The accepted prompt included fictional product names in behavioral
examples without a verified business catalog. Example contamination is a plausible
contributor, not a proven sole cause. The candidate removes those names, separates
missing knowledge from private information, and instructs contextual correction
and natural follow-ups. Skill Creator principles were applied to general decision
criteria; no caller-specific product blacklist was added.

The candidate rejects an unchanged delivered note acknowledgement and an exact
long opening repeated within the last three delivered assistant phrases. Explicit
repeat/status requests and new/unheard acknowledgements are distinct. This uses
existing call-local playback state and bounded SDK tool turns; it is not a general
semantic duplicate detector. Exhausted model/tool repair now clarifies without
requesting hangup. Synthetic unit cases cover repetition, explicit repeats, call
isolation, acknowledgement versions and exhausted repair. These guards remain
experimental: live model testing shows extra retries can cause unnecessary
clarification and exceed the owner's three-second preparation target.

The evaluator now supports seeded delivered history, first-opening comparisons
and elapsed times. Synthetic grounding fixtures include privacy-to-business
transitions, unknown catalogs/prices, correction of an assistant's unsupported
statement, legitimate notes, explicit repeats and incomplete requests. Mechanical
checks do not substitute for manual meaning review.

## Evidence and rejected alternatives

- Linux access was restored and verified with existing SSH authentication.
- Retained candidate unit suite: 131 passed, 1 skipped (5.91 seconds). The skip is
  pre-existing; it is not a pass. Ruff check passed. No C++ or audio change.
- A shorter prompt candidate achieved 57/58 mechanical general-dialogue checks;
  the remaining same-turn date correction also failed the accepted baseline.
  Manual review still found poor error ownership, redundant acknowledgements and
  unsupported promises. That prompt rewrite was rejected.
- Baseline controls: 7/9 checks; date correction and a speculative callback-time
  note update failed before this change too. This does not excuse new failures.
- Alternative policy transport/placement was investigated using the same model,
  provider and settings. A tiny streamed-tool marker probe differed between the
  separate instructions field and inline roles. This small observation does NOT
  prove that OpenRouter universally drops instructions. Full dialogue evaluation
  was decisive: inline system scored 53/58, recent developer policy 41/58, with
  premature endings and other regressions. All transport changes were rejected.
- No model, provider, reasoning level, sampling setting, ASR, TTS or gateway setting
  was changed in the retained candidate or live deployment.

OpenRouter documents both the [Responses instructions field and input messages](https://openrouter.ai/docs/api/api-reference/responses/create-responses).
OpenAI's [Harmony guide](https://github.com/openai/openai-cookbook/blob/main/articles/openai-harmony.md)
explains the developer role for application policy. These sources motivate tests;
they do not certify behavior on a specific provider route.

Retained candidate real-API run: 27/30 mechanical checks; first phrase preparation median 1060 ms, P95 3875 ms, maximum 4655 ms. These are synthetic text-to-agent measurements, not phone endpoint-to-RTP latency. Manual review also found unnecessary clarification after rejected repeated acknowledgements and incomplete ownership of an earlier unsupported answer. Release gate failed.

## Release gate and next investigation

Quality acceptance requires that unknown-business answers remain grounded,
corrections own the assistant's mistake, repeated boundaries remain useful, and
normal message/exit flows do not regress. A mechanical all-pass result alone is
insufficient. Rephrase retries must not turn an understood question into an ASR
clarification or add unacceptable delay. Next, inspect rejection reasons and
response construction together before adding further prompt text; preserve
baseline comparisons and test general behavior rather than patching individual
caller sentences.

Evidence is private under the isolated Linux workspace
`.local/grounded-dialogue-20261024/evidence/` and the managed worktree's ignored
`.local/grounded-dialogue-evidence/`. No credentials, caller transcripts or audio
were added to maintained documentation. No new carrier call or handset audio
acceptance was performed. The initial investigation left the live agent unchanged; the later owner-authorized trial is recorded below.


## Owner-authorized live trial

After being told about 131 passing unit tests, three failing conversation checks
and a measured 4.7-second worst preparation time, the owner explicitly requested
live deployment for a personal phone test. This authorizes the trial, not a claim
that the failed quality gate has passed.

At 2026-10-24 16:01 server local time, all logged calls were disconnected. Only
`services/agent/alojan_agent/backend.py` was replaced with the retained tested
candidate and the agent process was restarted with its existing command and
environment. No model/provider/audio configuration or other source was deployed.
Agent, EMA and ASR health checks returned SERVING; the existing gateway process
remained alive. Real carrier dialogue and handset audio acceptance are pending.

Candidate SHA-256: `5687ffa23c0e64477c2c7ed4b3bbbfe0386136a6ce806c71dca7ffa6ae95694f`.
Previous backend SHA-256: `1db8a966bb46c3487728b65649b2e8c5b1f40b4af5954cca3b8418ddffd42b96`.
Private rollback source and deployment manifest:
`.local/before-grounded-trial-20261024-160125/` on Linux. Restore `backend.py`
from that backup and restart only the agent using the recorded launch command,
while no call is active. Preserve the current private environment. Verify health
and the previous source hash after rollback. Do not restore unrelated services.
