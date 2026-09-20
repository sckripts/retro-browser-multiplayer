# Networking

The public edge exposes HTTPS/WSS for control and signaling. coturn is a separate
public service for STUN, TURN/UDP, TURN/TCP, and TURN/TLS. Participant runtimes and
RetroArch Netplay remain private.

## Milestone 3 public-test ports

Forward these ports from the Internet router to the Docker host and allow them through
the host firewall. The committed relay range is deliberately narrow for the one-session
proof; increase it only with a capacity calculation.

| Public port | Protocol | Container target | Purpose | Required profile |
|---|---|---|---|---|
| 80 | TCP | Traefik 8080 | Permanent redirect to HTTPS | all |
| 443 | TCP | Traefik 8443 | HTTPS, WSS, Selkies signaling | all |
| 3478 | UDP | coturn 3478 | STUN and TURN/UDP | direct, turn-udp |
| 3478 | TCP | coturn 3478 | TURN/TCP | turn-tcp |
| 5349 | TCP | coturn 5349 | TURN/TLS | turn-tls |
| 49160-49200 | UDP | coturn same range | UDP relay allocations | TURN profiles |

The current coturn profile disables RFC 6062 TCP relay endpoints but keeps TCP client
transport to UDP relay allocations. It therefore publishes neither the TCP relay range
nor the unused DTLS listener.

Do not expose port 8008 (TURN REST), Selkies port 8080, a RetroArch port, or a Docker
socket. TURN REST is reachable only from its private credential network. Selkies reaches
coturn over a separate TURN network; Traefik reaches Selkies over the edge network.
On that TURN network, coturn has an alias matching the public TURN hostname. This lets
the server-side WebRTC peer allocate against coturn directly while off-site browsers
use public DNS.

Same-site WebRTC testing has an additional constraint. Even when split DNS sends HTTPS
and TURN listener traffic directly to the Docker host, coturn advertises its public IP
for relay candidates. A LAN browser and the server-side peer must therefore be able to
reach that public relay address. At the accepted ARCADE-HOST test site, a U-turn destination
NAT rule maps the public IP back to `192.168.2.17` for TCP/UDP 3478, TCP 5349, and UDP
49160-49200, with source DIPP so replies remain symmetric. The matching security rule
uses the original public destination address and the post-NAT server zone. This U-turn
rule is unnecessary for off-site clients and does not expose RetroArch Netplay.

The coturn image discovers the host's public IPv4 address during startup using its
official DNS helper and advertises that address in relay candidates. Verify that the
router's WAN address is public and matches the detected address. Carrier-grade NAT
cannot be fixed with local port forwarding; obtain a public address or deploy coturn on
a public host.

The same detected public address is the sole explicit coturn peer allowlist entry. This
is required when both WebRTC endpoints allocate on this coturn instance: each endpoint
must be able to bind a channel to the other's publicly advertised relay address. The
exception is deliberately limited to the TURN public address; coturn's loopback, zero,
multicast, and other default peer-address protections remain enabled.

TURN/TLS uses TCP 5349 in this proof. It cannot use TCP 443 on the same public IP as
Traefik without a deliberate Layer-4 multiplexer or a separate public IP. Do not simply
map both services to 443.

Milestone 14 reuses the same listener and bounded relay plan for dynamically launched
participant runtimes. Only Traefik TCP 80/443 and coturn TCP/UDP 3478, TCP 5349, and
UDP 49160-49200 are public. authentik, RomM, Session Manager, Runtime Agent, TURN REST,
Valkey, databases, and participant ports are not published. Dynamic stream routes are
also constrained to the public RomM hostname.

The Milestone 1 proof is narrower: Traefik publishes one configurable local HTTP port
and forwards `/stream/m1` to Selkies on an internal Docker network. Selkies publishes no
host port. It uses the WebSocket transport, so no STUN/TURN or media UDP ports are
opened. The default loopback bind preserves the browser secure-context exception for
local controller testing; LAN gamepad testing requires locally trusted HTTPS.
