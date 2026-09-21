# Upstream Dependency Register

Verified against official upstream repositories and documentation on 2026-09-02.
Research pins remain candidates until the milestone that consumes them records an exact
artifact and its transitive licensing. Selkies, Traefik, RetroArch, and Mesen are
selected for the implemented browser/runtime proofs.

## RomM

- Project: RomM
- Purpose: ROM library, metadata, and user-facing control plane
- Canonical repository: https://github.com/rommapp/romm
- License: AGPL-3.0
- Selected release/tag: 5.2.0
- Selected commit: `42e8043372522089a3bd724e8f4a0635aa1c6bf9`
- Selected image: `rommapp/romm:5.2.0`
- Multi-platform image digest:
  `sha256:3512f2ca455782f90247271bed23116e6bc675bc74e379be2c41696e607ab11e`
- linux/amd64 manifest digest:
  `sha256:6a2a16f74ce55c4d528eafda5f49993357731cb638a55932abec8dde14e3a93f`
- Date verified: 2026-09-06
- Modification status: separate fork only; never copied into this repository
- Local fork: `<separate-romm-worktree>`; `origin` is `https://github.com/YOUR_GITHUB_OWNER/romm.git` and
  `upstream` is `https://github.com/rommapp/romm.git`
- Milestone 12 fork base: upstream `master` commit
  `2d089fe91442c49a9746ec10ec7a2c6441500b7f`, verified 2026-09-06
- Accepted fork release: `retrobrowser-v0.1.0` at commit
  `4bb2e5205b1aacc147cb1091403c9c0783234f28`, verified 2026-09-21
- Security notes: modified network-facing versions must provide corresponding source
- Update notes: the current official environment template exposes native OIDC settings

## Selkies

- Project: Selkies
- Purpose: HTML5 video/audio/input streaming
- Canonical repository: https://github.com/selkies-project/selkies
- License: MPL-2.0 for project files; bundled wheels/images include separately licensed components
- Latest formal release: 2.0.0rc1, commit `e6d04050955523a4e026e4dceef7c35096150fa1`
- Selected artifact status: versioned 2.0.0rc1 release with required secure mode and subfolder routing
- Selected commit: `e6d04050955523a4e026e4dceef7c35096150fa1`
- Current upstream `main` observed for Milestone 9:
  `f95210a33041b2311a9e912f54f9b75203fefcdb`; the token replacement and slot
  contract used by the selected commit remains current
- Successful upstream CI run: https://github.com/selkies-project/selkies/actions/runs/33318518640
- Container/package: `ghcr.io/selkies-project/selkies/desktop:2.0.0rc1-ubuntu26.04`
- Multi-platform image digest: `sha256:07ba642f431915158a7f4cec69d46303704816dced17d4ee95bd34b2a1ef23eb`
- amd64 manifest digest: `sha256:0bfcce1fa30024a8eb34e2504a74e1fb18f4c1424d92c1b6ad6282fb3b1ae87b`
- Date verified: 2026-09-21
- Modification status: unmodified upstream image, configured externally
- Security notes: secure mode keeps the master token server-side and provisions scoped client tokens; bootstrap URLs contain client tokens, so proxy access logging is disabled
- Network notes: Milestone 1 uses same-origin WebSockets behind `/stream/m1`;
  Milestone 3 uses WebRTC-only behind `/stream/m3` and obtains ephemeral
  credentials from a private TURN REST service
- Development-host note: Docker Desktop exposes NVML/NVENC discovery but lacks the CUDA-EGL interop symbol required by this image, so the proven stream falls back to x264; re-test NVENC on native Linux
- Capability notes: clipboard, files, commands, sharing, collaboration, microphone, webcam, second display, dual-mode switching, and embedded TURN are disabled for the proof
- Update notes: replace this snapshot with a formal release once secure mode and subfolder routing are released; re-run browser/gamepad and license checks before changing the digest
- Image licensing: the published default image is GPL-enabled and includes libx264 and a GPL-enabled Ubuntu FFmpeg build; see upstream `docs/licensing.md`

## Traefik

