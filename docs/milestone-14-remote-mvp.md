# Milestone 14 remote two-user MVP

Milestone 14 validates the complete product from two unrelated Internet connections.
It was accepted on 2026-09-08 after every item in the manual checklist below passed. The public
profile keeps RomM and authentik behind one TLS edge, keeps Session Manager, Runtime
Agent, Valkey, databases, Mailpit, and TURN REST private, and publishes only HTTPS plus
coturn listener and relay ports.

## Prerequisites

- Public DNS names for RomM and authentik, plus a TURN name (the TURN name may equal
  the RomM name). All must resolve to the deployment's public IPv4 address from the
  Internet. Split DNS may resolve them directly to the host on the local network.
- A currently valid PEM certificate/key pair covering all three names.
- Forward TCP 80/443, UDP and TCP 3478, TCP 5349, and UDP 49160-49200 to the Docker
  host. Do not forward any other service port.
- A real authenticated SMTP account. Mailpit is deliberately not published.
- Two distinct real email addresses controlled by the two testers.
- The ignored, hash-verified Super Tilt Bro test ROM. No ROM or BIOS content is added
  to Git or an image.

Run the start helper once. Its first run creates `.env.milestone14`, imports reusable
non-secret public settings where available, generates fresh TURN credentials, and
stops. Fill the blank public authentik, SMTP, administrator, and user email settings.
Then run it again:

```powershell
.\infra\scripts\acceptance\milestone14-start.ps1 -NoBrowser
.\infra\scripts\acceptance\milestone14-verify.ps1
```

The Runtime Agent—not the browser—selects WebRTC mode and the private TURN REST
endpoint. Each Selkies runtime receives the REST API key and a unique REST username;
the coturn shared secret never enters a runtime or browser. TURN REST returns expiring
credentials. Dynamic Traefik routes are scoped to the public RomM hostname, and access
logging remains disabled because the Selkies bootstrap URL contains a scoped token.

## Two-network acceptance checklist

Use two unrelated Internet connections, for example a residential connection and a
mobile hotspot. Do not accept a test where both clients traverse the same LAN or VPN.

1. User A signs in through public authentik and opens the supported NES game.
2. User B signs in independently through public authentik.
3. User A creates a two-player lobby named `Contra Night` and its runtime opens.
4. Browser A receives responsive video/audio and controller input.
5. User B discovers `Contra Night`, joins it, and its separate runtime opens.
6. Runtime B automatically joins Runtime A through private RetroArch Netplay.
7. Both controller slots affect the synchronized game.
8. In browser WebRTC diagnostics, record the selected candidate pair. Run at least one
   acceptance pass with a `relay` candidate to prove coturn, not only direct ICE.
9. User B leaves. Confirm B's stream stops, token is rejected, runtime is removed, and
   route disappears while A remains active.
10. User B rejoins if desired, then User A closes the lobby. Confirm both stream tokens
    are rejected, both runtimes terminate, both routes disappear, and the lobby is no
    longer discoverable.
11. Run the strict post-acceptance checks:

```powershell
.\infra\scripts\acceptance\milestone14-verify.ps1 -RequireRomMUsers -RequireClean
```

Record the two client network types, browsers, controller models, selected ICE
candidate type, and result for each checklist item. Do not record launch URLs, session
tokens, SMTP credentials, TURN credentials, or container environment.

Stop only this milestone's topology while preserving local databases and credentials:

```powershell
.\infra\scripts\acceptance\milestone14-stop.ps1
```

The stop helper first removes managed participant runtimes through Runtime Agent's
narrow UNIX-socket API, then removes the Compose project. It does not delete the local
library, user data, certificate, `.env.milestone14`, or named database volumes.

## Acceptance result

Public two-user acceptance completed on 2026-09-08. Two distinct users authenticated
through emailed links, created and joined a two-player lobby, received responsive video
and audio, and controlled the correct synchronized players. Runtime logs confirmed a
browser relay candidate and a bound TURN channel. Closing and reopening a player kept
the participant synchronized.

Acceptance exposed one Session Manager defect: after a participant left and rejoined,
the leave handler selected that user's earlier `LEFT` record instead of the current
`ACTIVE` record. The handler now targets a non-terminal matching participant, with a
regression test covering leave, rejoin, and leave again. Live retesting confirmed each
guest leave changed the lobby from two players to one without interrupting the host.
The owner then closed the lobby, and the strict verifier passed with both durable RomM
users present and no managed runtimes or generated participant routes remaining.

Final repository verification: Ruff lint and formatting passed, strict mypy passed for
55 source files, and pytest passed 148 tests with the existing Windows symlink test
skipped.
