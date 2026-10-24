# ADR 0007: Contextual call-center conversation and closing

Date: 2026-10-23. Status: accepted by explicit owner follow-up after the latest call.
Amends ADR 0006's automatic message-save closing; tasks M4-01/02, US-02.

The owner rejected the abrupt acknowledgement-and-hangup behavior and requested
that Kübra act as a professional call-center agent whose prompt governs the
conversation and natural closing. Saving a message no longer finishes the call.
Return the durable result to the model so it can acknowledge, ask a relevant
follow-up or give the caller a brief opportunity for another request. Avoid
rigid scripts and repeated anything-else loops. If the caller already finished,
do not prolong the call with an unnecessary question.

The model chooses a concise contextual farewell through finish_call's optional
closing_text argument. A closing question is not a farewell and cannot request
hangup. Do not close merely because a note exists. Preserve a clear caller exit,
including declined-message exits, and wait three seconds after final speech.
No content readback or confirmation question is restored. Notes stay unconfirmed.

Kübra's approved opening audio and availability policy remain. The role does not
authorize new capabilities, external delivery, invented owner availability facts,
private data disclosure or promised callbacks. Notifications remain deferred;
acknowledgement must follow successful storage and must not claim delivery.

Owner wording refinement: after explaining unavailability, invite the caller to
state their purpose with a polite open question (for example, “Hangi konuda
görüşmek istemiştiniz?”). Skip that generic question if the purpose is already
known. This supersedes ADR 0006's passive availability/message offer.

Owner clarification follow-up (2026-10-23): unclear recognition or an answer that
does not address the pending question must lead to a short clarification and
continued listening, not a farewell. Repeating an unanswered question is allowed;
re-requesting already understood information is not. Bare thanks alone do not
answer a pending question. Explicit goodbye, refusal or a request to end remains
valid. Existing resource/deadline limits are unchanged.

Owner executive-assistant refinement (2026-10-24), M4-01 / M5-03, US-02/06/08:
the owner rejected the latest call's dismissive support redirect and repeated
closing questions, and requested a senior executive-assistant manner. Kübra should
take ownership of concrete requests addressed to Burhan Bey, including product
questions she cannot answer herself. Store the actual problem/question locally
before acknowledging; ask for an unknown product or another necessary detail,
not an already supplied fact. This does not authorize product-support answers,
new integrations, callback guarantees or claims that delivery occurred.

Use warm, concise everyday Turkish and stop adding generic anything-else
questions. An acknowledged request with no essential question pending can end
naturally on thanks. Thanks do not answer an essential pending question, even
when the same assistant reply also answered an availability question. This
contextual distinction supersedes the blanket local rule that repeated any last
question on thanks. A narrow local guard still clarifies bare thanks during
unresolved intake (no note, a delivered question, no optional-invitation wording).
This text heuristic is intentionally limited; typed question intent is the upgrade
condition for broader recovery. Known stock ASR hallucinations still clarify locally without
saving or hanging up. Preserve explicit exits and new requests in the same turn.
Final acknowledgement/farewell still precedes the existing three-second hangup.

Observed generic invitations and unsupported callback claims are repaired at the
validated speech boundary. Acknowledgement requires durable storage; otherwise
use truthful uncertainty or request a bounded model correction. This avoids an
extra model roundtrip for a known callback claim. These finite checks are not a
general semantic-policy guarantee. See the
[executive-assistant evaluation](../validation/executive-assistant-2026-10-24.md).

Owner natural-closing refinement (2026-10-24): the next carrier call acknowledged
storage twice, including after the caller's thanks. The database contained only
one note version; repetition was conversational. Add the researched
[executive-assistant conduct rules](../AGENT_CONDUCT.md) to the system prompt.
An unchanged note whose acknowledgement was completely delivered must not be
re-announced during closing, including through a safety fallback. A new/corrected
note, unheard acknowledgement or explicit repeat request remains distinct.

Track completed acknowledgement receipts by the note version attached when each
phrase was emitted. A delayed old receipt must not acknowledge a newer note;
interrupted/unplayed speech must not count. This is sent-audio evidence, not proof
of handset perception and not caller confirmation. No protocol or database schema
change, extra model request or new integration is introduced. The phrase patterns
are finite; the broader no-repetition policy remains in the conversational prompt.

Owner once-per-call invitation refinement (2026-10-24), M4-01 / M5-03, US-02:
the owner explicitly requires one further-help question after handling a request.
This supersedes the earlier blanket prohibition on generic invitations. Ask
“Başka yardımcı olabileceğim bir konu var mı?” once after essential details are
collected; include it with the acknowledgement where possible. Informational
answers also lead to this invitation. Explicit exit/refusal still wins. Thanks
without a new request can close after the invitation, not silently skip it.
Track completed invitation playback per call, independently of note versions;
interrupted/unsent invitations do not consume the opportunity. Never repeat it
after a second request or correction. Model instructions and validated speech
checks retain bounded output, truthful acknowledgements and call isolation.

Owner service-practice refinement (2026-10-24), M4-01 / M5-03, US-02/06/08:
add researched positive conduct alongside the existing boundaries. Use concrete
empathy, simple language, contextual follow-ups and targeted misunderstanding
repair; describe only available next steps. Identify the product before offering
further help for a product problem. The source mapping in AGENT_CONDUCT.md separates
ISO's public framework from non-normative ICMI/Google/Retell guidance. No new
capability, conformity claim, call-flow permission or media policy follows.

Owner adversarial-dialogue refinement (2026-10-24), M4-01 / M5-03, US-02/06/08:
exercise unusual and adversarial questions, review failures, and apply bounded
improvements. Resolve conflicting prompt instructions around latest caller
intent; preserve the complete note across additions. Explicit AI identity answers
are permitted; harmless off-topic requests receive a brief warm redirect. Volunteered
credentials are omitted from generated notes/speech, without claiming raw transcript
redaction. Known content-free turns cannot rewrite a durable note. Invalid model/tool
output clarifies without closing; cancellation, validation and authorization remain.
No new external capabilities or recording changes follow from these tests.