- Project: Traefik Proxy
- Purpose: reverse proxy for the Selkies subfolder proofs and Milestone 3 HTTPS edge
- Canonical repository: https://github.com/traefik/traefik
- License: MIT
- Selected release/tag: v3.7.12
- Selected image: `traefik:v3.7.12`
- Multi-platform image digest: `sha256:9c2a54d87f76f5c2f5f2682c68394af92fb12c0a2686798d6462a3f84bd78eaf`
- amd64 manifest digest: `sha256:7523e37d0694ff940ee9cefe2184c5869dd0c0db7d6c5ee78254f7d985deecc6`
- Date verified: 2026-09-13
- Modification status: unmodified official image, configured through read-only files
- Security notes: file provider only; no Docker socket, dashboard, access log, version
  check, or anonymous telemetry; Milestone 3 rejects aliased header names and runs as
  unprivileged UID/GID 65534

## RetroArch

- Project: RetroArch
- Purpose: emulator frontend and Netplay
- Canonical repository: https://github.com/libretro/RetroArch
- License: GPL-3.0
- Selected release/tag: v1.22.2
- Selected commit: `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`
- Source archive SHA-256: `b4bfa46ea5ce09008494099b967816de8da7a146ede2f7d1a52d5842a6aae215`
- Local amd64 artifact SHA-256: `e7b3a9611e0d7bc429aac2cf92cafb7eeea3f730afaa7b0534805a01512ab73c`
- Container/package: source-built in the project `retro-session` image
- Date verified: 2026-08-30
- Modification status: unmodified source configured as a minimal X11/GL/Pulse/udev build
- Security notes: never dynamically download cores in participant runtimes. Milestone
  17 rechecked the official libretro save-directory contract, RetroArch
  `savefile_directory`/`SAVE_FILES` behavior, and Netplay protocol: the server is
  canonical for global synchronization and sends SRAM during the initial client sync.
  The built-in autosave worker is disabled during Netplay, so Milestone 17 uses the
  private stdin command dispatcher for main-thread flushes and keeps network commands
  disabled.

## RuntimeSpec validation packages

- Pydantic 2.13.5 and pydantic-core 2.46.5: MIT; strict typed RuntimeSpec and
  trusted core-manifest validation
- PyYAML 6.0.3: MIT; safe loading of the image-owned core manifest
- annotated-types 0.8.0: MIT
- typing-extensions 4.16.0: PSF-2.0
- typing-inspection 0.4.4: MIT
- Installation: exact versions and linux/amd64 wheel hashes are recorded in
  images/retro-session/requirements-runtime.txt and installed into an isolated
  target directory in the local runtime image
- Date verified: 2026-09-01
- Security notes: RuntimeSpec itself is JSON; YAML is accepted only for the
  trusted image-owned manifest and is parsed with safe_load

## Session Manager Python dependencies

- FastAPI 0.141.1: MIT; private typed HTTP API
- Starlette 1.6.0: BSD-3-Clause; FastAPI ASGI layer
- Uvicorn 0.52.4: BSD-3-Clause; selected ASGI server
- valkey-py 6.1.1: MIT; Valkey session repository client
- Pydantic 2.13.5 and pydantic-core 2.46.5: MIT; strict domain/API models
- prometheus-client 0.26.0: Apache-2.0; private metrics exposition
- HTTPX2 2.12.0 and HTTPCore2 2.12.0: BSD-3-Clause; API test client
- annotated-doc 0.0.5, AnyIO 4.14.2, and truststore 0.10.4: MIT
- Exact direct pins: `services/session-manager/pyproject.toml` and
  `requirements-dev.txt`
- Date verified: 2026-09-02
- Security notes: the Session Manager API is private and bearer-authenticated; Valkey
  persistence uses optimistic revisions and TTLs; no package receives Docker access

## Milestone 18 observability

- Prometheus 3.7.3, Apache-2.0, official image `prom/prometheus:v3.7.3`, multi-platform
  digest `sha256:49214755b6153f90a597adcbff0252cc61069f8ab69ce8411285cd4a560e8038`
- Grafana 12.3.0, AGPL-3.0-only, official image `grafana/grafana:12.3.0`, multi-platform
  digest `sha256:70d9599b186ce287be0d2c5ba9a78acb2e86c1a68c9c41449454d0fc3eeb84e8`
- Date verified: 2026-09-13
- Modification status: unmodified images configured with project-owned scrape and
  dashboard provisioning files
- Security notes: Prometheus is private and has no Docker socket or published port;
  Grafana binds to loopback by default, disables anonymous access/sign-up, and uses an
  ignored generated administrator password

