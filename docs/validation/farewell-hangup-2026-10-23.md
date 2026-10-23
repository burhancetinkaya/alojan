# No-message farewell did not close the call

Date: 2026-10-23. M4-01/02, US-01/02; continuation of ADR 0006.

## Actual carrier evidence

The latest call used the correct Kübra deployment. 180 Ringing preceded answering
by 3002 ms. Two caller turns were stored, no note was created. After the caller
declined a message and said they would call later, the assistant spoke a polite
farewell but the agent logged finish=0. The gateway then opened listening turn 3.
The remote side disconnected at 45501 ms. There was no local call_ending event.
No private transcript, identifiers or audio capture is retained in this report.

This was not an expired three-second timer: no finish decision reached the timer.
The previous tool policy allowed no-note closing only for a short exact-match
caller goodbye, leaving a natural-language decline outside the permitted path.

## Fix

The prompt now directs declined-message/later-call exits through finish_call
with reason=caller_finished. This reason can close without fabricating a note;
other no-note finish reasons remain refused. The application supplies a short
farewell. A complete standalone model farewell matching the small explicit
closing set also requests finish if the model omits the tool. This fallback
requires successful stream completion and matches the entire selected speech,
not a substring, commentary draft, partial response or failed stream.

Thanks followed by another question must continue listening. A request that
Burhan call the caller later must save a message, not take the no-message exit.
The existing audio completion, interruption and three-second closure delay are
unchanged. Notes are never marked confirmed by either exit path.

## Validation

- Mac: all 46 agent/phrase tests passed (4.56 s).
- Linux: 49 agent/phrase/PostgreSQL/native closing checks passed (35.79 s), no
  skips, one known audioop warning. Both codecs preserved the 3.0–3.7 s closing
  interval assertion. Ruff and diff whitespace checks passed.
- Real selected OpenRouter model: declined message closed without a note; thanks
  plus a question continued; requested callback saved an unconfirmed note and
  closed with the message acknowledgement.
- Synthetic adaptive PCMA with real CUDA ASR/EMA and API: natural-language
  later-call exit finished in one turn, no note, completed summary and local BYE.
  Closing audio was 1520 ms; first response output 2739 ms after ASR half-close.
  These are synthetic measurements, not handset acceptance or percentiles.
- Idle-line activation: agent launcher PID 1991486, gateway PID 1991663, all
  worker health checks passed. Native binary unchanged; no rebuild was needed.
  Prior backend, binary/arguments/profile and logs retained privately for rollback.

Human carrier retest remains pending. Exact farewell fallback is deliberately
limited; it is not a general semantic classifier or a guarantee of model behavior.
