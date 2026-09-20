# Retro Browser Multiplayer Platform — PROJECT.md

> **Purpose:** Source-of-truth engineering plan for a browser-native, self-hosted retro multiplayer platform built around RomM, RetroArch, Selkies, WebRTC/TURN, and a small custom orchestration layer.
>
> **Primary development workflow:** Visual Studio Code + Codex
>
> **Initial platforms:** NES, SNES, Sega Genesis / Mega Drive
>
> **Primary requirement:** Remote users need only a modern web browser and a controller. They must not be required to install an emulator, VPN, Moonlight, Parsec, or any other application.

---

## 1. Project Goal

Build a self-hosted browser gaming platform where an authenticated user can:

1. Open a public HTTPS website.
2. Authenticate using local credentials or email-based passwordless authentication.
3. Browse a centrally managed ROM library through RomM.
4. Select a supported game.
5. Create a multiplayer session and give it a friendly user-provided name.
6. Have the backend dynamically launch a dedicated server-side RetroArch instance for that player.
7. Stream that RetroArch instance directly into the browser with low-latency video, audio, keyboard, and gamepad input.
8. Allow other authenticated users to discover open sessions.
9. Join an existing named session from the web interface.
10. Dynamically launch a separate RetroArch + browser-streaming runtime for each joining player.
11. Automatically connect participating RetroArch runtimes using RetroArch Netplay over a private server-side network.
12. Hide all implementation details from users, including:
    - Docker/container runtime
    - ROM filesystem paths
    - RetroArch cores and configuration
    - IP addresses
    - Netplay ports
    - STUN/TURN configuration
    - WebRTC signaling
    - session/container identifiers
13. Cleanly terminate abandoned or completed sessions and remove their runtime resources.

The target user experience is:

```text
Open browser
    ↓
Sign in
    ↓
Browse RomM
    ↓
Select game
    ↓
Create Multiplayer Session
    ↓
Name: "Saturday Night SNES"
    ↓
Play in browser
```

For another user:

```text
Open browser
    ↓
Sign in
    ↓
Open Multiplayer Sessions
    ↓
Saturday Night SNES
Super Mario Kart
1 / 2 players
    ↓
Join
    ↓
Play in browser
```

---

# 2. Non-Negotiable Product Requirements

The following are architectural requirements, not future enhancements.

## 2.1 Browser-only client

Remote users must not be required to install:

- RetroArch
- RomM desktop clients
- Moonlight
- Parsec
- Tailscale
- WireGuard
- browser extensions
- native launcher applications

A modern browser is the client.

## 2.2 Internet-first networking

The architecture must function when users are:

- on different residential networks;
- behind NAT;
- behind carrier-grade NAT where TURN permits;
- on restrictive guest/hotel networks where TURN/TCP or TURN/TLS permits;
- geographically remote from the server.

LAN operation is useful for development but is not the final network assumption.

## 2.3 Centralized emulation

All emulator instances run on the server-side platform.

RetroArch-to-RetroArch Netplay traffic remains private to the server infrastructure.

Users receive only:

- browser UI;
- audio/video;
- controller/keyboard input.

## 2.4 Shared ROM library

The authoritative ROM library is centrally stored and mounted read-only into emulator runtimes.

The platform must never require the browser to upload the ROM used for a session.

## 2.5 Named discoverable sessions

A multiplayer session has:

- an internal UUID;
- a user-provided display name;
- an owner;
- a game;
- a platform;
- a core profile;
- current/max player count;
- state;
- creation and expiration timestamps.

The friendly name is never used as an internal security identifier or container name.

## 2.6 Authentication is centralized

Do not build custom password storage, password-reset logic, email OTP cryptography, OAuth, OIDC, or SAML implementations in this project.

Use an identity provider.

Initial identity provider: **authentik**.

RomM authenticates through authentik using OIDC.

Future enterprise identity can federate through authentik using OIDC or SAML without changing the multiplayer platform.

## 2.7 No public emulator runtimes

Individual RetroArch/Selkies containers must not expose arbitrary public host ports.

Public access occurs only through:

- the HTTPS edge proxy for web/signaling traffic;
- the controlled WebRTC/TURN path for media.

---

# 3. Selected Components

| Function | Selected component | Project responsibility |
|---|---|---|
| ROM library / metadata / primary UI | RomM | Upstream control plane |
| Identity / local auth / passwordless / federation | authentik | Upstream identity provider |
| Custom lobby/session orchestration | Retro Session Manager | **Build** |
| Privileged local container lifecycle | Runtime Agent | **Build** |
| Initial runtime provider | Docker Engine through Runtime Agent | Integrate |
| Optional future runtime provider | Wolf | Evaluate behind provider interface |
| Emulator | RetroArch | Upstream |
| Emulator cores | libretro cores | Upstream; pinned manifest |
| Browser streaming | Selkies | Upstream |
| Browser transport | WebRTC | Upstream standard / Selkies |
| STUN/TURN | coturn | Upstream |
| Ephemeral session state | Valkey | Upstream |
| Public reverse proxy | Traefik initially | Upstream; replaceable |
| ROM storage | Host/NAS filesystem | External infrastructure |
| Metrics later | Prometheus-compatible endpoint | Build/integrate |
| CI | GitHub Actions or equivalent | Project automation |

---

# 4. Why Wolf Is Optional, Not Mandatory

Wolf was originally considered the execution and streaming layer.

For the browser-only target, the Wolf server must not be placed in the critical path simply to translate or replace Moonlight.

Selkies already supplies the browser-facing functionality required by this project:

- HTML5 client;
- screen capture;
- H.264 encoding;
- Opus audio;
- browser keyboard/mouse/gamepad injection;
- WebRTC;
- secure orchestrated session tokens;
- reverse-proxy subfolder support.

Therefore the architecture defines an abstract execution provider.

```text
ExecutionProvider
    |
    +-- LocalRuntimeAgentProvider     ← initial implementation
    |
    +-- WolfExecutionProvider         ← optional evaluation
    |
    +-- KubernetesExecutionProvider   ← possible future scale-out
```

Wolf may still provide useful runtime or Games-on-Whales components. If a later milestone proves that Wolf adds concrete operational value without reintroducing Moonlight as a client requirement, implement it behind the provider boundary.

Do not architect the rest of the platform around Wolf-specific APIs.

---

# 5. Target Architecture

```text
                               INTERNET
                                  |
                         HTTPS / WSS / WebRTC
                                  |
                        +-------------------+
                        |    Edge Proxy     |
                        |     Traefik       |
                        +---------+---------+
                                  |
             +--------------------+--------------------+
             |                    |                    |
             v                    v                    v
        authentik                RomM             Selkies routes
        Identity               Control UI        /stream/{id}
             |                    |
             | OIDC               |
             +------------------->|
                                  |
                                  | private service API
                                  v
                       +------------------------+
                       | Retro Session Manager  |
                       |------------------------|
                       | Lobby Registry         |
                       | Participant Registry   |
                       | Core/Profile Resolver  |
                       | ROM Validation         |
                       | Netplay Coordinator    |
                       | Selkies Token Control  |
                       | Session Lifecycle      |
                       +-----------+------------+
                                   |
                         UNIX domain socket
                                   |
                                   v
                       +------------------------+
                       |     Runtime Agent      |
                       |------------------------|
                       | Docker lifecycle only  |
                       | GPU/device assignment  |
                       | Safe mount validation  |
                       | Network attachment     |
                       | Route publication      |
                       +-----------+------------+
                                   |
                             Docker socket
                                   |
                     +-------------+-------------+
                     |                           |
                     v                           v
             Participant Runtime A       Participant Runtime B
             +--------------------+       +--------------------+
Browser A <--| Selkies / WebRTC   |       | Selkies / WebRTC   |--> Browser B
             | RetroArch          |       | RetroArch          |
             | Core               |       | Core               |
             +---------+----------+       +----------+---------+
                       |                             |
                       +------ private retro-net ----+
                             RetroArch Netplay

                      +-----------------------------+
                      | Shared ROM library          |
                      | mounted read-only           |
                      +-----------------------------+

                              INTERNET
                                 |
                                 v
                         +---------------+
                         |    coturn     |
                         | STUN / TURN   |
                         +---------------+
                           ^           ^
                           |           |
                       Browser      Selkies
```

