# Third-Party Notices

No third-party source code, binaries, container layers, ROMs, BIOS files, or core artifacts are included in this repository.

External services and candidate dependencies are documented in `UPSTREAMS.md`. Their names and links are descriptive references, not endorsements. When a later milestone distributes an upstream artifact, add its required notices and license text here before release.

The project specifically does not include RomM AGPL-3.0 source. RomM modifications must remain in the separate RomM fork with its upstream notices intact.

The Milestone 1 Compose proof downloads, but does not redistribute, immutable Selkies
and Traefik container images. Selkies project files are MPL-2.0. Its selected published
desktop image is the upstream GPL-enabled build and includes libx264
(GPL-2.0-or-later), a GPL-enabled Ubuntu FFmpeg build, and other separately licensed
components documented in Selkies' `docs/licensing.md`. Traefik is MIT licensed. Image
digests and source references are recorded in `UPSTREAMS.md`.

The local derived image builds RetroArch 1.22.2, the Mesen 0.9.9 libretro core, the
pinned bsnes libretro core, and the pinned BlastEm libretro core from upstream GPL-3.0
sources. The image is a local development
artifact and is not published by this repository. Super Tilt Bro 2.6 is WTFPL-2.0; a
helper may download it from the author's page into an ignored local directory, but the
ROM is never included in this repository, Docker build context or image, tests, or CI.
Exact source and artifact hashes are recorded in `UPSTREAMS.md` and the core manifest.

The Milestone 4 local runtime image also installs hash-locked Python packages:
Pydantic, pydantic-core, annotated-types, typing-inspection, and PyYAML under
the MIT license, plus typing-extensions under PSF-2.0. They are installed into
an isolated image directory rather than copied into this repository. Exact
versions and hashes are recorded in the runtime requirements lock file.

The Milestone 3 public-test profile downloads, but does not redistribute, the official
coturn 4.17.2-r0 Debian image (BSD-3-Clause) and the Selkies TURN REST image
(MPL-2.0 source). coturn is pinned by a multi-platform digest; TURN REST is pinned
directly to its immutable linux/amd64 manifest because an earlier untagged `main`
index was garbage-collected. The TURN REST image contains its upstream application
rather than copied project source; exact references are recorded in `UPSTREAMS.md`.

The Milestone 7 Session Manager installs exact-version Python packages rather than
copying their source into this repository. FastAPI, Pydantic, valkey-py, annotated-doc,
AnyIO, and truststore use MIT-family licenses. Starlette, Uvicorn, HTTPX2, and
HTTPCore2 use BSD-3-Clause. Exact reviewed versions are recorded in `UPSTREAMS.md`.

The Milestone 11 proof downloads, but does not redistribute, official immutable
authentik, PostgreSQL, RomM, MariaDB, and Mailpit images. authentik core is MIT outside
its separately licensed portions; PostgreSQL uses the PostgreSQL License; RomM is
AGPL-3.0; MariaDB is GPL-2.0-only with separately licensed components; Mailpit is MIT.
No upstream source is copied into this repository. Exact image references are recorded
in `UPSTREAMS.md`.

Milestone 18 downloads, but does not redistribute, immutable official Prometheus
(Apache-2.0) and Grafana (AGPL-3.0-only) images. Session Manager installs the
Apache-2.0 `prometheus-client` Python package from its exact-version, hash-locked wheel.
No upstream observability source is copied into this repository; exact versions and
digests are recorded in `UPSTREAMS.md`.
