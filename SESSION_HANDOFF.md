# Session Handoff

Last updated: 2026-09-20

Read `AGENTS.md` and `PROJECT.md` before acting. This file records verified local state
and decisions so a fresh session can continue without relying on chat history. Treat
live process state and upstream versions as time-sensitive and re-check them.

## Current outcome

Production packaging now has a single repository-root `compose.yml`, stable production
configuration, and lifecycle scripts under `infra/scripts/production`. Historical
milestone Compose models and scripts are isolated under `acceptance/`. The deployment
procedure and emulator-profile extension path are documented. Static Compose rendering,
PowerShell parsing, Ruff, formatting, mypy, the full automated test suite, the public
content audit, and a candidate-file Gitleaks scan pass. The consolidated stack has not
yet had a live production-host deployment. Custom registry artifacts are not published,
and backup/restore plus rotation drills remain operator release gates.

Milestones 0 through 18 are complete. Milestone 11 passed automated, live Docker, and
two-user repeated browser-login acceptance on 2026-09-06 and is documented in
`docs/milestone-11-authentication.md`.

Milestone 12 passed automated checks, live Docker verification, and two-user browser
acceptance on 2026-09-07. From the RomM game page, one authenticated user created the
session, a second authenticated user joined it, both opened separately authorized
Selkies players, and both active streams displayed synchronized gameplay responding to
controller input. The local browser origin is `http://localhost:8096`; localhost is
required for Selkies' secure-context check unless trusted HTTPS is configured. Do not
use the former HTTP `arcade.127.0.0.1.nip.io` URL.

RomM changes remain only in the separate AGPL fork at `<separate-romm-worktree>` on
`feat/external-multiplayer-provider`; no RomM source is copied here.

Milestone 14 passed its public two-user remote MVP on 2026-09-08, including emailed
authentication, WebRTC relay evidence, synchronized video/audio/controllers, guest
leave and rejoin, uninterrupted host play, owner close, and strict clean-state
verification. The public stack remains running with no participant runtimes.

Milestone 15 passed its public SNES acceptance on 2026-09-13. The accepted public stack
remains running with no participant runtimes; ignored credentials, library state, and
named identity/database volumes are preserved.

Milestone 16 passed its public Genesis acceptance on 2026-09-13. Milestone 17 passed
its host-authoritative persistence acceptance later that day. The public stack remains
running with the Milestone 18 observability overlay and no participant runtimes.

Milestone 18 passed automated, live control-plane, and two-browser observability
acceptance on 2026-09-14. The public stack remains healthy with its observability
overlay and no participant runtimes, dynamic runtime routes, or metrics targets.

Milestone 19 began on 2026-09-15. Its first production-hardening slice is in progress:
quota enforcement, pseudonymous lifecycle audit events, explicit runtime resource
settings, edge rate/request controls, report-only CSP review, pinned security scans,
and CycloneDX SBOM generation are implemented and deployed. Experimental per-user solo
cartridge-save synchronization through RomM is implemented but disabled: live testing
proved a successful non-empty server upload and notification, but clean relaunch did
not restore the save. EmulatorJS browser-local saves are the accepted interim behavior;
the bounded save route remains tested. End-to-end solo server-save restoration,
backup/restore, rotation, incident-response, and remaining hardening work are not yet
complete; see `docs/milestone-19-production-hardening.md`.

Milestone 19 live validation resumed on 2026-09-19. The cross-game per-user runtime
quota passed with a conflict response and no second runtime. The four-session global
quota remains explicitly deferred until five distinct authenticated identities are
available; its automated tests are not a substitute for that live acceptance check.
Lobby/stream/controller/TURN, all three edge body limits, and report-only CSP review
also passed. CSP is origin-specific; RomM permits only the blob and WebAssembly
capabilities required by its pinned EmulatorJS runtime, while authentik keeps the
narrower policy. authentik static assets use a separate bounded rate limit after a
parallel chunk load exposed HTTP 429 responses. Native-play slowdown seen over Remote
Desktop was confirmed as a client test-environment artifact: save-sync-off, CSP-off,
and prior-image comparisons did not change it, while direct local play was normal.
Lifecycle audit validation also passed against eight live records: required fields and
pseudonymous actor formats were present, and no credential, raw identity, stream URL,
ROM path, or network fields were emitted.
The final clean-state acceptance check found zero active lobbies and no participant
runtime, and `milestone19-verify.ps1 -RequireRomMUsers -RequireClean` passed end to end.

## Repository state

- Workspace: `<repository-root>`
- Private repository: `https://github.com/YOUR_GITHUB_OWNER/retro-browser-multiplayer`
- Branch: `main`
- Latest accepted implementation: Milestone 18; this handoff is part of its
  implementation commit
- Milestone 6 parent/handoff commit: `44d45ad` (`docs: prepare milestone 6 handoff`)
- Milestone 5 implementation commit: `874439d` (`feat: complete milestone 5 netplay proof`)
- Milestone 4 implementation commit: `e9760c6`
- Milestone 3 implementation commit: `9e3dcc7`
- Milestone 1 implementation commit: `864b113`
- Last verified remote GitHub Actions run: commit `f04cabe`, successful run
  `33339563903`; Milestones 3 through 18 have not been pushed yet
- Local `main` is expected to be seventeen commits ahead of `origin/main` after the
  Milestone 18 commit
- Expected worktree at handoff: clean after the Milestone 18 commit
- Ignored local state: `.env.milestone1`, `.env.milestone2`, `.env.milestone3`,
  `.env.milestone5`, `.env.milestone5-public`,
  `.env.milestone6`, `.env.milestone8`, `.env.milestone9`, `.env.milestone10`,
  `.env.milestone11`, `.env.milestone12`, `.env.milestone14`, preserved Milestone 11,
  12, and 14 named
  identity/database volumes, generated Runtime Agent
  state under `local/runtime-agent/`, `local/runtime-agent-m8/`, and
  `local/runtime-agent-m9/`, `local/runtime-agent-m10/`,
  `local/runtime-agent-m12/`, `local/runtime-agent-m17/`,
  `local/runtime-agent-m18/`, staged Milestone 12 library content under
  `local/milestone12-library/`,
  `local/test-roms/super-tilt-bro-2.6.nes`, trusted certificate copies under
  `local/milestone3-cert/`, and generated Traefik routes
- GitHub CLI account: `YOUR_GITHUB_OWNER`, HTTPS Git operations authenticated
- Ignored official reference clones: `upstream-reference/selkies` and
  `upstream-reference/retroarch-m17`