---

# 6. Network Planes

Treat the system as three independent planes.

## 6.1 Control plane

```text
Browser
   |
HTTPS 443
   |
authentik / RomM
   |
Retro Session Manager
```

Responsibilities:

- authentication;
- library browsing;
- lobby creation;
- discovery;
- join/leave;
- authorization;
- session status.

## 6.2 Stream plane

```text
Browser
   |
WebRTC signaling over HTTPS
   |
Selkies
   |
WebRTC media
   |
direct ICE when possible
or
coturn relay when required
```

No native client is required.

For the first public MVP, assume TURN is required and deploy it from the beginning.

Do not design the system such that successful gameplay depends on direct peer connectivity.

## 6.3 Emulator plane

```text
RetroArch A
    |
private Docker network
    |
RetroArch B
```

This network is never exposed to the Internet.

Because all emulator instances are centralized, RetroArch Netplay ports do not need public NAT or Internet firewall rules.

---

# 7. Browser Streaming Model

Each participating remote user gets an independent runtime.

```text
User A Browser
      |
   WebRTC
      |
Selkies A
      |
RetroArch A
      |
      | private Netplay
      |
RetroArch B
      |
Selkies B
      |
   WebRTC
      |
User B Browser
```

Do not use one shared desktop stream for all participants in the initial design.

This preserves:

- independent browser sessions;
- independent authorization;
- independent stream quality;
- clean player lifecycle;
- clean future geographic distribution;
- RetroArch's native deterministic Netplay behavior.

---

# 8. Participant Runtime Image

Build one project-owned runtime image:

```text
retro-session
```

Conceptually:

```text
+------------------------------------------------+
| retro-session                                  |
|------------------------------------------------|
| Selkies                                       |
|  - HTML5 client                               |
|  - WebRTC signaling                           |
|  - H.264 video                                |
|  - Opus audio                                 |
|  - browser gamepad injection                  |
|  - secure session token enforcement           |
|                                                |
| Virtual display / audio                       |
|                                                |
| RetroArch                                     |
|                                                |
| Pinned libretro core                          |
|                                                |
| project session-entrypoint                    |
+------------------------------------------------+
```

The project-owned code in this image should be small.

Prefer deriving from a pinned upstream Selkies image or reproducing an upstream-supported container recipe rather than rebuilding its display/capture/input stack from scratch.

Milestone 0 must inspect current Selkies image options, current licensing inventory, and stable tags/digests before selecting the base image.

Do not use floating `latest`, `main`, `master`, or `edge` tags in a production definition.

---

# 9. Runtime Inputs

A participant runtime must be created from structured configuration, never from arbitrary shell text supplied by a client.

Conceptual runtime spec:

```yaml
session_id: uuid
participant_id: uuid
user:
  id: canonical-user-id
  display_name: Player One

game:
  romm_id: 1234
  platform: snes
  canonical_path: /roms/snes/Game.sfc
  sha256: "..."
  content_crc: "..."

emulator:
  retroarch_version: "pinned"
  core_id: snes-profile
  core_path: /cores/core_libretro.so
  core_version: "pinned"
  core_sha256: "..."

netplay:
  role: host
  host: null
  port: 55435
  player_slot: 1

stream:
  subfolder: /stream/<participant-id>
  mode: webrtc
  fixed_width: 1280
  fixed_height: 720
  target_fps: 60

storage:
  rom_root: /roms
  save_root: /userdata
```

The exact schema should be formalized as a Pydantic model and versioned.

---

# 10. Selkies Security Model

Run Selkies in secure orchestrated mode.

Each participant runtime receives:

- a unique Selkies master token;
- a dynamically provisioned controller session token;
- explicit role and gamepad assignment.

Rules:

1. The Selkies master token is never sent to the browser.
2. The Session Manager is the only component allowed to manage Selkies client tokens.
3. The browser receives only a short-lived participant token.
4. Leaving, being kicked, expiration, or session closure revokes that token.
5. A token is scoped to one runtime/participant.
6. Sharing features supplied by Selkies should be disabled unless deliberately used by the platform.
7. Clipboard, file upload, command execution, microphone, webcam, and other unrelated remote-desktop features should be disabled for the gaming profile whenever current Selkies settings permit.
8. Restrict allowed browser origins to the public gaming origin.
9. Assign a unique Selkies URL subfolder to each participant:

```text
/stream/{participant_id}
```

10. Do not expose the raw Selkies container port publicly.

For the first MVP it is acceptable for a short-lived Selkies token to participate in the initial browser bootstrap URL if that is the current upstream secure-mode workflow, but:

- reverse-proxy access logs must not record query strings containing tokens;
- tokens must be short-lived;
- tokens must be immediately revocable;
- the architecture must leave room for a later one-time launch-ticket exchange that removes long-lived credentials from URLs.

---

# 11. TURN / Internet Connectivity

Deploy coturn as a first-class production component.

WebRTC signaling through HTTPS is not sufficient for reliable Internet media connectivity.

The platform should support:

- STUN;
- TURN/UDP;
- TURN/TCP;
- TURN/TLS where required.

Prefer UDP for latency.

TURN/TCP or TURN/TLS is fallback behavior for restrictive networks.

Use ephemeral HMAC TURN credentials generated from a shared TURN secret rather than permanent user/password credentials.

Do not expose the coturn shared secret to browsers.

Use a bounded relay port range sized and tested for expected concurrent sessions.

The exact public port plan is deployment-specific and must be documented in:

```text
docs/networking.md
```

Important deployment note:

If TURN/TLS must use TCP 443 for restrictive networks, it cannot simply share the same IP:port as the normal HTTPS reverse proxy unless a deliberate compatible Layer-4 multiplexing design or separate public IP is used.

Do not hide this constraint in automation.

---

# 12. Authentication Architecture

Initial identity provider: authentik.

```text
                         authentik
                             |
       +---------------------+---------------------+
       |                     |                     |
Local username/password  Email/passwordless   Future federation
                                                 |
                                           OIDC / SAML IdP
                                                 |
       +---------------------+---------------------+
                             |
                            OIDC
                             |
                            RomM
```

Do not add a second custom login database to the Session Manager.

Initial supported sign-in options should be:

1. authentik local user/password;
2. email-based passwordless flow or one-time authentication after SMTP is configured.

Future:

- Microsoft Entra ID;
- Google;
- another OIDC IdP;
- SAML IdP;
- other authentik-supported sources.

RomM continues to consume OIDC regardless of upstream identity source.

Maintain one documented emergency local administrative access path.

---

# 13. User Identity Mapping

Use stable internal identifiers.

Conceptual mapping:

```text
authentik subject
       |
       v
RomM user
       |
       v
Session Manager user identity
       |
       +--> session owner
       +--> participant
       +--> save-data namespace
```

Do not use email address as the database primary key.

Email can change.

Use the stable OIDC subject / mapped RomM user identifier.

---

# 14. Privileged Runtime Boundary

The Retro Session Manager must **not** mount `/var/run/docker.sock`.

Create a separate project service:

```text
runtime-agent
```

The Runtime Agent is the only custom component allowed direct Docker Engine control.

Initial communication:

```text
Session Manager
      |
UNIX domain socket
      |
Runtime Agent
      |
Docker socket
```

The Runtime Agent API must be intentionally narrow.

Permitted conceptual actions:

```text
create_runtime(spec)
inspect_runtime(runtime_id)
stop_runtime(runtime_id)
remove_runtime(runtime_id)
list_managed_runtimes()
health()
```

It must not expose a generic:

