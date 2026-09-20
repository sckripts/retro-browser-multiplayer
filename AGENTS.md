# Project Rules

Read `PROJECT.md` and `SESSION_HANDOFF.md` before changing code.

The browser-only Internet client is a hard requirement.

RomM owns library UI and user-facing control-plane integration. authentik owns authentication. Session Manager owns lobby/session orchestration. Runtime Agent owns privileged container lifecycle. Selkies owns browser streaming. RetroArch owns emulation and Netplay. coturn owns STUN/TURN.

Do not move responsibilities across these boundaries without an ADR.

Never expose the Docker socket to Session Manager or public services. Never accept an arbitrary ROM path from a browser. Never copy large upstream source files into this repository. Never copy RomM AGPL code into the independently licensed Session Manager. Use an upstream API, configuration, or derived image before creating replacement code.

Do not place ROMs or BIOS images in Git, Docker images, tests, CI artifacts, or examples. Pin runtime dependencies and container images.

Before implementing:

1. Read `PROJECT.md`.
2. Inspect existing code.
3. Inspect relevant current upstream documentation/source.
4. Summarize existing behavior.
5. Identify the smallest correct change.
6. Add or update tests.
7. Implement.
8. Run checks.
9. Update docs or an ADR when architecture changes.

Do not perform unrelated refactoring or silently change architecture.

A task is complete only when tests and lint/type checks pass, security boundaries remain intact, documentation is current, no secrets or ROM content are added, and the final report says what changed and what remains.