The separate RomM fork exists at `<separate-romm-worktree>`:

- branch `feat/external-multiplayer-provider`
- accepted commit: `50d1e6c94` (`feat(multiplayer): add external session provider`)
- `origin`: `https://github.com/YOUR_GITHUB_OWNER/romm.git`
- `upstream`: `https://github.com/rommapp/romm.git`
- locally modified to backport upstream RomM automatic save synchronization; no RomM
  source is copied into the RetroBrowser repository

Never copy its AGPL source into this repository.

## Development environment

- Windows host with PowerShell 7 and WSL 2
- Git `2.55.0.windows.3`
- GitHub CLI `2.98.0`
- Python `3.14.7`; repository virtual environment is `.venv`
- Docker client/server `29.0.1`; Docker Desktop Linux engine is running at handoff
- NVIDIA GeForce RTX 4060 Ti, Windows driver `591.86`

Milestone 8 acceptance ended with no managed runtime, harness container, or proof
network. Recheck live Docker state rather than assuming it remains empty.
The Milestone 5 token-bearing local QR was deleted after acceptance. Milestone 1 can be
started with:

- browser URL: `http://127.0.0.1:8088/stream/m1/`
- Traefik is the only service with a published host port
- Selkies is private on the internal Docker network
- start/open: `.\infra\scripts\acceptance\milestone1-start.ps1`
- forced CPU mode: `.\infra\scripts\acceptance\milestone1-start.ps1 -CpuFallback`
- stop: `.\infra\scripts\acceptance\milestone1-stop.ps1`

`.env.milestone1` contains generated local master/session tokens. It is ignored. Do not
print, commit, or reuse those values as a product credential design.

## Milestone 1 implementation

Important files:

- `infra/compose/acceptance/compose.milestone1.yml`
- `infra/compose/acceptance/compose.milestone1.gpu.yml`
- `infra/traefik/static/milestone1.yml`
- `infra/traefik/dynamic/milestone1.yml`
- `infra/scripts/acceptance/milestone1-start.ps1`
- `infra/scripts/acceptance/milestone1-stop.ps1`
- `tests/integration/test_milestone1_config.py`
- `docs/milestone-1-selkies-proof.md`
- `UPSTREAMS.md`
- `THIRD_PARTY_NOTICES.md`

Pinned runtime artifacts:

- Selkies source commit: `e6d04050955523a4e026e4dceef7c35096150fa1`
- Selkies image index: `sha256:07ba642f431915158a7f4cec69d46303704816dced17d4ee95bd34b2a1ef23eb`
- Selkies amd64 manifest: `sha256:0bfcce1fa30024a8eb34e2504a74e1fb18f4c1424d92c1b6ad6282fb3b1ae87b`
- Traefik: `v3.7.12`
- Traefik image index: `sha256:9c2a54d87f76f5c2f5f2682c68394af92fb12c0a2686798d6462a3f84bd78eaf`

Milestone 1 originally required an unreleased snapshot because Selkies `v1.6.2` lacked
secure mode and native subfolder routing. The pin was refreshed on 2026-09-21 to the
versioned `2.0.0rc1` release above after the old rolling-tag digest was removed upstream.
Re-check the official release and runtime contract before changing this pin.

The stack uses Selkies secure mode, native `/stream/m1` subfolder routing, same-origin
WebSockets, fixed 1280x720 at 60 fps, stereo Opus audio, keyboard/mouse/gamepad input,
and the unprivileged Joystick Interposer. Clipboard, file transfer, commands, sharing,
collaboration, microphone, webcam, second display, dual-mode switching, and embedded
TURN are disabled. Traefik uses only read-only file configuration and never receives the
Docker socket.

## Milestone 1 evidence and runtime quirks

Automated and browser checks proved:

- proxied health and subfolder page returned HTTP 200
- proxy root returned HTTP 404
- unauthenticated token-table update returned HTTP 401
- a real Edge client authenticated and opened the data WebSocket
- display locked to 1280x720 at 60 fps
- video pipeline ran through x264
- stereo Opus pipeline started and an FFmpeg-generated tone was audible
- keyboard input reached QTerminal
- Bluetooth Xbox controller appeared in the Selkies overlay
- `/dev/input/js0` emitted controller event bytes inside QTerminal
- an incognito client without a token opened no streaming WebSocket

NVIDIA is visible in the container through `nvidia-smi`, and Selkies detects NVENC, but
Docker Desktop's WSL GPU bridge lacks `cuGraphicsEGLRegisterImage`. NVENC initialization
therefore fails and upstream correctly falls back to x264. This is a host/runtime
constraint, not a functional failure. Re-test the NVIDIA zero-copy path on native Linux.

The reliable controller verification command inside streamed QTerminal is:

```bash
JS_LOG=1 od -v -An -w8 -t x1 /dev/input/js0
```

Do **not** wrap it in `stdbuf`: that interfered with the Selkies `LD_PRELOAD` interposer
and exposed the placeholder character device directly, producing `Permission denied`.
QTerminal itself correctly inherited `SELKIES_INTERPOSER` and the interposer libraries.

The audio verification command is:

```bash
ffplay -nodisp -autoexit -f lavfi "sine=frequency=440:duration=3"
```

## Milestone 2 implementation and evidence

Important files:

- `images/retro-session/Dockerfile`
- `images/retro-session/config/retroarch.cfg`
- `images/retro-session/entrypoint/run`
- `images/retro-session/manifests/cores.yaml`
- `infra/compose/acceptance/compose.milestone2.yml`
- `infra/scripts/acceptance/milestone2-start.ps1`
- `tools/test-roms/fetch-super-tilt-bro.ps1`
- `tests/integration/test_milestone2_config.py`
- `docs/milestone-2-retroarch-proof.md`

Pinned artifacts:

- RetroArch 1.22.2 commit `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`,
  binary SHA-256 `e7b3a9611e0d7bc429aac2cf92cafb7eeea3f730afaa7b0534805a01512ab73c`
- Mesen 0.9.9 commit `f3a18bed018fa853627e0e15d02a3f2ba4960222`, core
  SHA-256 `1c3d682cdc8a47658235663ed92d39146f2c09ffcb565ed212c9260fb44d55e8`
- Super Tilt Bro 2.6, WTFPL-2.0, external ROM SHA-256
  `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d`