```text
run_any_container(command)
```

or:

```text
docker_api_proxy()
```

The Runtime Agent validates all:

- image names;
- image digests;
- volume mount roots;
- network names;
- environment variable keys;
- device requests;
- resource limits;
- labels;
- container naming.

Only project-approved images may launch.

Only project-approved filesystem roots may mount.

Future multi-host runtime agents may use mutually authenticated TLS, but the first single-host implementation should use a UNIX socket.

---

# 15. Reverse Proxy / Stream Routing

Initial edge proxy: Traefik.

Do not give Traefik the Docker socket merely for convenience.

Preferred initial route model:

1. Runtime Agent creates a participant runtime.
2. Runtime Agent publishes a restricted dynamic route file in a shared route-config directory.
3. Traefik watches that directory using its file provider.
4. Route:

```text
/stream/{participant-id}
```

maps only to the matching private Selkies runtime.
5. Runtime removal also removes the route.
6. Route files are generated from templates, not arbitrary user input.

Keep routing behind an abstraction:

```text
RouteProvider
    |
    +-- TraefikFileProvider
    |
    +-- FutureNginxProvider
```

The session display name is never used in a route.

---

# 16. Shared Storage

ROM storage:

```text
/storage/roms
```

Runtime mount:

```text
/roms:ro
```

Rules:

- read-only in all participant containers;
- never included in Git;
- never copied into Docker images;
- never placed into CI artifacts;
- never supplied by a browser path;
- canonicalize all resolved paths;
- reject path traversal;
- reject symlink escape outside approved roots.

Persistent per-user data can eventually use:

```text
/storage/users/{stable-user-id}/
```

but save-state persistence is not a prerequisite for the first multiplayer MVP.

---

# 17. ROM Resolution Trust Model

A public browser request must never contain an authoritative filesystem path.

Bad:

```json
{
  "rom_path": "/etc/passwd"
}
```

Correct:

```text
Browser
   |
RomM ROM ID
   |
RomM backend resolves canonical game
   |
private trusted integration request
   |
Session Manager verifies approved ROM root
   |
Runtime Agent receives already-validated runtime spec
```

The Session Manager should independently verify:

- canonical path;
- approved root;
- expected extension/profile;
- file existence;
- ROM hash where required.

---

# 18. RetroArch Netplay Model

Use RetroArch Netplay for synchronization between centralized emulator runtimes.

The Session Manager is the authoritative lobby registry.

Do not depend on RetroArch LAN broadcast discovery.

Host:

```text
RetroArch A
NETPLAY_ROLE=host
```

Joiner:

```text
RetroArch B
NETPLAY_ROLE=client
NETPLAY_HOST=<private host runtime>
```

All participants must use the exact project-pinned:

- RetroArch version;
- core version;
- core artifact/hash;
- game content/hash.

The platform must verify these inputs before marking a participant ACTIVE.

---

# 19. Core Profiles

Do not scatter console-specific conditionals throughout orchestration code.

Create a versioned Core/Profile Registry.

Example conceptual structure:

```yaml
profiles:
  nes-default:
    platform: nes
    core: mesen
    max_players: 2
    netplay: true
    core_sha256: "..."
    license_reviewed: true

  snes-default:
    platform: snes
    core: snes9x
    max_players: 4
    netplay: true
    multitap_supported: true
    core_sha256: "..."
    license_reviewed: true

  genesis-default:
    platform: genesis
    core: genesis_plus_gx
    max_players: 4
    netplay: true
    core_sha256: "..."
    license_reviewed: true
```

The values above are conceptual until Milestone 0 verifies the chosen current cores and their licenses.

Never assume all libretro cores use RetroArch's license.

The manifest must record:

- project;
- source repository;
- version/tag;
- commit;
- artifact SHA-256;
- license;
- redistribution notes;
- commercial-use restrictions if any;
- platform;
- Netplay validation status.

If the platform ever becomes commercial, perform a new core-license review before launch.

---

# 20. Session Domain Model

## 20.1 Session

```text
session_id
display_name
owner_user_id
romm_rom_id
platform
rom_sha256
core_profile_id
max_players
state
created_at
updated_at
expires_at
```

Suggested session states:

```text
CREATING
   |
STARTING
   |
OPEN
   |
RUNNING
   |
DRAINING
   |
CLOSED

Any state -> ERROR
```

## 20.2 Participant

```text
participant_id
session_id
user_id
display_name
player_slot
runtime_id
stream_path
state
joined_at
last_heartbeat
```

Suggested participant states:

```text
ALLOCATING
    |
STARTING
    |
STREAM_READY
    |
NETPLAY_CONNECTING
    |
ACTIVE
    |
LEAVING
    |
LEFT

Any state -> ERROR
```

## 20.3 Names

Friendly session names:

- are user-provided;
- have a reasonable length limit;
- are escaped in UI;
- are never shell input;
- are never container names;
- are never filesystem paths;
- are never authorization keys.

The UUID is authoritative.

---

# 21. State Store

Use **Valkey** for initial ephemeral state.

Reasons:

- appropriate for leases/TTL;
- fast session lookup;
- distributed locks;
- straightforward expiration;
- permissive BSD-style upstream licensing.

Initial stored data:

- active sessions;
- participants;
- leases;
- idempotency keys;
- session locks;
- runtime mappings;
- short-lived handoff metadata.

Do not share RomM's database.

Do not make the Session Manager dependent on RomM database internals.

A relational database may be added later if durable session history, auditing, analytics, or recovery requirements justify it.

For early milestones, a Session Manager restart may intentionally invalidate active sessions and trigger managed-runtime cleanup. Document this behavior rather than pretending transparent recovery exists.

---

# 22. Public and Private API Boundaries

## 22.1 Browser

The browser should primarily call RomM.

Avoid making the Session Manager a separately exposed public API for MVP.

RomM integration endpoints:

```text
POST   /api/multiplayer/sessions
GET    /api/multiplayer/sessions
GET    /api/multiplayer/sessions/{id}
POST   /api/multiplayer/sessions/{id}/join
POST   /api/multiplayer/sessions/{id}/leave
DELETE /api/multiplayer/sessions/{id}
POST   /api/multiplayer/participants/{id}/launch
```

Exact RomM routes should follow current RomM conventions discovered during the integration milestone.

## 22.2 RomM → Session Manager

Private API, versioned:

```text
POST   /v1/sessions
GET    /v1/sessions
GET    /v1/sessions/{id}
POST   /v1/sessions/{id}/join
POST   /v1/sessions/{id}/leave
DELETE /v1/sessions/{id}
POST   /v1/participants/{id}/stream-token
GET    /healthz
GET    /readyz
```

Authenticate service-to-service requests.

Initial deployment may use a high-entropy shared service credential on a private network.

Plan for mTLS if services become multi-host.

## 22.3 Session Manager → Runtime Agent

UNIX-socket API only for initial deployment.

## 22.4 Session Manager → Selkies

Private network/API using each runtime's master token.

## 22.5 Browser → Selkies

Only via edge proxy path and participant session token.

---

# 23. Repository Strategy

Do not build this as a monolithic RomM fork.

Use separate repositories.

Recommended workspace:

```text
retro-platform-workspace/
|
├── retro-browser-multiplayer/      # primary original project
|
├── romm/                            # our RomM fork
|
└── upstream-reference/             # optional local read-only clones,
    ├── selkies/                     # ignored by primary Git repo
    ├── retroarch/
    └── wolf/
```

Use a VS Code multi-root workspace to open the primary repository and the RomM fork together.

Do not use Git submodules merely to make upstream source visible to Codex.

Reference checkouts should be treated as upstream source, not project-owned source.

---

# 24. Primary Repository Layout

