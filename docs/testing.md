# Testing

The baseline validates formatting, lint, typing, package smoke tests, and Milestone 1
infrastructure invariants. Milestone 1 additionally has a Docker health/security proof
and a manual browser, audio, keyboard, and physical-gamepad checklist in
`milestone-1-selkies-proof.md`. Later layers add fake-provider orchestration tests,
Docker/runtime integration, two-runtime Netplay, public WebRTC/TURN, and full
RomM/authentik end-to-end tests.

ROM fixtures require explicit redistribution provenance in `tools/test-roms/README.md`.

Milestone 5 adds structural tests for identical host/client artifacts, explicit private
Netplay addressing, isolated stream networks, distinct scoped tokens, public HTTPS and
TURN wiring, and the absence of public port 55435 or Docker socket mounts. Manual
acceptance additionally requires two browser devices/controllers, synchronized game
state, independent participant input, and clean removal of both runtimes.

Milestone 9 adds provider tests for master/controller token separation, exact Selkies
token-table replacement, slot assignment, error redaction, actor-scoped launch, and
revocation ordering. Its isolated live verifier checks the actual proxied Selkies
WebSocket handshake: no token receives `401`, while the participant controller token
receives `101`. The verifier never prints the credential.

Milestone 10 adds deterministic tests for participant heartbeat renewal, bounded lobby
and maximum-lifetime leases, idle guest and abandoned-owner handling, unhealthy runtime
cleanup, startup reconciliation, idempotent missing-container removal, and orphan-route
reconciliation. The live harness kills the browser heartbeat, RetroArch, Selkies, a
whole participant container, and Session Manager in turn, then requires closed state,
revoked runtime access, no managed containers, and no generated routes. See
milestone-10-session-lifecycle.md for the deliberate restart interruption and current
single-manager limitation.

Milestone 11 adds structural tests for immutable identity images, loopback-only public
ports, absence of Docker-socket mounts, strict OIDC callback matching, authorization
code, verified-email mapping, and stable `sub` usernames. Its live verifier checks
discovery, exact provider configuration, issuer reachability from RomM, distinct
authentik UIDs, RomM redirect state/nonce, and exactly two durable RomM rows after each
user repeats browser authentication. The verifier never prints credentials or links.

Milestone 17 adds deterministic coverage for opaque per-user/game/core save namespaces,
host-only writable mounts, ephemeral client saves, single-writer rejection, reuse after
runtime removal, immutable preferences, and ephemeral save states. Its public acceptance
runbook verifies persisted host SRAM across lobbies without recording save contents.
That browser acceptance passed on 2026-09-13, including canonical guest state,
single-writer HTTP `409`, reconnect, leave/rejoin, TURN relay, and strict cleanup.

Milestone 18 adds unit coverage for bounded metrics, sanitized session diagnostics,
runtime-capacity enforcement, and atomic Selkies target discovery. Its Compose verifier
validates Prometheus configuration, private Session Manager and coturn scrapes, Grafana
health, and the inherited strict runtime/route cleanup checks. Manual acceptance
correlates a selected browser relay candidate with TURN and per-participant WebRTC data.

Milestone 19 begins with tests for global session and per-user runtime admission,
pseudonymous lifecycle audit events, explicit Runtime Agent resource settings, edge
rate/request/browser controls, pinned security actions, and SBOM coverage for every
project-owned image. Run the Security workflow for vulnerability and CycloneDX evidence;
live and remaining hardening acceptance is tracked in
`milestone-19-production-hardening.md`.