The runtime launches the one fixed read-only ROM path directly, validates mount and
artifact hashes, waits for Selkies initialization before fixing X to 1280x720, and uses
Mesen NTSC at 60.10 fps with 48 kHz audio. Selkies' optional apps runner is removed.
Health requires both the Selkies API and a live RetroArch process. The start helper
refreshes Traefik after runtime recreation so the proxy never retains an old backend IP.

Manual acceptance proved direct launch, video, audible audio, Xbox D-pad and left-stick
input, correct uncropped 1280x720 presentation, fullscreen enter/exit, continued play
after Escape, and clean shutdown. On Docker Desktop the accepted encoder remains x264
software H.264 because CUDA-EGL interop is unavailable. Re-test NVENC on native Linux.

Start and stop:

```powershell
.\infra\scripts\acceptance\milestone2-start.ps1 -CpuFallback
.\infra\scripts\acceptance\milestone2-stop.ps1
```

## Milestone 3 implementation and evidence

Important files:

- `infra/compose/acceptance/compose.public-test.yml` and its Milestone 3 transport/GPU overrides
- `infra/traefik/static/milestone3.yml`
- `infra/traefik/dynamic/milestone3.template.yml`
- `infra/scripts/acceptance/milestone3-start.ps1`
- `infra/scripts/acceptance/milestone3-stop.ps1`
- `tests/integration/test_milestone3_config.py`
- `docs/milestone-3-public-webrtc-proof.md`

The profile uses HTTPS-only Traefik, WebRTC-only Selkies, private TURN REST credential
issuance, and public coturn listeners. Selkies has no host port. TURN REST has no public
port. Neither receives the Docker socket. coturn uses one-hour HMAC credentials and a
bounded UDP relay range. The accepted public hostname is `arcade.example.test`.

The ARCADE-HOST site router has no NAT reflection. Selkies therefore shares a dedicated TURN
network with coturn, where the public TURN hostname is a coturn network alias; browsers
still resolve public DNS. Re-test all external state rather than assuming it persists:

- ARCADE-HOST NAT/security forwarding: TCP 80, 443, 3478, 5349 and UDP 3478, 49160-49200
- Windows Firewall group: `RetroBrowser Milestone 3`
- example Docker host LAN address: `192.0.2.17`
- trusted certificate copies: `local/milestone3-cert/arcade-fullchain.pem` and
  `local/milestone3-cert/arcade-privkey.pem`; current certificate expires 2026-11-30

Public acceptance proved:

- TURN/UDP relay gameplay on LTE and a second off-site hotspot
- video, audio, USB-attached controller input, and same-session reconnect
- TURN/TCP and TURN/TLS connectivity, with lag/choppy media on LTE
- direct ICE failure across combined Docker/site NAT, making TURN/UDP the default

The pinned profile configures 1280x720, 60 FPS, and 8000 kbps. The Selkies client did
not emit its expected statistics CSV during acceptance, so observed numeric bitrate/FPS
remain unavailable and are documented rather than inferred.

Start and stop the accepted default:

```powershell
.\infra\scripts\acceptance\milestone3-start.ps1 -Transport turn-udp -CpuFallback
.\infra\scripts\acceptance\milestone3-stop.ps1
```

## Milestone 4 implementation and evidence

The project-owned `session-entrypoint` accepts a typed runtime spec with
session/participant IDs, approved ROM path and expected hash, approved core profile,
player name, Netplay role/host/port, Selkies configuration, and fixed display profile.
Resolve ROMs only inside an approved root, verify ROM/core hashes, reject arbitrary
commands and shell interpolation, generate per-session RetroArch configuration, and do
not download cores at runtime.

RuntimeSpec v1 is strict, frozen, and rejects extra fields, duplicate JSON keys,
oversized specs, path/symlink escapes, bad hashes, arbitrary commands, and invalid
Netplay role/host combinations. The launcher verifies the read-only ROM mount and
pinned RetroArch/core artifacts, generates participant-specific configuration and
storage paths, and directly executes a list argument vector without a shell.

Hand-authored Milestone 2 and 3 RuntimeSpecs preserve both accepted proof paths. The
runtime image built successfully, emitted the expected IDs and artifact hashes, and
became healthy behind the local edge. Manual local testing confirmed normal video,
audio, and controller input. Controllers were absent only through a separate remote
desktop session because Edge there exposed no host gamepads; direct host testing passed.

## Milestone 5 implementation and evidence

Important files:

- `images/retro-session/specs/milestone5-host.json`
- `images/retro-session/specs/milestone5-client.json`
- `infra/compose/acceptance/compose.milestone5.yml`
- `infra/compose/acceptance/compose.milestone5.public.yml`
- `infra/scripts/acceptance/milestone5-start.ps1`
- `infra/scripts/acceptance/milestone5-public-start.ps1`
- `tests/integration/test_milestone5_config.py`
- `docs/milestone-5-netplay-proof.md`

The fixed harness launches one host and one client from the same runtime image with
identical RetroArch/core/ROM hashes. The client explicitly connects to `retro-host` on
private internal `retro-net`; TCP 55435 is not published. Host and client have separate
internal stream networks, HTTPS routes, master tokens, and scoped controller tokens.
Traefik is the only web service with host ports, TURN REST remains private, and no
service receives the Docker socket.

Manual acceptance proved synchronized local play and then two independent public
browser participants: player 1 in Edge on the development PC and player 2 on an LTE
phone with a USB controller. Both HTTPS/WebRTC sessions completed ICE through coturn,
video and audio passed, and each controller operated only its participant. Opening one
scoped token in multiple tabs correctly supersedes the older connection, so use one
browser profile/device per participant.

For same-site testing, ARCADE-HOST internal DNS resolves `arcade.example.test` to
`192.168.2.17`. Because coturn advertises the public relay address, the accepted site
also has U-turn destination NAT plus symmetric source DIPP for TCP/UDP 3478, TCP 5349,
and UDP 49160-49200. The off-site forwarding rules remain unchanged.

The public stop helper removed both runtimes, edge, TURN services, and all proof
networks. The token-bearing QR was deleted. `.env.milestone5`,
`.env.milestone5-public`, the legal test ROM, certificates, and generated Traefik route
remain ignored local state. No milestone stack is running.

## Milestone 6 implementation and evidence

Important files:

- `services/runtime-agent/src/retro_runtime/service.py`
- `services/runtime-agent/src/retro_runtime/api/server.py`
- `services/runtime-agent/src/retro_runtime/docker/client.py`
- `services/runtime-agent/src/retro_runtime/routes/provider.py`
- `services/runtime-agent/Dockerfile`
- `infra/compose/acceptance/compose.milestone6.yml`
- `infra/scripts/acceptance/milestone6-start.ps1`
- `infra/scripts/acceptance/milestone6-stop.ps1`
- `services/runtime-agent/tests/test_runtime_service.py`
- `tests/integration/test_milestone6_config.py`
- `docs/milestone-6-runtime-agent.md`

The private HTTP/JSON API listens only on a mode-0660 UNIX socket and implements
create, inspect, stop, remove, managed list, and health. Runtime creation independently
validates the digest-qualified image, named networks, ROM root/hash, fixed GPU profile,
and approved user-data root. Commands, entrypoints, arbitrary environment, mounts,
labels, host ports, and Docker flags are not representable. Names, ownership labels,
limits, security options, health checks, RuntimeSpec, and Traefik routes are generated.

Only Runtime Agent receives `/var/run/docker.sock`. The proof caller has only the UNIX
control socket and no network. Runtime Agent also has no network or published port.
Native Linux uses fixed UID/GID 1000 ownership. The Docker Desktop proof explicitly
uses pre-provisioned Windows user-data directories because Windows bind mounts reject
Linux `chown`; that setting is admin configuration and is absent from the create API.

Live Docker acceptance created the Milestone 5 participant through the UNIX API and
waited for RetroArch/Selkies health. A duplicate request returned the identical
container ID. Listing reported `orphaned: false`; inspection showed an unprivileged
digest-approved runtime, no host port bindings, only the two private allowlisted
networks, and project ownership labels. API deletion removed both container and route.
Final shutdown left no managed runtime or Milestone 6 network.

Start and remove the fixed proof:

```powershell
.\infra\scripts\acceptance\milestone6-start.ps1
.\infra\scripts\acceptance\milestone6-stop.ps1
```

## Milestone 7 implementation

Important files:

- `services/session-manager/src/retro_sessions/api/app.py`
- `services/session-manager/src/retro_sessions/models/domain.py`
- `services/session-manager/src/retro_sessions/models/state.py`
- `services/session-manager/src/retro_sessions/services/session_service.py`
- `services/session-manager/src/retro_sessions/repositories/valkey.py`
- `docs/milestone-7-session-manager.md`

The private FastAPI v1 API implements create, discover, get, join, leave, close,
health, and readiness. All v1 calls require a 32-character-or-longer bearer service
credential; actor mutations additionally consume stable identity assertion headers.

The provider-independent service resolves only numeric RomM IDs through a trusted
`RomMProvider`, selects approved profiles through `CoreRegistry`, and never accepts
ROM/core paths, Docker options, private addresses, or stream credentials. Runtime,
stream, route, RomM, repository, and core-registry interfaces remain separate.

The fake path opens a lobby with the owner in slot 1. Join/leave/close are idempotent,
capacity and owner authorization are enforced, and due sessions close deterministically.
Friendly names are normalized display data while UUIDs remain authoritative.

Automated acceptance proves:

- create, discovery, get, join, leave, and close;
- expiration, capacity enforcement, and duplicate operations;
- owner authorization and friendly-name validation;
- private service authentication and actor assertion requirements;
- Valkey JSON round trips, TTL assignment, readiness, and optimistic revisions.

Real Runtime Agent calls, runtime readiness, startup cleanup, Netplay connection, and
private host handling remain Milestone 8. Selkies token orchestration remains Milestone
9. No live infrastructure or RomM source was added for Milestone 7.

## Milestone 8 implementation and evidence

Important files:

- `services/session-manager/src/retro_sessions/providers/execution/runtime_agent.py`
- `services/session-manager/src/retro_sessions/services/session_service.py`
- `services/session-manager/src/retro_sessions/__main__.py`
- `services/session-manager/Dockerfile`
- `services/runtime-agent/src/retro_runtime/service.py`
- `infra/compose/acceptance/compose.milestone8.yml`
- `infra/scripts/acceptance/milestone8-start.ps1`
- `infra/scripts/acceptance/milestone8-create-and-join.ps1`
- `infra/scripts/acceptance/milestone8-stop.ps1`
- `tests/integration/test_milestone8_config.py`
- `docs/milestone-8-runtime-orchestration.md`

Session Manager now drives `ALLOCATING`, `STARTING`, and `ACTIVE` around real Runtime
Agent calls. It waits up to 180 seconds for the host and 45 seconds for the client,
polling Docker lifecycle and health through the UNIX-socket adapter. Failed starts call
idempotent removal and persist `ERROR`. Leave, close, expiration, and the stop helper
also remove runtimes through Runtime Agent.

The Runtime Agent healthcheck requires RetroArch, Selkies, and Netplay socket state.
Host readiness requires TCP `LISTEN`; client readiness requires TCP `ESTABLISHED`.
Both `/proc/net/tcp` and `/proc/net/tcp6` are checked because live acceptance found the
host listener in the IPv6 table. Runtime Agent exposes health separately from container
lifecycle state.

Private client hostnames are derived only in `LocalRuntimeAgentProvider` from the host
participant UUID. They are absent from Session state and API responses. The provider
uses a server-only HMAC secret to derive a stable per-participant Selkies master token
for Runtime Agent create idempotency. It is never placed in RuntimeSpec or returned;
controller-token provisioning and browser launch data remain Milestone 9.

The local harness uses Valkey 9.1.2 Alpine pinned at image index
`sha256:a174b894902bd3367e330d47cc2054367dc4917701776aaf336f41d83b65ec7a`
and a hash-pinned Session Manager image. Only Runtime Agent has the Docker socket.
Session Manager is unprivileged and private, with only Valkey networking and the shared
mode-0660 control socket. Traefik has only a localhost port and file-provider routes.

Live Docker Desktop acceptance proved two API calls created two healthy runtimes with
empty host-port bindings and a private established Netplay connection. A duplicate join
created no third runtime. False-negative startup attempts timed out and cleaned up.
Final shutdown removed both runtimes through Runtime Agent and left no harness container
or proof network.

Start, exercise, and stop:

```powershell
.\infra\scripts\acceptance\milestone8-start.ps1
.\infra\scripts\acceptance\milestone8-create-and-join.ps1
.\infra\scripts\acceptance\milestone8-stop.ps1
```

## Milestone 9 implementation and evidence

Important files:

- `services/session-manager/src/retro_sessions/providers/streaming/selkies.py`
- `services/session-manager/src/retro_sessions/security/tokens.py`
- `services/session-manager/src/retro_sessions/services/session_service.py`
- `services/session-manager/src/retro_sessions/api/app.py`
- `infra/compose/acceptance/compose.milestone9.yml`
- `infra/scripts/acceptance/milestone9-start.ps1`
- `infra/scripts/acceptance/milestone9-verify.ps1`
- `infra/scripts/acceptance/milestone9-stop.ps1`
- `tests/integration/test_milestone9_config.py`
- `docs/milestone-9-selkies-orchestration.md`

Session Manager now reaches each runtime's Selkies token API only on the private stream
network. It preserves the Milestone 8 master-token derivation for Runtime Agent create
idempotency and derives a separate domain-separated controller token. After runtime
readiness it installs exactly one controller token for local gamepad slot 1. Raw tokens
are absent from Session/Valkey state and normal API responses.

`POST /v1/sessions/{id}/launch` returns path, scoped token, and lease expiry only when
the stable asserted actor matches an active participant. The owner-only kick endpoint
retires non-owner participants. Leave, kick, close, expiration, and failed startup all
attempt Selkies token-table replacement with `{}` before runtime removal. If Selkies is
already unreachable, removal remains the fail-closed disconnect.

The local harness attaches Session Manager to control and private stream networks but
publishes no Session Manager port. An edge-only non-internal ingress network allows
Docker Desktop to publish Traefik on localhost while the runtime stream and Netplay
networks remain internal. Only Runtime Agent holds the Docker socket and it retains
`network_mode: none`.

Live acceptance proved tokenless gameplay WebSocket HTTP `401`, scoped-token HTTP
`101`, non-participant launch denial, leave retirement, empty runtime port bindings,
and clean shutdown. The harness intentionally remains local WebSockets; public dynamic
WebRTC/TURN sessions are still deferred. Current Selkies upstream `main` was checked at
`f95210a33041b2311a9e912f54f9b75203fefcdb`; the pinned token API contract is unchanged.

Start, verify, and stop:

```powershell
.\infra\scripts\acceptance\milestone9-start.ps1
.\infra\scripts\acceptance\milestone9-verify.ps1
.\infra\scripts\acceptance\milestone9-stop.ps1
```

## Milestone 10 implementation and evidence

Important files:

- `services/session-manager/src/retro_sessions/services/session_service.py`
- `services/session-manager/src/retro_sessions/api/app.py`
- `services/session-manager/src/retro_sessions/providers/execution/runtime_agent.py`
- `services/runtime-agent/src/retro_runtime/service.py`
- `services/runtime-agent/src/retro_runtime/routes/provider.py`
- `images/retro-session/Dockerfile`
- `infra/compose/acceptance/compose.milestone10.yml`
- `infra/scripts/acceptance/milestone10-start.ps1`
- `infra/scripts/acceptance/milestone10-verify.ps1`
- `infra/scripts/acceptance/milestone10-stop.ps1`
- `tests/integration/test_milestone10_config.py`
- `docs/milestone-10-session-lifecycle.md`

Active participants now renew both their heartbeat and a bounded lobby lease through
the actor-scoped heartbeat endpoint. The default 45-second participant idle timeout,
120-second renewable lobby lease, and four-hour absolute maximum lifetime are
server-only configuration. Successful runtime readiness refreshes the initial lease so
a slow bounded startup does not consume browser activity time.

A FastAPI lifespan worker reconciles before readiness and then sweeps every ten seconds.
It closes expired or abandoned-owner sessions, retires idle guests, inspects active
runtime health, closes failed-host sessions, and retires failed guests. Revocation still
precedes Runtime Agent removal. Runtime Agent now lists managed runtimes through the
existing UNIX socket, removes a generated route even when its container is already
missing, and removes route files without corresponding managed containers at startup.
Only Runtime Agent retains Docker socket access.

Restart policy is deliberately fail closed: Session Manager startup closes all retained
non-closed Valkey sessions with `manager_restarted`, removes their runtimes, and removes
any additional managed orphan runtimes. Gameplay is interrupted. Live session
restoration is not implemented.

The participant image now applies its existing fail-closed s6 finish policy to Selkies
as well as RetroArch. Runtime health changes from 30 to three post-start failures at a
five-second interval, while retaining the 45-second startup grace period.

Live Docker Desktop acceptance on 2026-09-05 proved browser-heartbeat abandonment,
RetroArch exit, Selkies exit, whole participant-container kill, and hard Session Manager
kill/restart all converge to the expected closed reason. Every case ended with no
managed runtime and no generated route. The stop helper removed the harness and all
proof networks. `.env.milestone10`, legal test ROM, generated user data, and routes
remain ignored local state.

Start, verify, and stop:

```powershell
.\infra\scripts\acceptance\milestone10-start.ps1
.\infra\scripts\acceptance\milestone10-verify.ps1
.\infra\scripts\acceptance\milestone10-stop.ps1
```

## Milestone 11 implementation and evidence

Important files:

- `infra/compose/acceptance/compose.milestone11.yml`
- `infra/authentik/blueprints/milestone11-romm.yaml`
- `infra/scripts/acceptance/milestone11-start.ps1`
- `infra/scripts/acceptance/milestone11-verify.ps1`
- `infra/scripts/acceptance/milestone11-stop.ps1`
- `tests/integration/test_milestone11_config.py`
- `docs/milestone-11-authentication.md`
- `docs/authentication.md`

The local identity harness pins authentik 2026.8.1, PostgreSQL 16.10 Alpine, RomM
5.2.0, MariaDB 11.8.3, and Mailpit 1.27.8 by multi-platform digest. Database services
remain private. Only authentik, RomM, and the test SMTP UI publish loopback ports, and
no service receives the Docker socket. The library is an empty named volume; no ROM or
BIOS content is present.

The authentik blueprint creates a confidential authorization-code OIDC provider with
an exact callback, per-provider issuer, signed tokens, hashed stable subjects, shown to
RomM as `sub`, and a custom verified-email claim. Its ten-minute email magic-link flow
uses enumeration-resistant identification. The start helper generates credentials only
in ignored `.env.milestone11`, preserves the emergency `akadmin` path, and provisions
two distinct verified-email test identities. RomM OIDC autologin remains disabled so
the RomM local-login path stays reachable for an emergency administrator created or
retained during initial setup.

Automated live validation proved six healthy services, successful blueprint loading,
the expected discovery issuer, one exact callback, issuer reachability from inside
RomM, distinct authentik UIDs, and a state- and nonce-bound RomM authorization-code
redirect. RomM 5.2.0 does not add PKCE for this confidential client; that upstream
behavior is documented rather than hidden.

