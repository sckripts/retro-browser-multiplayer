# Milestone 10: session lifecycle and cleanup

Milestone 10 makes the Milestone 9 dynamic runtime topology fail closed when a
browser, emulator, streamer, participant container, or Session Manager disappears.
It does not add RomM integration, public dynamic sessions, or live restoration.

## Lifecycle policy

An active browser participant calls the private control-plane heartbeat endpoint:

```text
POST /v1/sessions/{session_id}/heartbeat
```

The stable asserted actor must match an active participant. A heartbeat updates only
that participant and renews the lobby lease. Renewal is capped at the absolute maximum
session lifetime measured from creation; it can never create an unbounded session.

The production defaults are:

| Setting | Default | Meaning |
|---|---:|---|
| `SESSION_MANAGER_IDLE_TIMEOUT_SECONDS` | 45 | participant silence before retirement |
| `SESSION_MANAGER_LOBBY_LEASE_SECONDS` | 120 | renewable lobby lease |
| `SESSION_MANAGER_MAX_SESSION_SECONDS` | 14400 | non-renewable four-hour lifetime |
| `SESSION_MANAGER_CLEANUP_INTERVAL_SECONDS` | 10 | background inspection interval |

The Milestone 10 local harness intentionally uses 30, 60, 300, and 5 seconds so
failure tests finish in bounded time. These are server-only settings, not browser
inputs.

Each sweep:

1. closes an expired lease or maximum-lifetime session;
2. closes the lobby if its owner is absent or idle;
3. retires an idle non-owner participant;
4. inspects every active participant runtime;
5. closes the lobby for a failed host runtime;
6. retires only the affected guest for a failed guest runtime;
7. revokes the Selkies controller token before asking Runtime Agent to remove the
   runtime and its generated Traefik route.

Join, leave, kick, close, runtime create, runtime remove, and heartbeat remain
idempotent within the supported single-Session-Manager deployment. Valkey optimistic
revisions reject stale writes.

## Restart reconciliation

FastAPI lifespan startup runs reconciliation before readiness is exposed. The Session
Manager closes every non-closed Valkey session with `manager_restarted`, attempts token
revocation, and removes its participant runtimes. It then asks Runtime Agent for all
remaining project-managed runtimes and removes those orphans as well.

Runtime Agent independently removes generated route files that have no corresponding
managed container when it starts. Removing a participant whose container has already
disappeared also removes its route before returning not-found; the Session Manager
treats that result as successful idempotent cleanup.

This policy deliberately interrupts all gameplay when Session Manager restarts. Live
session restoration does not exist and is not implied. Clients must return to the lobby
and create a new session.

Docker ownership remains label-based and allowlisted. Docker documents labels as
static container metadata and supports label filters for listing containers, which is
the mechanism Runtime Agent already uses to enumerate only project-managed runtimes.
FastAPI's documented lifespan mechanism owns startup reconciliation and shutdown of
the periodic task.

- [Docker object labels](https://docs.docker.com/engine/manage-resources/labels/)
- [Docker Engine API](https://docs.docker.com/reference/api/engine/)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)

## Local verification

The harness reuses the legal external Super Tilt Bro ROM and the pinned runtime image.
No ROM, secret, or token is added to Git.

```powershell
.\infra\scripts\acceptance\milestone10-start.ps1
.\infra\scripts\acceptance\milestone10-verify.ps1
.\infra\scripts\acceptance\milestone10-stop.ps1
```

The verifier exercises:

- heartbeat renewal followed by simulated browser abandonment;
- RetroArch termination;
- Selkies termination and bounded healthcheck failure;
- participant-container termination;
- hard Session Manager termination and startup reconciliation;
- empty Runtime Agent managed-runtime list and no generated route files after every
  case.

The runtime healthcheck uses a 45-second startup grace period and three five-second
post-start failures. This preserves slow startup tolerance while bounding detection of
a later RetroArch, Selkies, or Netplay failure.

## Known limitations

- Heartbeats are part of the private Session Manager contract. Milestone 12's RomM
  integration must proxy them from the embedded player; until then the proof client is
  the caller.
- The initial supported deployment has one Session Manager process. Distributed locks
  and active-session restoration are not implemented.
- Cleanup retries when a provider is temporarily unavailable. Readiness already fails
  while a required provider is unhealthy, and the background worker continues after a
  failed sweep.
- Closed records remain in Valkey for the configured short retention window for
  diagnostics, then expire. They are not live sessions.

## Accepted evidence

Live Docker Desktop acceptance passed on 2026-09-05. The verifier demonstrated:

- a heartbeat extended the initial lease, the session remained open beyond the
  original idle deadline, and later silence closed it as owner_abandoned;
- terminating RetroArch closed the participant container and the session as
  owner_runtime_failed;
- terminating Selkies invoked the project fail-closed s6 finish policy and closed the
  session as owner_runtime_failed;
- killing the participant container closed the session as owner_runtime_failed;
- killing Session Manager and starting it again closed the retained session as
  manager_restarted before the service became healthy;
- every case ended with an empty Runtime Agent managed-runtime list and no generated
  Traefik runtime route.
