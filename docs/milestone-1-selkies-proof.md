# Milestone 1: Selkies Browser Streaming Proof

## Scope and result

This milestone proves the browser-facing streaming layer without adding RetroArch,
RomM integration, identity, session orchestration, or public TURN. Traefik exposes one
subfolder route and reaches Selkies over an internal Docker network. Selkies itself has
no published host port, and neither container receives the Docker socket.

The proof uses Selkies' WebSocket transport. It carries H.264 video, Opus audio, and
keyboard, mouse, and gamepad input over the single reverse-proxied HTTP/WebSocket port.
WebRTC was inspected but is intentionally deferred: public WebRTC requires the coturn
work assigned to Milestone 3.

## Upstream selection

The latest formal Selkies release is `v1.6.2`, but that tag does not contain the
required secure-mode master/session token API or native subfolder routing. Those
features exist on upstream `main`. For that reason this proof pins the immutable image
published by the successful CI run for commit
`3f87241fcd6abc44e205b22f6596e78ef4946670`:

```text
ghcr.io/selkies-project/selkies/desktop:main-ubuntu26.04
@sha256:2f6ab2c01d312e9b066aa1393f99c87983a6f207147ccb93570569c9a3ee9480
```

The selected multi-platform index resolves to amd64 manifest
`sha256:0cfad57d761da912b279dc226850ffe77aae3a6d4379bca4844d87b111982e0d`
on this development host. It is an unreleased upstream snapshot, not a Selkies stable
release. Re-evaluate and prefer a formal release once one contains both required
features.

Traefik is pinned to `v3.7.12` and image index
`sha256:9c2a54d87f76f5c2f5f2682c68394af92fb12c0a2686798d6462a3f84bd78eaf`.
It uses only the file provider; the dashboard, access log, and Docker provider are off.

## Start and stop

From the repository root in PowerShell:

```powershell
.\infra\scripts\acceptance\milestone1-start.ps1
```

The helper creates `.env.milestone1` when absent. The file is ignored by Git and holds
independent 256-bit master and controller tokens. It starts the NVIDIA hardware-first
configuration, waits for health, provisions the controller token through the server-side
API, and opens the browser. It never prints the master token.

If the host has no usable NVIDIA Container Toolkit path, run the explicit CPU fallback:

```powershell
.\infra\scripts\acceptance\milestone1-start.ps1 -CpuFallback
```

Stop the proof with:

```powershell
.\infra\scripts\acceptance\milestone1-stop.ps1
```

The default bind is `127.0.0.1:8088`. This is deliberate: browser gamepad access needs
a secure context, and browsers treat localhost as trustworthy. To bind on a LAN, change
`M1_BIND_ADDRESS` in `.env.milestone1` to the host's LAN address and configure locally
trusted HTTPS before testing gamepads from another device. Public certificates and the
final HTTPS edge are later deployment work.

## Fixed proof configuration

- Route: `http://127.0.0.1:8088/stream/m1/`
- Transport: WebSockets through Traefik; no direct Selkies port
- Display: 1280x720, resize disabled
- Frame rate: locked to 60 fps
- Encoder: `h264enc`; NVIDIA hardware-first attempt with upstream x264 fallback
- Fallback: the base Compose file forces the software H.264 path
- Audio: enabled, stereo Opus stream
- Input: keyboard, mouse, and four browser gamepad slots enabled
- Container gamepad path: Selkies Joystick Interposer; no privileged `/dev/uinput`
- Disabled: clipboard, binary clipboard, file upload/download, commands, sharing,
  collaboration, microphone, webcam, second display, dual transport switching, and
  embedded TURN

## Manual acceptance checklist

The person holding the physical browser and controller must complete these checks. Do
not mark the milestone complete from health checks alone.

