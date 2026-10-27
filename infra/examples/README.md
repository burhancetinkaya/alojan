# Profile and system configuration SQL

These scripts use **PostgreSQL 17 SQL**, not Microsoft SQL Server T-SQL.
Run the existing migration runner first; it applies `0001`, `0002` and the additive
`0003_profile_settings.sql` both on fresh and existing databases. Never edit an
already applied migration: the runner checks its checksum.

On the authorized Linux host, from the project root:

```sh
PYTHONPATH=services/app-api uv run --frozen --env-file .local/dev.env python -m alojan.migrate
```

`0003` creates `recipient_scopes`, `assistant_profiles`, immutable
`assistant_profile_revisions`, and the typed singleton `system_settings`.
System defaults are seeded by the migration. Credentials and host addresses remain
private deployment configuration, not ordinary database settings or SQL examples.

`profile_settings.sql` is optional demonstration data, not an automatic production
seed. It creates disabled Kübra/Burhan and Berkcan/Serkan profiles without phone
numbers, bot tokens, destinations or outbound actions. Repeating it does not
replace existing revisions or operator settings. Run it in a development database:

```sh
uv run --frozen --env-file .local/dev.env python - <<'PY'
import os
from pathlib import Path
import psycopg
with psycopg.connect(os.environ['ALOJAN_DATABASE_URL'], autocommit=True) as conn:
    conn.execute(Path('infra/examples/profile_settings.sql').read_text())
PY
```

Profile fields include names and Turkish address forms, role/tone/business context,
greeting and availability, reply length/questions, further-help policy, recovery,
farewell, note acknowledgement and summary wording. Only Turkish and the existing
EMA voice are enabled. Template placeholders are data for the future renderer;
SQL does not execute/interpolate them. Changing a name requires a new revision
and updated address forms, availability text and greeting readiness before future
publication. Old revisions reject UPDATE/DELETE, preserving call snapshots.

`system_settings` contains the model/provider/routing, generation and transport
budgets, call/turn/DB timeouts, text limits and mandatory safety policies. The latter
are represented explicitly but CHECK constraints prevent disabling them. Changing
a model or capacity setting still requires the existing approval/calibration gates;
a stored value does not establish model availability or qualified hardware capacity.

**Implementation boundary:** this migration implements configuration storage only.
The existing agent/gateway still use their current runtime constants. Number
bindings, live configuration loading, greeting generation, API publication and
Telegram delivery remain PROF-03–05 work; editing these rows does not change a live
call. Do not enable a second carrier line on the assumption that storage implements
routing. Future consumers must validate template fields, enforce shared policy,
pin revisions per call, and apply system settings with explicit reload semantics.

Tests use temporary schemas on the existing Linux database and remove only those
schemas. They cover migration upgrade/repeat, seed repeat, retained calls/settings,
cross-scope rejection, immutable revisions, validation and mandatory safety flags:

```sh
uv run --frozen --env-file .local/dev.env pytest -q tests/test_database.py tests/test_profile_settings.py
```


## Planned per-agent settings transition

[ADR 0011](../../docs/ADR/0011-self-service-voice-agents.md) now assigns model and
runtime settings to each agent release. Migration 0003 remains unchanged as a
historical storage foundation; its global agent fields will be copied into per-agent
runtime revisions by a future additive migration. `platform_settings` will retain
only infrastructure, creation defaults and hard ceilings. These examples do not
yet implement that transition, workspace accounts, configured tools or actions.


## Prepared-release catalog example (AGP-02)

After migrations 0006/0007, `agent_catalog.sql` inserts an immutable initial engine
preset and model entry, with qualification **disabled**. Repeating it does not edit
an existing definition or reset operator state. The JSON is the expanded shared
`EnginePreset` contract with its canonical SHA-256 digest. It deliberately does not
create accounts, grants, prepared assets, releases or number bindings. The selected
model/preset requires complete consumer/performance qualification before enabling.

The management API now implements scoped drafts and immutable release preparation,
publication and rollback; see the [HTTP contract](../../services/app-api/README.md).
The historical 0003 settings example remains unchanged and does not drive live calls.


## Agent vocabulary authoring (AGP-03)

Supply these optional business fields in the authenticated agent draft API; publish
a new immutable release after validation. Do not UPDATE published manifests or copy
private worker environment values into every agent. Existing drafts/releases without
these fields default to an empty ASR dictionary; no database migration is needed.

```json
{
  "vocabulary": ["Example Product"],
  "asr_replacements": {"Example Prodakt": "Example Product"}
}
```

`vocabulary` supplies prompt context, while `asr_replacements` performs only approved
exact multiword spelling correction. It cannot map numbers or single-word replies.
These fields do not yet enable native routed calls; see the configuration audit.


## Native calibration revision (AGP-03)

`agent_calibration.sql` is an optional PostgreSQL development example for revision 2
of the initial preset/catalog model. It stores the complete operator-owned calibration
(including explicit partial hinting), starts disabled and is repeatable. It never
updates revision 1, enables routing, creates an account or changes active releases.
The historical `agent_catalog.sql` remains byte-for-byte unchanged; its omitted
calibration resolves to frozen historical v1 behavior without changing stored digests.

Apply examples only to the intended development schema after the existing migrations.
The calibration example is not an applied migration and does not certify the model.
Qualification and a new publication are required before selection/activation. New
preset revisions must store explicit calibration; never edit historical defaults
or synthesize an updated digest for an existing release. Users still select only
qualified models/business behavior and cannot supply technical calibration in drafts.


