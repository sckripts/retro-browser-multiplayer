# Milestone 13: Lobby and embedded player UX

Milestone 13 keeps RomM as the user-facing control plane and embeds each participant's existing Selkies route in the RomM v2 game page. It does not change session orchestration, runtime lifecycle, authentication, or network exposure.

## Implemented UX

- **Create session** opens a focused dialog for the friendly lobby name and a two-to-four-player capacity.
- Creating a session or joining an open session proceeds directly to the player after runtime startup.
- Lobby rows show the friendly name, current capacity, and participant display names.
- **Open player** restores the embedded player when an active participant closes it without leaving.
- The in-app player fills the RomM viewport and shows the lobby and game names, a loading or online state, local controller assignment, fullscreen control, and **Leave**. Selkies' own fullscreen action remains available inside the stream.
- The Selkies client remains same-origin under `/stream/{participant_id}/`. Its participant token is placed only in the iframe URL, and the iframe uses `referrerpolicy="no-referrer"`.
- The fixed 1280×720 gaming stream locks Selkies CSS scaling on so HiDPI browsers stretch the canvas to the available player area while preserving its aspect ratio.
- While the player is open, RomM's global navigation gamepad handling is suspended so controller input reaches Selkies.

The two-to-four-player choices match the currently approved core manifest. Session Manager remains authoritative and rejects a capacity above a resolved core profile's limit.

## Security boundaries

The browser still receives only the participant-scoped launch response defined in Milestone 9. The UI receives no ROM path, core path, private address, Netplay port, TURN secret, container identifier, or Selkies master token. Runtime Agent remains the only custom Docker client.

Selkies upstream `main` was reviewed at `1d9b67be6f9c695f187a0509a3c1d3b3e204807b`. Its current documentation continues to support embedding the HTML5 client and browser gamepad input. The project retains its pinned runtime rather than following that branch.

## Automated evidence

The RomM fork includes focused component coverage for configurable lobby creation, same-page scoped stream embedding, and leave cleanup. Runtime Agent coverage verifies that CSS scaling is locked on for every fixed-resolution participant stream. The full frontend suite passes 904 tests. TypeScript, focused ESLint, locale completeness and ordering, and the production build also pass. The rebuilt local topology passes the Milestone 12 service-boundary verifier with RomM, authentik, Session Manager, Runtime Agent, and their private dependencies healthy.

## Acceptance record

Milestone 13 was manually accepted on 2026-09-07. The user confirmed a properly embedded responsive player, visible footer controls, fullscreen entry and return with controls retained, and successful exit, join, and leave behavior. All remaining manual checks were reported clear. Milestone 14 remains the public two-network test.
