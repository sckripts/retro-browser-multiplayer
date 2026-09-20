# Milestone 2: RetroArch Inside Selkies

## Scope and result

This milestone adds one thin `retro-session` image and proves the local chain:

```text
Browser -> Traefik -> Selkies -> RetroArch -> Mesen -> Super Tilt Bro
```

It does not add RomM, authentication, orchestration, Netplay, public WebRTC, or TURN.
RetroArch launches the fixed ROM directly; LXQt remains disabled. The ROM is an ignored
host file mounted read-only at the one image-defined path `/run/roms/milestone2.nes`.
No browser value can select a ROM path.

## Pinned runtime

- Selkies image index: `sha256:2f6ab2c01d312e9b066aa1393f99c87983a6f207147ccb93570569c9a3ee9480`
- RetroArch: `1.22.2`, commit `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`
- RetroArch binary SHA-256: `e7b3a9611e0d7bc429aac2cf92cafb7eeea3f730afaa7b0534805a01512ab73c`
- Mesen: `0.9.9`, commit `f3a18bed018fa853627e0e15d02a3f2ba4960222`
- Mesen core SHA-256: `1c3d682cdc8a47658235663ed92d39146f2c09ffcb565ed212c9260fb44d55e8`
- Test content: Super Tilt Bro `2.6`, SHA-256 `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d`

The image builds RetroArch and Mesen from the exact source commits and checks both
source archives and resulting amd64 artifacts. `SOURCE_DATE_EPOCH` fixes RetroArch's
build date. Runtime startup checks the embedded binary/core hashes and the mounted ROM
hash before launch, then logs the versions and hashes.

## Legal test content

Super Tilt Bro is developed by Sylvain Gadrat and published under WTFPL-2.0. The helper
downloads version 2.6 from the author's itch.io upload and verifies its exact SHA-256.
The ROM is deliberately excluded from Git, Docker build context, images, tests, and CI.

```powershell
.\tools\test-roms\fetch-super-tilt-bro.ps1
```

The default destination is the ignored file
`local/test-roms/super-tilt-bro-2.6.nes`. Provenance is recorded in
`images/retro-session/manifests/cores.yaml` and `UPSTREAMS.md`.

## Start and stop

On this Docker Desktop development host, use the verified software encoder path:

```powershell
.\infra\scripts\acceptance\milestone2-start.ps1 -CpuFallback
.\infra\scripts\acceptance\milestone2-stop.ps1
```

The launcher creates ignored `.env.milestone2` credentials, verifies the external ROM,
builds the image, waits until both Selkies and RetroArch are healthy, provisions a
controller token without printing the master token, and opens
`http://127.0.0.1:8089/stream/m2/`.

Without `-CpuFallback`, the NVIDIA override requests NVENC and retains Selkies' x264
fallback. Docker Desktop on this machine lacks the required CUDA-EGL interop, so the
exact accepted local encoder path is Selkies `h264enc` using x264 software H.264.

## Fixed gaming profile

- Display: X11 and RetroArch fixed at 1280x720, resize disabled
- Frame rate: Selkies 60 fps; Mesen NTSC reports 60.10 fps
- Audio: PulseAudio, 48 kHz core output, browser audio enabled
- Input: Selkies browser gamepad to its unprivileged joystick interposer; RetroArch udev
- UI: direct fullscreen RetroArch launch, no desktop and no RetroArch menu
- Safety: RetroArch's keyboard Escape-to-quit binding is disabled; lifecycle is
  controlled by the container/stop helper
- Disabled: clipboard, files, commands, sharing, collaboration, microphone, webcam,
  second display, dual transport, embedded TURN, and the optional apps runner/panel
- Exposure: only Traefik binds localhost; the session container has no published port

## Automated evidence

On 2026-08-30, the local CPU-fallback runtime reported:

- RetroArch running with the fixed config, core, and ROM arguments
- Mesen loaded the game as NTSC at 60.10 fps and 48 kHz
- both the X/GL display and RetroArch video size were 1280x720
- PulseAudio started successfully
- the expected RetroArch, Mesen, and ROM SHA-256 values matched
- proxied health returned 200, proxy root returned 404, and an unauthenticated token
  update returned 401
- process-aware container health was healthy, the apps runner was absent, and the
  session container published no host port

## Manual acceptance checklist

The person holding the physical browser and controller must complete these checks:

1. Confirm Super Tilt Bro appears immediately with no desktop interaction.
2. Confirm motion is visible and stable at the fixed fullscreen 1280x720 presentation.
3. Confirm game music and effects are audible in the browser.
4. Confirm the connected Xbox controller can operate the game.
5. Toggle browser fullscreen and confirm gameplay remains correctly fitted.
6. Stop with `milestone2-stop.ps1` and confirm both Milestone 2 containers exit cleanly.

### Acceptance record

Completed on 2026-08-30 against the pinned artifacts recorded above:

- Passed: Super Tilt Bro appeared immediately without a desktop or RetroArch menu.
- Passed: game video and motion were visible and stable.
- Passed: music and game audio were audible in the browser.
- Passed after correcting the Linux hat bindings: both the Xbox D-pad and left analog
  stick operated the game.
- Passed after ordering display initialization: RetroArch opened at 1280x720 and the
  entire game remained visible without cropped edges.
- Passed: `Ctrl+Shift+F` entered browser fullscreen, the image remained fitted, Esc
  exited browser fullscreen without closing RetroArch, and gameplay continued.
- Passed: terminating RetroArch produced exit status 0, and the stop helper removed
  both containers and both milestone networks while preserving the ignored ROM.

Milestone 2 is accepted. Public WebRTC/TURN, orchestration, RomM, identity, and Netplay
remain assigned to later milestones.
