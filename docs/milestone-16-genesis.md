# Milestone 16 Genesis / Mega Drive profile

Milestone 16 adds the pinned `genesis-blastem` profile to the accepted public stack.
The runtime builds BlastEm from commit
`b4d75247ebad8852fd9bc385b423df704c6c5af5`, verifies the source archive and compiled
amd64 artifact, and never downloads a core at runtime. Generic orchestration selects
the profile only from RomM's trusted `genesis` platform slug.
The build fixes Python hash seeding for generated sources and omits the core's default
LTO so independent builds reproduce the pinned artifact checksum.

The profile is intentionally two-player. BlastEm's standalone emulator implements Sega
and EA multitaps, but the selected commit's libretro adapter exposes only two six-button
pad choices, leaves `retro_set_controller_port_device` empty, and polls only ports 0 and
1. Advertising more than two browser players would create participants slots whose input
the core cannot consume. Multitap support therefore does not apply to this profile and
requires a future upstream adapter change or a separately reviewed core decision.

No ROM or BIOS is supplied by this repository. Start with a legally obtained Genesis /
Mega Drive ROM that supports two players. `GenesisRomPath` is a host Windows path to an
existing `.md`, `.bin`, or `.gen` file; quote it when the path contains spaces. An
already-managed file under `<M10_DOCKER_ROM_ROOT>\genesis\roms` is accepted on rerun:

```powershell
.\infra\scripts\acceptance\milestone16-start.ps1 -GenesisRomPath C:\path\to\game.md -NoBrowser
.\infra\scripts\acceptance\milestone16-verify.ps1
```

In RomM, scan the Genesis platform so the copied file receives a numeric RomM ID. Do not
record or commit the ROM, saves, launch URLs, session tokens, TURN credentials, or
container environment.

## Acceptance checklist

1. Two distinct authenticated Internet users create and join a two-player Genesis
   lobby. Confirm synchronized video/audio and that each controller affects only its
   expected player slot.
2. Exercise the full six-button mapping required by the selected game, including Start,
   A/B/C, and X/Y/Z where supported.
3. Close and reopen each embedded player. Confirm reconnect preserves the participant
   and controller slot without creating another runtime.
4. In browser WebRTC diagnostics, record the selected ICE candidate type. At least one
   pass must use a `relay` candidate and show a bound coturn channel.
5. Have the non-owner leave and rejoin. Confirm slot 2 is reassigned, the old stream
   token is rejected, and the old runtime and route disappear.
6. Have the owner close the lobby. Confirm every token is rejected, all runtimes and
   dynamic routes disappear, and the lobby is no longer discoverable.
7. During the active lobby, run:

```powershell
.\infra\scripts\acceptance\milestone16-verify.ps1 -RequireRomMUsers -RequireGenesisRuntime
```

8. After cleanup, run:

```powershell
.\infra\scripts\acceptance\milestone16-verify.ps1 -RequireRomMUsers -RequireClean
```

## Acceptance observations

- 2026-09-13: two authenticated players loaded the Genesis game and remained in sync.
  Both participant runtimes were healthy, used `genesis-blastem`, and verified the
  pinned BlastEm artifact. Controller isolation passed: each controller affected only
  its assigned player slot, including while both players supplied input. The complete
  supported button test also passed for both players, including the six-button mapping.
  Both players then disconnected and rejoined the embedded game successfully while
  retaining their assigned slots. Browser WebRTC diagnostics subsequently confirmed a
  selected `relay` candidate while coturn recorded the active allocation. Explicit
  leave/rejoin then worked for both players. The original Runtime Agent records,
  containers, and dynamic route labels were removed, and two fresh healthy
  `genesis-blastem` runtimes passed active verification after rejoin. The retired stream
  URL was explicitly rejected. Finally, the owner closed the lobby: the other player
  disconnected, the lobby disappeared, and both current stream URLs were rejected.
  The strict `-RequireRomMUsers -RequireClean` verifier passed with zero runtimes and
  clean dynamic routing.

The complete public two-player browser/controller/Netplay matrix passed on 2026-09-13,
and the profile is `validated`.

Stop the public topology while preserving databases, library files, and ignored
credentials:

```powershell
.\infra\scripts\acceptance\milestone16-stop.ps1
```