1. Start the proof and confirm the page loads under `/stream/m1/`, not at the root.
2. Confirm the LXQt desktop is visible and reports a 1280x720 display.
3. Open QTerminal in the streamed desktop and type several shifted and unshifted keys.
4. Run `ffplay -nodisp -autoexit -f lavfi "sine=frequency=440:duration=3"` and confirm
   the tone plays in the local browser.
5. Connect a physical gamepad, enable gamepad input in the Selkies UI, and confirm its
   buttons and axes move in the Selkies gamepad visualizer.
6. In QTerminal run `od -An -t x1 /dev/input/js0`, press buttons and move sticks, and
   confirm bytes appear. This proves a Linux application receives the forwarded input,
   not only that the browser detects the device. Press `Ctrl+C` to stop it.
7. Confirm clipboard, files, sharing, microphone, and webcam controls are absent or
   unavailable.
8. Confirm a private/incognito page without the session-token bootstrap does not start
   a stream.

### Acceptance record

Completed on 2026-08-30 against commit `864b113` and the image digests recorded above:

- Passed: the LXQt desktop streamed through `/stream/m1/` at the locked 1280x720 size.
- Passed: keyboard input reached QTerminal.
- Passed: the generated FFmpeg tone played through the local browser.
- Passed: a Bluetooth Xbox controller appeared in the Selkies input overlay.
- Passed: controller events produced bytes from `/dev/input/js0` in QTerminal, proving
  the Joystick Interposer delivered physical input to a Linux application.
- Passed: an incognito client without a session token opened no streaming WebSocket.
- Passed automatically: the proxy root returned 404 and an unauthenticated token-table
  update returned 401.

Milestone 1 is accepted. The Docker Desktop NVENC limitation documented below remains a
performance constraint, not a functional acceptance failure; upstream x264 fallback
carried the successful proof.

## Automated verification

Run the repository checks plus Compose rendering:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe services
.\.venv\Scripts\python.exe -m pytest
$env:SELKIES_MASTER_TOKEN = "compose-validation-placeholder"
docker compose -f infra/compose/acceptance/compose.milestone1.yml `
  -f infra/compose/acceptance/compose.milestone1.gpu.yml config --quiet
Remove-Item Env:SELKIES_MASTER_TOKEN
```

Runtime verification should also confirm `/stream/m1/api/health` succeeds through
Traefik, an unauthenticated `POST /stream/m1/api/tokens` is rejected, and the Selkies
logs identify the active H.264 encoder. The config tests enforce digest pins, the
file-only proxy provider, lack of a Docker socket, the private Selkies port, disabled
capabilities, fixed display settings, and the absence of RetroArch/TURN services.

## Licensing notes

Selkies project files are MPL-2.0. The selected published desktop image is the default
GPL-enabled build: its software H.264 fallback uses libx264 (GPL-2.0-or-later), and the
Ubuntu FFmpeg build is GPL-licensed. Other bundled components retain their own licenses;
the upstream licensing inventory is authoritative. NVIDIA's driver is proprietary and
is injected at runtime rather than included by this repository. This repository neither
copies Selkies source nor redistributes the container layers.

## Development-host runtime evidence

The automated proof on 2026-08-30 observed HTTP 200 for the proxied health and
subfolder page, HTTP 404 at the proxy root, and HTTP 401 for an unauthenticated token
table update. A real Edge client authenticated through Traefik, opened the data
WebSocket, applied 1280x720 at 60 fps, and started stereo Opus capture. Selkies also
initialized all four Joystick Interposer sockets.

The RTX 4060 Ti is visible to the container through `nvidia-smi`, and Selkies detected
NVENC, but Docker Desktop's WSL GPU bridge did not expose the CUDA-EGL interop symbol
`cuGraphicsEGLRegisterImage`. Selkies therefore selected its documented x264 fallback.
This host/runtime combination does not support the required zero-copy NVIDIA encode
path; the GPU override remains useful on native Linux/NVIDIA Toolkit hosts. Physical
keyboard, audible output, and controller-to-application checks remain manual because
they require the person and devices at the browser.
