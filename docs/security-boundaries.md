# Security Boundaries

The browser supplies stable public identifiers, never authoritative paths, container parameters, IP addresses, or shell fragments. RomM resolves its ROM ID; Session Manager validates the canonical path and hashes; Runtime Agent independently enforces allowlisted images, roots, networks, environment keys, device requests, and limits.

Runtime Agent is the sole Docker-socket holder and listens on a UNIX socket initially. Traefik consumes generated file-provider routes and does not receive the Docker socket. Selkies master tokens and coturn shared secrets remain server-side; participant tokens and TURN credentials are short-lived and revocable.

Runtime Agent container names, project ownership labels, mount targets, resource
limits, security options, health checks, and Traefik file-provider routes are generated
server-side. Removal requires both the managed label and matching participant label.

Milestone 17 adds one operator-owned durable save root exclusively to Runtime Agent.
Only the Netplay host receives a generated writable save mount. Its opaque namespace is
derived from stable user identity, core profile, and trusted ROM digest, and Runtime
Agent rejects concurrent managed writers for the same namespace. Guests, browsers,
RomM, and Session Manager never select or receive filesystem save paths.

Digest-qualified images and existing project-owned networks are allowlisted; host
networking and published runtime ports are forbidden.

Native Linux user-data directories are owned by the fixed runtime UID 1000 with
restrictive modes. Docker Desktop's Windows bind filesystem cannot apply Linux
ownership. The isolated Milestone 6 harness therefore uses an explicit admin-only
pre-provisioned mode: PowerShell creates the participant directory under the ignored
approved root and the agent does not alter its host ACL. This mode is configuration,
not an API field. RuntimeSpec contains no token; the Selkies master token remains only
in the generated container environment.

Session Manager reaches runtime Selkies APIs only on the private stream network. It
derives a unique master token and a domain-separated participant controller token from
the server-only orchestration secret; raw credentials are not persisted in Session or
Valkey records. Only the actor-scoped launch response releases the controller token.
Public session reads expose a stream path but no credential. Revocation replaces the
entire per-runtime Selkies token table with `{}` before runtime removal, and Traefik
access logging stays disabled because the browser bootstrap URL can contain the token.
