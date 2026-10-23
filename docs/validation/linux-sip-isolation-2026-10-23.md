# Linux SIP impairment and call-isolation validation

Date: 2026-10-23 (Europe/Istanbul). Branch: `codex/sip-isolation`.
Tasks: M1-02 / M1-05 transport impairment, observability and isolation subitems;
M1-08 evidence. Requirements: US-01, sections 3, 6, 7, 12 and 15.
Baseline: `a59675e9806e6fbe09cb4b8c3725ec89a7a27716` plus the preserved uncommitted
foundation, Linux setup and this change. No publication or merge occurred.

## Change and test boundary

The loopback-only gateway defaults to one active call. Explicit
`--test-max-calls 2` admits two test calls; a third receives 486. Values 0, 3,
negative and malformed input fail before endpoint startup. This is an isolation
profile, not production capacity approval or a new externally reachable endpoint.

Calls retain independent media ports, codecs, playback cursors, input meters and
teardown. Two staggered calls play the same deterministic 8 kHz WAV (440 Hz for two
seconds, then 880 Hz), allowing their simultaneous output to be distinguished.
The intended tone must have amplitude above 2000 and the other tone below one
eighth of that amplitude. Both PCMA/PCMU assignments pass. One call receives
non-silent input and the other silence; only the first input meter records nonzero
samples. The test deliberately uses the same inbound SSRC on separate transports.

After ending the first call, the survivor continues sending audio with its original
SSRC. A replacement call takes the freed slot without terminating the survivor.
Both accepted sessions report exactly one closure. Shutdown tests now cover one
and two calls, with and without BYE acknowledgments, within the existing four-second
test bound (gateway dialog-drain budget remains two seconds).

Inbound impairment begins after 20 frames. Every 20-frame cycle drops two frames,
reorders a pair, duplicates one frame and delays one frame by 20 ms. Sequence and
timestamp rollover are exercised. Both codecs continue receiving paced playback,
deliver decoded nonzero input and end with `playback_complete`. A separate
reorder-only profile verifies positive reorder count with zero net loss/duplicates.
The final run recorded net loss/reorder/duplicates of 7/7/7 for both combined-impairment codec cases; reorder-only cases recorded 0/7/0. Maximum observed jitter snapshots were 4000/4125 microseconds for the combined profiles. These are diagnostic samples, not performance bounds. The clean profile remains covered. These are real local SIP and RTP packets with
synthetic audio; no microphone, external call or raw recording is used.

## Statistics regression

The first expanded run had **15 passed, 2 failed in 48.36 seconds**. The impairment
assertions exposed two distinct issues: PJSUA2 2.16's `RtcpStreamStat::fromPj` maps
`reorder` from `prm.loss`, and the initial stimulus's equal losses/duplicates made
RTCP net loss zero. The stimulus now loses two packets per duplicate; the gateway
reads the existing native `pjsua_call_get_stream_stat` API to obtain the correct
fields. The source pin was not patched or upgraded. Reorder-only assertions guard
against reintroducing the wrapper mapping bug without confusing loss with reorder.

The event loop samples RTCP at 100 ms intervals, outside media callbacks, and logs
only scalar snapshots on closure: received packets, net loss, reorder, duplicates
and maximum jitter in microseconds. These are last active-media samples, not exact
final packet totals. No SIP headers, phone numbers or audio samples are logged.

## Commands and results on the Linux server

Environment: the existing `~/ai/alojan` workspace from the Linux development report;
Ubuntu 24.04.2, GCC 13.3.0, Python 3.12.3, PJSIP 2.16 and locked project tools.

- `uv run --frozen cmake --build --preset local -j 8`: passed.
- Focused RTP profiles: **6 passed in 28.71 seconds** after the statistics fix.
- Full `uv run --frozen --env-file .local/dev.env pytest -q --tb=short`:
  **54 passed in 64.06 seconds**, no skipped tests; 21 SIP/configuration,
  4 database, 5 protobuf and 24 gRPC/PCM cases.
- `uv run --frozen ctest --preset local`: **1/1 passed**.
- Ruff lint and format, clang-format: passed.
- Codebase graph refreshed; whitespace and documentation links checked.

Python emits one `audioop` deprecation warning. The independent test decoder uses
the standard library under the pinned Python 3.12; replace it before a Python 3.13
upgrade. No new runtime dependency was introduced. Private test logs remain in
`.local/logs/m1-isolation-tests.log`, `m1-impairment-tests.log` and `m1-full-tests.log`
on the server; pytest's temporary WAVs are synthetic.

## Remaining gates

This completes the selected impairment/isolation subitems, not all of M1/G1.
M1-03 spoken AI greeting/fallback and M1-04 caller identity remain unimplemented;
explicit codec-vector/resampling checks and broader labeled scenarios remain open.
The test does not measure speech intelligibility, WAN recovery, maximum loss
tolerance or real model latency. Keep M2–M5 gated on the complete G1 development
scenario set. GPU/model inference, container host-network integration, Netgsm/NAT
and iOS acceptance were not run in this change. Historical GPU smoke evidence is
unchanged and does not imply model readiness.
