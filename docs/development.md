# Development

The primary custom services target Python 3.14. Use the repository `.venv`, install `requirements-dev.txt`, and run Ruff, mypy, and pytest before every pull request.

Open `retro-platform.code-workspace` after the separate RomM fork exists beside this repository. The RomM fork must have `origin` pointed at the owner's fork and `upstream` at `https://github.com/rommapp/romm.git`.

Docker Desktop and its Linux engine are required from Milestone 1 onward. The current Windows host must have Docker Desktop running and WSL 2 integration enabled before container tests.

The Milestone 1 Selkies proof is isolated in `compose.milestone1.yml`; it does not turn
the empty full-platform development stack into a partially implemented architecture.
Run `infra/scripts/acceptance/milestone1-start.ps1` for the NVIDIA path or add `-CpuFallback` for
software encoding. Local tokens are generated into the ignored `.env.milestone1` file.

For Milestone 2, first fetch the pinned legal test ROM into ignored local storage, then
start the direct RetroArch proof using the verified Docker Desktop software path:

```powershell
.\tools\test-roms\fetch-super-tilt-bro.ps1
.\infra\scripts\acceptance\milestone2-start.ps1 -CpuFallback
.\infra\scripts\acceptance\milestone2-stop.ps1
```

The ROM and `.env.milestone2` must remain ignored. See
`docs/milestone-2-retroarch-proof.md` for hashes, runtime behavior, and acceptance.

Milestone 3 adds the public HTTPS/WebRTC proof. Its first start creates the ignored
`.env.milestone3`; configure real public DNS and trusted certificate paths before
off-site acceptance:

```powershell
.\infra\scripts\acceptance\milestone3-start.ps1 -Transport turn-udp -CpuFallback
.\infra\scripts\acceptance\milestone3-stop.ps1
```

Use the direct, TURN/TCP, and TURN/TLS profiles separately as documented in
`docs/deployment.md`. A local self-signed certificate is useful only for
configuration validation and does not satisfy public browser acceptance.

Milestone 6 replaces manual participant-container lifecycle with the private Runtime
Agent. The local proof creates the accepted legal test runtime through a UNIX socket,
waits for health, and leaves no public agent port:

```powershell
.\infra\scripts\acceptance\milestone6-start.ps1
.\infra\scripts\acceptance\milestone6-stop.ps1
```

The stop helper removes the participant through the API before taking down the named
proof project. Generated tokens, requests, user data, and routes remain under ignored
`local/runtime-agent/`; `.env.milestone6` is also ignored.

Milestone 7 is exercised without live infrastructure. Its lifecycle tests use fake
RomM/core providers and an in-memory repository; a separate adapter test proves the
Valkey serialization and optimistic-update contract. See
`docs/milestone-7-session-manager.md`. Install the updated exact dev requirements and
run the normal repository checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe services
.\.venv\Scripts\python.exe -m pytest
```