## Output budget revision (AGP-03)

agent_output.sql is a repeatable PostgreSQL development example for preset/model
revision 3. It includes explicit calibration and output limits (120 characters,
480 bytes per phrase, eight phrases, 4096 turn bytes), starts disabled and never
updates revisions 1/2 or enables a route. The catalog/calibration examples remain
unchanged. Apply only to an intended development schema after existing migrations;
this is not an automatically applied migration or qualification evidence. Operators
must qualify the full combination and publish a new release before activation.
New presets should declare calibration/output explicitly; historical omissions keep
frozen compatibility semantics and must never be retroactively rewritten.

## Scoped action delivery (AGP-05)

`action_delivery.sql` is a read-only PostgreSQL diagnostic after migration 0014.
It explicitly filters one synthetic workspace and returns bounded metadata/status
without credentials or selected output values. It creates no jobs or consent and
never retries an uncertain delivery. These scripts target the existing PostgreSQL
schema, not SQL Server T-SQL.

`action_retries.sql` inspects bounded retry metadata after migration 0015. Consent
must come from the exact reviewed owner API flow, never an initialization script.
The example performs no state reset and does not reveal the stored review text.

## MCP discovery storage example (AGP-07)

After migration 0020, `mcp_discovery.sql` demonstrates a disabled anonymous connection
inside an existing synthetic workspace. It requires a `workspace_id` psql variable
and ends with ROLLBACK. It stores no credentials, queues no network request and creates
no permission. Use authenticated connection/discovery APIs for real authoring; do
not bypass the worker by inserting a trusted-looking manifest. This is PostgreSQL,
not SQL Server T-SQL. [API and worker contract](../../services/app-api/README.md#mcp-connections-and-discovery-agp-07-backend-slice).

`mcp_tool_permissions.sql` is a read-only, workspace-filtered diagnostic after
migration 0021. It shows bounded review/grant identifiers, hashes and state without
credentials, fixed parameters or caller content. It never seeds approvals; operator
capability review and exact owner consent use their separate CLI/API paths. The
transaction ends with ROLLBACK and is safe to repeat in a synthetic workspace.


AGP-07 OAuth: `mcp-oauth-providers.json` is a synthetic preregistered public-client
registry template; replace all endpoints/client identity after provider registration.
Never put access tokens, refresh tokens or client secrets in it. Migration 0023 owns
schema creation; `mcp-oauth-status.sql` contains scoped, metadata-only PostgreSQL
inspection queries. Use the owner/session-bound API for connection creation, never
manual token inserts. See `services/app-api/README.md` for lifecycle/deployment gates.

## HTTP destinations and delivery status (AGP-08)

After migration 0024, `http-actions.sql` demonstrates a disabled anonymous target
in an existing synthetic workspace and bounded metadata-only delivery queries.
Pass `workspace_id` as a psql variable; the transaction ends with ROLLBACK. No
credential, permission, request, job, retry or lasting state is created. Actual
authoring/grants use the authenticated owner API. This is PostgreSQL 17, not T-SQL;
[contract](../../services/app-api/README.md#typed-http-post-call-actions-agp-08-candidate).

## Declared outputs (AGP-08)

`declared-outputs.sql` is a read-only PostgreSQL SELECT returning a synthetic agent
output definition and HTTP body mapping fragment. It creates no row, grant, release
or request. Merge definitions into an owned draft and mappings into the selected HTTP
action through the authenticated API; the demonstration `body_mapping_example` key
is not an accepted draft property. Existing JSON storage needs no new table migration.
Model descriptions are data goals, not execution permission. Publication and exact
output disclosure grants remain separate. [Contract](../../services/app-api/README.md#declared-post-call-outputs-agp-08-candidate).

## Post-call summary conditions

[`post-call-conditions.sql`](post-call-conditions.sql) is read-only PostgreSQL. It
returns three valid HTTP action examples (`answered`, `summary_ready`, `summary_failed`)
with a synthetic connection UUID. Replace that UUID with an owned connection and use
the normal save/review/grant/publication flow. Executing the SQL creates no connection,
grant, job or send. Non-default conditions require compatible v5/v4 consumers.

## Optional transcript sharing

[`transcript-sharing.sql`](transcript-sharing.sql) is a read-only PostgreSQL SELECT
returning a synthetic HTTP action with `bounded_text.v1` and paired text/status body
mappings. Use an owned connection and normal save/review/grant/prepare/publication;
executing the example creates no row, permission or request. No T-SQL engine is used.

## Call lifecycle conditions

[`call-lifecycle-actions.sql`](call-lifecycle-actions.sql) contains read-only PostgreSQL
examples for `no_answer` and `interrupted`, using synthetic connection IDs. Configure
through owned API drafts and exact grants; no SQL execution publishes, enqueues or
sends. Migration 0025 and compatible v7/v6 consumers are required before activation.


## Shared response experience (ADR 0014)

`response-experience.sql` returns example draft JSON and aggregate read-only
diagnostics. It does not alter stored profiles. Use the authenticated HTTP/MCP API
with version checking, prepare the waiting voice asset and publish a new release.
Timing, resource caps and Jev shadow mode remain platform-owned; no user engine
tuning or provider credential belongs in the example.
