# Retro Browser Multiplayer

A browser-native, self-hosted retro multiplayer platform. Players use a modern browser
and controller; emulation, streaming, and Netplay run server-side.

This repository contains original Apache-2.0 orchestration code and infrastructure. It
does not contain RomM, Selkies, RetroArch, emulator cores, ROMs, or BIOS files. RomM
integration changes remain in a separate AGPL-3.0 fork.

## Deployment

The repository-root `compose.yml` is the single supported production topology. It
combines the accepted control plane, identity, RomM integration, streaming, TURN,
Netplay, persistence mounts, quotas, and observability configuration.

Start with the ten-step operator procedure in `docs/deployment.md`. Production commands
live in `infra/scripts/production`; milestone scripts and Compose files are retained
under their respective `acceptance/` directories for regression evidence only.

The current release is source-deployable. It does not yet publish the four custom image
artifacts to a registry, so operators must build them and retain immutable image
digests. Backup/restore and secret-rotation drills remain release-gating operational
work documented in the deployment guide.

## Architecture boundaries

- RomM: library UI and user-facing control plane
- authentik: identity
- Session Manager: lobby and session orchestration
- Runtime Agent: narrow privileged container lifecycle boundary
- Selkies: browser streaming
- RetroArch: emulation and Netplay
- coturn: STUN/TURN
- Valkey: ephemeral session state

Runtime Agent is the only service with Docker socket access. Browser requests never
select an image, core, or ROM path.

See `PROJECT.md`, `docs/architecture.md`, `docs/adding-emulators.md`, and `docs/adr/`
before development. Current verified history and outstanding work are in
`SESSION_HANDOFF.md`.

## Development checks

The custom Python services target Python 3.14.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
mypy services
pytest
```

Never commit credentials, ROMs, BIOS images, or generated deployment state.