Versions and licenses were checked against official project sources and installed
distribution metadata.

## Runtime Agent base image

- Project: Docker Official Image for Python
- Purpose: Python 3.14 Runtime Agent process
- Canonical image: `python:3.14.7-slim-trixie`
- Multi-platform image digest:
  `sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2`
- linux/amd64 manifest digest:
  `sha256:810da6270e43d30a1f3e0e1eabbeb6fbd9d78ad9dd2e754d5297a3d6cb42df46`
- Source revision: `688a0b86bb44289df16a363e9f41d90514c1a5f9`
- Date verified: 2026-09-01
- Modification status: project service code copied into an immutable official base
- Security notes: no TCP listener; only Runtime Agent receives the Docker socket;
  Python dependencies are exact-version and hash pinned

## Emulator cores

Mesen is selected for the NES runtime. bsnes is selected for the Milestone 15 SNES
runtime. BlastEm is selected for the Milestone 16 Genesis runtime.

| Platform | Candidate | Repository | License | Status |
|---|---|---|---|---|
| NES | Mesen 0.9.9, commit `f3a18bed018fa853627e0e15d02a3f2ba4960222` | https://github.com/libretro/Mesen | GPL-3.0 | Selected; source archive `9edba76d...a3fba`, amd64 core `1c3d682c...55e8`; Netplay unverified |
| SNES | bsnes, commit `260f5234410d0899f8446882c63d17f891b686e0` (2026-09-04) | https://github.com/libretro/bsnes-libretro | GPL-3.0-or-later | Selected; source archive `975645c6...add44`, amd64 core `41f08812...0d399`; four-player multitap Netplay validated in Milestone 15 |
| Genesis | BlastEm, commit `b4d75247ebad8852fd9bc385b423df704c6c5af5` (2026-09-02) | https://github.com/libretro/blastem | GPL-3.0-or-later | Selected; source archive `c1c216d3...c042d`, amd64 core `52044324...1714`; two-player libretro Netplay validated in Milestone 16 |

Snes9x and Genesis Plus GX are not initial candidates because their current upstream terms include non-commercial restrictions. Re-evaluate only with a deliberate licensing decision.

BlastEm's standalone configuration supports Sega and EA multitaps. The selected
libretro adapter does not: its controller-device callback is empty and its input loop
polls only ports 0 and 1. The Milestone 16 profile therefore has a two-player maximum.
Source, build recipe, GPL-3.0-or-later notice, and adapter behavior were rechecked
against the official repository on 2026-09-13.

## Milestone 2 legal test content

- Project: Super Tilt Bro
- Purpose: legally redistributable NES browser-gameplay proof
- Author/canonical download: Sylvain Gadrat, https://sgadrat.itch.io/super-tilt-bro
- Source repository: https://github.com/sgadrat/super-tilt-bro
- License: WTFPL-2.0
- Selected version: 2.6
- Selected source commit: `a0b25e56ec8bde7bea623573b76343fdd3d584bc`
- itch.io upload ID: `16311760`
- Published filename: `Super_Tilt_Bro_(E).nes`
- Artifact size: 524304 bytes
- Artifact SHA-256: `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d`
- Storage: external ignored local file, mounted read-only; never placed in Git, images,
  tests, examples, or CI artifacts
- Date verified: 2026-08-30

## authentik

- Project: authentik
- Purpose: identity provider and OIDC provider for RomM
- Canonical repository: https://github.com/goauthentik/authentik
- License: MIT for core outside documented exceptions; website CC BY-SA 4.0; enterprise and third-party portions separately licensed
- Selected release/tag: version/2026.8.1
- Selected image: `ghcr.io/goauthentik/server:2026.8.1`
- Multi-platform image digest:
  `sha256:9d605ed569ff9f39146be39da93714b2acf19072acc4ab0f0e2f2d81be88cdce`
- linux/amd64 manifest digest:
  `sha256:d670ebbf308212c0c971649c4beb903bb7e0bc7fb0ec08b7fc78faa9188846da`
- Date verified: 2026-09-06
- Modification status: configure upstream service
- Security notes: use authorization-code OIDC; stable `sub` claim is the identity key

## Milestone 11 supporting images