```text
retro-browser-multiplayer/
|
├── PROJECT.md
├── AGENTS.md
├── README.md
├── LICENSE
├── UPSTREAMS.md
├── THIRD_PARTY_NOTICES.md
├── SECURITY.md
├── CONTRIBUTING.md
├── .editorconfig
├── .gitignore
├── .env.example
|
├── docs/
│   ├── architecture.md
│   ├── authentication.md
│   ├── networking.md
│   ├── security-boundaries.md
│   ├── open-source-policy.md
│   ├── core-profiles.md
│   ├── development.md
│   ├── deployment.md
│   ├── testing.md
│   ├── troubleshooting.md
│   ├── api/
│   ├── runbooks/
│   └── adr/
│       ├── 0001-browser-native-client.md
│       ├── 0002-romm-control-plane.md
│       ├── 0003-selkies-streaming.md
│       ├── 0004-runtime-agent-boundary.md
│       ├── 0005-valkey-session-state.md
│       ├── 0006-authentik-identity.md
│       ├── 0007-turn-required-for-public-mvp.md
│       └── 0008-wolf-optional-provider.md
|
├── services/
│   ├── session-manager/
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   │   └── retro_sessions/
│   │   │       ├── api/
│   │   │       ├── models/
│   │   │       ├── repositories/
│   │   │       ├── services/
│   │   │       ├── providers/
│   │   │       │   ├── execution/
│   │   │       │   ├── streaming/
│   │   │       │   ├── romm/
│   │   │       │   └── state/
│   │   │       ├── retroarch/
│   │   │       ├── security/
│   │   │       └── observability/
│   │   └── tests/
│   │
│   └── runtime-agent/
│       ├── pyproject.toml
│       ├── src/
│       │   └── retro_runtime/
│       │       ├── api/
│       │       ├── docker/
│       │       ├── validation/
│       │       ├── routes/
│       │       └── models/
│       └── tests/
|
├── images/
│   └── retro-session/
│       ├── Dockerfile
│       ├── entrypoint/
│       ├── config/
│       └── manifests/
│           └── cores.yaml
|
├── infra/
│   ├── compose/
│   │   ├── README.md
│   │   └── acceptance/             # milestone proof and regression layouts
│   ├── traefik/
│   │   ├── static/
│   │   └── dynamic/
│   ├── coturn/
│   ├── authentik/
│   ├── valkey/
│   └── scripts/
|
├── tests/
│   ├── integration/
│   ├── e2e/
│   ├── network/
│   └── fixtures/
|
└── tools/
    ├── verify-upstreams/
    ├── license-audit/
    └── test-roms/
```

---

# 25. Open-Source Code Reuse Policy

This project should aggressively reuse upstream functionality while minimizing copied upstream source.

## 25.1 General rule

Preferred order:

```text
1. Use upstream service/API unchanged.
2. Configure upstream image/package.
3. Derive a thin image from upstream.
4. Add an adapter around upstream API.
5. Submit generic fixes upstream.
6. Maintain a small upstream fork only when necessary.
7. Copy source into this repository only as a documented last resort.
```

## 25.2 Never casually copy repositories

Do not copy complete RomM, Selkies, Wolf, RetroArch, or libretro source trees into the primary repository.

Do not ask Codex to "copy the useful parts" of another project.

## 25.3 If a small upstream code fragment must be copied

Before copying:

1. identify exact source project;
2. identify source file;
3. identify upstream commit;
4. verify license;
5. preserve required copyright/license notices;
6. record the copy in `THIRD_PARTY_NOTICES.md`;
7. document why an API/dependency/fork was insufficient;
8. isolate the copied code;
9. avoid silently rewriting it until provenance is lost.

## 25.4 Upstream modifications

If RomM must change:

- change the separate RomM fork;
- retain its license and notices;
- keep official RomM as `upstream`;
- keep our delta small;
- prefer generic extension points that can be proposed upstream.

If Selkies must change:

- fork Selkies separately;
- preserve MPL-2.0 requirements on modified Selkies files;
- submit generic fixes upstream when reasonable;
- consume the pinned forked image/package from our main project.

If Wolf must change:

- use a separate fork;
- submit reusable changes upstream;
- do not paste Wolf code into Session Manager.

Do not modify RetroArch unless a proven upstream limitation requires it.

---

# 26. Current License Assumptions

Milestone 0 must re-check these against the exact versions selected.

Current architectural assumptions:

| Component | Current license assumption |
|---|---|
| RomM | AGPL-3.0 |
| Selkies | MPL-2.0, with additional dependency/image licensing to review |
| coturn | BSD-3-Clause |
| authentik core | predominantly MIT with separately licensed portions/enterprise code |
| Valkey | BSD-3-Clause with component exceptions |
| RetroArch | GPL family; verify selected release |
| libretro cores | core-specific; must be individually reviewed |
| Wolf | MIT; verify if used |

Do not treat this table as legal advice or as a substitute for inspecting the exact upstream release.

The main project's original code should use **Apache-2.0 by default** unless the owner deliberately selects another license before Milestone 0 closes.

Do not mix RomM AGPL source into the Apache-licensed Session Manager repository.

Service/API integration is the preferred boundary.

---

# 27. UPSTREAMS.md Required Format

Every material upstream dependency must record:

```text
Project:
Purpose:
Canonical repository:
License:
Selected release/tag:
Selected commit:
Container/package:
Container digest:
Date verified:
Modification status:
Local fork:
Upstream issue/PR:
Security notes:
Update notes:
```

Container images must be pinned by digest in production definitions.

---

# 28. Dependency Update Policy

Never upgrade major runtime components casually.

For every update:

```text
Read release notes
      ↓
Review security advisories
      ↓
Verify license has not changed materially
      ↓
Update pinned test environment
      ↓
Run unit tests
      ↓
Run integration tests
      ↓
Run browser streaming test
      ↓
Run Internet TURN test
      ↓
Run two-player Netplay test
      ↓
Update UPSTREAMS.md
      ↓
Promote
```

Do not use automatic dependency bots to merge runtime image changes without integration testing.

---

# 29. Git and Branch Management

Primary branch:

```text
main
```

Recommended branch naming:

```text
milestone/00-foundation
milestone/01-selkies-retroarch
feature/session-state-machine
fix/runtime-cleanup
chore/update-selkies
```

Rules:

- one milestone or logically related change per branch;
- atomic commits;
- no giant "implement multiplayer" commit;
- no unrelated refactors during feature work;
- never force-push shared main;
- never commit secrets;
- never commit ROMs or BIOS files;
- never commit generated runtime route files;
- never commit active session tokens;
- never commit `.env`;
- do not let Codex commit or push unless explicitly requested.

Suggested commit style:

```text
feat(session): add lobby state model
feat(runtime): add validated container creation
test(netplay): add two-runtime harness
docs(adr): record Selkies secure-mode decision
fix(stream): revoke token during participant leave
```

---

# 30. Codex Working Rules

Create `AGENTS.md` during Milestone 0.

Minimum required content:

```text
# Project Rules

Read PROJECT.md before changing code.

The browser-only Internet client is a hard requirement.

RomM owns library UI and user-facing control-plane integration.
authentik owns authentication.
Session Manager owns lobby/session orchestration.
Runtime Agent owns privileged container lifecycle.
Selkies owns browser streaming.
RetroArch owns emulation and Netplay.
coturn owns STUN/TURN.

Do not move responsibilities across these boundaries without an ADR.

Never expose Docker socket to Session Manager or public services.

Never accept an arbitrary ROM path from a browser.

Never copy large upstream source files into this repository.

Never copy RomM AGPL code into the independently licensed Session Manager.

Use an upstream API/configuration/derived image before creating replacement code.

Do not place ROMs or BIOS images in Git, Docker images, tests, CI artifacts, or examples.

Pin runtime dependencies and container images.

Before implementing:
1. read PROJECT.md;
2. inspect existing code;
3. inspect relevant current upstream documentation/source;
4. summarize existing behavior;
5. identify the smallest correct change;
6. add/update tests;
7. implement;
8. run checks;
9. update docs/ADR when architecture changes.

Do not perform unrelated refactoring.

Do not silently change architecture.

A task is complete only when:
- tests pass;
- lint/type checks pass;
- security boundaries remain intact;
- documentation is updated where necessary;
- no secrets or ROM content are added;
- final output states what changed and what remains.
```

