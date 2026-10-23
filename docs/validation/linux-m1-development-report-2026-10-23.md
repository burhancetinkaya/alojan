# M1 native Linux development completion report

Date: 2026-10-23, Europe/Istanbul. Task: M1-08, consolidating M1-01–05.
Requirements: US-01, local US-03 parsing, §§5–6, 7.1, 8.2, 15–16 and 18.
Tester/reviewer: Codex; listening reviewer: the owner in this chat.
Branch: `codex/m1-development-report`, preserving the uncommitted foundation on
`a59675e9806e6fbe09cb4b8c3725ec89a7a27716`. No publication or merge.

## Decision and scope

**The native Linux G1 development scenario set is complete. M1-08's development
report is delivered.** The owner accepted the EMA v2 voice and then accepted the
personalized v3 greeting before requesting the next task. This closes the last
local listening condition. M2-01 can now proceed under the existing sequence in
ADR 0003; no model, architecture or product-scope decision changes.

This is the native gateway/Python plus isolated PostgreSQL development profile.
The build/contract/DB prerequisites needed by this profile passed. G0's remaining
production containers, runtime-role hardening and hosted CI work are still open;
this report does not mark full G0 or the overall M1 product milestone complete.
G2 and G6 still require real direct/forwarded carrier calls. Durable identity
persistence belongs to subsequent call-record integration and full US-03 acceptance.

## Environment and evidence

Build/test host: the authorized `~/ai/alojan` Ubuntu 24.04.2 x86_64 workspace,
GCC 13.3.0, Python 3.12.3, pinned PJSIP 2.16 and frozen uv dependencies.
Mac was used for editing and delivery of listening files, not renewed Mac testing.
The most recent full execution is the [named greeting validation](linux-named-greeting-2026-10-23.md):
**89 pytest passed, 1 warning, 121.62 s, no skips; 3 CTests passed, 1.04 s.**
Native build, Ruff and formatting passed there. This report changes documentation
and acceptance metadata only, so those unchanged executable tests were not rerun.
A fresh Linux collection confirmed **89 tests in 0.07 s**; collection is an inventory
check, not a new execution pass. The warning is Python 3.12 `audioop` deprecation.

The suite contains 33 real loopback SIP scenarios, 9 admission/identity CLI checks,
14 prompt/startup checks, 4 database tests, 5 protobuf tests and 24 gRPC contract
tests. The gRPC tests use an explicit test service, not real ASR/TTS inference.
All call audio is synthetic. Tests keep received RTP in memory; no microphone,
private conversation recording, real carrier traffic or external notification is used.

## Acceptance matrix

Test names below resolve in [the SIP suite](../../tests/sip-integration/test_sip.py)
unless another source is linked. Counts are parameterized cases, not asserted lines.
All automated rows passed in the latest full execution cited above.

