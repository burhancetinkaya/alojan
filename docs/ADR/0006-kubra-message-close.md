# ADR 0006: Kübra and message collection without readback

Date: 2026-10-23. Status: accepted by explicit owner request in chat.
Automatic save-and-close is superseded by ADR 0007; other decisions remain.
Amends US-02 and section 9.2; tasks M1-03 and M4-01/02/03.

The owner named the assistant Kübra and approved the opening wording, then
changed the owner reference to Burhan Bey. The approved text is:
“Merhaba, ben Kübra. Burhan Bey’in yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?”
Generate this text with the existing resident EMA voice, retaining the 400 ms
carrier lead-in and three-second ringing interval.

After receiving a usable message, persist it without reading it back or asking
for confirmation. Keep confirmed=false in notes and summaries: bypassing a
confirmation question is not evidence of caller confirmation. After successful
storage, say exactly “Burhan Bey’e mesajınızı ileteceğim.” and disconnect three
seconds after closing playback finishes. Preserve failure, cancellation and
interruption handling; do not announce successful collection after a failed save.

The owner-selected closing is a future-intent phrase, not delivery evidence.
Automated notifications remain deferred; no external delivery is introduced or
marked successful. The owner has been informed that the message is currently
stored only in PostgreSQL. Other commitments/actions remain prohibited.

Legacy confirmation fields remain backward compatible. Current agent tools must
not upgrade a note to confirmed. No model, voice cloning or recording change.

Owner follow-up: when asked only about availability or speaking to the owner,
say “Burhan Bey şu an müsait değil, bir toplantıda olabilir. İsterseniz mesajınızı
alabilirim.” Treat the meeting as a possibility, not verified calendar data.
An actual message or callback request must be saved instead of repeating this
availability offer. Do not invent a return time.
