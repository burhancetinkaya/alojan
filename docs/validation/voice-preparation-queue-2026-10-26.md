# Durable resident voice preparation — 2026-10-26

AGP-06 / M2,M5, ADR 0011, requirements §11.2/12/12.1/14–16. Ponytail full;
Linux is the primary test/build/deployment environment. This completes the next
prepared-audio UI slice, not the whole self-service platform or PERF acceptance.

## Result and review

Added migration 0016 and scoped version/CSRF-protected audio request/status APIs,
request-only management grants, a separately privileged CPU-only host coordinator,
independent locked runtime, user systemd unit, and frontend request/retry/status
controls. Existing prepared speech is reused. Publication/binding remain explicit.
The API has no inference, asset write or admission-control capability.

Reviewed immutable preparation/asset identity, actual generation lease/configure/
stream/release callers, native drain logs, worker quiescence, Docker supervisor,
role policies, current deployment mounts and frontend callers before editing.
Subsequent review added gate-loss checks, fresh managed-route readiness before
reopening, bounded progress/RPC deadlines, and throttled DB liveness checks outside the live
call path. The private coordinator has process/file/session fences and leaves
admission closed on uncertain cleanup, restart or lost ownership. TTS alone opens
for preparation; no second EMA is loaded.

## Exact Linux evidence

- Initial queue tests: **8 passed in 4.26s**. Expanded first suite: **54 passed in
  20.42s**. Final after fencing/readiness cases: **57 passed in 23.23s**, zero skips.
  Includes scoped/stale/CSRF requests, concurrent deduplication, bounded retries,
  interrupted jobs, dedicated SQL privileges, real loopback gRPC with synthetic PCM,
  valid WAV installation/recovery after a failed metadata commit, restart/cleanup/gate/readiness failures and prior release/
  preview/worker maintenance regression. These simulations do not establish GPU quality.
- TypeScript check, production Next build, Ruff and whitespace check passed.
  **9 real HTTPS browser scenarios passed in 14.3s** against a disposable restricted
  role/schema. Added request persistence across reload; no worker consumed those
  synthetic browser requests. Zero production configuration writes or external sends.
- Desktop/mobile screenshots reviewed. Real owner login/read-only navigation/audio
  playback/logout passed with zero browser errors and zero configuration mutations.
- Actual resident EMA preparation in a separate disposable schema: **4.252 seconds**
  including coordinated maintenance and installation; greeting **44,160 samples**,
  unavailable **25,920 samples**, mono PCM16/8 kHz. All four voice process identities
  were preserved during this generation, both WAVs validated, and admission reopened.
  No SIP call, notification, production agent/profile mutation, publication or binding.
  Test files/schema were removed. This is real model execution, not a listening or
  matched call-latency/quality acceptance result.

Initial lint rejected two compact test statements; formatter corrected them before
passing checks. The first standalone worker import exposed a missing indirect
cryptography dependency, which was explicitly pinned and locked before deployment.
The first real-model harness attempt omitted the required draft instructions and
was rejected before requesting maintenance/inference; corrected the disposable
fixture and reran successfully. These failed attempts are not counted as passes.

## Deployment and recovery

Backed up the existing database privately, applied the additive migration and
provisioned the dedicated role. During an acknowledged drain, recreated **only TTS**
with its existing image and a separate admission state filename. Fresh receipts
were obtained after restart; gateway/ASR/agent identities were preserved and normal
admission restored. No model revision, voice calibration or live profile change.

Updated management and web only after validation; **eight peer containers retained
identity and health** in that rollout. Worker runs separately with 0.5 CPU/256 MiB,
no listening port and no automatic restart after failure. Its 42 source/runtime
files are pinned in a private content-addressed release (`ef0f0036a50b…`), so later
checkout edits do not change the running deployment. Recovery requires fresh
operator evidence, not a time-based reclaim or forced readiness flag.

Private evidence lives under `.local/voice-preparer/`, `.local/web-voice-queue-20261026/`
and the HTTPS harness directory ending `38be7dc4874a4537917d8d736457d03d`. No credentials,
phone digits or transcripts are included here. Management image:
`sha256:4acb6b060e3472fcabab6ab7a291998b3e5f538ad4116feb672292e388bce845`;
web image: `sha256:e30f6b3341abcb05bfd3a4244729a2e8c40fcda260f478403b407ddfb278b562`.

Next AGP-06 work: scoped full call detail (summary/note/delivery outcome), then the
remaining approved builders. Public-launch abuse controls, recovery experience,
MCP/HTTP adapters, full handset scenarios and PERF-01–06 remain separate gates.
