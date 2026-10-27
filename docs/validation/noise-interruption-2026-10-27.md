# Fragmented voice evidence and noisy-speakerphone investigation — 2026-10-27

Scope: M3-02, M5-03, VXP-06; US-05/06, requirements §7.3–4; ADR 0003/0014.
The owner prioritized false interruptions in a noisy room with speakerphone on,
while silent. Further Jev work is deferred; existing Jev runtime settings are unchanged.

## Finding and change

The native interruption monitor accumulated all VAD-positive 32 ms blocks until
an 800 ms candidate-expiry gap. It reused this total for the 640 ms sustained-voice
fallback. Consequently, multiple short bursts separated by hundreds of milliseconds
could interrupt output even without a recognized correction or sustained speech.

Separate the existing ASR candidate total from sustained voice evidence. A gap of
at least the existing sustained-quiet setting (160 ms by default) resets only the
sustained counter. Shorter VAD dips retain it. The existing candidate expiry,
recognized correction path, onset thresholds, bounded pre-roll, callback epoch
revocation, cancellation and sent-audio accounting remain in place. No new agent
setting, model, network request, audio filter or dependency is introduced.

The event-loop interruption record now reports content-free voice/sustained/quiet
durations, last VAD probability, fresh-ASR coverage flag and monitor-local rejected
echo frame count. These are diagnostic evidence, not a classifier of the acoustic
source. No transcript or audio is added to logs. Values are published before the
interruption counter; no logging or additional work is added to media callbacks.

## Reproduction

- Linux deterministic regression using the old accumulation behavior failed on
  separate 128 ms voice-positive bursts with a 160 ms quiet gap. The regression
  also covers 320/768 ms quiet gaps in the corrected candidate.
  The corrected implementation passes this sequence while uninterrupted speech
  still interrupts at 640 ms and fresh recognized corrections remain eligible.
- The unchanged prior Linux gateway binary failed the new loopback SIP/RTP case:
  six pinned synthetic EMA short acknowledgments separated by 480 ms of silence
  produced an unwanted interruption. Real native Silero/Smart Turn and G.711
  transport were used, with explicitly scripted ASR/TTS services. This reproduces
  the accumulation defect, not the owner's exact room acoustics.

## Validation status

Primary Linux host results:

- Native build passed (four parallel build jobs); no new dependency.
- Initial candidate CTest: **11 passed**, 3.80 s; SIP suite: **13 passed**, 241.00 s.
- Final code preserves the original ASR-candidate expiry comparison exactly; only
  sustained evidence uses the newly separated quiet-gap count. Added custom-gap
  boundary coverage and two seeded noisy-echo cases. Final CTest: **11 passed**,
  3.78 s. Focused SIP: **3 passed**, 12 deliberately deselected, 55.02 s. These
  cover the previously failing repeated-burst case and delayed echo plus seeded
  +/-1000 PCM-unit noise in PCMA and PCMU. The 12 deselected cases are not a
  second full-suite pass. The earlier full suite covers real correction/cancel,
  old-output suppression, silence, single acknowledgments, clean delayed echo,
  monitor hangup/reuse, seeded standalone noise and invalid ASR coverage.
- Clang-format dry-run, Ruff lint/format and task-scoped diff whitespace checks
  passed. The known Python audioop deprecation warning remains.
- Task diff reviewed; graph refreshed. Source hashes match between Mac and Linux.

At the end of the initial investigation, serving gateway and agent were read-only
verified healthy and unchanged. The gateway image was `sha256:aabd1c88e373ed422e765bbcf2aab541dfc81b491d9921306a37b9df4cd01b8d`;
the rebuilt candidate was not installed in that image. No call or notification was
initiated and no number binding or Jev setting was changed. The later owner-authorized
deployment is recorded below; the handset trial remains pending.

## Limits

The owner's three interruptions cannot be attributed conclusively without the
missing acoustic decision evidence. Continuous background human speech, distorted
speakerphone echo and double-talk remain distinct risks. The current reference
correlation is echo rejection, not acoustic echo cancellation. This fix does not
claim complete noise immunity, a new latency percentile or carrier acceptance.
A matched noisy-speakerphone trial with silence and deliberate interruptions is
still required; raw recording remains disabled. Do not promote previously rejected
denoisers or retune VAD thresholds solely on this synthetic regression.

