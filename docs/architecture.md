# Architecture

The platform separates the control, stream, and emulator planes.

- Control: browser to RomM/authentik; RomM calls Session Manager privately.
- Stream: browser to participant-specific Selkies through the edge proxy and WebRTC/TURN.
- Emulator: centralized RetroArch runtimes communicate through private Netplay networking.

Session Manager never receives Docker privileges. Runtime Agent alone controls approved runtime images, mounts, networks, resources, and generated proxy routes over a local UNIX socket. Each participant receives an independent Selkies plus RetroArch runtime.

`PROJECT.md` is the source of truth for the complete design.
