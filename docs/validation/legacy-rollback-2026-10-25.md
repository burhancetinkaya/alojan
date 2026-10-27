# Legacy rollback consumer boundary

Resume status (2026-10-26): synchronization, expanded regression, rebuilt package
imports and Compose configuration checks below are now complete. See
[resume evidence](platform-resume-2026-10-26.md). The original interruption history
below is retained; live rollout and real voice qualification remain pending.

Date: 2026-10-25. ADR 0003/0011, AGP-09 / M4/M5, requirements §9–12,
workspace isolation and preservation of existing calls/notifications. Ponytail full.

## Change and boundary

The preserved `lifecycle-20261024` consumer omits workspace filters. Restoring its
original privileged database credentials over managed calls would expose those calls
to the old summary/notification loop. The new operator provisioning purpose
`legacy-rollback` permits only records without a managed route. Both permissive and
restrictive PostgreSQL policies are installed for the dedicated role; forging the
workspace session setting or adding a permissive policy cannot broaden those records.

The existing role validator rejects superuser/BYPASSRLS, role memberships and object,
schema or database ownership. Provisioning also rejects schema CREATE, unexpected
effective table/column/sequence rights (including PUBLIC grants), and missing forced
record RLS. All grants/policies are transactional and repeatable. It grants no user,
password, credential, manifest, binding, grant or action-job access. It cannot delete
or truncate records, change legacy channel activation, or rewrite summary ownership.
There is no data migration, queue reset or external send during provisioning.

The role can read three routing-directory columns (`call_id`, `scope_id`, `release_id`)
because the existing invoker-rights ownership triggers and RLS predicates require them.
These opaque identifiers are an explicit internal compatibility exception; called
numbers, routing details and manifests remain inaccessible. This is an operator-only
temporary rollback role, never a customer API or managed voice/worker identity.

Legacy model/Telegram secrets still belong to the original single-owner deployment.
This boundary does not improve that old Telegram adapter's crash/retry semantics.
Old pending/uncertain notifications must be reviewed before restart; never replay them
as part of rollback. The newer scoped action worker remains stopped or separately
controlled, with its immutable jobs and receipts retained.

## Validation evidence

On primary Linux, **14 passed in 8.95s**, no skips. Coverage includes unfiltered old
queries with absent/correct/foreign workspace settings, known managed identifiers in
legacy inserts, forbidden account/key/manifest/number reads, RLS-disable failure,
excess column/table rights and an additional permissive policy. The preserved original
Store and Notifications code completed one synthetic legacy call, note, summary,
enqueue and fake delivery while a managed call's summary stayed pending and its legacy
outbox stayed empty. Repeated enqueue/delivery did not duplicate the completed message.
Transport was synthetic; no external message was authorized or sent in this turn.

The preserved source modules were checked against the actual deployed image:

| Module | SHA-256 (snapshot and image identical) |
|---|---|
| store.py | `1e77ccb43fcc172104cc8a5127dda9fb9954d6f720bb53f8e3d0eda98c1bef87` |
| models.py | `669475db245adf05e3d2b49e150a2ce883c54f254521335d9311f4861051c554` |
| notifications.py | `89fc7b6b5918c0736cfc08c505b2a3d8eb568baa3b6d2189106c35c42d6a2a76` |
| telegram.py | `ef1f41af79fc01a782b17b67fd07a89f6b0bbb59133b64ee92eeecc2d0fd6ef5` |

The test executes those source modules with the Linux test interpreter/dependencies;
it is not a full running-container or SIP rollback rehearsal. Without an explicitly
selected `ALOJAN_ROLLBACK_SOURCE`, that artifact-specific test skips rather than using
the current source as substitute evidence.

Initial run: 14 setup errors because PostgreSQL evaluated a sequence-privilege function
on a non-sequence before applying the catalog filter. An explicit CASE type guard fixed
the query; the subsequent 14-test run above passed. Initial Ruff checks/format passed;
final local syntax/whitespace inspection passed. A broader five-suite regression,
management image build and Compose validation were attempted but SSH then timed out.
They are **pending**, not passing. The new Compose overlay and this documentation were
not synchronized after that loss of connectivity. Python implementation/tests had
already been synchronized for the successful Linux run.

## Operator deployment and rollback sequence

1. Complete the remaining performance/voice gates and backup/restore rehearsal.
   Apply the platform migrations with bounded lock/statement budgets. Create a fresh
   non-owner, non-inheriting login role through private operator tooling; no password
   in command arguments, documentation or chat. Do not reuse the existing superuser DSN.
2. With private migration credentials, provision the role through the management
   package: `python -m alojan.roles ROLE --purpose legacy-rollback`. The current package
   must contain `alojan.legacy_roles`; rebuilding its image remains pending.
3. Store only `ALOJAN_DATABASE_URL` for that dedicated role in a separate private
   mode-0600 environment file. Set `ALOJAN_LEGACY_DATABASE_ENV` to its absolute path.
   Append `infra/compose.legacy-rollback.yaml` **last** to the preserved lifecycle base
   and voice Compose files. It replaces `database_env` for the old agent, health API
   and Telegram service; missing explicit configuration fails interpolation. Validate
   the resolved configuration privately, confirming the restricted file is actually
   mounted. Never dump resolved credentials or use `dev.env` as this file.
4. Before rollback, fence candidate admission, drain calls, withdraw managed readiness
   and stop affected scoped consumers. Preserve all managed calls, notes and action
   states. Review legacy pending work without reactivation/backfill. Restore only the
   original single-owner number to the preserved voice stack with the restricted DSN;
   new users/numbers must never reach the legacy route. Verify actual DB `current_user`,
   role/RLS enforcement and empty managed visibility before admitting calls.
5. On recovery, stop legacy admission/consumption before resuming the qualified managed
   deployment. Keep additive data/schema; do not restore a whole database over newer
   writes. Retire the rollback login after the rollback window closes.

The original snapshot and image remain unchanged. No production role, credentials,
schema, process, mapping or account ownership was changed. Real voice comparison and
container/Compose verification must resume when Linux connectivity is restored.
