# ADR 0004: Runtime Agent privilege boundary

- Status: Accepted
- Date: 2026-08-29

## Decision

Only Runtime Agent may access the Docker socket. Session Manager calls its narrow allowlisted API over a local UNIX socket.

## Consequences

There is no generic Docker proxy or arbitrary command endpoint. Runtime Agent validates images, digests, mount roots, networks, environment keys, devices, resource limits, labels, names, and cleanup ownership.
