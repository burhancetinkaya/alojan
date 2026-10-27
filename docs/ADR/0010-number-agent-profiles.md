# ADR 0010: Number-scoped assistant profiles and Telegram delivery

Date: 2026-10-25.
Status: Superseded in scope/settings/notification cardinality by [ADR 0011](0011-self-service-voice-agents.md). Historical profile-routing decisions remain applicable only where compatible.
No runtime implementation, migration, carrier activation or delivery is claimed.

## Context and authorization

The owner requests two Netgsm numbers on the existing Linux installation:
Kübra represents Burhan Bey; Berkcan represents Serkan Bey. Both use the existing
EMA voice. Each number's post-call result goes through a different Telegram bot
to its configured chat. A later frontend must manage these mappings.
The subsequent request authorizes designing this infrastructure. Actual numbers,
bot credentials and recipient chats have not been supplied for provisioning.

This amends the one-owner/number baseline in requirements §1–2 and ADR 0001,
the global Kübra identity assumption in ADR 0006, and M5-01's webhook-first plan.
It authorizes centrally administered multiple recipient scopes, not a public
multi-tenant SaaS, independent customer accounts or unrestricted external tools.
DEC-01–15 remain: particularly the same voice/model, C++ media control, PostgreSQL,
private management, raw recording off, and explicit AI identity. ADR 0009 capacity
targets remain independent from number count and unverified at five/50 calls.

## Decision

Use the existing application and database with explicit recipient scopes,
versioned assistant profiles, carrier-number records, versioned Telegram targets
and atomic routing bindings. Each incoming call resolves a trusted called number
before its greeting and durably freezes the selected revisions for its lifetime.
Never select an assistant from caller ID, caller speech or model output. Both the
number owner's display name and assistant name are independently editable profile
fields; the named pairs above are initial values. Renames create a new revision,
regenerate greeting assets and apply to newly published bindings without changing
stable IDs, recipient scope or Telegram destination.

Keep one resident ASR/EMA service set per call server and call-local contexts.
Neither a second Docker installation nor a model per assistant is required.
Reuse the native Linux development profile and isolated database deployment;
production packaging and simultaneous-call qualification remain separate work.

The existing app-api becomes the protected management boundary. PostgreSQL is
the configuration source of truth. A later frontend uses its versioned API;
neither direct database edits nor environment files are the profile-management API.
Bot secrets remain outside ordinary profile rows and are never returned to clients.

Post-call summary commit and notification enqueue share one transaction. A worker
delivers only to the call's frozen target revision, with leases, bounded retries,
redacted errors and explicit ambiguous-delivery handling. Telegram is not an LLM
tool. No claim of exactly-once external delivery is made.

The detailed schema, API, lifecycle, migration and acceptance contracts are in
[PROFILE_ROUTING_PLAN](../PROFILE_ROUTING_PLAN.md), tasks PROF-01–07.

## Alternatives and consequences

- Cloning the entire stack per number duplicates GPU models and maintenance;
  different processes alone do not isolate records or prevent misdirected delivery.
- Mutable global prompt/environment switches can change an ongoing call's owner.
  Immutable revisions and call snapshots avoid this race.
- A general tenant platform, new message broker, routing microservice and Kubernetes
  are unnecessary for two centrally administered profiles. PostgreSQL and existing
  service boundaries suffice.
- Shared processes remain a shared failure domain. Logical recipient isolation is
  not process isolation or independently authenticated customer access.
- Unknown/ambiguous numbers fail closed instead of falling back to Burhan's profile.
  Existing calls finish with their original profile; publication affects new calls.
- Telegram may accept a message before a response is lost. Local deduplication
  prevents duplicate jobs, but cannot prove exactly-once remote delivery.

## Migration and release

Use additive schema/protobuf changes; seed the existing Kübra profile without
changing its behavior. Backfill only verified historical ownership. Do not send
historical calls or old outbox rows to newly provisioned targets automatically.
Deploy capable services before publishing the second binding. Keep legacy behavior
only in an explicitly single-number mode; disable it in multi-number mode.

The current carrier reachability failure recorded in CALL_TEST_PLAN remains open.
Restore and verify existing service before dual-number live acceptance. Rollout
requires per-number called-DID evidence, correct identity/summary/recipient checks,
and capacity qualification before allowing overlapping real AI calls.