Private evidence: `.local/noise-interruption-20261027/`; pre-change source snapshots
and native binary are retained on the primary Linux host. No Git publication.


## Owner-authorized live deployment

The owner requested activation after the above investigation. On 2026-10-27 at
15:57 UTC, installed only the qualified native gateway binary on the exact previous
image. Linux source hashes match the tested Mac snapshot; the build reported no work.
The resulting image passed the interruption policy test in a network-disabled
container and its native binary matched the qualified artifact hash.

- Previous image: `sha256:aabd1c88e373ed422e765bbcf2aab541dfc81b491d9921306a37b9df4cd01b8d`.
- Installed image: `sha256:904aaa208607f0d173eeaa2f252e3eb91f291d474eb33cc452af0304f1cae651`.
- Native binary SHA-256: `8b82ea19060bc481138811af7ca79203fe6393a79025ccfa4d2dc5e65ed33e50`.

Deployment checked zero active/initializing calls and no preparation jobs, held the
existing PostgreSQL advisory lock and preparer file lock, stopped the idle preparer,
and waited for fresh native draining/drained acknowledgements. Saved the previous
private gateway Compose configuration, changed only its image, and recreated only
the gateway. Health and bound-route readiness passed before reopening admission and
restarting the preparer. Phone-number IDs/versions/bindings/enabled state, the managed
agent configuration and the agent/ASR/TTS container identities were verified unchanged.

Independent post-deployment checks passed: mapped running executable hash matches,
container healthy with zero restarts, direct SIP OPTIONS response succeeds, all voice
services healthy, admission open, bound routes ready and voice preparer active.
No handset call, recording, notification, remote MCP execution, GPU benchmark or new
carrier/acoustic acceptance was performed. The current Kübra binding remains in place;
Jev is unchanged. Same-room noisy-speakerphone validation is still outstanding.

Private deployment evidence and rollback configuration are under
`.local/noise-deploy-20261027/` on the Linux host. Rollback must use the same idle-call,
preparer and admission fences: restore `compose-before.json` to the existing gateway
Compose path, recreate only the gateway, confirm previous image/health/route readiness,
then reopen admission and resume the preparer. Keep admission closed if recovery
cannot be verified. Do not restore the agent image or change phone-number bindings.


## Post-deployment handset review

After activation, the owner reported a completed call and explicitly confirmed
being silent when the second response stopped. Read-only review found one call
after deployment, with 48.4 s connected duration. The serving image still matched
the installed candidate and was healthy.

- First response completed; endpoint-to-first-output 2179 ms.
- Second response started after 1059 ms, then was interrupted. Decision evidence:
  `voiced_ms=640 sustained_ms=640 quiet_ms=8 vad_milli=699 asr_fresh=0
  monitor_echo_frames=2`. Combined with the owner's report, this is a false
  interruption via the no-fresh-ASR sustained fallback. It is not the previously
  fixed accumulation of separated short bursts. The two rejected frames establish
  only limited echo detections, not successful rejection of all speakerphone echo.
- Next listening turn had `accepted=0 audio_ms=20000 last_voice_audio_ms=20000
  decision_silence_ms=0`; wall duration was 18347 ms because monitor pre-roll was
  replayed. Native error 8 maps to `incomplete_turn`, not an LLM/Jev failure.
  The input capture limit was reached without an accepted endpoint; the gateway
  used its fallback and closed. The generic closing label
  `dependencies_unavailable` is not evidence of an actual unavailable service.
- Summary job completed and the configured action was sent. No conversational MCP
  execution was recorded. No extra message or call was initiated during review.

The candidate does not pass this handset acoustic acceptance check. Continuous
speech-like background sound and distorted echo remain possible sources; no raw
recording exists to discriminate them. Further work must qualify the sustained
interruption path under noisy echo/background speech while preserving deliberate
barge-in, and improve recovery after an unproductive interruption. Raising thresholds
or adding a serial remote-model call is not established as a validated remedy.

Private sanitized metrics: `.local/noise-call-review-20261027/evidence.json`.
No code, runtime setting, number binding or container was changed by this review.
