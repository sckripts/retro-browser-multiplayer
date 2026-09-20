# Milestone 5: Two Browser Runtimes and RetroArch Netplay

## Status

Accepted on 2026-09-01 after local and public browser tests. Two independent
Selkies/RetroArch runtimes joined one Netplay session, remained synchronized, and
accepted independent controller input from a development-PC browser and an LTE phone
browser with a USB-attached controller.

## Implemented topology

- `retro-host` launches the approved runtime as Netplay host/player 1.
- `retro-client` waits for the host and connects explicitly to `retro-host:55435` as
  player 2; RetroArch LAN discovery is not used.
- Both runtimes use the same image, RetroArch binary, Mesen core, read-only legal test
  ROM, and verified hashes.
- Only the two Selkies stream networks and the private `retro-net` connect the
  runtimes. TCP 55435 is exposed only as container metadata and is never published on
  the host.
- Traefik provides distinct `/stream/m5-host` and `/stream/m5-client` routes. Each
  route has a distinct Selkies master token and scoped controller token.
- The public profile reuses the Milestone 3 HTTPS, TURN REST, and coturn security
  boundaries. TURN REST and RetroArch remain private, and no service receives the
  Docker socket.

The launcher explicitly disables Netplay input swapping, Netplay delay frames, and
remote pausing so the proof's player assignment is deterministic.

## Start and stop

Local WebSocket proof:

```powershell
.\infra\scripts\acceptance\milestone5-start.ps1
.\infra\scripts\acceptance\milestone5-stop.ps1
```

Public HTTPS/WebRTC/TURN proof:

```powershell
.\infra\scripts\acceptance\milestone5-public-start.ps1 -NoBrowser
.\infra\scripts\acceptance\milestone5-public-stop.ps1
```

The first public start creates ignored `.env.milestone5-public` credentials. When a
Milestone 3 environment exists, it imports only deployment settings and generates new
Milestone 5 master, session, TURN REST, and TURN shared-secret values. Secrets are not
printed. Use separate browser profiles or devices for the two scoped controller URLs;
opening the same token in multiple tabs intentionally supersedes the older connection.

## Acceptance evidence

| Check | Result |
|---|---|
| Local host/client containers | Healthy |
| Netplay connection | Host player 1 and client player 2 joined over private `retro-net` |
| Artifact identity | Same RetroArch, core, ROM path, ROM SHA-256, and content CRC |
| Local synchronization | Two browser windows showed synchronized game state |
| Public signaling/media | ICE completed for both HTTPS/WebRTC routes |
| Public audio/video | Passed for both streams |
| Controller isolation | PC controller operated player 1; LTE phone USB controller operated player 2 independently |
| Remote synchronization | Both browser-only participants played the same synchronized game |
| Shutdown | Compose removed both runtimes, edge, TURN services, and all proof networks |
| Secret cleanup | Token-bearing local QR deleted; environment and generated route remain ignored |

For same-site HTTPS testing, internal DNS resolves `arcade.example.test` to
`192.168.2.17`. coturn still advertises the public relay address, so the ARCADE-HOST also
requires U-turn NAT for TCP/UDP 3478, TCP 5349, and UDP 49160-49200. Source NAT keeps
the return path symmetric. This is a local test-site constraint; off-site browsers use
the existing public forwarding rules.

## Scope boundary

This is a fixed test harness, not product orchestration. It does not add RomM UI,
Session Manager, Runtime Agent lifecycle management, arbitrary ROM/core selection, or
multi-session discovery. Milestone 6 owns the narrow privileged Runtime Agent boundary.
