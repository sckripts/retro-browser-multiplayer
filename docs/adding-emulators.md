# Adding an emulator profile

An emulator addition is a server-owned compatibility profile, not a browser-supplied
core or path. The browser selects a game through RomM; Session Manager maps the trusted
RomM platform to an approved profile; Runtime Agent can launch only the configured,
digest-qualified retro-session image.

## Current model

The current image contains RetroArch plus Mesen, bsnes, and BlastEm. Profile metadata
is recorded in `images/retro-session/manifests/cores.yaml`, while Session Manager's
`StaticCoreRegistry` currently repeats the executable profile fields. A new supported
core therefore requires both locations to change and remain covered by tests.

Runtime Agent currently approves exactly one retro-session image digest. In the near
term, add approved cores to that image and publish a new digest. A future move to one
image per system should first add a server-owned digest allowlist and an ADR; a browser
must never provide an image, core, or filesystem path.

Use `docs/examples/emulator-profile.example.yaml` as a planning worksheet. It is
deliberately outside the runtime manifest and is not loaded by the application.

## Profile checklist

1. Select the canonical RomM platform slug and add only necessary aliases to
   `infra/romm/config.production.yml`.
2. Review the frontend/core license and redistribution terms. Exclude artifacts whose
   terms are incompatible with the intended distribution.
3. Pin the upstream source commit, source archive SHA-256, build dependencies, and
   resulting artifact SHA-256. Runtime downloads are not permitted.
4. Add a deterministic build stage to `images/retro-session/Dockerfile`, copy only the
   resulting core artifact, and keep the final image free of ROM and BIOS content.
5. Add the complete profile to `images/retro-session/manifests/cores.yaml` with
   `netplay_status: planned` until acceptance is complete.
6. Add the matching server-owned `CoreProfile` to Session Manager. Validate the maximum
   players, controller devices, topology, and platform mapping.
7. Add unit and integration tests for profile lookup, launch arguments, player limits,
   controller ports, and artifact verification.
8. Confirm that every participant uses the same RetroArch version, core artifact, core
   options, and content hash. The core must support serialization and deterministic
   execution well enough for RetroArch Netplay.
9. Run real two-or-more-client acceptance across separate networks: create/join,
   controller assignment, reconnect, join/leave, TURN relay, cleanup, and save
   persistence. Exercise the declared maximum player count where practical.
10. Record the tested matrix and only then mark Netplay `validated`, rebuild the
    retro-session image, and update the approved production digest.

## Systems that need more platform work

BIOS-dependent systems are not ready to add. They first need a trusted, operator-owned
BIOS root and a narrow read-only mount contract in Runtime Agent. BIOS files must never
enter Git, container images, logs, examples, or browser-provided input.

Disc, playlist, and multi-file systems also need a trusted content-set resolver between
RomM and Session Manager. The current provider resolves one library file. Do not work
around that boundary by accepting arbitrary browser paths.

The next useful internal refactor is a single versioned core catalog consumed by the
image verification tests and Session Manager. That removes the current duplicated
metadata without changing component ownership.
