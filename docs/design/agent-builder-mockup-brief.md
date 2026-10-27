# Agent builder visual proposal — 2026-10-26

Status: mockups approved by the owner on 2026-10-26; first functional slice
implemented and privately deployed. See [validation](../validation/web-preview-2026-10-26.md). The owner
selected Next.js and shadcn/ui and requested a very simple flat interface conveying
entry into the world of personal agents. Concurrent-call development is deferred
at the owner's request; the current live admission limit remains one.

Maps to AGP-06 / M2,M5, ADR 0011 and requirements §1/12/14–16. Apply Ponytail full.
Design method: pm-market-research:customer-journey-map. Persona assumptions below
come from this conversation, not user research. The images are conceptual mockups;
sample statuses and text are illustrative, never live operational evidence.

## Persona and outcome

A business owner wants a named Turkish voice assistant to answer an owned number,
collect useful messages and send a summary to the configured destination. They
should describe the assistant's job without tuning speech/inference internals.
First value: hear the prepared assistant introduce itself and then receive the
summary of an actual call after publication.

## Product journey

| Stage | Touchpoint and action | Expected feeling / question | Friction | Design response |
|---|---|---|---|---|
| Discover | Product introduction | Curious: what can my assistant do? | Abstract AI terminology | One concrete answering-and-summary example |
| Join | Native registration or sign-in | Cautious: is this my private space? | Account confusion | One email/password form and clear workspace identity |
| Create | Agent list, Create agent | Confident: where do I start? | Blank-page uncertainty | Short form for agent name, owner and instructions |
| Configure | Agent editor | In control: how should it behave? | Technical option overload | Business instructions first; qualified model/voice choices; engine tuning stays system-owned |
| Connect | Number and Telegram settings | Reassured: is everything ready? | Secret entry and number ownership | Write-only credentials, explicit verification and readiness feedback |
| Publish | Preview and publish review | Certain: what changes now? | Accidentally changing the live agent | Saved draft distinct from published version, affected number and action destination shown |
| Return | Call list and delivery state | Trust: did it do the job? | Silent failures | Call outcome, saved summary and delivery result shown separately |

Highest-priority moment of truth: preview → publish. A name or greeting change must
prepare fresh audio before readiness; saving a draft must not change the serving
release. The main drop-off risks are unclear publication state and confusing tool
permissions. Prefer plain Turkish labels and reveal detail only where it is needed.

## Visual direction

- Warm near-white canvas, white surfaces, charcoal type, muted sage/green accent.
- Flat appearance: no gradients, glass, large shadows, decorative charts or robots.
- Compact left navigation: Agentler, Numaralar, Aramalar, Bağlantılar; account below.
- Clear typography and generous whitespace; restrained 6–8 px corners and 1 px rules.
- Text plus icon for state; never color alone. Accessible contrast and focus states
  will be checked in implementation; generated images cannot establish accessibility.
- Primary action is contextual: create on the list, preview/publish on the editor.

## Mockup screens

1. **Agent list:** Kübra as the current published assistant; Berkcan as an illustrative
   unbound draft, not a claim that a second agent/number is deployed. Minimal rows/cards
   show owner, publication state and masked number. No invented usage analytics.
2. **Agent editor:** Identity and instructions in the main column. Model and EMA voice
   available as simple selectors. Separate sections distinguish conversational tools
   from deterministic post-call actions. A narrow preview area shows the prepared
   greeting and number/notification readiness. Draft save and publish remain distinct.

Approved first implementation slice: native sign-in/registration, agent list,
and editing the existing owner's agent through the scoped management API. Then wire
number/connection controls and asset preparation/publication. MCP and generic HTTP
builders remain later milestones; do not show them as working options. Frontend HTTP
deployment remains separate from all voice services and never enters the media path.

Component reference: https://ui.shadcn.com/ — use Sidebar, Button, Input, Textarea,
Tabs, Select, Badge, Separator and Dialog where appropriate. Final component choices,
version pins and responsive/mobile behavior belong to the approved implementation.

The owner approved the visual direction and both core layouts. The implementation
is separate from these conceptual images; partial feature scope and exact evidence
are recorded in the linked validation report.

## MCP extension within the approved layout (2026-10-26)

The candidate adds a separate MCP connection section to Connections and a reviewed
external-tool section to the existing Tools tab. Existing flat cards, native typed
fields and shadcn dialogs distinguish configuration, discovery, permission and
publication. Exact destinations and fixed/runtime values appear in the permission
dialog; remote metadata is always text. Historical permissions remain accessible
after tools are removed. A 390px viewport check covers the scrollable parameter
dialog and its apply action. OAuth and generic HTTP actions remain unimplemented
and are not presented as working choices. See
[validation and deployment limits](../validation/mcp-ui-2026-10-26.md).
