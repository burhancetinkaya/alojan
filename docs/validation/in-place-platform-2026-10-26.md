# In-place managed voice trial — 2026-10-26

Ponytail full; ADR 0003/0011, AGP-03/05/09, M1/M4/M5, US-01/05/07/08,
requirements §11.2/12/12.1. The owner explicitly authorized testing on the unused
existing line and rejected another environment or an intervening legacy reopening.
This supersedes the isolated-candidate deployment sequence in earlier records.

## Successful handset retry and post-call recovery

The owner retried the real line and explicitly reported that everything worked as
well as before. DB/native correlation: incoming **08:05:38 UTC**, answered
**08:05:41**, ended **08:06:33**, answered duration **52,196 ms** on 2026-10-26.
The native gateway reported PCMA (the DB codec field was null), 2,585 received RTP
packets, three lost packets, no reorder/duplicates, and 14,320 ms of response output.
Seven caller and seven assistant records, two native interruption events, one note
and confirmed setup release were observed. Scope and pinned release match the
installed owner configuration. No transcript, number or audio is published here.

This is functional carrier evidence, not a matched performance result. Completed
response endpoint-to-output measurements were 1,639, 939, 2,478, 1,059 and 960 ms;
estimated last-voice-to-output values were 2,535, 1,563, 3,230, 1,931 and 1,480 ms.
The owner reported no perceived degradation, but the small mixed-turn sample is
not latency/capacity acceptance and retains the existing PERF work.

Post-call inspection found the summary stuck in recoverable processing. A
content-free diagnostic identified `ValidationError`, `instructions/string_too_long`:
the retained action-worker image still used the former 6,000-character maximum,
while the agent/management contract already allowed 20,000. The source diff was
only that previously approved field limit/comment; no user instructions were cut.
Built a derivative of the retained worker image copying only the current shared
configuration module. Validated the exact pinned release inside that image with
network disabled; the compiled 32 KiB prompt limit remains enforced.

Linux worker lifecycle and long-instruction regression: **5 passed in 4.85s**.
Updated only summary/delivery containers to image
`sha256:af25a2105799a3f344c144d14d375b8901fb0e14efb386398575fcdebb6cfe0b`;
configuration SHA-256
`b3654d3225f4fc1d1a4c200b35c6398d5cc0be17d2063fb61d4adfeb72d42c2e`.
Seven peer container identities and health, including all voice services, were
preserved. No migration, release change, model reload, lease reset or extra test
notification was performed. The ordinary expired-lease recovery completed the
existing summary on claim six and committed its finalization. Telegram delivery
is `sent`, **one attempt**, no failure code, with a remote message receipt.
This proves Telegram accepted the real call's notification, not recipient reading.

Sanitized private evidence: `.local/called-prefix-fix-20261026/handset-result.json`,
worker build/regression logs and before/after deployment configuration. The earlier
404 and delayed summary remain recorded failures. One managed carrier round trip
now works; full handset scenarios, load/soak, matched PERF, frontend and interactive
account recovery are still separate work.

## First handset failure and prefix correction

The first owner handset attempt after reopening failed: Netgsm played its
unavailable announcement. Native events showed trusted carrier identity,
`INCOMING code=100`, immediately followed by `DISCONNECTED code=404 elapsed_ms=0`
with zero input/media packets. This is a failed carrier trial, superseding the
earlier readiness statement below; no agent turn or Telegram success is inferred.

The retained carrier INVITE target is ten digits beginning `850`, matching the
verified binding when prefixed with `+90`. The private managed gateway deployment
had explicitly selected `ALOJAN_CALLED_NATIONAL_PREFIX=none`. The existing parser
therefore rejected it before call initialization. Previous loopback voice trials
sent canonical `+90850…` and missed this deployment mismatch.

Added a synthetic ten-digit carrier-format case to native managed-session coverage.
Before correction it failed to obtain SIP 200 (**1 failed in 10.24s**). With the
existing `--called-national-prefix 0` option, all three session variants passed
(**3 passed in 77.99s**, no skips); they cover conversation, interruption, pinned
leases and cleanup using scripted inference and real native CPU turn models.
The existing identity/security CTest passed (**1/1 in 1.02s**), including exact
prefix forms, untrusted sources and invalid-number rejection. Ruff check/format
and whitespace checks passed; the existing audioop deprecation warning remains.

Changed only the private gateway prefix setting from `none` to `0`. Waited for
native admission closure and zero local calls, recreated only that container,
verified the same image and healthy SIP loop, then reopened admission. Gateway
started at **2026-10-26 07:59:53 UTC**, using unchanged image
`sha256:e16548aee6be449305457279f09a69edeacf1ed3baa5bf797ae52f0adea72c0b`.
Eight peer container identities and health were preserved, with fresh health
checks of all three speech/agent workers. No model reload, schema/release change,
permission relaxation or synthetic external message was required.

Private before/after configuration and test evidence are retained under
`.local/called-prefix-fix-20261026/`. Actual handset retry and post-call Telegram
delivery remain pending. This correction is not carrier, GPU or PERF acceptance.

## Data and ownership

Stopped the global legacy summary/Telegram consumers. Before applying migrations,
all 29 historical calls had ended and their summaries were complete. Saved and
validated a private PostgreSQL dump (47,337 bytes; SHA-256
`c3bf1e45ef94276f92ce39f6e1e9abd28ee692c664fef5b7c2006d7422dbed14`).
Applied all 16 checksum-checked migrations to the existing database, then repeated
migration. Exact original-column row fingerprints remained equal across nine
original tables, including 29 calls, 29 summaries, 25 notes and 292 utterances.
The additive migration took 0.353 seconds. No historical notification was replayed.

