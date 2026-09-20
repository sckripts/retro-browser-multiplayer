# Runtime configuration

The shared RetroArch and Mesen options fix the browser profile to X11/GL, PulseAudio,
udev gamepad input, fullscreen 1280x720, NTSC timing, and 48 kHz core audio. Runtime
state is written only below a temporary home. The browser profile disables RetroArch's
Escape-to-quit binding so browser fullscreen exit cannot accidentally end a session.
Core-specific controller-port devices, including the SNES multitap, come from the
image-owned core manifest and are rendered into the per-session configuration.
Do not commit active tokens, secrets, ROM paths from a real library, saves, or states.
