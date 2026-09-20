# Milestone 17 — Persistence

Milestone 17 deliberately persists only battery-backed save data owned by the lobby
host. This includes normal SRAM and core-managed memory-card equivalents that use the
libretro save directory. A stable, opaque namespace is derived from the authenticated
host user ID, selected core profile, and trusted ROM SHA-256. Display names, email
addresses, ROM paths, and browser-provided values are not used in save paths.

Solo browser play uses RomM's separate, user-owned save model. In Milestone 19,
EmulatorJS automatically uploads changed cartridge SRAM through RomM's authenticated
`/api/saves` API after the bytes are stable across two save ticks. An existing personal
save is loaded when that player launches the game again. “Save & Quit” remains the
immediate explicit sync path; the automatic path follows EmulatorJS's configured System
Save interval. Solo saves remain private to the authenticated RomM user and do not share
the Runtime Agent namespace used by multiplayer hosts.

## Policy

- The host's save is authoritative for a multiplayer session. RetroArch Netplay gives
  joining clients the host's canonical serialized machine state.
- RomM owns solo-play saves and states; Runtime Agent owns multiplayer persistence.
  Neither service receives or derives the other's storage path.
- Guests use per-runtime ephemeral save directories. Their exit-time SRAM cannot
  overwrite personal data or the host's durable save.
- Runtime Agent is the only component that derives or mounts a save directory. The
  browser and RomM never receive its host path or opaque key.
- Runtime Agent permits exactly one managed runtime to mount a given save namespace.
  A second simultaneous lobby for the same user, ROM digest, and core profile fails
  closed until the first runtime is removed. This includes stopped-but-not-removed
  containers and remains enforceable after a Runtime Agent restart through labels.
- Save states are session-ephemeral and auto-save/auto-load states remain disabled.
  Loading a state can replace SRAM, so `block_sram_overwrite` is enabled as defense in
  depth. Save-state portability and multiplayer state ownership are deferred.
- RetroArch preferences and core options remain image-owned and immutable;
  `config_save_on_exit` stays disabled. Per-user preference persistence is deferred.
- SRAM is flushed every ten seconds through RetroArch's private stdin `SAVE_FILES`
  command and again during a normal shutdown. Upstream deliberately disables its
  background autosave worker during Netplay; the image-owned FIFO invokes the command
  on RetroArch's main thread instead of reading core memory concurrently with rollback.
  The network command interface remains disabled. A host or machine failure can still
  lose the most recent interval, but cannot create a concurrent writer through the
  supported lifecycle.

The implementation follows RetroArch's documented `savefile_directory` setting,
`SAVE_FILES` command, and libretro's `RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY` contract.
See the upstream [RetroArch configuration](https://github.com/libretro/RetroArch/blob/master/retroarch.cfg),
[command contract](https://github.com/libretro/RetroArch/blob/master/command.h),
[libretro API](https://github.com/libretro/RetroArch/blob/master/libretro-common/include/libretro.h),
and [Netplay design](https://docs.libretro.com/development/retroarch/netplay/).

## Storage and operations

The start helper creates an ignored operator-owned directory at
`local/runtime-agent-m17/saves` and records its absolute path in the ignored
`.env.milestone14`. The directory is mounted into Runtime Agent, not Session Manager.
Each participant runtime receives either one generated host save mount at
`/run/retro-saves` or no durable save mount. ROMs remain read-only and the Docker socket
remains exclusive to Runtime Agent.

On native Linux, Runtime Agent owns each opaque namespace as fixed runtime UID 1000 with
mode `0700`. Docker Desktop's drvfs bind filesystem cannot use that ownership model, so
the explicitly configured compatibility mode uses `0777` on the opaque leaf directory
only. Its parent save root is not mounted into participant runtimes, and each live host
receives only its own leaf.

Back up the save root only when no participant runtime is active, or use a filesystem
snapshot with crash-consistent semantics. Restore only while the stack is stopped.
Deleting a namespace permanently deletes that user's save for that ROM/core pairing;
there is intentionally no browser delete endpoint in this milestone.

Start or upgrade the accepted public stack:

```powershell
.\infra\scripts\acceptance\milestone17-start.ps1 -NoBrowser
.\infra\scripts\acceptance\milestone17-verify.ps1 -RequireRomMUsers -RequireClean
```

Stopping the stack does not delete the save root:

```powershell
.\infra\scripts\acceptance\milestone17-stop.ps1
```

## Live acceptance

Use only an operator-supplied game with battery-backed saving. Do not record the ROM,
save contents, stream URLs, tokens, or credentials.

1. Create a two-player lobby. Verify
   `milestone17-verify.ps1 -RequireRomMUsers -RequirePersistentHost` passes with exactly
   one durable mount, belonging to the host, and no durable guest mount.
2. Create recognizable in-game progress, wait at least ten seconds, then have the owner
   close the lobby. Require clean runtime and route removal.
3. Create a new lobby as the same user with the same game. Confirm the saved progress
   loads and the guest receives the host's canonical state after joining.
4. While that host is active, try to create another lobby as the same user for the same
   game. Confirm startup fails and no second persistent runtime or mount appears.
5. Close the first lobby, then confirm a new lobby can start and retain the save.
6. Confirm leave/rejoin, browser reconnect, TURN relay, and owner-close cleanup still
   pass. Finish with `-RequireRomMUsers -RequireClean`.

Milestone 17 was accepted on 2026-09-13 after all browser checks below passed.

## Evidence

- 2026-09-13: the seven-file Compose model rendered with one private writable save
  root on Runtime Agent and no Docker socket on Session Manager.
- 2026-09-13: a real Session Manager → RomM resolver → Runtime Agent host launch became
  healthy with one exact `/run/retro-saves` mount and an opaque 64-character save key.
  A simultaneous same-user/same-game launch was rejected and the managed runtime count
  stayed at one. Owner close removed the proof runtime and route; the strict clean
  verifier passed. No ROM or save content was recorded, and the proof produced no save
  file.
- 2026-09-13: final Ruff lint/format, strict mypy for 55 source files, 177 tests plus
  one existing Windows symlink skip, PowerShell parsing, Compose rendering, embedded
  core hash checks, and the clean public verifier passed.
- 2026-09-13: initial browser acceptance exposed that upstream disables the configured
  autosave interval while Netplay is enabled; the first `DPG`/sword marker produced no
  durable file and did not restore. The implementation now uses the private stdin
  command dispatcher for periodic main-thread flushes.
- 2026-09-13: the retest proved the command dispatcher was issuing `SAVE_FILES`, Mesen
  exposed 8 KiB of save RAM, and RetroArch selected the correct durable path, but drvfs
  rejected file creation because its opaque leaf was root-owned `0755`. Docker Desktop
  compatibility now makes only that isolated leaf writable.
- 2026-09-13: browser retest restored the recognizable `DPG`/sword marker through
  repeated owner-close and fresh-lobby cycles, including a runtime upgrade between
  save and restore. The guest received the host's canonical state. A concurrent
  same-user/same-game launch returned HTTP `409` without creating another runtime.
  Guest leave/rejoin, guest and host browser reconnect, synchronized gameplay, and a
  selected TURN `relay` candidate passed. Both owner-close checks removed the guest,
  all managed runtimes, and dynamic routes; the final strict clean verifier passed.
