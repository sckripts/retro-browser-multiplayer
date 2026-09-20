# Milestone 4 Deterministic Runtime Launcher

Milestone 4 replaces the fixed ROM/core shell launch with a project-owned,
typed session-entrypoint. The browser-only client path and the accepted
Selkies/RetroArch boundary remain unchanged.

## Runtime contract

The launcher reads exactly two trusted inputs:

- /run/retro-session/runtime-spec.json, mounted read-only for one participant;
- /etc/retro-session/cores.yaml, copied into the immutable runtime image.

RuntimeSpec schema version 1 contains:

- UUID session and participant identifiers;
- stable user identifier and display name;
- canonical ROM path and expected SHA-256;
- approved core profile;
- Netplay role, host, and port;
- Selkies stream subfolder and fixed hd-720p60 display profile.
- an image-bounded persistence mode, defaulting to ephemeral for older proofs.

Models are strict, frozen, versioned, and reject unknown fields. JSON duplicate
keys, oversized documents, control characters, unsafe identifiers, invalid
Netplay role/host combinations, and unsafe stream subfolders fail closed.

## Validation and launch

Before RetroArch starts, session-entrypoint:

1. resolves the ROM beneath /run/roms and rejects traversal or symlink escape;
2. requires the ROM to be on a read-only mount and verifies its SHA-256;
3. resolves the selected core beneath /opt/libretro;
4. verifies the core and RetroArch executable hashes from the approved manifest;
5. confirms the fixed Selkies display/subfolder environment matches RuntimeSpec;
6. creates participant-specific state, system, core-option, and config paths, plus an
   ephemeral save path or verifies the exact writable host-save mount;
7. builds a direct argument vector for standalone, host, or client Netplay mode;
8. executes the verified RetroArch binary without a shell.

The runtime accepts no browser-provided command, argument vector, core path, or
unrestricted ROM path. It performs no dynamic core download.

Pydantic and PyYAML plus their transitive runtime packages are exactly pinned
with wheel hashes and installed into /opt/retro-session/python, separate from
the base image's managed Python packages.

## Proof specifications

The committed specs/milestone2.json and specs/milestone3.json preserve the
accepted local WebSocket and public WebRTC proofs. Both select the same approved
NES profile and external legal test ROM; their session IDs, participant IDs,
and stream subfolders differ.

These files are hand-authored proof inputs only. A later Session Manager will
produce per-participant RuntimeSpecs through the Runtime Agent boundary.

## Verification

Automated checks on 2026-09-01:

- 42 tests passed; one Windows symlink test skipped because the host did not
  grant symlink creation;
- Ruff lint and format checks passed;
- strict mypy passed for 25 source files;
- the retrobrowser/retro-session:milestone4 image built successfully;
- the Milestone 2 stack became healthy through the local Traefik edge;
- logs recorded the expected RuntimeSpec IDs and exact ROM, core, and frontend
  hashes;
- the running RetroArch process used only the generated configuration,
  allowlisted core, and canonical ROM.

Manual acceptance on the development PC confirmed normal 1280x720 video,
audio, and physical-controller input. A failed controller attempt from a
separate remote desktop session was diagnosed as host controller forwarding:
Edge in that remote session exposed no controllers even to a local-only
Gamepad API diagnostic. Direct testing on the development PC succeeded.

## Scope boundary

Milestone 4 does not add Session Manager orchestration, Runtime Agent container
lifecycle, RomM integration, or a second Netplay participant. Those remain
later milestones.
