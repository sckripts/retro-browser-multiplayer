# Production deployment

The repository-root `compose.yml` is the supported production model. It replaces the
milestone overlay chain as the operator interface. The overlays under
`infra/compose/acceptance` remain useful for regression testing, but are not a
production deployment method.

The deployment target is a native Linux Docker host. PowerShell 7 is required for the
operator scripts. Docker Desktop remains suitable for development, not a public host.

## Ten-step procedure

1. **Prepare the host.** Install current Docker Engine with Compose v2 and PowerShell
   7. Allocate storage for the RomM library, per-user data, saves, databases, and
   metrics. Do not mount the Docker socket into any service other than Runtime Agent.

2. **Prepare the network.** Create public DNS records for the RomM endpoint, authentik,
   and TURN. Provide a public IPv4 path and open TCP 80/443, TCP+UDP 3478, TCP 5349, and
   the configured UDP relay range. Keep Grafana bound to loopback unless it is placed
   behind a separately authenticated operator route. See `docs/networking.md`.

3. **Initialize deployment state.** From the repository root run:

   ```powershell
   ./infra/scripts/production/initialize.ps1
   ```

   This creates ignored `.env.production`, generates independent secrets without
   printing them, creates default host-data directories, and adds an empty Prometheus
   target file. Move data roots outside the checkout for a long-lived installation.

4. **Configure endpoints and mail.** Edit `.env.production`. Set `PUBLIC_HOSTNAME`,
   `AUTH_HOSTNAME`, `TURN_HOST`, `TURN_REALM`, authenticated SMTP values, and the initial
   administrator address. Use real public DNS names; the start script rejects test
   domains and IP-address endpoints.

5. **Install TLS material.** Set absolute `TLS_CERT_FILE` and `TLS_KEY_FILE` paths to a
   valid PEM pair whose SANs cover all configured public names. Keep the private key
   outside Git. Certificate renewal takes effect after restarting the TLS-consuming
   services with the normal start command.

6. **Provide immutable images.** Set `RUNTIME_AGENT_IMAGE`, `SESSION_MANAGER_IMAGE`,
   `RETRO_SESSION_IMAGE`, and `ROMM_IMAGE` to `name@sha256:...` references. Until a
   registry release exists, build locally from this checkout and a separate, clean RomM
   AGPL integration checkout pinned to an explicitly approved commit:

   ```powershell
   ./infra/scripts/production/build-images.ps1 `
     -RomMSource /srv/src/romm-integration `
     -RomMCommit 0123456789abcdef0123456789abcdef01234567
   ```

   The helper writes local immutable image IDs to `.env.production`. Keep the RomM fork
   and its corresponding source offer separate from this Apache-2.0 repository.

7. **Populate operator-owned content.** Set absolute `ROM_ROOT`, `USER_DATA_ROOT`,
   `SAVE_DATA_ROOT`, `ROUTE_CONFIG_ROOT`, and `METRICS_TARGET_ROOT` paths. Import only
   content you are entitled to use into RomM's library layout. ROM and BIOS files must
   never enter Git, images, CI artifacts, tests, or examples.

8. **Validate and start.** Review capacity/resource values, then run:

   ```powershell
   ./infra/scripts/production/start.ps1
   ```

   It validates required values, digest references, host paths, SMTP mode, certificate
   dates/SANs, and the rendered Compose model before starting and waiting for health.

9. **Verify the installation.** Run:

   ```powershell
   ./infra/scripts/production/verify.ps1 -RequireClean
   ```

   Then complete a two-account browser check from separate networks: email login,
   create/join, synchronized input/audio/video, TURN relay, leave/rejoin, owner close,
   and zero remaining runtimes/routes. `verify.ps1` checks service state, Runtime Agent,
   the public heartbeat, and browser security headers; it does not replace that manual
   compatibility check.

10. **Establish operations before inviting users.** Back up the authentik and RomM
    databases, RomM assets/resources, per-user data, saves, and `.env.production`/TLS
    material through a protected secrets-aware process. Perform a restore drill and a
    secret/certificate rotation drill, configure monitoring/alerts, and record the
    installed image digests. These drills are not automated in the repository yet, so
    production readiness remains conditional on the operator completing and recording
    them. Apply upgrades by changing pinned digests, running `start.ps1`, verifying, and
    retaining a tested rollback set.

## Lifecycle commands

`start.ps1` is idempotent for the configured model. `stop.ps1` removes containers and
project networks but deliberately preserves named volumes, host data, credentials,
ROMs, and saves:

```powershell
./infra/scripts/production/stop.ps1
```

There is intentionally no production data-destruction helper. Diagnose and back up an
installation before manually removing any persistent data.

## Adding systems

New systems are approved profiles, not downloadable runtime plugins. Follow
`docs/adding-emulators.md`. BIOS-dependent and multi-file/disc systems need additional
trusted server-side contracts before they can be safely supported.
