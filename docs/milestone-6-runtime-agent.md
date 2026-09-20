# Milestone 6 Runtime Agent

Milestone 6 is complete. The narrow Runtime Agent replaces manual participant Docker
operations while preserving the Session Manager privilege boundary.

## Implemented boundary

- Private HTTP/JSON API on `/run/retrobrowser/runtime-agent.sock`; no TCP listener.
- Direct Docker Engine API client over `/var/run/docker.sock`; no generic proxy.
- Strict `CreateRuntimeRequest` v1 with unknown-field and duplicate-key rejection.
- Exact digest-qualified image and named-network allowlists.
- Independent ROM root resolution and SHA-256 verification.
- Generated RuntimeSpec, container name, ownership labels, fixed mount targets,
  environment keys, health check, resource limits, capabilities, and security options.
- CPU/NVIDIA device profiles selected only from agent configuration.
- Atomic Traefik file-route publication/removal through `RouteProvider`.
- Ownership-checked inspect, stop, and removal; idempotent duplicate creation.
- Managed-list route orphan detection.

The Docker daemon socket is mounted only into Runtime Agent. The proof caller has only
the control socket and has `network_mode: none`. Runtime Agent itself also has no
network and publishes no port. Participant containers publish no host port and cannot
use host networking.

## Local proof

On 2026-09-02, Docker Desktop Engine 29.0.1 accepted a create call from the no-network
client over the UNIX socket. The agent launched the same pinned RetroArch 1.22.2,
Mesen 0.9.9, and Super Tilt Bro 2.6 participant profile used in Milestone 5. The
runtime became healthy with container ID prefix `b5a561d89e23`.

A duplicate create returned that same container ID. Managed listing reported the
runtime as `orphaned: false`. Inspection confirmed:

- digest-qualified `retrobrowser/retro-session` image;
- `Privileged=false`;
- no host port bindings;
- private `retrobrowser-m6-stream` plus `retrobrowser-m6-retro-net` attachment;
- generated management, participant, session, request-fingerprint, and route labels;
- generated route present only while the runtime existed.

The delete call removed the participant and route. Compose shutdown then removed the
agent, unprivileged network anchor, control volume, and proof networks. A final Docker
query found no managed container or Milestone 6 network.

Docker Desktop cannot apply `chown` to a Windows bind. The proof uses the documented
admin-only pre-provisioned user-data mode. Native Linux defaults to UID/GID 1000 and
restrictive directory/file modes.

## Verification

Automated coverage includes invalid image, missing/escaping ROM mount, host network,
unmanaged removal, duplicate idempotency, route orphan detection, fixed mount and
hardening payloads, arbitrary-command rejection, atomic route files, Docker-socket
isolation, and immutable agent base-image configuration.

Run:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe services
.\.venv\Scripts\python.exe -m pytest
```

Milestone 6 deliberately does not implement Session Manager lobby/state behavior,
RomM integration, dynamic public sessions, or browser token issuance.
