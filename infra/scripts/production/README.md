# Production scripts

These scripts are the supported deployment interface:

1. `initialize.ps1` creates `.env.production`, generates secrets without printing them,
   and creates default host-data directories.
2. Fill the blank DNS, TLS, SMTP, administrator, and image settings.
3. Use registry-published digest references, or run `build-images.ps1` against an
   explicitly pinned clean RomM integration checkout.
4. `start.ps1` validates configuration and TLS, renders the private Traefik file, and
   starts the single root `compose.yml` model.
5. `verify.ps1` checks the rendered model, service state, privileged boundary, public
   heartbeat, and security headers. Add `-RequireClean` during maintenance.
6. `stop.ps1` removes containers and project networks while retaining volumes and host
   data. It never removes databases, saves, ROMs, or credentials.

Milestone scripts are acceptance evidence and are not a production deployment API.
