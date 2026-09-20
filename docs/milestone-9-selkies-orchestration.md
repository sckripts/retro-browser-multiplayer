# Milestone 9 — Selkies Secure Session Orchestration

Milestone 9 makes every dynamic browser stream participant-specific and revocable.
Runtime Agent remains the only Docker-socket holder; Session Manager uses Selkies'
narrow token API over the private stream network and receives no additional container
privileges.

## Secure launch flow

After Runtime Agent reports RetroArch, Selkies, and Netplay healthy, Session Manager:

1. derives the runtime's stable server-only Selkies master token using the unchanged
   Milestone 8 HMAC construction;
2. derives a separate domain-separated controller token for the participant;
3. posts exactly one `controller` entry with local gamepad slot 1 and exclusive
   mouse/keyboard control to `POST /stream/{participant}/api/tokens`;
4. stores only `/stream/{participant}` in the participant record;
5. releases the controller token only from the authenticated participant's launch
   endpoint, with the session lease expiry.

Each browser user has an independent runtime, so its RetroArch instance consumes
Selkies gamepad slot 1 even when that user occupies Netplay player slot 2. The Netplay
slot and local virtual gamepad slot are deliberately different concepts.

The access token is deterministic under the high-entropy server secret so Session
Manager can reproduce it after a process restart without persisting raw credentials.
It differs from the master token through explicit HMAC domain separation. Tokens are
unique per participant/runtime and remain valid only while the session lease is
active; leave, owner kick, close, expiry, and failed startup all attempt revocation.

## Revocation and failure behavior

Selkies' token endpoint replaces the complete token table. Revocation therefore posts
`{}`, which upstream immediately uses to disconnect clients whose credential is no
longer present. Session Manager attempts that operation before removing the runtime.
If the private token endpoint is already unavailable, runtime removal remains the
fail-closed disconnect and the control-plane transition can complete.

The owner-only kick endpoint cannot target the owner. The owner closes the complete
session instead. Launch requests from users who are not active participants return
`403` and never contact the target stream.

## Runtime hardening retained

Runtime Agent continues to generate and enforce the Selkies subfolder, allowed origin,
master token, fixed display, gamepad support, and minimal UI profile. Basic auth,
sharing, collaboration, clipboard, files, commands, microphone, webcam, and embedded
TURN remain disabled. Traefik has no Docker socket and no access log.

The local Milestone 9 harness intentionally retains WebSocket transport. The secure
token API and authorization model are transport-neutral. The already accepted static
public proof covers WebRTC and external coturn; public dynamic-session/TURN wiring is
outside this milestone as directed by the project handoff.

## Local verification

```powershell
.\infra\scripts\acceptance\milestone9-start.ps1
.\infra\scripts\acceptance\milestone9-verify.ps1
.\infra\scripts\acceptance\milestone9-stop.ps1
```

The verifier keeps launch JSON in memory, never prints the token, expects `401` from
the tokenless gameplay WebSocket, expects `101` with the scoped token, rejects a launch
attempt by a non-participant, and retires the runtime through the leave API.

The implementation was checked against the official Selkies repository. The pinned
runtime commit remains `3f87241fcd6abc44e205b22f6596e78ef4946670`; current upstream
`main` was `f95210a33041b2311a9e912f54f9b75203fefcdb` on 2026-09-02. The documented
`POST /api/tokens` replacement contract and controller `slot` semantics are unchanged
between those revisions. The latest formal release remains v1.6.2, which predates the
secure-mode runtime pin.

## Acceptance evidence

Automated acceptance passed Ruff lint and formatting, strict mypy across 53 source
files, and 110 tests; the existing Windows symlink test was skipped because the host
does not grant symlink creation.

Live Docker Desktop acceptance proved:

- localhost edge publication on `127.0.0.1:8093`, with only the edge on the
  edge-only ingress network;
- an unrelated authenticated actor received no launch credential;
- a tokenless proxied gameplay WebSocket received HTTP `401`;
- the scoped participant controller token received WebSocket HTTP `101`;
- leave retired the participant after revocation was attempted;
- Session Manager and the participant runtime were unprivileged and had no host port
  bindings;
- Runtime Agent remained unprivileged, had `network_mode: none`, and remained the only
  Docker-socket holder;
- final shutdown left no Milestone 9 containers or private runtime networks.