Browser acceptance on 2026-09-06 used two distinct users in separate browser profiles.
Each authenticated through an email link and repeated OIDC login. The strict verifier
then found exactly two RomM rows whose usernames had authentik's expected 64-character
hashed-subject form; neither repeat created a duplicate row. The stack was stopped
without deleting its named proof volumes.

RomM 5.2.0 still locates returning OIDC users by email. A stable email retains the same
RomM database ID, but changing email may create a second account. Any correction belongs
in the separate AGPL fork and is outside the minimal Milestone 12 extension.

## Milestone 12 implementation and evidence

Important Retro Browser files:

- `services/session-manager/src/retro_sessions/providers/romm/http.py`
- `services/session-manager/src/retro_sessions/services/session_service.py`
- `images/retro-session/session_entrypoint/models.py`
- `infra/compose/acceptance/compose.milestone12.yml`
- `infra/traefik/dynamic/milestone12-romm.yml`
- `infra/scripts/acceptance/milestone12-start.ps1`
- `infra/scripts/acceptance/milestone12-verify.ps1`
- `tests/integration/test_milestone12_config.py`
- `docs/milestone-12-romm-integration.md`

Important files in the separate RomM fork:

- `backend/adapters/services/multiplayer.py`
- `backend/endpoints/multiplayer.py`
- `backend/endpoints/responses/multiplayer.py`
- `frontend/src/services/api/multiplayer.ts`
- `frontend/src/v2/components/GameDetails/MultiplayerSessions.vue`

RomM exposes a generic external multiplayer provider boundary. Its browser endpoints
return only lobby data and participant-scoped launch data. A separate constant-token
endpoint resolves the selected numeric RomM ID to a confined relative library path and
digest for Session Manager. Browser requests cannot supply ROM paths, runtime options,
private addresses, Netplay details, Docker settings, or Selkies master credentials.
Runtime Agent remains the only Docker-socket holder.

The Session Manager maps RomM's 64-character stable OIDC subjects to bounded
session-local RetroArch player names, serializes create/join lifecycle transitions,
allows a failed guest to retry, and keeps full open rooms discoverable so participant
heartbeats and **Open player** remain available. The RomM v2 game page implements
create, discover, join, leave, close, heartbeat, and pop-up player launch without
absorbing orchestration responsibilities.

The local overlay publishes RomM and dynamic Selkies routes through one Traefik origin
at `http://localhost:8096`. The localhost origin satisfies the browser secure-context
requirement for local testing. The start helper reconciles authentik's exact callback
when the origin changes and aligns Runtime Agent's generated Selkies origin allowlist.
LAN and public deployments still require trusted HTTPS.

Live acceptance on 2026-09-07 used two authenticated users in separate browser profiles.
One created the session, the second joined, both opened separately authorized Selkies
players, and both active screens showed synchronized gameplay responding to controller
input. The live verifier also proved the private RomM resolver, matching authentik
callback, and absence of Docker-socket access in Session Manager.

## Verification baseline

These checks pass with the Milestone 12 implementation:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe services
.\.venv\Scripts\python.exe -m pytest
```

Result on 2026-09-07: Ruff and formatting clean, strict mypy clean for 55 service source
files, and 139 tests passed with the existing Windows-only symlink test skipped.
The merged three-file Milestone 12 Compose model passes `docker compose config --quiet`.

In the RomM fork, the focused provider tests pass (7), endpoint security-boundary tests
pass (6), and targeted mypy with skipped imports passes for the three new backend
modules. The full frontend suite passes 901 tests; all locale namespaces match and
sort; ESLint passes for the changed frontend modules; and both `vue-tsc --noEmit` and
the production Vite build pass in `retrobrowser/romm-dev:milestone12`. The Vite build
retains existing warnings from the PDF dependency and an existing deep selector.

## Milestone 13 accepted

Important files:

- `<separate-romm-worktree>\frontend\src\v2\components\GameDetails\MultiplayerSessions.vue`
- `<separate-romm-worktree>\frontend\src\v2\components\GameDetails\MultiplayerSessions.test.ts`
- `<separate-romm-worktree>\frontend\src\v2\lib\overlays\RDialog\RDialog.vue`
- `<separate-romm-worktree>\frontend\src\v2\lib\overlays\RDialog\RDialog.stories.ts`
- `<separate-romm-worktree>\frontend\src\locales\*\multiplayer.json`
- `docs/milestone-13-lobby-player-ux.md`

RomM's v2 game page now uses a create dialog with a selectable two-to-four-player
capacity. Create and join proceed directly into a same-origin embedded Selkies player;
an active participant may close and reopen that player without leaving the lobby. The
player surface fills the RomM viewport and shows the friendly lobby and game names,
loading or online state, local controller assignment, fullscreen, and leave controls.
Selkies' own fullscreen action remains available inside the stream. Global RomM gamepad
navigation is suspended only while the player is open.

The fixed 1280x720 gaming profile locks Selkies CSS scaling on so the canvas fills its
available player area on HiDPI browsers while preserving aspect ratio. The fullscreen
dialog uses border-box viewport height so its RomM footer remains visible.

The participant-scoped launch contract is unchanged. The iframe retains a no-referrer
policy, and no infrastructure details or administrative token are exposed. Selkies
upstream `main` was reviewed at `1d9b67be6f9c695f187a0509a3c1d3b3e204807b`.

Focused component tests pass (3), the full frontend suite passes 904 tests, strict
TypeScript and focused ESLint pass, all 18 locale sets are complete and sorted, and the
production build passes with the existing upstream PDF and deep-selector warnings.
The rebuilt local topology passes the Milestone 12 service-boundary verifier and remains
running at `http://localhost:8096`.

Manual acceptance completed on 2026-09-07. The user confirmed the embedded player
scales responsively, the RomM footer controls remain visible, fullscreen entry and return
preserve those controls, and exit, join, and leave behavior all pass. All remaining
Milestone 13 manual checks were reported clear.

## Suggested fresh-session request

```text
Read AGENTS.md, PROJECT.md, and SESSION_HANDOFF.md. Milestone 15 SNES support is accepted
and committed, and the public stack is running without participant runtimes. Begin
Milestone 16 Genesis / Mega Drive. Keep all RomM AGPL changes in <separate-romm-worktree>.
```

## Milestone 14 accepted

