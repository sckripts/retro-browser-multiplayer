# ADR 0003: Selkies streaming

- Status: Accepted
- Date: 2026-08-29

## Decision

Use upstream Selkies for HTML5 video, audio, keyboard, and gamepad streaming. Consume it through configuration or a thin derived image.

## Consequences

The project does not reimplement capture, encoding, WebRTC, audio, or input injection. Secure mode, short-lived scoped tokens, reverse-proxy subfolders, and disabled unrelated features are required.
