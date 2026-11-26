# ADR 0016: Workspace outbound announcements

Accepted 2026-11-26 by the owner for OUT-01–04, extending DEC-05 and the
agent release scope in ADR 0011. See [requirements](../REQUIREMENTS.md).

A published agent may opt into single-recipient announcements using its verified
Netgsm line and released voice. Pin release, line, exact message and timing with
the request. Prepare the AI introduction and message before dialing. Start
playback on confirmed answer and active media. Finish after the configured delay
from the last sent audio frame. A recipient hangup cancels pending playback.
Completion records sent audio; it cannot attest that a human listened.

A workspace request queues one Turkish mobile or geographic destination.
Outbound defaults are 30 seconds to answer and 2 seconds after playback.
Allow per-call overrides. Start with one active outbound attempt inside the
shared gateway admission limit. An uncertain attempt after restart requires
a terminal outcome without automatic redial. Keep raw recordings off.

Phase one adds agent settings, a manual web form and scoped history. Phase two
exposes the same submission and history operations to scoped API tokens.
Submitting requires an idempotency key; conflicting reuse is rejected.
Retain the existing transcript/metadata privacy policies. Exclude destination,
message and SIP credentials from diagnostic logs. Scheduling, campaigns and
conversational responses are future scope.

Qualify egress separately before panel development: confirm carrier transport,
authentication, permitted caller identity, ringing, answer, media and teardown
on the owner's designated handset. Keep the current inbound binding available.
Store live settings, test numbers and credentials only in private operator state.