---

# 31. Development Standards

Initial custom services:

- Python 3 current supported stable release selected in Milestone 0;
- FastAPI;
- Pydantic;
- async HTTP client where appropriate;
- Valkey client;
- Docker SDK only inside Runtime Agent.

Quality:

```text
ruff
mypy
pytest
coverage
```

Formatting and lint should run locally and in CI.

Public API models must be typed.

Avoid untyped dictionaries for domain state.

Use structured JSON logging.

Use UTC timestamps internally.

Use UUIDs for session/participant/runtime identifiers.

---

# 32. Security Rules

## 32.1 Secrets

Use environment/secrets files only for local development.

Production secrets should use a proper secret mechanism appropriate to deployment.

Never log:

- OIDC client secrets;
- SMTP passwords;
- Selkies master tokens;
- Selkies participant tokens;
- TURN shared secrets;
- TURN generated passwords;
- service API credentials.

## 32.2 Containers

Participant runtimes must:

- run with minimum privileges;
- use approved image digests only;
- mount ROMs read-only;
- receive only required devices;
- have resource limits;
- use private networks;
- not mount Docker socket;
- not mount host root;
- not receive host SSH keys;
- not receive Session Manager credentials.

## 32.3 Runtime Agent

Runtime Agent is privileged and must:

- listen only on UNIX socket initially;
- enforce allowlists;
- reject arbitrary images;
- reject arbitrary mount roots;
- reject arbitrary host networking;
- reject privileged containers unless an ADR documents a proven requirement;
- label every managed runtime;
- clean only project-managed resources.

## 32.4 Web

Use:

- TLS;
- secure cookies;
- CSRF protections consistent with RomM/authentik;
- strict origin policy;
- CSP where compatible;
- session authorization on every create/join/leave operation;
- rate limiting on session creation and authentication endpoints;
- no internal runtime addresses in browser APIs.

---

# 33. Observability Contract

All custom service logs should include applicable correlation fields:

```text
request_id
session_id
participant_id
user_id
runtime_id
romm_rom_id
core_profile_id
```

Never include authentication secrets.

Metrics later:

```text
active_sessions
active_participants
session_create_total
session_create_failures_total
runtime_start_seconds
stream_ready_seconds
netplay_connect_seconds
participant_disconnect_total
turn_relay_sessions
direct_webrtc_sessions
orphan_runtime_cleanup_total
session_expiration_total
```

---

# 34. Test ROM Policy

Use only legally redistributable test content in source control and CI.

Preferred:

- purpose-built homebrew;
- public-domain ROMs;
- synthetic emulator test ROMs with explicit redistribution rights.

Record provenance/license for every test ROM in:

```text
tools/test-roms/README.md
```

Never substitute a commercial ROM just because it is convenient.

---

# 35. Milestone 0 — Foundation, Licensing, and Repository

## Goal

Establish boundaries before functional coding.

## Tasks

- create primary Git repository;
- create separate RomM fork;
- configure RomM remotes:
  - `origin` = our fork;
  - `upstream` = official RomM;
- create VS Code multi-root workspace;
- create repository tree;
- create:
  - `PROJECT.md`;
  - `AGENTS.md`;
  - `README.md`;
  - `UPSTREAMS.md`;
  - `THIRD_PARTY_NOTICES.md`;
  - `SECURITY.md`;
  - ADR directory;
- select project license;
- verify current upstream licenses;
- verify current stable RomM;
- verify current stable Selkies;
- inspect Selkies secure-mode implementation;
- inspect current Selkies container/image licensing options;
- verify current RetroArch release;
- identify candidate NES core;
- identify candidate SNES core;
- identify candidate Genesis core;
- record current core licenses;
- verify authentik OIDC integration path with current RomM;
- verify coturn TURN shared-secret support;
- verify current Valkey release/license;
- establish Python tooling;
- create empty custom-service packages;
- create CI skeleton.

## No feature code

Do not implement:

- lobby logic;
- Docker launching;
- RomM buttons;
- WebRTC orchestration.

## Exit criteria

Codex can answer from project files:

- what code is ours;
- what code is upstream;
- which repos may be forked;
- where AGPL code belongs;
- how Selkies is consumed;
- what the privileged boundary is;
- how dependencies are pinned;
- what current licenses apply.

All empty service skeleton checks pass.

---

# 36. Milestone 1 — Single Selkies Browser Stream

## Goal

Prove the browser streaming technology before adding RetroArch orchestration.

## Tasks

Launch one upstream-supported Selkies environment.

Verify from a browser:

- HTML5 client loads;
- H.264 video works;
- audio works;
- keyboard input works;
- gamepad input works;
- secure mode can be enabled;
- reverse proxy subfolder works;
- fixed virtual resolution works;
- hardware encoder works if target host has supported hardware;
- software fallback behavior is documented.

Use LAN initially for this milestone.

## Exit criteria

A browser can control a Linux graphical application through Selkies with no client software installed.

---

# 37. Milestone 2 — RetroArch Inside Selkies

## Goal

Prove one legal test ROM can be played completely inside a browser.

## Tasks

Build first thin `retro-session` image.

Requirements:

- derive from pinned upstream components;
- install/use pinned RetroArch;
- install one pinned NES core;
- mount test ROM read-only;
- launch directly into RetroArch;
- browser gamepad controls RetroArch;
- video/audio stream correctly;
- no desktop interaction required;
- fixed 1280x720/60 test profile initially;
- document exact encoder path;
- log RetroArch/core versions and hashes.

Disable unrelated Selkies features where practical.

## Exit criteria

```text
Browser
   |
Selkies
   |
RetroArch
   |
NES test ROM
```

works reliably.

---

# 38. Milestone 3 — Public Internet WebRTC + coturn

## Goal

Prove the browser-native session works from an off-site Internet connection.

This milestone occurs before Session Manager development.

## Tasks

Deploy:

- HTTPS reverse proxy;
- public test hostname;
- coturn;
- STUN/TURN configuration;
- Selkies WebRTC mode.

Test:

- direct ICE where available;
- TURN/UDP;
- TURN/TCP fallback;
- TURN/TLS if deployment supports it;
- browser behind residential NAT;
- second off-site network;
- reconnect;
- controller input;
- audio/video stability.

Record:

- ICE path selected;
- TURN relay behavior;
- bitrate;
- frame rate;
- observed latency;
- failure modes.

Do not declare success based only on the page loading.

The game must be controllable remotely.

## Exit criteria

An off-site user with only a browser can play the single NES test game.

---

# 39. Milestone 4 — Deterministic Runtime Launcher

## Goal

Turn the manually configured browser emulator into a repeatable participant runtime.

## Build

Project-owned `session-entrypoint`.

Inputs:

- session ID;
- participant ID;
- ROM path;
- expected ROM hash;
- core profile;
- player name;
- Netplay role;
- Netplay host;
- Netplay port;
- Selkies configuration;
- fixed display profile.

Validation:

- ROM must resolve inside approved root;
- expected ROM hash must match;
- core must exist in approved manifest;
- core hash must match;
- arbitrary command arguments are rejected;
- no shell interpolation from user-provided strings.

Generate per-session RetroArch configuration.

Do not dynamically download cores at runtime.

## Exit criteria

The same image can deterministically launch different approved games/configurations from a typed runtime spec.

---

# 40. Milestone 5 — Two Browser Runtimes + RetroArch Netplay

## Goal

Prove the core multiplayer architecture manually before building orchestration.

Launch two participant runtimes.

```text
Browser A
   |
Selkies A
   |
RetroArch A (host)
      |
      | private retro-net
      |
RetroArch B (client)
   |
Selkies B
   |
Browser B
```

Requirements:

