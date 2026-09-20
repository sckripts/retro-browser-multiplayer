# Milestone 7 — Session Manager Skeleton

Milestone 7 implements the provider-independent lobby control logic in
`services/session-manager`. It deliberately does not call Runtime Agent, Selkies,
Traefik, or a live RomM instance; those integrations remain later milestones.

## Implemented boundaries

The service defines typed `ExecutionProvider`, `StreamProvider`, `RouteProvider`,
`RomMProvider`, `SessionRepository`, and `CoreRegistry` protocols. Milestone 7 uses
fake RomM/core providers and the in-memory repository in lifecycle tests. The
`ValkeySessionRepository` is the production state adapter and stores strict Pydantic
JSON with optimistic `WATCH`/`MULTI` revision checks, an index set, and bounded TTLs.

The Session Manager never accepts a ROM path, core path, Docker option, command,
private network address, or stream credential from its HTTP API. `RomMProvider`
resolves the numeric RomM ROM ID into trusted platform/hash metadata, and
`CoreRegistry` selects an approved profile.

## Private API

Implemented routes:

```text
POST   /v1/sessions
GET    /v1/sessions
GET    /v1/sessions/{id}
POST   /v1/sessions/{id}/join
POST   /v1/sessions/{id}/leave
DELETE /v1/sessions/{id}
GET    /healthz
GET    /readyz
```

Every `/v1` request requires `Authorization: Bearer <service token>`. The configured
token must contain at least 32 characters and is compared in constant time. Mutating
routes also require `X-Authenticated-User-Id` and
`X-Authenticated-User-Display-Name`. These headers are trusted only because the
caller has authenticated with the private service credential. The Session Manager
must remain private; a browser must not call it directly. RomM service integration
and credential provisioning are not part of this milestone.

## Fake-path lifecycle

Create resolves trusted game/core metadata, opens the lobby, and creates the owner as
active player 1. Join allocates the lowest free player slot. Duplicate active joins
and repeated leaves/closes are idempotent. Full lobbies are excluded from discovery
and reject additional users. Only the stable owner user ID may close a lobby.

Expiration is deterministic: reads and discovery reap due sessions, move active
participants to `LEFT`, mark the session `CLOSED`, and record `expired`. A background
lease sweeper, heartbeat handling, runtime cleanup, and restart reconciliation belong
to Milestone 10.

Friendly names are NFC-normalized, limited to 64 characters, and reject surrounding
whitespace and Unicode control/format characters. Names remain display data only;
UUIDs are the authoritative identifiers.

## Known limits

- No participant runtime is created; the fake path marks participants active so the
  lobby state machine can be tested independently.
- No browser stream launch data or infrastructure detail is returned.
- A user who has left cannot rejoin the same lobby in this skeleton.
- Optimistic Valkey conflicts return a conflict; retry policy is deferred until real
  orchestration.
- There is no deployable Session Manager composition yet because the real RomM and
  Runtime Agent providers are intentionally absent.

## Verification

Run:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe services
.\.venv\Scripts\python.exe -m pytest
```

The Milestone 7 tests cover create, discovery, get, join, leave, close, expiration,
capacity, duplicate join/leave/close behavior, owner authorization, name validation,
service authentication, identity assertions, readiness, and Valkey round trips.
