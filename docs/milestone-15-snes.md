# Milestone 15 SNES profile

Milestone 15 adds the pinned `snes-bsnes` profile to the accepted public stack. The
runtime builds bsnes from commit `260f5234410d0899f8446882c63d17f891b686e0`, verifies
the source archive and compiled amd64 artifact, and never downloads a core at runtime.
The profile owns its SNES multitap topology: RetroArch port 2 uses libretro device 257.
Generic orchestration still selects a profile only from RomM's trusted platform slug.

The runtime limits OpenMP to two workers, matching Runtime Agent's two-CPU container
quota. This is required for bsnes: without the bound, libgomp observes every host CPU,
creates an oversized busy worker pool, and can starve emulation and Netplay startup.

No ROM or BIOS is supplied by this repository. Start with a legally obtained SNES ROM
that supports the player count being tested. `SnesRomPath` is a host Windows path to an
existing `.sfc` or `.smc` file; quote it when the path contains spaces. An already-managed
file under `<M10_DOCKER_ROM_ROOT>\snes\roms` is also accepted on a rerun:

```powershell
.\infra\scripts\acceptance\milestone15-start.ps1 -SnesRomPath C:\path\to\game.sfc `
    -UserCEmail player3@example.com -UserDEmail player4@example.com -NoBrowser
.\infra\scripts\acceptance\milestone15-verify.ps1
```

In RomM, scan the SNES platform so the copied file receives a numeric RomM ID. Use a
multitap-compatible title for the three- and four-player passes. Do not record or commit
the ROM, saves, launch URLs, session tokens, TURN credentials, or container environment.

## Acceptance checklist

1. Two distinct authenticated Internet users create and join a two-player SNES lobby.
   Confirm synchronized video/audio and that each controller affects only its expected
   player slot.
2. Close and reopen each embedded player. Confirm reconnect preserves the participant
   and controller slot without creating another runtime.
3. Repeat with three users, then four users, on a multitap-compatible game. Confirm the
   lobby reports slots 1–4 and each physical controller affects only the matching game
   player. Record the game and whether it supports three-player and four-player modes.
4. In browser WebRTC diagnostics, record the chosen ICE candidate type. At least one
   pass must use a `relay` candidate and show a bound coturn channel.
5. Have a non-owner leave and rejoin. Confirm the released slot is assigned correctly,
   the old stream token is rejected, and the old runtime and route disappear.
6. Have the owner close the lobby. Confirm every token is rejected, all runtimes and
   dynamic routes disappear, and the lobby is no longer discoverable.
7. During an active SNES lobby, run:

```powershell
.\infra\scripts\acceptance\milestone15-verify.ps1 -RequireRomMUsers -RequireSnesRuntime
```

8. After cleanup, run:

```powershell
.\infra\scripts\acceptance\milestone15-verify.ps1 -RequireRomMUsers -RequireClean
```

The profile is `validated` by the completed two-to-four-player
browser/controller/network matrix below.

## Acceptance observations

- 2026-09-08: four simultaneous Internet participants successfully played through the
  `snes-bsnes` multitap profile after bounding OpenMP to the two-CPU runtime quota.
  Runtime and host logs confirmed four healthy containers on the corrected image and
  deterministic Netplay assignments for players 1–4. Observed join pings were 37–48 ms.
- 2026-09-13: Player 2 closed and reopened the embedded player successfully. Runtime
  inspection confirmed the same participant and container retained Netplay slot 2,
  with exactly four healthy session containers and no duplicate runtime.
- 2026-09-13: Player 3 completed the same reconnect pass. The original healthy runtime
  retained the same participant and Netplay slot 3; the session remained at four
  containers with no duplicate.
- 2026-09-13: Player 4 completed the reconnect pass. The original healthy runtime kept
  the same participant and Netplay slot 4, and no fifth container was created.
- 2026-09-13: Player 1 completed the host reconnect pass without closing the lobby. The
  original host runtime retained Netplay slot 1 while all four runtimes stayed healthy.
  Reconnect preservation is therefore confirmed for players 1–4.
- 2026-09-13: browser WebRTC diagnostics reported `relay` as the selected ICE candidate
  type, confirming the public stream used the configured TURN relay path.
- 2026-09-13: in a fresh two-player lobby, Player 2 explicitly left while the host
  remained healthy. The client container, Runtime Agent record, and dynamic route were
  removed; revisiting the saved pre-leave stream URL returned `404 Not Found` and did
  not reopen the stream. Player 2 then rejoined with a fresh participant and healthy
  runtime, reclaimed Netplay slot 2 at 32 ms, and synchronized with the unchanged host.
- 2026-09-13: Player 1 closed the lobby. Player 2 disconnected, both runtime containers
  and Runtime Agent records were removed, both dynamic routes disappeared, and both
  saved stream URLs returned `404 Not Found`. The required `-RequireRomMUsers
  -RequireClean` post-clean verification passed.

Stop the public topology while preserving local databases, library files, and ignored
credentials:

```powershell
.\infra\scripts\acceptance\milestone15-stop.ps1
```