- same RetroArch build;
- same core build;
- same ROM hash;
- private Docker network;
- no LAN broadcast discovery;
- client receives host address through config;
- two physical controllers;
- two separate browsers;
- stable game synchronization;
- clean shutdown.

Test both browsers:

- on LAN;
- then remotely through Internet/TURN.

## Exit criteria

Two remote browser-only users can control two server-side RetroArch instances participating in one Netplay game.

This is the project's primary technical proof.

Do not begin deep RomM UI work before this milestone passes.

---

# 41. Milestone 6 — Runtime Agent

## Goal

Remove manual Docker operations without exposing Docker privileges to the Session Manager.

## Build

`services/runtime-agent`

UNIX socket API.

Implement:

```text
create_runtime
inspect_runtime
stop_runtime
remove_runtime
list_managed_runtimes
health
```

Runtime creation is based only on a typed, allowlisted spec.

Enforce:

- approved image digest;
- approved networks;
- approved ROM root;
- approved user-data root;
- approved GPU/device model;
- container resource limits;
- project labels;
- generated container name;
- no arbitrary command;
- no arbitrary mounts.

Add route publication/removal through `RouteProvider`.

## Tests

- invalid image rejected;
- invalid mount rejected;
- traversal rejected;
- host network rejected;
- unmanaged container cannot be removed;
- duplicate runtime request idempotency;
- orphan list detection.

## Exit criteria

A local API call over UNIX socket can safely create and remove the same participant runtime proven in Milestone 5.

---

# 42. Milestone 7 — Session Manager Skeleton

## Goal

Implement the platform's original control logic without RomM coupling.

## Build

`services/session-manager`

Use:

- FastAPI;
- Pydantic;
- Valkey;
- provider interfaces.

Implement domain models and state machines.

Interfaces:

```text
ExecutionProvider
StreamProvider
RouteProvider
RomMProvider
SessionRepository
CoreRegistry
```

Use fake providers for unit tests.

API:

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

No real Runtime Agent call required until fake-path tests pass.

## Exit criteria

Automated tests prove:

- create;
- discover;
- join;
- leave;
- close;
- expiration;
- capacity enforcement;
- duplicate join handling;
- owner authorization;
- session name validation.

---

# 43. Milestone 8 — Real Runtime Orchestration

## Goal

Connect Session Manager to Runtime Agent.

Flow:

```text
Create Session
     |
Session Manager
     |
Runtime Agent
     |
Participant runtime
     |
Selkies ready
     |
RetroArch ready
```

Then Join:

```text
Join
 |
Session Manager
 |
Runtime Agent
 |
second runtime
 |
RetroArch client config
 |
Netplay connect
```

Requirements:

- runtime readiness probe;
- startup timeout;
- Netplay connect timeout;
- idempotent operations;
- failed startup cleanup;
- max player capacity;
- private host address never returned to browser.

## Exit criteria

Two API calls:

```text
create
join
```

produce the complete two-browser Netplay topology with no manual Docker or RetroArch configuration.

---

# 44. Milestone 9 — Selkies Secure Session Orchestration

## Goal

Make browser stream access participant-specific and revocable.

For each runtime:

1. create unique Selkies master token;
2. keep it server-side only;
3. provision controller token for assigned participant;
4. configure gamepad slot;
5. return only browser-safe short-lived launch information;
6. revoke on leave;
7. revoke on kick;
8. revoke on session close;
9. revoke on lease expiry.

Disable upstream Selkies sharing shortcuts unless intentionally exposed through our authorization model.

Configure:

- allowed origins;
- subfolder;
- WebRTC mode;
- TURN configuration;
- minimal UI controls.

## Exit criteria

Knowing another participant's stream URL without a valid token does not grant gameplay access.

Revocation disconnects access.

---

# 45. Milestone 10 — Session Lifecycle and Cleanup

## Goal

Make the system trustworthy before integrating it into RomM.

Implement:

- participant heartbeat;
- lobby lease;
- idle timeout;
- maximum session lifetime;
- abandoned host handling;
- orphan runtime cleanup;
- route cleanup;
- token revocation;
- duplicate operation protection;
- startup reconciliation.

Initial restart policy may be:

```text
Session Manager starts
     |
query Runtime Agent for project-managed runtimes
     |
terminate stale runtimes
     |
clear expired Valkey state
```

Document any gameplay interruption.

Do not pretend live session restoration exists until it is explicitly built and tested.

## Exit criteria

Killing:

- browser;
- RetroArch;
- Selkies;
- participant container;
- Session Manager

does not leave indefinite unauthorized streams or unmanaged containers.

---

# 46. Milestone 11 — authentik + RomM OIDC

## Goal

Establish final identity architecture before public multiplayer UI.

Deploy authentik.

Configure:

- local admin;
- local test users;
- SMTP;
- email passwordless/OTP flow;
- OIDC provider for RomM.

Validate stable identity mapping.

Do not modify Session Manager to validate passwords.

## Exit criteria

Two distinct users can authenticate to RomM through authentik and retain stable user identities.

---

# 47. Milestone 12 — Minimal RomM Integration

## Goal

Turn RomM into the web control plane without embedding orchestration logic inside RomM.

Use a separate RomM fork.

Add the smallest extension necessary to:

- create multiplayer session for current ROM;
- list sessions;
- join;
- leave;
- close if authorized;
- open participant browser player.

RomM should not learn:

- Docker;
- coturn internals;
- RetroArch command lines;
- private IPs;
- Netplay ports;
- Selkies master tokens.

The RomM backend resolves the selected ROM using its normal trusted model and passes only validated game metadata through the private integration boundary.

Prefer generic concepts such as:

```text
External Multiplayer Session Provider
```

over project-specific hardcoding where feasible.

Generic extension points should be considered for upstream contribution.

## Exit criteria

From a RomM game page, an authenticated user can create a session that launches the proven backend topology.

---

# 48. Milestone 13 — Named Lobby UX + Embedded Browser Player

## Goal

Deliver the intended product UX.

Game page:

```text
[ Play ]

[ Create Multiplayer Session ]
```

Dialog:

```text
Session name
[ Saturday Night SNES ]

Players
[ 2 ]

[ Create ]
```

Lobby list:

```text
OPEN MULTIPLAYER SESSIONS

Saturday Night SNES
Super Mario Kart
Player One
1 / 2

[ Join ]
```

Player view:

```text
+---------------------------------------+
| Saturday Night SNES                   |
| Super Mario Kart                      |
|                                       |
|          browser game canvas          |
|                                       |
+---------------------------------------+
| Connected | Controller 1 | Leave      |
+---------------------------------------+
```

Do not expose:

- container names;
- private addresses;
- core filenames;
- Netplay ports;
- TURN credentials;
- Selkies administration controls.

## Exit criteria

A nontechnical remote user can authenticate, find a game, create/join, and play without seeing infrastructure concepts.

---

# 49. Milestone 14 — Remote Two-User MVP

## Goal

Validate the full platform outside the development network.

Environment:

- public HTTPS RomM/authentik;
- private Session Manager;
- private Runtime Agent;
- public coturn;
- two unrelated Internet clients.

Scenario:

1. User A signs in.
2. User B signs in.
3. User A opens supported NES game.
4. User A creates "Contra Night".
5. Runtime A launches.
6. Browser A streams game.
7. User B discovers session.
8. User B joins.
9. Runtime B launches.
10. RetroArch B automatically joins A.
11. Both controllers function.
12. Either player can leave.
13. Host closes lobby.
14. stream tokens revoke.
15. runtimes terminate.
16. routes disappear.
17. no orphan state remains.

## MVP definition

Do not call the project MVP until all 17 steps pass.

---

# 50. Milestone 15 — SNES

Add a verified SNES core profile.

Test:

- two-player;
- multitap where supported;
- three/four players;
- controller slot mapping;
- Internet/TURN;
- reconnect;
- cleanup.

Console-specific behavior belongs in the profile layer.