- PostgreSQL `16.10-alpine`, PostgreSQL License, multi-platform digest
  `sha256:029660641a0cfc575b14f336ba448fb8a75fd595d42e1fa316b9fb4378742297`,
  linux/amd64 manifest
  `sha256:ab8380566c3ea09690a9ecaa85a59d82bfc6eb86744151a2a54335866c83a3e9`
- MariaDB `11.8.3`, GPL-2.0-only with separately licensed components,
  multi-platform digest
  `sha256:ae6119716edac6998ae85508431b3d2e666530ddf4e94c61a10710caec9b0f71`,
  linux/amd64 manifest
  `sha256:1cc14cc479613f2925315a5da7aa0eb5288f938565d94b56cd137b724d2ea12b`
- Mailpit `v1.27.8`, MIT, multi-platform digest
  `sha256:6abc8e633df15eaf785cfcf38bae48e66f64beecdc03121e249d0f9ec15f0707`,
  linux/amd64 manifest
  `sha256:9d85d6bd20c834ec2b7d08ff97976af7b13e2330d9c56ecade4a231dcd3481ba`
- Date verified: 2026-09-06
- Modification status: unmodified upstream images configured only by Compose
- Security notes: database services are private; Mailpit binds only to loopback and is
  a test SMTP sink, never a production mail service

## coturn

- Project: coturn
- Purpose: STUN/TURN relay
- Canonical repository: https://github.com/coturn/coturn
- License: BSD-3-Clause
- Selected release/tag: 4.17.2
- Selected source commit: `de0c9b28f22281a0251d7e98aa8a097895a5b185`
- Selected image: `coturn/coturn:4.17.2-r0-debian`
- Image source revision: `34230574e952f51858f2f2166dab162d448e7809`
- Multi-platform image digest: `sha256:aa68aab64a3b929d57fc2924c98ea447bf996cf8dade2508e7b71eaf23f1f14e`
- amd64 manifest digest:
  `sha256:75e9ebd1e19005bec0c7f591d29afe22f959916ac8d9c852452f27db8c789828`
- Date verified: 2026-08-31
- Modification status: unmodified official image, configured through Compose arguments
- Security notes: one-hour TURN REST HMAC credentials; shared secret remains
  server-side; CLI disabled; relay ports 49160-49200; read-only root; all capabilities
  dropped except the image's required `NET_BIND_SERVICE`

## Selkies TURN REST

- Project: Selkies TURN REST addon
- Purpose: private issuance of short-lived coturn HMAC credentials
- Canonical repository: https://github.com/selkies-project/selkies
- License: MPL-2.0
- Source inspected: upstream `main` at
  `ca30aa9606617186c70e731da998c962df8914be`
- Selected image: `ghcr.io/selkies-project/selkies/turn-rest:main`
- Selected amd64 manifest digest:
  `sha256:53e48365eee7a66886a75a9f37a4733895d864703928600bb5e4fa786e977f04`
- Current multi-platform index at verification:
  `sha256:452127fe433e44afc93a9b55547197bb23923d0496b4e247d9353c1b13f12927`
- Provenance note: the selected image exposes no OCI revision label. A previous
  untagged `main` index was garbage-collected while its amd64 child manifest
  remained pullable, so Compose pins that platform manifest directly. The deployment
  target is linux/amd64.
- Date verified: 2026-08-31
- Modification status: unmodified upstream image, configured externally
- Security notes: private Docker network only; API-key gated; one-hour TTL; shared
  secret is absent from Selkies and browsers

## Valkey

- Project: Valkey
- Purpose: ephemeral sessions, leases, locks, and idempotency
- Canonical repository: https://github.com/valkey-io/valkey
- License: BSD-3-Clause for current project code, with inherited/component exceptions requiring image inventory
- Selected release/tag: 9.1.1
- Selected commit: `d27f9ba65a04e80d9c417112a7621fc98a56f70d`
- Container/package: not selected
- Container digest: not selected
- Date verified: 2026-08-29
- Modification status: configure upstream service

## Wolf

- Project: Wolf
- Purpose: optional future ExecutionProvider evaluation
- Canonical repository: https://github.com/games-on-whales/wolf
- License: MIT
- Selected release/tag: none; latest formal release v2024.07 is stale relative to active commit images
- Selected commit: none
- Container/package: none
- Container digest: none
- Date verified: 2026-08-29
- Modification status: not used in the initial architecture
- Security notes: its primary client path is Moonlight, which does not satisfy the browser-only requirement
