# Supervised admission persistence — 2026-10-26

Scope: ADR 0003/0011, AGP-09 / PERF-01/03 preparation, M1/M5, requirements
§12/12.1. Ponytail full. Linux execution; no carrier or real inference.

## Change and review

Imported the existing `supervise.py` and unchanged `health.py` from the preserved
Linux `.local/call-lifecycle-release` deployment, since these files were absent from
the Mac source tree/graph. Reviewed the resident command, launcher, source, callers,
SIP fixture and admission acknowledgement before editing. No new dependency.

An optional gateway-only `ALOJAN_ADMISSION_FILE` enables control. Every child starts
closed; the first native draining acknowledgement permits supervisor signalling.
Only a bounded regular non-symlink file containing exactly `open\n` permits admission.
All other content, missing/unreadable paths and non-regular files request closure.
The supervisor polls outside the media process and retains existing health/restart
and bounded termination behavior. It sends signals to the direct exec child, never
an entire process group. Existing shutdown still terminates the process group.

The Netgsm launcher forwards startup arguments in all three profiles. Comparison
against Linux found its existing national-prefix argument absent locally; that
remote setting was preserved and copied into the Mac source rather than removed.
Source synchronization touched only eight explicit files; backups and all eight
matching SHA-256 values are retained under `.local/supervised-drain-20261026/`.

The optional compose overlay requires an explicit compatible image and private
parent-directory bind mount. Atomic operator writes survive replacement/restart;
the container cannot change them. No PID 1 USR forwarding, HTTP endpoint, model
reload, new service, user-visible tuning or higher call capacity was introduced.

## Linux checks

- New supervisor/real SIP-RTP suites: **12 passed in 17.60s**, zero skips/failures.
  PCMA/PCMU media continues during drain; new calls receive 486; persisted closed
  startup and explicit reopen work. Invalid/missing state closes an already-open
  gateway. Tests cover regular-file bounds, symlink/FIFO rejection, startup
  acknowledgement gating, health-failure forced reap, signal-handler restoration
  after launch failure, and all three Netgsm launcher profiles.
- Initial broad regression: **117 passed, 11 skipped in 230.33s**, no failures.
  The command omitted the explicit database environment; skipped cases are not
  acceptance evidence. Database-dependent suites were subsequently rerun below.
- DB-enabled prepared-setup/managed-session rerun: **78 passed in 202.64s**, zero
  skips/failures. The two regression commands together cover all **128 distinct
  existing scenarios**; the 78 include 67 repeated passes and all 11 initially
  skipped cases. With 12 new cases, 140 distinct tests passed.
- Ruff check/format, shell syntax and `git diff --check`: passed. The SIP harness
  still emits its existing Python 3.12 `audioop` deprecation warning.
- Compose overlay configuration: passed against preserved base/voice definitions;
  no deployment command issued. Graph refreshed: 5635 nodes / 18737 edges.
- Native source/binary unchanged this turn; no native rebuild or duplicate CTest
  claimed. Previous native acceptance is linked in the admission-drain evidence.

## Isolated Docker acceptance

Built `alojan-gateway:admission-validation-20261026` from the exact retained live
runtime image, replacing only the tested native binary, supervisor, health probe
and launcher. Base image ID:
`sha256:3d10dd6d7005aa8f5d9f7d555955fea6ce9d3559ff27f634cb830f32e04fa4b3`.
Final image ID:
`sha256:e0e21c73db2d49ad45287e2523834cb5900e94176d96704fc9a70961735fa852`.
Native SHA-256:
`28f6bbfc252eb39e94a4038307a7807866d892fb51ac8028b4e40f59fb3ef5b4`.
Supervisor SHA-256:
`8e718bc1a9fe488acbdf8de0a6dcd66eac90968de0b1f5fc6214f04ddb2a89ec`.

The first build attempt passed a bare image ID as FROM and failed because BuildKit
resolved it as a registry name. The validation container therefore did not start
on that attempt. Tagging the exact existing local ID and rebuilding succeeded;
no running deployment changed. The recipe requires an explicit base tag and has an
expected no-default-FROM build warning; this was not a Dockerfile lint pass.

Actual container checks passed with network disabled, no secrets/DB/GPU, non-root
user, read-only filesystem/state mount, 0.5 CPU / 256 MiB / 64 PIDs:

1. Closed startup rejects local SIP INVITE with 486.
2. Persisted explicit open permits 200; the synthetic call ends normally.
3. Persisted drain rejects 486 while OPTIONS health remains successful.
4. Killing only the test native child causes supervisor exit and **one actual
   Docker automatic restart**.
5. The restarted process retains closed admission and rejects 486.
6. Closed admission stays healthy through a supervisor health-probe interval.
7. Explicit reopen permits 200 again.

Removed the isolated validation container. Retained the image and private
`docker_check.py`, `docker-result.json`, source hashes, logs and staged context on
Linux. The retained operator state was persisted closed after validation. Seven
live services remain healthy with their original 2026-10-24 start times; sanitized
state is retained in `live-status.json`.

## Limits and next step

The resident lifecycle gateway has not been upgraded and still must not receive
USR signals. This is functional Linux/container evidence, not GPU, model, latency,
carrier, full-source release-build or production migration acceptance.

Polling is 250 ms; an in-flight health probe can delay observation up to its
five-second timeout plus scheduling. A file write/request event is not a drain
receipt. Serialize operations; use fresh native state/local-drained events and the
current container start identity, and repeat verification after restart. Closed
admission health is deliberately distinct from voice readiness and GPU idleness.

Next: establish dependent ASR/TTS/agent quiescence and a coordinated compatible
maintenance deployment, then run fresh matched real voice/PERF comparison. Expired
leases or local_calls=0 alone cannot prove a non-preemptible inference has stopped.
Do not start a second EMA instance or expose candidate routes before these gates.
No external message, account/publication/grant/binding change, push or merge occurred.