Do not add SNES-specific conditionals to generic orchestration unless unavoidable.

---

# 51. Milestone 16 — Genesis / Mega Drive

Repeat the profile-based implementation.

Test:

- two-player;
- supported multitap modes where applicable;
- core licensing;
- Netplay stability;
- browser controller mapping;
- public Internet sessions.

---

# 52. Milestone 17 — Persistence

After multiplayer is stable, add user persistence deliberately.

Potential:

- SRAM;
- memory card equivalents;
- RetroArch config preferences;
- save-state policy.

Define ownership semantics.

For multiplayer sessions, explicitly decide whether:

- host save is authoritative;
- each participant maintains separate save data;
- saves are disabled for certain multiplayer profiles.

Do not allow concurrent runtimes to corrupt the same writable save file.

---

# 53. Milestone 18 — Observability and Operations

Add:

- Prometheus-compatible metrics;
- dashboards;
- structured error events;
- session-level diagnostics;
- TURN usage visibility;
- WebRTC statistics;
- runtime capacity.

Create runbooks:

```text
stream-will-not-connect.md
turn-relay-failure.md
controller-not-detected.md
netplay-hash-mismatch.md
orphan-runtime.md
auth-login-failure.md
gpu-encoder-exhaustion.md
```

---

# 54. Milestone 19 — Production Hardening

Before wider Internet exposure:

- security review;
- dependency scan;
- container image scan;
- SBOM;
- secret rotation procedures;
- CSP review;
- rate limiting;
- request limits;
- audit events;
- backup of configuration/state that matters;
- restore test;
- SMTP abuse controls;
- TURN abuse controls;
- session quotas;
- per-user quotas;
- runtime CPU/memory limits;
- encoder-capacity limits;
- public source/license obligations for modified RomM;
- vulnerability response process.

---

# 55. Performance Testing

Do not choose acceptable latency by assumption.

Measure.

For each test session capture:

- browser-to-server RTT;
- ICE candidate type;
- TURN/direct;
- video bitrate;
- encoded FPS;
- decoded FPS;
- packet loss;
- jitter;
- stream startup time;
- Netplay connection time;
- user-perceived controller responsiveness.

Use Linux network emulation later to test:

```text
20 ms RTT
50 ms RTT
100 ms RTT
jitter
packet loss
bandwidth constraints
```

Keep each performance test repeatable.

---

# 56. Browser Test Matrix

Initial priority:

1. Chromium/Chrome desktop;
2. Edge desktop;
3. Firefox desktop.

Test at minimum:

- Windows;
- macOS where available;
- controller connected before page load;
- controller connected after page load;
- fullscreen;
- browser tab focus loss;
- disconnect/reconnect.

Safari/mobile support is not an initial MVP requirement unless proven inexpensive.

Do not claim browser support that has not been tested.

---

# 57. CI/CD Requirements

Every pull request for custom code should run:

## Python

```text
ruff check
ruff format --check
mypy
pytest
```

## Containers

- build runtime image;
- lint Dockerfiles;
- vulnerability scan;
- generate/record SBOM later.

## Security

- secret scan;
- dependency vulnerability scan;
- no ROM/BIOS extensions in tracked changes except explicitly licensed test fixtures.

## Licensing

- dependency license inventory;
- fail on unknown/disallowed license according to project policy.

## RomM fork

Run:

- upstream RomM test/lint requirements;
- multiplayer integration tests;
- regression test showing normal RomM behavior remains functional.

---

# 58. Integration Test Layers

## Layer 1 — Unit

No containers required.

Test:

- state machines;
- path validation;
- profile selection;
- authorization;
- quotas;
- token lifecycle;
- route templates;
- runtime spec validation.

## Layer 2 — Fake providers

```text
Session Manager
Valkey
Fake Runtime Agent
Fake Selkies
```

Test orchestration.

## Layer 3 — Runtime integration

```text
Session Manager
Runtime Agent
Docker
Selkies
RetroArch
```

Use legal test ROM.

## Layer 4 — Netplay

Two full participant runtimes.

## Layer 5 — Public WebRTC

One and then two off-site browsers through coturn.

## Layer 6 — Full RomM E2E

```text
authentik
RomM
Session Manager
Runtime Agent
Valkey
Traefik
coturn
Selkies A/B
RetroArch A/B
```

---

# 59. Failure Tests

Explicitly test:

- invalid ROM ID;
- ROM path escape;
- modified ROM hash;
- wrong core hash;
- unsupported platform;
- full lobby;
- duplicate join;
- owner leaves;
- browser disappears;
- runtime dies;
- RetroArch crashes;
- Selkies crashes;
- TURN unavailable;
- Valkey restart;
- Session Manager restart;
- Runtime Agent restart;
- edge proxy restart;
- expired stream token;
- stolen/reused token;
- route points to removed runtime;
- two simultaneous close requests.

---

# 60. Capacity and Resource Controls

Runtime Agent must enforce configurable limits.

Examples:

```text
max_total_runtimes
max_runtimes_per_user
max_sessions_per_user
max_players_per_session
max_idle_minutes
max_session_minutes
max_memory_per_runtime
max_cpu_per_runtime
```

GPU encoder capacity must be measured on target hardware.

Do not assume unlimited NVENC/VA-API concurrency.

Reject new sessions gracefully when capacity is exhausted.

---

# 61. Discord

Discord integration is not part of the infrastructure MVP.

A browser gameplay window should be screen-shareable using normal Discord screen sharing.

Do not add Discord APIs, bots, or streaming SDKs unless a later requirement justifies them.

---

# 62. Definition of Done for Every Milestone

A milestone is complete only if:

- acceptance criteria pass;
- relevant tests are automated where practical;
- lint/type checks pass;
- no secrets are committed;
- no commercial ROMs/BIOS are committed;
- dependency pins are recorded;
- architectural changes have ADRs;
- security boundary changes are documented;
- `UPSTREAMS.md` is updated if dependencies changed;
- deployment instructions are reproducible;
- known limitations are written down;
- the next milestone does not depend on undocumented manual state.

---

# 63. First Codex Session — Milestone 0 Prompt

Use this prompt after placing this file in the new repository:

```text
Read PROJECT.md completely before changing files.

Implement Milestone 0 only.

This is a browser-native Internet-first retro multiplayer platform.
Do not implement gameplay functionality yet.

Create the repository scaffolding specified in PROJECT.md, including:

- AGENTS.md
- README.md
- LICENSE
- UPSTREAMS.md
- THIRD_PARTY_NOTICES.md
- SECURITY.md
- CONTRIBUTING.md
- docs and ADR structure
- services/session-manager skeleton
- services/runtime-agent skeleton
- images/retro-session skeleton
- infra directories
- tests directories
- Python tooling for ruff, mypy, and pytest
- .env.example containing names only, never real secrets

Before pinning or documenting an upstream dependency, inspect its current
official repository/documentation and verify its current license and stable
release information.

Do not copy source code from RomM, Selkies, Wolf, RetroArch, authentik,
coturn, Valkey, or libretro cores into this repository.

Record upstream dependencies and integration boundaries only.

Use Apache-2.0 for new original project code unless an existing repository
file or explicit owner instruction says otherwise.

Do not create a RomM source tree inside this repository. Document that RomM
must be maintained as a separate fork with official RomM configured as the
upstream remote.

Create ADRs for:
1. browser-native client;
2. RomM as control plane;
3. Selkies as browser streaming layer;
4. Runtime Agent as Docker privilege boundary;
5. Valkey for ephemeral session state;
6. authentik as identity provider;
7. TURN as a public-MVP requirement;
8. Wolf as an optional ExecutionProvider rather than a required dependency.

Configure the empty Python service skeletons so these commands execute
successfully:

ruff check .
ruff format --check .
mypy services
pytest

Do not implement:
- Docker lifecycle;
- WebRTC orchestration;
- session/lobby behavior;
- RomM API integration;
- RetroArch launch behavior.

At completion:
1. run all configured checks;
2. show the resulting file tree;
3. summarize verified upstream licenses and versions;
4. identify any licensing uncertainty;
5. list unresolved technical decisions for Milestone 1;
6. state exactly which files were created or modified.
```

