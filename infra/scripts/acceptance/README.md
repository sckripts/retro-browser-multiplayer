# Acceptance scripts

These scripts preserve milestone proofs and release-regression workflows. They are
not the supported production deployment interface. Use the scripts in
`infra/scripts/production` for a deployed installation.

`milestone18-start.ps1` upgrades the accepted public stack with private Prometheus,
loopback-only Grafana, native coturn metrics, dynamically discovered Selkies/WebRTC
targets, runtime-capacity reporting, and structured service errors. The verifier
composes prior strict checks with scrape/configuration health. See
`docs/milestone-18-observability.md` and `docs/runbooks/README.md`.

`milestone16-start.ps1` upgrades the accepted public stack in place with the pinned
Genesis/BlastEm runtime and imports an operator-selected ROM into RomM's `genesis`
library. Its verifier composes all earlier boundary checks with the BlastEm artifact
and optional active-runtime checks. See `docs/milestone-16-genesis.md`.

`milestone15-start.ps1` upgrades the accepted public Milestone 14 stack in place with
the pinned SNES/bsnes runtime and provisions two additional real-email testers.
`milestone15-verify.ps1` composes the public-boundary checks with artifact and optional
active-SNES-runtime checks. `milestone15-stop.ps1` performs the existing fail-closed
public stack shutdown. See `docs/milestone-15-snes.md`.

Scripts added here must be non-interactive where practical, validate their targets, avoid embedded secrets, and document destructive behavior.

The milestone start helpers create ignored local credential files, validate required
inputs, wait for container health, provision only a scoped browser token, and optionally
open the browser. Their matching stop helpers run `docker compose down` only against the
named milestone project.

`milestone3-start.ps1` supports `direct`, `turn-udp`, `turn-tcp`, and
`turn-tls`. It validates public hostnames, the certificate/key pair and validity
window, and the legal ROM hash before rendering an ignored host-specific route. Its
first invocation creates `.env.milestone3` and intentionally exits so the operator
can supply public values. See `docs/deployment.md`.

`milestone5-start.ps1` launches the fixed two-runtime local Netplay proof.
`milestone5-public-start.ps1` launches the same host/client pair behind separate
HTTPS/WebRTC routes and the accepted coturn path. It generates distinct host/client
master and session tokens, and can import non-secret deployment values from the local
Milestone 3 environment. Use separate browser profiles or devices because one scoped
controller token permits one active browser connection. The matching stop scripts
remove only their named Compose project.

`milestone6-start.ps1` builds the digest-qualified runtime and pinned Runtime Agent,
starts an agent with no network or published port, and calls it from a no-network
sidecar that has only the UNIX control socket. `milestone6-stop.ps1` removes the fixed
proof participant through that API and then removes only the named proof project.

`milestone9-start.ps1` launches the isolated dynamic secure-stream harness on
`127.0.0.1:8093`. `milestone9-verify.ps1` creates one runtime, obtains launch material
without printing it, proves tokenless gameplay WebSocket access is rejected, proves
the scoped controller token is accepted, and leaves the session. The matching stop
helper removes any remaining managed runtimes through Runtime Agent before removing
the named Compose project.

The milestone10 helpers launch the isolated lifecycle harness on
127.0.0.1:8094. The verifier exercises heartbeat abandonment, RetroArch failure,
Selkies failure, whole-runtime failure, and Session Manager restart reconciliation.
After every case it requires both Runtime Agent's managed list and generated route set
to be empty. The stop helper removes any remaining managed runtimes through the narrow
UNIX-socket API before removing only the named Compose project. See
docs/milestone-10-session-lifecycle.md.

The milestone11 helpers launch the local authentik/RomM OIDC proof, generate credentials
only in ignored `.env.milestone11`, provision two verified-email test identities, and
verify discovery plus RomM's authorization-code redirect. Mailpit is a local-only SMTP
sink. Normal stop preserves named identity/database volumes; `-RemoveData` explicitly
deletes only the Milestone 11 proof volumes.

The Milestone 14 helpers compose the accepted control plane with public HTTPS,
host-scoped dynamic stream routes, WebRTC, private TURN REST credential minting, and
public coturn listeners. The first start creates ignored configuration and stops for
public DNS, certificate, SMTP, administrator, and two-user values. The verifier checks
the public OIDC/control boundary and can require both RomM identities and zero runtime
or route remnants after manual two-network acceptance. See
`docs/milestone-14-remote-mvp.md`.

The Milestone 19 helpers upgrade an accepted, clean Milestone 18 stack with explicit
session/user/runtime quotas and a generated rate-limit, request-size, and browser-policy
edge configuration. The verifier composes all nine overlays, inherits the strict
Milestone 18 checks, and confirms the effective Runtime Agent and Traefik controls. See
`docs/milestone-19-production-hardening.md`; this milestone remains in progress.
