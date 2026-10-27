# Restorable live backup and isolated owner preparation

Date: 2026-10-26. Ponytail full; ADR 0003/0011, AGP-02/03/05/09,
M1/M4/M5, requirements §9–12 and US-07/08. This advances migration preparation;
it does not transfer the live number or certify voice performance.

## Actual backup restoration

On the primary Linux host, an exported PostgreSQL repeatable-read snapshot supplied
both the logical backup and content fingerprints. The live three-migration ledger
matched the checked-in SQL. `pg_dump` used the existing PostgreSQL container, custom
format, no owner/ACL restoration and a five-second lock wait. No credentials were
passed in command arguments or printed. Private rows stayed on Linux.

The 47,337-byte archive was restored transactionally into a newly created temporary
database with PUBLIC access revoked. All ten original tables matched by row count
and SHA-256 of sorted serialized rows. Counts included 29 calls, 29 summaries,
29 summary jobs, 25 notes, 292 utterances and eight outbox entries. These are snapshot
counts, not evidence that new call admission was fenced.

The restored database then received all 16 migration files through 0015, followed
by a second application. Every original column/value outside the intentionally
extended migration ledger remained identical. No accounts, workspaces, profiles,
connections, grants, action jobs or route snapshots were inferred from history.
The first upgrade took 0.063 seconds on this small restored dataset, with a
two-second lock timeout and 15-second statement timeout. This is not a loaded
production DDL or performance acceptance measurement. The temporary database was
removed after verification. The backup remains private on Linux at
`.local/owner-preparation-20261026/live-before-platform.dump`, mode 0600 in a 0700
directory; SHA-256:
`1d35ded54dd42d53c753892d3f82681b9028c907f55d5a9f012b243e7254264f`.

This validates logical data restoration, not a full-host disaster recovery drill.
Database roles, deployment files, images and external secret-key recovery remain
separate concerns. Take a fresh backup at eventual cutover; do not treat this earlier
snapshot as the final recovery point.

## Disconnected candidate workspace

Created `alojan_candidate_20261026` on the existing PostgreSQL instance, without
copying historical calls. It has all current migrations and PUBLIC database access
revoked. Its dedicated management login is unprivileged, owns no objects, has a
four-connection limit and bounded statement/lock/idle-transaction timeouts. It uses
the existing `grant_management` policy. No resident service points to this database.

Using the existing account/profile/connection application methods with that restricted
login, created one owner workspace for the explicitly requested Burhan account, one
Kübra draft and two encrypted scoped connections. Provider and Telegram values were
read privately from the existing authorized configuration files. Encryption was
checked against the original values; neither secret appeared in the audit records.
The management role cannot select either ciphertext column or read live call records.

The draft preserves every original business field and the complete live instructions;
only provider and post-call connection references/configuration were added. The
Telegram action selects assistant identity, caller number with provenance, duration,
summary status and the six summary fields. It is draft configuration only: there is
no standing grant, published release, phone number, binding or delivery job. The
second number remains absent. No message or model request was sent.

The account received an unshared random initial password; the preparation session
was explicitly revoked. No active session remains. Before interactive acceptance,
the owner must choose a password through the existing private operator recovery
flow. Account creation here is neither email verification nor a production ownership
transfer. Production ownership remains pending the actual cutover.

Existing repeatable catalog SQL was applied twice. It created one immutable model/
preset entry with qualification disabled. No readiness or synthetic qualification
was seeded. EMA assets, effective prompt/summary quality, matched real inference,
load/soak and carrier acceptance remain pending.

Private operator artifacts are in `.local/owner-preparation-20261026/` on Linux:
`owner-state.json` records exact identities/provenance; `management.env` is the
restricted candidate DSN; `provider.key` is the candidate encryption key;
`container.env` is its container-network DSN. All are mode 0600. These are candidate
files, not replacements for the future production management configuration. Keep
the key separate from database backup distribution. Exclusive attempt journals
prevent accidental replay of the one-off provisioning scripts.

## Validation and review

- Real backup/restore, repeated schema upgrade and original-row preservation passed.
- Restricted owner creation, full draft round-trip, encrypted-secret round-trip,
  denied secret/live-record reads and session revocation passed on the candidate DB.
- Five existing Linux suites (native auth, drafts, provider connections, Telegram
  connections and action grants): **42 passed in 25.09 seconds**, no skips/failures.
- The previously built `alojan-management:legacy-rollback-validation` image ran a
  real HTTP probe against the candidate database. Readiness returned 200 and an
  unauthenticated workspace request returned 401. The temporary container used
  0.5 CPU, 512 MiB, 64 PIDs, read-only root, dropped capabilities and no-new-privileges.
  No host port was published; the container exited and was removed afterward.
- All seven resident containers remained healthy with their original 2026-10-24
  start times. The live schema still has three migrations and no account table.

Two operational corrections were required. The first backup invocation lacked
`PYTHONPATH` and stopped at import, before any backup/database action. The initial
draft import correctly rejected an incomplete output selection missing caller-number
provenance and summary status. Corrected the private configuration and resumed using
the already-created account/connections; no duplicate account or connection was
created. The initial session was revoked on failure. Application validation was not
relaxed and no production source behavior changed.

Maintained documentation and whitespace checks passed; documentation was mirrored to
the established remote review directory without overwriting independently edited
remote root documentation. No push, merge, live migration, GPU generation, carrier
call, live process restart or external send occurred. Next: qualify EMA assets in an
admission-fenced maintenance window, then matched real voice/PERF and scoped canary
before production ownership, grant and binding activation.