---

# 64. Second Codex Session — Milestone 1 Prompt

```text
Read PROJECT.md and AGENTS.md.

Implement Milestone 1 only.

Goal:
Prove the current pinned Selkies release can provide browser-native video,
audio, keyboard, and physical gamepad input through the project reverse proxy.

Before implementation, inspect the pinned Selkies documentation for:
- secure mode;
- WebRTC and WebSocket modes;
- gamepad support;
- reverse-proxy subfolder support;
- image/container options;
- licensing implications.

Use upstream Selkies functionality. Do not reimplement capture, encoding,
audio, WebRTC, or gamepad injection.

Do not add RetroArch yet.

Create the minimum local Docker Compose/reverse-proxy configuration and
documentation required for the proof.

Do not expose Docker socket to public services.

Do not use floating image tags in the final test definition.

Document manual verification for:
- page load;
- video;
- audio;
- keyboard;
- gamepad;
- secure mode;
- reverse-proxy subfolder.

Run existing repository checks before completion.
```

---

# 65. Third Codex Session — Milestone 2 Prompt

```text
Read PROJECT.md and AGENTS.md.

Implement Milestone 2 only.

Goal:
Run one pinned RetroArch instance with one legally redistributable NES test
ROM inside the existing Selkies browser-streamed environment.

Build a thin retro-session image.

Do not recreate Selkies display, video, audio, WebRTC, or gamepad code.

Pin RetroArch and the selected NES core.
Record versions, hashes, repositories, and licenses in UPSTREAMS.md and the
core manifest.

Mount ROM content read-only.

Use only test ROM content whose redistribution license is documented.

Launch directly into RetroArch/gameplay without requiring the remote user to
interact with a Linux desktop.

Use a fixed 1280x720 at 60 FPS test profile unless the current upstream
implementation provides a documented reason to choose another initial test
resolution.

Disable unrelated remote-desktop features where supported.

Add automated validation tests for project-owned configuration/entrypoint
logic.

Document manual browser verification for:
- video;
- audio;
- controller;
- fullscreen;
- clean shutdown.
```

---

# 66. Fourth Codex Session — Milestone 3 Prompt

```text
Read PROJECT.md and AGENTS.md.

Implement Milestone 3 only.

Goal:
Prove the single browser RetroArch session works from an off-site Internet
connection using WebRTC and self-hosted coturn.

Inspect current Selkies and coturn documentation before configuring ports,
shared-secret authentication, ICE, or TURN behavior.

Deploy coturn with ephemeral/HMAC credential support.

Do not place the TURN shared secret in browser-visible configuration or Git.

Add public-test configuration with environment placeholders only.

Test and document:
- WebRTC signaling through HTTPS;
- direct ICE if available;
- TURN/UDP;
- TURN/TCP fallback;
- TURN/TLS if supported by the available public network design;
- controller input from an off-site browser;
- stream reconnect;
- selected ICE candidate type.

Do not implement Session Manager or RomM multiplayer integration yet.

Record exact firewall requirements in docs/networking.md.
```

---

# 67. Fifth Codex Session — Milestone 4 Prompt

```text
Read PROJECT.md and AGENTS.md.

Implement Milestone 4 only.

Create the deterministic participant runtime launcher.

Define a typed versioned RuntimeSpec.

Inputs must include:
- session ID;
- participant ID;
- stable user/display name;
- ROM canonical path;
- expected ROM SHA-256;
- approved core profile;
- Netplay role;
- Netplay host when client;
- Netplay port;
- stream subfolder.

Requirements:
- reject ROMs outside approved ROM root;
- reject symlink/path traversal escape;
- verify ROM hash;
- verify core profile;
- verify core artifact hash;
- do not accept arbitrary shell arguments;
- generate per-runtime RetroArch configuration;
- log versions/hashes without logging secrets;
- never dynamically download a core at runtime.

Add unit tests for every validation boundary.

Do not implement Docker orchestration or RomM integration yet.
```

---

# 68. Sixth Codex Session — Milestone 5 Prompt

```text
Read PROJECT.md and AGENTS.md.

Implement Milestone 5 test harness only.

Goal:
Prove two independent browser-streamed RetroArch runtimes can join one
RetroArch Netplay session over a private Docker network.

Launch runtime A as Netplay host.
Launch runtime B as Netplay client.

Both must use:
- exact same RetroArch build;
- exact same core build/hash;
- exact same ROM hash.

Do not use RetroArch LAN discovery.
Pass the private host address explicitly.

Verify:
- Browser A controller controls participant A;
- Browser B controller controls participant B;
- Netplay connects;
- game remains synchronized;
- both streams work through the public WebRTC/TURN test path;
- shutdown removes both containers.

Do not implement RomM UI or Session Manager yet.

This milestone is not complete until two remote browser-only users can
actually play the same test game.
```

---

# 69. Subsequent Codex Work Pattern

After Milestone 5, continue one bounded milestone per Codex session.

Every session starts:

```text
Read PROJECT.md and AGENTS.md.
Implement Milestone N only.
Inspect existing code and current upstream APIs before changing files.
Do not expand scope into the next milestone.
```

Every session ends by:

1. running tests;
2. running lint/type checks;
3. reporting changed files;
4. reporting unresolved failures;
5. updating documentation;
6. stating whether milestone exit criteria passed.

---

# 70. Architectural Success Criteria

The architecture is successful when components remain replaceable.

If RomM is replaced:

```text
new UI
   |
Session Manager API
```

still works.

If Selkies is replaced:

```text
new StreamProvider
```

does not require rewriting lobby logic.

If Docker is replaced:

```text
new ExecutionProvider
```

does not require rewriting RomM.

If a core changes:

```text
new CoreProfile
```

does not require changing orchestration code.

If identity changes:

```text
new upstream IdP
   |
authentik federation
   |
OIDC to RomM
```

does not require changing the Session Manager.

That separation is the primary maintainability goal of this project.

---

# 71. Final MVP Architecture

```text
                         INTERNET USERS
                              |
                         Modern browser
                              |
                     +--------+--------+
                     |                 |
                   HTTPS             WebRTC
                     |                 |
                     v                 v
               +-----------+       +--------+
               |  Traefik  |       | coturn |
               +-----+-----+       +----+---+
                     |                  |
           +---------+----------+       |
           |                    |       |
           v                    v       |
      authentik                RomM     |
           |                    |       |
           +------ OIDC --------+       |
                                |       |
                                v       |
                      Retro Session Manager
                                |
                         UNIX runtime API
                                |
                         Runtime Agent
                                |
              +-----------------+-----------------+
              |                                   |
              v                                   v
       Retro Session A                     Retro Session B
       Selkies + RetroArch                 Selkies + RetroArch
              |                                   |
              +--------- private Netplay ---------+
```

No remote-user installation.

No public RetroArch ports.

No public Docker API.

No public Selkies administrative credentials.

No custom password implementation.

No commercial ROM distribution.

No unnecessary fork of upstream infrastructure.

---

# 72. First Release Scope

The first usable release is deliberately narrow:

- one server host;
- Docker runtime;
- public HTTPS;
- authentik;
- RomM;
- Valkey;
- Runtime Agent;
- Session Manager;
- Selkies WebRTC;
- coturn;
- NES;
- one verified NES core;
- two remote users;
- named lobby;
- create/join/leave;
- browser gamepad;
- automatic cleanup.

After that works:

1. SNES;
2. Genesis;
3. 3–4 player profiles;
4. persistent saves;
5. observability;
6. scale-out execution providers;
7. optional Wolf evaluation;
8. broader browser/device support.

Do not expand the initial scope until the two-user browser-only NES MVP passes end to end.