Milestone 14 began on 2026-09-07 and was accepted on 2026-09-08. The public overlay, TLS edge configuration,
start/verify/stop helpers, integration tests, and two-network acceptance runbook are
implemented. Runtime Agent now supports a fail-closed, server-selected WebRTC profile
with private TURN REST configuration and can constrain generated Selkies routes to the
public RomM hostname. WebSocket mode remains the default for prior milestones. The
coturn shared secret is never placed in a participant runtime; runtimes receive only
the private TURN REST API key and unique username used to mint one-hour credentials.

Public DNS, a certificate covering the public RomM and authentik names, authenticated
SMTP, administrator email, and two tester addresses are configured in the ignored
environment. The stack is running, and no participant runtime remains after acceptance.

Static checks currently pass: Ruff, Ruff formatting, strict mypy for 55 service files,
148 tests passed with the existing Windows-only symlink test skipped, and the four-file
Compose model rendered successfully with safe dummy values. The pinned Traefik 3.7.12
process also loaded the static and rendered dynamic configuration without an error.
Start or verify with:

```powershell
.\infra\scripts\acceptance\milestone14-start.ps1 -NoBrowser
.\infra\scripts\acceptance\milestone14-verify.ps1
```

The complete manual checklist in `docs/milestone-14-remote-mvp.md` passed. A defect
found during cleanup was fixed in Session Manager: leave now selects the user's active
participant after a prior leave/rejoin rather than returning early on the stale `LEFT`
record. Live retesting passed both guest leave paths while the host stayed active, the
owner close removed the final runtime, and the strict verifier passed with
`-RequireRomMUsers -RequireClean`.

## Milestone 15 complete

Milestone 15 now has a pinned `snes-bsnes` implementation and acceptance harness. The
runtime builds bsnes-libretro commit
`260f5234410d0899f8446882c63d17f891b686e0` from a hash-verified source archive; the
reproducible amd64 core artifact hash is
`41f08812445a8ff08fbe3e9faf891ae685452d524e6569df15dbd90fa040d399`. The image-owned
profile enables the SNES multitap through bounded controller-port data rather than an
SNES conditional in orchestration. Session Manager's static registry now resolves the
existing NES profile or the four-player SNES profile from RomM's trusted platform slug.

The focused profile/registry tests pass and the final runtime image builds with both
artifact checks. `infra/scripts/acceptance/milestone15-start.ps1` upgrades the accepted public
Compose project in place, imports an operator-selected `.sfc`/`.smc` beneath the SNES
library root, and provisions two additional authenticated testers. The verifier and
`docs/milestone-15-snes.md` cover two-, three-, and four-player slot mapping, multitap,
TURN relay, reconnect, leave/rejoin, and cleanup.

Live public acceptance passed on 2026-09-13 with two- through four-player slot mapping,
four-player gameplay, reconnect preservation for all four players, a selected TURN
`relay` candidate, non-owner leave/rejoin with old-route rejection, owner-close cleanup,
and the strict `-RequireRomMUsers -RequireClean` verification. The SNES manifest
`netplay_status` is now `validated`. No SNES ROM or tester credentials are stored in Git.

Two acceptance-time defects are fixed: bsnes OpenMP workers are bounded to the runtime's
two-CPU quota to prevent startup/Netplay starvation, and the start helper accepts an
already-managed SNES ROM on rerun without copying it onto itself. The verifier forwards
optional switches to the Milestone 14 verifier with named-parameter splatting.

Operational note: the accepted stack retains Milestone 14's 45-second participant idle
timeout and 10-second cleanup interval. Idle means a missing browser control-plane
heartbeat, not missing controller input. If the owner's device sleeps or its browser
suspends the RomM page, the lobby closes as abandoned. Consider a deliberate timeout
increase in a future milestone; do not silently weaken cleanup policy.

Final local checks: Ruff and formatting clean, strict mypy clean for 49 source files,
161 tests passed with the existing Windows-only symlink test skipped, the five-file
Compose model rendered successfully, the pinned RetroArch/bsnes artifact checks passed,
and `milestone15-verify.ps1 -RequireRomMUsers -RequireClean` passed against the live
public stack. Runtime Agent and Session Manager are healthy with zero participant
runtimes.

## Milestone 16 complete

Milestone 16 began on 2026-09-13. The implementation selects BlastEm commit
`b4d75247ebad8852fd9bc385b423df704c6c5af5` under GPL-3.0-or-later, with source
archive SHA-256 `c1c216d39ab5d1401abd6da02938cb4b40fd52a033045ec49a25890b2dcc042d`
and reproducible amd64 artifact SHA-256
`52044324adbbda37a36c4d916dfb3bb677bf1952444c48a64d78f1c472991714`.
The build fixes `PYTHONHASHSEED=0` for generated CPU sources and disables BlastEm's
nondeterministic default LTO (`OPT=-O2`); independent rebuilds produced the pinned hash.

The `genesis-blastem` profile is deliberately capped at two players. Although the
standalone emulator supports Sega and EA multitaps, the selected libretro adapter has
an empty controller-device callback and polls only ports 0 and 1. The manifest,
Session Manager registry, Compose overlay, start/verify/stop helpers, integration tests,
dependency notices, and acceptance runbook are implemented. Public two-player
Netplay, controller, reconnect, TURN relay, leave/rejoin, and cleanup acceptance are
recorded below.

Automated checks are green: Ruff lint/format, strict mypy for 59 source files, 165
tests with one existing Windows-only symlink skip, PowerShell AST parsing, the six-file
Compose model, all four embedded image artifact hashes, BlastEm runtime linkage and
manifest loading, and the live Milestone 15 clean-baseline verifier. The new image is
available locally as `retrobrowser/retro-session:milestone16`.

Live acceptance began on 2026-09-13. The public stack is running the Milestone 16
Session Manager and Runtime Agent, and two authenticated players loaded the Genesis
game in sync. Both participant runtimes were healthy, selected `genesis-blastem`, and
verified the pinned BlastEm artifact. The active-runtime verifier was corrected to
join Docker's log-line array before applying whole-log regular expressions. Controller
isolation subsequently passed, including simultaneous input without crossed or
duplicated slots. The supported six-button mapping then passed for both players.
Both players subsequently disconnected and rejoined the embedded game successfully
while retaining their assigned slots. Browser WebRTC diagnostics then confirmed a
selected `relay` candidate while coturn recorded the active allocation. Explicit
participant leave/rejoin then worked for both players. The two original Runtime Agent
records, containers, and dynamic route labels were gone; two fresh healthy
`genesis-blastem` runtimes passed active verification, and the retired stream URL was
explicitly rejected. The owner then closed the lobby; the other player disconnected,
the lobby was no longer discoverable, and both current stream URLs were rejected. The
strict `milestone16-verify.ps1 -RequireRomMUsers -RequireClean` check passed with zero
runtimes and clean dynamic routing. The profile is now `validated`, completing
Milestone 16.

