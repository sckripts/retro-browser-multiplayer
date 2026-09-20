# Milestone 3: Public Internet WebRTC and coturn

## Status

Accepted on 2026-09-01 after local infrastructure validation and browser gameplay from
LTE and a second off-site hotspot. The game rendered, produced audio, accepted controller
input, and resumed the same running state after reconnect through TURN/UDP.

## Implemented boundary

- Traefik terminates HTTPS on a host-and-path-scoped `/stream/m3` route and has no
  Docker socket, dashboard, or access log.
- Selkies runs WebRTC-only and exposes no host port.
- TURN REST runs only on an internal credential network and mints one-hour HMAC-SHA1
  credentials behind a separate API key.
- coturn owns public STUN/TURN listeners and the bounded relay range.
- The browser receives a scoped Selkies controller token and ephemeral TURN
  credentials, never a master token, TURN REST API key, or coturn shared secret.
- RetroArch still launches only the fixed, hash-verified, read-only legal test ROM.

## Local evidence

| Check | Result |
|---|---|
| All four containers | Healthy |
| HTTPS route and Selkies health through SNI | HTTP 200 |
| TURN REST without API key | HTTP 400 |
| Authenticated credential | Valid ICE JSON; about 3600-second expiry; secret not printed |
| Direct profile | No TURN REST key/shared secret in runtime; project STUN host selected |
| TURN/UDP profile | Correct `turn:` UDP URI; authenticated relay self-test passed 6/6 before public address mapping |
| TURN/TCP profile | Correct `turn:` TCP URI; authenticated relay self-test passed 6/6 |
| TURN/TLS profile | Correct `turns:` TCP URI; authenticated TLS relay test completed |
| TLS versions | TLS 1.0/1.1 rejected; TLS 1.2/1.3 accepted |
| Public candidate mapping | Official coturn helper resolved a non-private IPv4 without printing it |
| Cellular TURN/UDP session | Peer connection established after relay candidates were exchanged; video, audio, and USB-attached controller input passed |
| Secrets and content | `.env.milestone3`, generated route, TLS directory, and ROM are ignored |

The mapped public candidate cannot be loopback-validated reliably from the same
residential host because that depends on router hairpin behavior. That is why the
off-site checks below are mandatory.

## Public acceptance procedure

1. Configure real DNS, a trusted certificate, and every router/host firewall rule in
   `docs/networking.md`.
2. Start `turn-udp` and open the printed HTTPS URL on a browser using a different
   residential or cellular network.
3. In browser WebRTC diagnostics, record the selected candidate-pair types, transport,
   local/remote candidate protocols, and whether the remote candidate is `relay`.
4. Confirm the game renders, audio plays, both D-pads move, all four tested buttons
   respond, and focus can be released without terminating the container.
5. Record resolution, configured video bitrate, observed frame rate, approximate
   input latency, reconnect time, and any visible/audio failure.
6. Repeat with `direct`, `turn-tcp`, and `turn-tls`. A TURN run is accepted
   only when the selected pair includes a relay candidate; page load alone is
   insufficient.
7. Repeat the default TURN/UDP gameplay run from a second off-site network.
8. Disconnect/reconnect the browser once and confirm the same running game resumes.

Record results here:

| Network | Profile | Candidate pair/path | Resolution | Bitrate | FPS | Input latency | Reconnect | Video/audio/controller |
|---|---|---|---|---|---|---|---|---|
| LTE cellular A | direct | failed during ICE; remained connecting | n/a | n/a | n/a | n/a | n/a | no media or controls |
| LTE cellular A | TURN/UDP | relay/UDP; established | 1280x720 configured | 8000 kbps configured; observed unavailable | 60 configured; observed unavailable | responsive; not measured | pass; same game state | pass/pass/pass (USB controller) |
| LTE cellular A | TURN/TCP | relay/TCP; established | 1280x720 configured | 8000 kbps configured; observed unavailable | 60 configured; observed unavailable | intermittent control delay | not tested | pass/pass/pass; choppy audio and video lag/catch-up at times |
| LTE cellular A | TURN/TLS | relay/TLS-over-TCP; established | 1280x720 configured | 8000 kbps configured; observed unavailable | 60 configured; observed unavailable | laggy | not tested | pass/pass/pass; substantially less playable because all three lagged |
| Hotspot B | TURN/UDP | relay/UDP; established | 1280x720 configured | 8000 kbps configured; observed unavailable | 60 configured; observed unavailable | mildly laggy but usable | not tested | good/good/usable; controller slightly laggy |

TURN/UDP is the deployment default: it was playable on both tested off-site paths.
TURN/TCP and TURN/TLS are connectivity fallbacks, not preferred gameplay paths. Direct
ICE did not cross the combined Docker and site NAT topology.

The pinned Selkies client did not write its enabled statistics CSV after these mobile
sessions, so observed bitrate and FPS were unavailable. The profile now pins the
previous upstream default bitrate explicitly and uses the existing writable `/tmp`
directory for future statistics capture.

## Non-goals

This milestone does not add RomM, authentik, Session Manager, Runtime Agent, arbitrary
ROM selection, RetroArch Netplay, or multi-session routing. Those ownership boundaries
remain unchanged.
