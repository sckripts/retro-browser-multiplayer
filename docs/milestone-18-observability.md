# Milestone 18: Observability and operations

Milestone 18 adds a private Prometheus/Grafana observability plane without changing
the control, stream, emulator, or privileged-runtime boundaries. Prometheus scrapes
Session Manager and coturn by service name. Runtime Agent atomically publishes one
file-discovery target per managed Selkies runtime and removes it with the runtime.
Prometheus joins the private control and stream networks; it has no Docker socket and
no published port. Grafana is the only observability service with a host port, bound to
`127.0.0.1` by default and protected by a generated admin password.

Selkies keeps its metrics API behind normal secure-mode authentication. A small
project-owned proxy inside each participant image retrieves that endpoint over loopback
with the master token and exposes it on non-routed port 9091 only after validating a
separate participant-specific HMAC token. Prometheus receives that metrics-only token;
it never receives a Selkies master or controller token. The proxy has no Docker access,
does not log request URLs, and cannot mutate Selkies state.

The pinned Selkies runtime already derives client FPS, latency, GPU utilization, and
sanitized browser `RTCPeerConnection.getStats()` data. Milestone 18 enables its private
metrics endpoint rather than introducing a second WebRTC collector. coturn's native
exporter supplies allocation, traffic, and rejection visibility on private port 9641.
The Session Manager exporter deliberately avoids session IDs and user IDs as metric
labels; session-level investigation uses the authenticated diagnostics endpoint.

## Start and verify

Close active lobbies before upgrading, then run:

```powershell
.\infra\scripts\acceptance\milestone18-start.ps1 -NoBrowser
.\infra\scripts\acceptance\milestone18-verify.ps1 -RequireRomMUsers -RequireClean
```

Open `http://127.0.0.1:3000`, sign in as `admin` with the generated value stored only in
`.env.milestone14`, and select **RetroBrowser / RetroBrowser Operations**. Prometheus is
not published. To inspect its targets without opening a new network path:

```powershell
docker compose --env-file .env.milestone14 -f infra/compose/acceptance/compose.milestone10.yml -f infra/compose/acceptance/compose.milestone11.yml -f infra/compose/acceptance/compose.milestone12.yml -f infra/compose/acceptance/compose.milestone14.yml -f infra/compose/acceptance/compose.milestone15.yml -f infra/compose/acceptance/compose.milestone16.yml -f infra/compose/acceptance/compose.milestone17.yml -f infra/compose/acceptance/compose.milestone18.yml exec -T prometheus wget -qO- http://127.0.0.1:9090/api/v1/targets
```

The authenticated, browser-safe control-plane endpoints are:

- `GET /v1/operations/capacity`
- `GET /v1/sessions/{session_id}/diagnostics`

The first endpoint reports configured runtime capacity, current use, and available
slots.

Diagnostics include lifecycle and runtime health, but not paths, container IDs, private
addresses, master tokens, TURN credentials, or access tokens. Services emit one-line
JSON errors with a stable event/category/operation vocabulary. Never paste full logs or
Prometheus target output into an issue without checking it for deployment identifiers.

## Acceptance

1. Verify Session Manager, coturn, and Prometheus are `UP` in Prometheus targets.
2. Create a two-player lobby and confirm two Selkies targets appear, each with the right
   session, participant, and core labels.
3. Confirm the dashboard shows runtime use, browser FPS/latency, and TURN activity. Use
   browser WebRTC diagnostics to confirm the chosen candidate is `relay`; correlate its
   time with coturn allocation/traffic metrics.
4. Call the session diagnostics endpoint through the existing trusted RomM integration
   and confirm both slots and runtime health are present without sensitive internals.
5. Leave/rejoin and confirm the retired target disappears before the new target appears.
6. Close the lobby and run the strict verifier. It must report zero runtimes and no
   generated route or metrics-target remnants.

The upstream integration references are the [Prometheus Python ASGI guidance](https://prometheus.github.io/client_python/exporting/http/asgi/),
[coturn Prometheus documentation](https://github.com/coturn/coturn/blob/master/docs/Prometheus.md),
and the pinned Selkies source under `upstream-reference/selkies`.

## Current acceptance status

Milestone 18 passed automated, live control-plane, and two-browser acceptance on
2026-09-14. The external-Internet and home-LAN clients both used Microsoft Edge with
Xbox controllers. Two healthy Selkies targets populated FPS and latency series, coturn
recorded bidirectional peer traffic, browser diagnostics selected a `relay` candidate,
and both controller slots affected synchronized gameplay.

The second participant's leave removed its runtime, dynamic route, and metrics target
while the owner remained healthy. Rejoin created a fresh runtime and restored two
healthy Prometheus targets. The trusted RomM integration received a sanitized session
diagnostic with two healthy participants and the expected remaining capacity, without
container IDs, private addresses, paths, or credentials. Owner close removed both
runtimes, routes, and targets. The final strict verifier passed with zero runtime state.

The first two-browser attempt exposed a Docker network-ordering regression in the
observability overlay. Attaching coturn directly to the new observability network made
its dynamically allocated relay sockets bind on that internal address while Docker's
published UDP range arrived through the existing public TURN network. Firewall and
Windows packet counters showed the datagrams reaching the host and coturn namespace,
where the kernel reported no matching relay port. The overlay now leaves coturn on its
accepted stream/public networks; Prometheus already shares the private stream network
and scrapes port 9641 there. Browser acceptance must be repeated after redeployment.

The follow-up external attempt proved bidirectional peer traffic but exposed a second
issue: coturn rejected a channel bind to its own advertised public address with 403,
preventing the two allocations on this single TURN server from forming a relay-to-relay
candidate pair. The TURN profiles now allowlist only the detected public TURN address.
Live address-class tests confirmed private peers remained accepted and isolated the
rejection to that public self-address; broader peer protections remain enabled.
