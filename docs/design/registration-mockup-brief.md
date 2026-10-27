# Registration journey visual proposal

Date: 2026-10-26. Status: approved by the owner on 2026-10-26; implemented and deployed to the private preview.
See [implementation evidence](../validation/registration-ui-2026-10-26.md).
Task: AGP-06, M2/M5, ADR 0011; requirements §1/12/14–16.

## Design and scope

The owner requested a registration mockup and a view of the current login.
The existing deployed login is captured anonymously in
[desktop](registration-mockup/current-login-desktop.png) and
[mobile](registration-mockup/current-login-mobile.png) screenshots.
These are actual product views, not proposed replacements. The password recovery
link currently describes administrator-assisted recovery, not an automated email flow.

The [interactive proposal](registration-mockup/index.html) uses the approved flat
sage visual direction. Its three steps are also available in the
[overview](registration-mockup/registration-overview.png). All people and agent
names in the proposal are synthetic. The prototype makes no API requests, saves
no credentials or browser storage, and creates no real account, agent or binding.

## Job stories and observable outcomes

1. When arriving for the first time, I want to create my personal account without
   configuring telephony, so I can explore the product immediately. Collect my
   name, email and password; distinguish the account holder from the agent identity.
   Match the existing minimum password length and provide a reveal control.
2. When starting my first agent, I want to name it and explain its role in everyday
   language, so I can get a useful draft without tuning inference parameters.
   Collect agent name, assistant owner and instructions; show an explicitly AI
   greeting as a text preview. Allow skipping this step with an honest empty state.
3. When my draft exists, I want to know what is needed before it answers calls,
   so I can complete setup confidently. Show voice preparation, number ownership/
   routing verification and optional notification configuration. Keep preparation,
   publication and binding separate. Show that a draft cannot yet answer calls.

The greeting preview updates from the entered names. Telegram remains optional and
requires configuring the destination and permission. No immediate number ownership,
publication, real audio generation or external delivery is implied by this mockup.

## Review evidence

Rendered using the pinned Playwright browser on the authorized Linux host.
Checks cover all three screens, password reveal/hide, synthetic form transitions,
optional skip/empty state, and 390px mobile horizontal overflow. Actual login capture
uses a fresh anonymous context and blocks non-GET API requests. No account writes
were performed. No voice services or deployed UI were changed.

During review, hash-only navigation was corrected to render the selected prototype
screen. Capture assertions were tightened to wait for the intended heading and
reload each mobile route before taking its screenshot. Product workflow acceptance
remains pending; prototype checks do not establish backend registration readiness.

Methods: PM job-stories and minimalist-ui skills, with Ponytail full review.
The approved journey is implemented; broader self-service workflow acceptance
remains separately tracked. Existing AGP-06/MCP roadmap remains unchanged.
