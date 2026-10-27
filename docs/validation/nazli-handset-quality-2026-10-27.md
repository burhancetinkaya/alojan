# Nazlı private handset quality trial

Date: 2026-10-27. Mapping: VXP-02/06, AGP-07/09, PERF-02/03,
M2/M4/M5, US-01/04/05/06/07/08; ADR 0011/0014.

The owner requested a real Nazlı quality test and explicitly selected temporary
replacement of Kübra on the existing verified number, followed by restoration.
The owner was informed that telephone caller identity is not authenticated and
Nazlı can use its already authorized organizational analytics reads. This is a
supervised trial, not general access-control or performance qualification.

## Coordinated candidate deployment

Built gateway, agent, management, MCP transport, background-worker and web images
with the currently serving pinned dependencies. Prepared a new content-addressed
host voice-preparer release. Control/candidate/management/worker compilation of
all three existing releases preserved their voice, model and instruction behavior.

Drained native admission under the existing coordinator/advisory locks; verified
no active calls or pending post-call work. Stopped writers, saved private deployment
configuration and a checked PostgreSQL archive, refreshed the narrow management
transcript grant, and activated compatible consumers before reopening admission.
ASR/EMA containers stayed resident; six unrelated containers retained identity and
start time. Bound routes/releases stayed unchanged during the service deployment.
All required health/readiness checks passed and preparer supervision resumed.

Jev remains disabled. No new inference dependency, speculative waiting synthesis,
automatic recipe route or caller-authentication feature was enabled.

## Nazlı preparation through public HTTPS MCP

A temporary scoped owner token updated only `response_experience` on draft v7,
producing v8 with `enabled=true` and natural style. Eight selected read tools,
instructions, model, variables and the existing Telegram action were preserved.
The API rejected an initial private request missing its required idempotency key;
the corrected request succeeded without bypassing version or permission checks.

The supervised preparer produced a digest-bound pack. MCP previews returned a
mono 8 kHz greeting of 8.28 seconds and a waiting clip of 2.52 seconds. The waiting
statement is “Sizi kısa bir süre bekleteceğim, kontrol ediyorum.” Generation and
integrity/readiness are not human listening acceptance.

Prepared and published revision 1, verified fresh node readiness, then activated
the existing verified number at version 6. Exactly one binding became active;
Kübra's prior immutable release was retained for restoration. Raw call audio
recording remains off. Real answered calls retain the owner's existing Telegram
post-call authorization; no standalone test message was sent.

## Handset observation

One real carrier conversation lasted approximately 120 seconds, using resident
ASR/EMA, the configured answer model and authenticated Deliver2.ai tools. The
owner reported that a first-name person lookup failed. This trial is not accepted
as an overall quality pass.

The owner subsequently explicitly accepted the **voice and waiting experience** as
very good. Record this as handset acceptance of that experience in this conversation;
it does not resolve the deferred lookup issue, full latency/load criteria or the
final incomplete turn below.

The gateway recorded 13 turns: seven completed, five interrupted and one final
`incomplete_turn` (error 8) without useful response audio. The failed final turn is
retained, not counted as fast success. Human validation of each interruption and
the exact final-turn cutoff cause remains open. The observed duration coincides
with the existing 120-second engine default; this alone does not prove causation.

Across the seven completed turns, endpoint-to-useful-audio P50 was 2498 ms and
P95/max 4658 ms. Ready-PCM-to-output P50/P95 was 9/17 ms; warm EMA first chunk
9/11 ms. These seven correlated samples are not a 50-turn latency qualification.
The first two data responses took 3619/4280 ms from endpoint to useful audio
(the second was subsequently interrupted). Corresponding tool work took
approximately 1406/1517 ms; model planning and answer generation accounted for
most of the remaining processing time. Prepared waiting does not accelerate them.

Three waiting receipts were persisted: two partial at 1600/1780 ms with no invented
text and one complete 2520 ms clip. Eight remote tool executions succeeded at the
transport level, including three semantic `developer_not_found` results. Summary
generation completed and the already authorized Telegram action reached `sent`.
An early collector snapshot contained only four imported latency rows; the final
post-call collection contains all 13. No rows from the partial snapshot are treated
as the final call total.

## Reported lookup defect and owner-requested deferral

The agent's existing instructions deliberately resolve people through
`mcp_cost_summary` before requesting sessions by the returned developer ID.
The reviewed upstream schema documents **exact developer name or email**, not
first-name/fuzzy directory search. The short spoken name returned
`developer_not_found`; that does not prove the person or their sessions do not
exist. The answer should ask for a surname/exact identity rather than assert that
the developer is absent. Two earlier spoken email attempts also appeared malformed
in ASR output; raw audio was not recorded, so recognition fidelity cannot be
independently adjudicated from a recording.

The owner explicitly deferred an instruction-level correction. No instructions,
tool selection, grants, ASR replacements, budgets or lookup code were changed in
response to this finding. First-name resolution still depends on an appropriate
source capability or a fully specified identity, not a guessed developer ID.

## Restoration

After the call, public management MCP restored the exact previous Kübra release
at number version 7. The binding was read back and verified; Nazlı revision 1 remains
published but is not bound to the live number. The temporary MCP token was revoked
and its login session closed. Shared compatible runtime updates remain installed;
Kübra's existing release has waiting disabled. No test is left routing to Nazlı.

## Jev verification after owner feedback

Read-only inspection verified the same agent container/image used for the trial.
Its actual agent process environment has no `ALOJAN_JEV_SHADOW` override; the
installed startup code defaults it to `0` and constructs the Decisions client only
for `1`. The backend returns without creating a decision task when that client is
absent. Container logs contain no Jev/decision-shadow observations. Together these
confirm the trial did not dispatch Jev requests; the conclusion is not based on
missing log lines alone. No setting was changed during verification.

Waiting speech was triggered by the deterministic authorized-operation watchdog
and played from prepared EMA audio. It was not generated, timed or selected by Jev.
The optional shadow implementation would classify final caller text as lookup,
explanation, conversation or unknown for observation only. Prior synthetic Jev
evaluations are separate evidence and were not this handset conversation.

Private deployment, audio previews, scoped MCP responses and rollback evidence are
kept in `.local/nazli-live-quality-20261027/`, excluded from Git. Do not publish
credentials, number identifiers, organization metrics or personal transcripts.
