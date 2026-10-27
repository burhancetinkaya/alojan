# Private frontend preview — 2026-10-26

AGP-06 / M2,M5; ADR 0011; requirements §1/12/14–16. Owner approved the
agent-list/editor mockups and selected a private preview address. Ponytail full;
PM customer journey work informed the approved layout. No new carrier/capacity
acceptance is claimed.

## Implementation and review

Independent Next.js/shadcn frontend with native account flows, scoped list/create/
edit, text preview, guarded publication, number/connection controls and notification
metadata. The draft PUT retains fields not exposed in this first slice, including
vocabulary and existing post-call configuration. Live releases and number bindings
are never changed by draft save. The backend remains the permission authority.

Visual inspection found an excessively expanding textarea for 16,800-character
instructions and a wrong model-label field. Fixed both and added browser assertions.
Desktop/mobile screenshots were reviewed. Tabs match the flat proposal; the long
editor stays bounded and mobile layouts have no horizontal overflow.

## Linux evidence

- Exact npm lock installed; npm audit reported **0 vulnerabilities** at installation.
- TypeScript check and production webpack build **passed** on the primary Linux host.
- Ruff format/check for the browser harness **passed**.
- **7 real HTTPS browser scenarios passed in 9.3 seconds**, no retries/skips:
  secured login/logout; workspace isolation; long draft preservation and version
  conflict; creation/text preview/missing-audio publication block; CSRF and expired
  session; registration isolation; mobile layout/navigation; write-only connections
  and unverified-number routing protection (some scenarios combine related checks).
- Separate restricted-role test schema was removed; **zero production configuration
  writes and zero external sends** from these browser tests. No published test release
  or action job was created. The harness refuses a build pointing to the live API.
- Real owner account browser smoke **passed**: login, Kübra editor with its long
  existing instructions, selected model, existing Telegram target, all navigation
  and logout; **zero browser errors and zero agent/configuration mutations**.
- New web/TLS containers are healthy; private URL returns HTTP **200** through the
  Mac-to-Linux SSH forward. Management origin changed to match the private URL;
  its container alone was recreated. **Eight existing peer container identities and
  health were preserved**, including native voice, database and background workers.

Initial failures are retained honestly: a missing synthetic encryption-key fixture,
an ambiguous test alert selector and a reused-port check were fixed. TLS initially
failed because an unused Nginx temp path pointed at its read-only filesystem; all
temporary paths now point into bounded `/tmp` and the TLS service has a health check.
These failures did not restart voice services or mutate a serving agent release.

Image: `alojan-web:preview-20261026`,
`sha256:6e07b69c37a982fc1fefff7fbab214350703106439b9344e0a136f96c24e9f03`.
Node/browser/Nginx base image digests are pinned in source. Synthetic browser evidence
is retained privately in `.local/web-validation-958db5f45f7d40edaccae0377ce6d51a` on
Linux; private preview setup, rollback copy and sanitized owner smoke are retained
in `.local/web-preview-20261026`. Credentials, phone numbers and transcripts are
excluded from maintained evidence.

## Remaining acceptance

Private, self-signed TLS preview only; no public domain or trusted certificate,
email recovery or public registration rollout. Owner initial password was prepared
through audited operator reset, verified and saved privately; setup sessions revoked.
The owner should change it at first login.

Audio playback/preparation in the UI, post-call action creation/grants/output mapping,
full call detail, MCP/HTTP builders and full AGP-06 acceptance remain open. Existing
publication guards stay enforced. No new handset call, simultaneous-call test,
GPU benchmark, matched performance run or load/soak was run for this HTTP-only
change; preserving containers is not proof of latency equivalence.
