# Nazlı pre-publication checks — 2026-10-27

AGP-06/07/09, MCP-06, M4–M5, US-08; ADR 0011–0013. The owner requested final
checks and the intended session/count/cost/user questions before going live.

## Checked

- Public HTTPS management MCP read draft v6, current exact tool review, numbers
  and publication state. Current voice status is ready. Both audio previews were
  retrieved again and checked against the prepared manifest using the production
  WAV/duration/leading-padding/hash validator.
- `alojan_prepare_release` returned `ready_to_publish` for the current draft. No
  publish or number activation was invoked. The existing verified bound number
  remains ready; Nazlı has no published release. Gateway admission is open and
  management/MCP/web/agent/coordinator health checks passed.
- The selected real model answered five independent questions with real authenticated
  Deliver2.ai results: today's count, cost, combined count/cost, named person, and
  all-user breakdown. Session counts and the incomplete actual-cost subtotal were
  checked against source values. The exact-name miss correctly requested clarification.
  The all-user question narrowed to one user, rather than inventing a full distribution;
  complete all-user reporting is not implemented by that behavior.
- A three-turn real conversation checked name miss → known email → that person's
  cost. Email resolved an actual developer ID; the session request used that returned
  ID. The cost follow-up retained the person filter. Zero count and zero complete cost
  were verified against source data, not inferred from an error or missing value.
- Real tool operations completed inside the unchanged four-second tool deadline.
  The count/cost/combined model-plus-tool checks took 2.951/4.444/3.955 seconds.
  These timings exclude ASR, TTS, RTP and phone latency; they are not voice performance
  or concurrent-load acceptance. No new model qualification is claimed.

## Test boundary

The private harness compiled the current draft with the current qualified preset
and exact enabled MCP grant. It used the production Backend and MCPExecutor with
real providers, schema/fixed-argument/output validation, capability/credential checks,
periodic authorization refresh, and normal call/turn/time/size budgets. Only execution
audit start/completion were recorded privately instead of creating fictional live
call/route rows; the database connection for tool authorization was read-only. Thus
production call-route persistence, audio playback and carrier integration are **not**
covered by this conversational preflight. No carrier calls, writes through remote
tools, notifications or recordings were generated.

Private responses and audit data are retained only under
`.local/nazli-preflight-20261027/`. Do not commit private team metrics, identities,
transcripts, phone numbers or credentials. Temporary personal tokens were revoked
and account sessions logged out. One private operator script initially read an
incomplete uploaded request file; it performed no preparation action in that attempt,
cleaned up its token, and the completed file was subsequently executed successfully.

## Open items before activation

1. **Caller access policy:** the phone path does not authenticate the individual
   caller. The reviewed tool grant authorizes the agent/workspace, not that caller;
   caller ID and a spoken name are not authentication. Binding this analytics agent
   to a reachable number would make its selected organizational reads available to
   callers. Decide authorized access and enforce any required caller verification
   outside model instructions before treating it as a private internal assistant.
2. **All-user reporting:** selected Deliver2.ai tools have no complete grouped
   per-user aggregate. Bounded page samples cannot provide a reliable full ranking.
   Per-person queries work; full distribution requires an appropriate aggregate
   capability or another explicitly designed complete-data approach.
3. **Publication, explicit number choice/replacement and handset acceptance:** not
   performed. The only currently configured verified number already has an active
   release; replacing its agent must be an explicit decision. After publication,
   check that release's node readiness, then activate the chosen number and perform
   the real voice test. Prepared status is not proof of those steps.
4. **Post-call delivery configured after preflight:** the owner subsequently requested
   Kübra's Telegram destination. Draft v7 copies the action from Kübra's currently
   bound release, using the same enabled connection, answered-call trigger and
   structured summary fields. Exact review and standing authorization passed through
   management MCP. Other draft fields and voice digest are unchanged; v7 preparation
   returns `ready_to_publish`. No test message, publication or binding was performed.
   Actual Nazlı notification delivery still needs a finalized call after activation.
