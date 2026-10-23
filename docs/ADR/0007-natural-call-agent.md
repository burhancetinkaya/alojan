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