| Task / condition | Evidence | Cases / result |
|---|---|---|
| M1-01: inbound answer, ACK and normal teardown | `test_two_way_rtp_and_playback_completion`; real INVITE/200/ACK/RTP/BYE | 6 codec/impairment cases |
| M1-01: ringing, pre-answer CANCEL, cleanup and slot reuse | `test_cancel_before_answer_and_reuse` | 1 |
| M1-01: busy admission and remote BYE | `test_busy_and_remote_bye` | 1 |
| M1-01: RTP inactivity, silent packets and duration limit | `test_missing_rtp_ends_call_and_releases_slot`, `test_silent_rtp_keeps_call_alive_until_packets_stop`, `test_max_duration_ends_before_wav_finishes` | 3 |
| M1-01/05: bounded shutdown | `test_shutdown_active_call_is_bounded`; one/two calls, with/without BYE acknowledgment | 4; process exits within 4 s test bound |
| M1-02: PCMA/PCMU, 20 ms pacing, loss/reorder/duplicate/jitter and sequence/timestamp wrap | `test_two_way_rtp_and_playback_completion`; 16 kHz input, 320 samples/frame, zero malformed frames | Same 6 cases above; not additional cases |
| M1-02: independent codec vectors and resampling | `audio-conversion` CTest; [numerical report](linux-audio-conversion-2026-10-23.md) | Fixed vectors, all PCM16 inputs, filter delay/tail, anti-aliasing and context isolation |
| M1-03: complete named AI greeting and closing before BYE | `test_spoken_greeting_and_unavailable_finish_before_bye` | 2 codecs; sample comparison, handoff ≤100 ms |
| M1-03: interruption, ACK gating and missing-file recovery | `test_remote_bye_stops_greeting_or_fallback`, `test_speech_waits_for_ack`, `test_prompt_disappearing_after_startup_ends_call_without_crashing` | 4; slot reuse and no continued speech after BYE |
| M1-03: valid assets and startup safety | [Prompt checks](../../tests/test_prompts.py) | 14; historical/new asset hashes, invalid WAVs and incompatible options |
| M1-03: intelligible AI disclosure | Owner accepted v2 and the named v3 greeting; manifest acceptance records | Passed local listening; not a handset/carrier test |
| M1-04: trusted/untrusted identity, normalization, anonymity and redirects | `test_caller_identity_policy_and_redacted_logs`; `caller-identity` CTest; [identity evidence](linux-caller-identity-2026-10-23.md) | 10 SIP cases plus native parser assertions |
| M1-05: independent calls, survivor and slot reuse | `test_two_call_media_and_cleanup_isolation` | 2 codec assignments; independent tones, ports, SSRCs, meters and single closure |
| M1-05: invalid admission/identity options | `test_invalid_test_admission_limit`, `test_invalid_identity_configuration`; `gateway-invalid-port` CTest | 9 CLI cases plus invalid-port CTest |

The existing pytest entry point is the reproducible smoke/scenario runner; no
additional wrapper is needed. Default admission remains one. Two calls are an
explicit isolation test, not validated two-call inference capacity. Single-closure
and reuse assertions establish tested cleanup behavior, not an exhaustive leak proof.

## Listening provenance

The current [v3 manifest](../../assets/prompts/tr-v3-ema/manifest.json) records the
owner's acceptance. The accepted 8 kHz greeting hash is
`29ef43e49532cb52e9a5e2a31b180dde6bee3068a87f2c35b64ae849f3fe45c2`.
No WAV or text was changed for this acceptance update. EMA CUDA synthesis evidence
remains separate from SIP tests: EMA 1.1.2 / torch 2.6.0+cu124, pinned model revision
`e7c96f2fc0ba843cd0f86e02786655bb56f50df8`, RTX 4080. These two offline texts do not
establish a persistent TTS service, general Turkish quality or ASR/TTS coexistence.

## Reproduction and review

From the Linux repository root with `~/.local/bin` on PATH and the existing private
DB configuration (never copied to the Mac):

```sh
uv run --frozen cmake --build --preset local
uv run --frozen ctest --preset local
uv run --frozen --env-file .local/dev.env pytest -q
uv run --frozen --env-file .local/dev.env pytest --collect-only -q
```

This report's checks: reviewed requirements-to-test mapping, preserved audio/text
hashes, changed-document relative links, whitespace and complete task diff; verified
local/remote source equality before editing and after synchronization. Codebase
Memory was unavailable (`Transport closed`), so known source files were inspected
directly. No code structure changed and no graph refresh is claimed.

## Next task and explicit open work

**Next: M2-01**, persistent faster-whisper large-v3-turbo with pinned CUDA dependencies
and model revision, Turkish partial/final transcription, deadlines/cancellation and
per-call isolation. Measure real ASR and later concurrent EMA memory use; the existing
gRPC test peer cannot count as ASR readiness. No ASR implementation is claimed by
this report. Subsequent M2-02/03 remain ordered by the existing task dependencies.

M1-06/07 and G2 remain pending operator/network facts: routable IPv4/NAT, confirmed
trunk source/auth/media configuration, followed by a real bidirectional Netgsm call.
Live agent/API, turn decisions, barge-in, persistent call records, notification,
carrier identity, production containers, long soak and the §3 performance targets
remain unproven. Full G0/M1 and G2–G7 are not closed. License/distribution review,
clang-tidy, hosted CI and a new Mac validation run remain separate.
