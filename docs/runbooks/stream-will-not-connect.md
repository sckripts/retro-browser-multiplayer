# Stream will not connect

## Trigger

The player route loads but video/audio never connects, or the route returns 404/502.

## Diagnose

1. Record the session and participant IDs and UTC time; do not record the launch token.
2. Check the session diagnostics endpoint for `ACTIVE` plus runtime `healthy`.
3. In Prometheus targets, require that participant's Selkies target to be `UP`.
   A `401` indicates a stale metrics-only target token; it is not a reason to weaken
   Selkies authentication.
4. Check browser WebRTC diagnostics for ICE state and the selected candidate type.
5. If no relay candidate exists, continue with [TURN relay failure](turn-relay-failure.md).
6. If the runtime is unhealthy, retain its JSON logs and follow the runtime-specific error.

## Recover

Have the participant leave and rejoin once. This revokes the old token and replaces only
their runtime. If the owner is affected or replacement fails, close the lobby and create
a new one. Confirm the retired route and metrics target disappear. Do not expose the raw
Selkies port or weaken secure-mode token checks.
