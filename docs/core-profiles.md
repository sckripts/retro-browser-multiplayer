# Core Profiles

See `docs/adding-emulators.md` for the supported extension workflow and the planning
template. The manifest is authoritative image metadata, but Session Manager currently
duplicates its executable fields in `StaticCoreRegistry`; both must be updated together.

Core selection is data-driven. A profile will record platform, exact core artifact and SHA-256, source commit, license, maximum players, controller topology, and Netplay validation status.

The runtime currently contains pinned Mesen, bsnes, and BlastEm profiles. `nes-milestone2` uses
Mesen 0.9.9. `snes-bsnes` uses bsnes commit
`260f5234410d0899f8446882c63d17f891b686e0` and owns the SNES multitap port mapping
(`input_libretro_device_p2 = 257`) as trusted manifest data. It supports four lobby
participants and is `validated` after the Milestone 15 public acceptance matrix
passed. `genesis-blastem` uses BlastEm commit
`b4d75247ebad8852fd9bc385b423df704c6c5af5` and is limited to two players because
the current libretro adapter exposes and polls only two controller ports. Its public
two-player Netplay acceptance matrix passed in Milestone 16.

Snes9x and Genesis Plus GX carry non-commercial terms and are excluded from the default
candidate set. A core is never downloaded inside a participant runtime.