Final post-acceptance checks: the rebuilt `retrobrowser/retro-session:milestone16` image
contains the validated manifest and passes all four embedded artifact checks; Ruff
lint and tracked-Python formatting, strict mypy for 59 source files, 165 tests with one
existing Windows-only symlink skip, PowerShell parsing, and the six-file Compose model
all pass.
The ignored runtime pin was refreshed to the post-acceptance image digest; Runtime Agent
and Session Manager were recreated successfully and are healthy with zero participant
runtimes. The strict clean verifier passed again after that refresh.

## Milestone 17 accepted

Milestone 17 persistence is implemented, accepted, and deployed to the public stack.
The explicit policy makes the
Netplay host's battery-backed save authoritative. Runtime Agent derives an opaque
namespace from stable user ID, core profile, and trusted ROM SHA-256, mounts it only
into the host, and rejects a second managed writer under a process lifecycle lock.
Guests, save states, RetroArch preferences, and core options remain ephemeral or
image-owned. A private image-owned FIFO invokes RetroArch's main-thread `SAVE_FILES`
command every ten seconds because upstream disables its background autosave worker
during Netplay; the network command interface stays disabled. `block_sram_overwrite`
is enabled.

The first browser acceptance attempt found and corrected two persistence defects. The
pinned RetroArch disables its normal autosave worker during Netplay, requiring the
main-thread FIFO command above. After that correction, live logs showed Mesen exposing
8 KiB of SRAM and `SAVE_FILES` targeting the correct mount, but Docker Desktop's
root-owned `0755` drvfs leaf rejected file creation. Compatibility mode now uses `0777`
only on the opaque mounted leaf; native Linux retains UID 1000 and `0700`.

Important files:

- `services/runtime-agent/src/retro_runtime/service.py`
- `services/runtime-agent/src/retro_runtime/models/config.py`
- `images/retro-session/session_entrypoint/models.py`
- `images/retro-session/session_entrypoint/launcher.py`
- `infra/compose/acceptance/compose.milestone17.yml`
- `infra/scripts/acceptance/milestone17-start.ps1`
- `infra/scripts/acceptance/milestone17-verify.ps1`
- `docs/milestone-17-persistence.md`
- `tests/integration/test_milestone17_config.py`

At Milestone 17 acceptance, the seven-file Compose model, Ruff lint/format, and strict mypy for 55 source
files are clean; 177 tests pass with one existing Windows symlink skip. A live
control-plane proof launched
one healthy host with the exact writable save mount, rejected a concurrent same-key
writer without creating a second runtime, and returned to a strict clean state. The
public stack was running Milestone 17 with zero participant runtimes.

Public browser acceptance on 2026-09-13 restored the recognizable `DPG`/sword marker
through repeated owner-close and fresh-lobby cycles, including a runtime upgrade. The
guest received the canonical host state and synchronized gameplay. A concurrent
same-user/same-game launch returned HTTP `409` and left exactly one durable writer.
Guest leave/rejoin, guest and host browser reconnect, and a selected TURN `relay`
candidate passed. Both owner-close checks removed all participant runtimes and routes;
the final strict clean verifier passed. No ROM, save contents, stream URL, token, or
credential was recorded.

## Milestone 18 complete

Milestone 18 observability and operations began on 2026-09-14. Session Manager now
exports low-cardinality Prometheus metrics, JSON error events, runtime capacity, and an
authenticated sanitized session diagnostic. Runtime Agent enforces the same configured
capacity and atomically manages per-runtime Prometheus file-discovery targets alongside
Traefik routes.

The pinned Selkies build already collects browser WebRTC statistics, but its metrics API
correctly requires secure-mode authentication. The runtime image therefore includes a
small metrics-only proxy on private, non-routed port 9091. It authenticates a distinct
participant-specific HMAC token, accesses Selkies only over loopback with the master
token, logs no request URL, and exposes no control operation. Prometheus receives no
Selkies master/controller token. A temporary live runtime proved unauthenticated scrape
rejection, authenticated target discovery/scraping, and target deletion on owner close.

The public stack currently includes pinned Prometheus 3.7.3 and Grafana 12.3.0.
Prometheus has no published port or Docker socket. Grafana binds only to
`127.0.0.1:3000` by default with a generated ignored admin password, anonymous access
and update telemetry disabled, and the RetroBrowser Operations dashboard provisioned.
Native coturn metrics are private on port 9641. Seven failure-mode runbooks are under
`docs/runbooks/`.

Automated checks: Ruff lint/format, strict mypy, 185 tests with one existing Windows
symlink skip, PowerShell AST parsing, the eight-file
Compose model, image build, Grafana dashboard lookup, Session Manager/coturn scrapes,
and `milestone18-verify.ps1 -RequireRomMUsers -RequireClean` pass.

The first Milestone 18 two-browser attempt found a coturn network-ordering regression:
adding coturn to the internal observability network caused relay sockets to bind there
while Docker's published UDP range entered through the public TURN network. ARCADE-HOST,
Windows Packet Monitor, kernel UDP, and coturn counters isolated the mismatch. The
overlay now keeps coturn on its accepted stream/public networks; Prometheus scrapes its
private exporter over the already-shared stream network.

The next external-only attempt proved peer traffic reached coturn in both directions,
then isolated repeated ICE failure to coturn 403 responses for CHANNEL_BIND requests to
its own advertised public relay address. Private candidate classes bound successfully.
The public TURN profiles now allowlist only the detected public TURN address so two
allocations on the same coturn instance can form a relay-to-relay pair; loopback, zero,
multicast, and other default peer protections remain enabled.

Final acceptance used an external-Internet client and a home-LAN client, both Microsoft
Edge with Xbox controllers. Both streams worked, browser diagnostics selected a TURN
`relay` candidate, FPS/latency and coturn traffic populated, and controller actions
remained synchronized. Participant leave removed one runtime, route, and metrics target;
rejoin created a fresh healthy set. The trusted RomM integration returned a sanitized
diagnostic for two healthy participants with expected capacity and no sensitive
internals. Owner close removed every runtime, dynamic route, and metrics target, and the
final strict verifier passed cleanly.