Installed the already prepared native account/workspace, Kübra draft v2, encrypted
provider/Telegram connections and immutable catalog data, preserving their IDs.
Seven dedicated runtime roles separate management, routing, records, readiness,
credentials, summaries and actions. The initial account password has not been
distributed; interactive account recovery/frontend acceptance remains pending.
Historical unscoped records remain retained; new managed calls use owner snapshots.

Used the retained carrier capture to match the inbound INVITE target and transport
source against private Netgsm configuration. The operator recorded existing-owner
migration and carrier evidence, then used normal number verification/binding APIs.
There is one verified number; no second number/bot was fabricated. Caller ID was
not used as ownership authentication. Private evidence keeps the full number out
of this document.

## Voice and deployment

Added explicit `--managed-agent-port`, `--managed-asr-port`, and
`--managed-tts-port` options to the existing native gateway. They use the existing
prepared-call, pinned-profile, scoped-record and cleanup path. Managed carrier
startup requires complete distinct service ports, adaptive turns, a SIP source
allowlist and explicit trusted sources within that allowlist. Mixed test/legacy
profiles, fixed capture, global prompt overrides and calibration overrides fail
before listening. Existing `--setup-test-*` remains loopback-only.

The Netgsm launcher's `managed` profile supplies infrastructure addresses/ports and
called-number extraction policy. Greeting, timings and conversational calibration
come from the immutable release. No management HTTP request enters the media path.
The initial imported preset omitted the deployed partial-hint override; review
caught this before reopening. A new immutable preset/catalog revision 2 preserves
the existing enabled hint. No model/provider, EMA revision, decoder or capacity
change was introduced. The same resident ASR and EMA containers were reused.

The owner-directed trial explicitly enables the existing model catalog entry with
a trial evidence reference. This is not a claim that quality or PERF qualification
passed. A real provider probe with installed scoped credentials completed six
turns; only three of six behavioral checks passed. Topic-only inquiries were saved
prematurely in two scenarios, affecting three checks. Correction and farewell
worked. First-phrase observations were 1261, 1861, 1158, 2527, 1671 and 544 ms;
these exclude ASR/TTS/RTP and are not a performance distribution.

Reused exact deployed greeting/unavailable WAVs. The first real managed two-turn
PCMA loopback used resident CUDA ASR/EMA, OpenRouter, scoped credentials, the main
database and actual release readiness. It persisted an unconfirmed note and
completed a real scoped summary. Native resource cleanup was acknowledged.
The synthetic notification was prevented from sending. Its operator harness first
assumed a transport without `resolve()` and incorrectly attempted to re-enable an
immutable revoked grant; both mistakes are retained as failed harness attempts.
Normal claim/begin then paused the job under the revoked grant. A fresh grant for
the identical already-authorized notification scope was recorded through the API;
the superseding release otherwise retained identical configuration.

Independent management HTTP, scoped summary and scoped Telegram services use
separate Docker containers and restricted credentials on the existing host.
Management binds only loopback with a reserved local HTTPS origin; a public UI/TLS
route has not been deployed. PostgreSQL was not recreated. Old global consumers
remain stopped. Synthetic jobs must be terminal/paused before delivery workers
resume; no new external message is authorized by these synthetic fixtures.

## Checks and limits

The final engine revision passed a second two-turn real-model PCMA loopback in
**33.29 seconds**, including scoped note, actual summary and native cleanup.
Summary/delivery services were stopped during this synthetic fixture. Its action
was completed with an explicitly synthetic, network-free rejection transport and
an operator audit record; no Telegram request occurred. The first fixture's action
remains paused under its revoked grant; the second is terminal failed. Neither is
eligible for automatic replay. Both background services were restarted afterward.

Fresh release readiness, verified binding, enabled action grant, zero active calls
and terminal synthetic jobs were checked. Native admission acknowledged open and
the authorized privileged command removed only the temporary
`ip alojan_initial_maintenance` table. The managed gateway is open for the owner's
phone trial. Seven health-checked containers are healthy; summary/delivery workers
are running without restarts but have no Docker health check. The database has
31 calls/summaries, including the two synthetic calls, and the original eight
legacy outbox rows. Handset/carrier acceptance has not occurred on this release.
This requested evaluation does not turn known quality/PERF failures into passes.

- Linux native build, clang-format, Ruff and shell syntax passed.
- Managed Session, carrier-configuration and admission tests: **46 passed in
  147.41s**, zero skips/failures. This includes the new explicit managed profile
  with synthetic public SDP, real native turn/interruption models, scripted
  inference, pinned records and cleanup. The existing audioop warning remains.
- Native CTest: **10/10 passed in 3.88s**.
- New gateway image:
  `sha256:e16548aee6be449305457279f09a69edeacf1ed3baa5bf797ae52f0adea72c0b`;
  binary SHA-256 `185870fe30a5bed0efd14d8d2c16475a6beb5e42a3294388580f19440ff0008f`.
- Managed agent image:
  `sha256:484d70ab98029c428e97695989570631627a52e77acbee093a49827f4663cf7b`.

The real loopback is a functional check, not a Netgsm handset call. Full matched
latency/quality/load/soak and carrier acceptance remain open. Topic-only intake
quality remains a known failure. No claim of five/50-call capacity is made.
Raw caller recording stays disabled. No push, PR publication or merge occurred.

Private scripts, exact results, backups, manifests and sanitized-status journals
are under `.local/in-place-platform-20261026/` on the primary Linux host. Do not
rerun the one-shot migration/owner-install scripts. Persistent admission and the
narrow bootstrap INVITE fence are managed separately; opening requires fresh
managed readiness and a confirmed terminal state for all synthetic notifications.
