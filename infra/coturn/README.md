# coturn

Milestone 3 uses the immutable official coturn 4.17.2 Debian image with HMAC
`use-auth-secret` credentials minted by the private Selkies TURN REST service.

The public listeners are 3478 TCP/UDP and 5349 TCP. Relay ports are bounded to
49160-49200. The server drops all Linux capabilities except `NET_BIND_SERVICE`,
runs as the image's `nobody` user, has a read-only root filesystem, disables its
CLI, rejects multicast peers, and advertises the public IPv4 discovered by the image's
official DNS helper.

Never commit or expose `M3_TURN_SHARED_SECRET`. Browsers receive only one-hour HMAC
credentials. Do not publish TURN REST port 8008. See `docs/networking.md` for exact
router/firewall rules and the TCP 443 collision constraint.
