# Milestone 8 — Real Runtime Orchestration

Milestone 8 connects Session Manager to Runtime Agent through the mode-0660 UNIX
control socket. The accepted local harness turns two private API calls—`create` and
`join`—into a host/client RetroArch Netplay topology without manual Docker or
RetroArch configuration.

## Implemented flow

Session Manager resolves a numeric game ID through its trusted provider and an
approved core through `CoreRegistry`. The browser-facing request still cannot supply
a ROM path, image, network, port, command, private host, or credential.

For the owner, Session Manager persists `ALLOCATING`/`STARTING`, asks
`LocalRuntimeAgentProvider` to create the host, and waits up to 180 seconds for the
generated container healthcheck. For a joiner it allocates the next slot, derives the
host participant internally, creates the client, and waits up to 45 seconds for
Netplay to connect. Only after readiness does the participant become `ACTIVE`.

Runtime Agent's generated healthcheck requires all of:

- a live RetroArch process;
- a healthy Selkies HTTP API;
- a listening Netplay TCP socket for the host, or an established Netplay TCP socket
  for the client.

Both `/proc/net/tcp` and `/proc/net/tcp6` are checked because RetroArch uses a
dual-stack listener on the accepted runtime. Docker reports health separately from
container lifecycle state, and Runtime Agent exposes both fields through its narrow
inspect response.

If creation, inspection, health, or a timeout fails, Session Manager calls idempotent
Runtime Agent removal, marks the participant `ERROR`, and marks a failed owner session
`ERROR`. Leave, close, expiration, and the stop helper remove runtimes through Runtime
Agent rather than Docker commands.

## Private addressing and credentials

The Docker hostname is derived only inside `LocalRuntimeAgentProvider` from the host
participant UUID. It is sent to Runtime Agent for the client's RuntimeSpec but is not
stored in or returned by the `Session` API model. Live acceptance confirmed the API
response contains neither the private hostname nor the Netplay address.

Runtime Agent still requires Selkies secure mode. For create-request idempotency, the
provider derives a stable per-participant master token with HMAC-SHA-256 from a
server-only orchestration secret. The master token is sent only over the UNIX socket
and never appears in Runtime Agent responses, RuntimeSpecs, Session records, or API
responses. Controller-token provisioning, browser launch data, and revocation remain
Milestone 9.

## Harness and privilege boundaries

`infra/compose/acceptance/compose.milestone8.yml` provides:

- unprivileged Session Manager with private Valkey access and the control socket;
- Runtime Agent as the sole Docker-socket holder, with only `CHOWN` added so it can
  assign the control socket to group 1000;
- pinned Valkey 9.1.2 running directly as its built-in unprivileged UID/GID;
- private stream and Netplay networks;
- a localhost-only Traefik edge consuming generated file-provider routes, without a
  Docker socket.

The harness uses one statically configured, hash-validated legal test game instead of
live RomM. This preserves the provider boundary; RomM integration remains Milestone
11. On Docker Desktop, an explicit admin-only setting uses traversable `0755` runtime
directories and `0644` RuntimeSpecs because Windows bind mounts reject Linux `chown`.
Native Linux retains `0700`/`0600` and UID 1000 ownership.

Start, exercise, and stop:

```powershell
.\infra\scripts\acceptance\milestone8-start.ps1
.\infra\scripts\acceptance\milestone8-create-and-join.ps1
.\infra\scripts\acceptance\milestone8-stop.ps1
```

The environment file and generated runtime state are ignored. No ROM, token, or
secret is committed.

## Acceptance evidence

Live Docker Desktop acceptance on 2026-09-02 proved:

- Session Manager, Runtime Agent, Valkey, and the localhost edge became healthy;
- `create` returned only after the host listened on TCP 55435;
- `join` returned only after the client connection reached TCP `ESTABLISHED`;
- a duplicate join returned the existing participant and did not create a third
  runtime;
- exactly two runtime containers were healthy;
- both runtimes shared only the internal Netplay and stream networks;
- both runtime containers had empty host-port bindings;
- generated Traefik routes existed for both participants;
- the API response omitted private host addressing and credentials;
- forced false-negative startup attempts timed out and left Runtime Agent's managed
  list empty;
- shutdown removed both runtimes through Runtime Agent, then removed all harness
  containers and proof networks.

The current official Docker Engine API documents `State.Status` and health status as
separate inspect fields. The harness also pins the official Valkey 9.1.2 Alpine image
index at `sha256:a174b894902bd3367e330d47cc2054367dc4917701776aaf336f41d83b65ec7a`.

## Deliberately deferred

- Selkies participant/controller token provisioning and revocation (Milestone 9);
- startup reconciliation, heartbeat leases, and orphan sweeps (Milestone 10);
- live RomM API integration (Milestone 11);
- public dynamic-session exposure and TURN orchestration.
