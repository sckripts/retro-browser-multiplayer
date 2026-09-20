# TURN relay failure

## Trigger

No `relay` candidate is gathered/selected, coturn is down, or remote streams fail while
same-site streams work.

## Diagnose

1. Check the Prometheus `coturn` target and coturn health before changing firewall rules.
2. Correlate coturn allocation, traffic, authentication, and dropped-401 metrics with the
   failure time. Do not enable username labels: TURN REST usernames are ephemeral.
3. Verify private TURN REST credential minting with the Milestone 18 verifier; never print
   the returned credential.
4. Verify public TCP/UDP 3478, TCP 5349, and UDP 49160-49200 against `docs/networking.md`.
5. Confirm external-IP mapping and DNS still resolve to the intended public address.

## Recover

Restore DNS/firewall/NAT symmetry or restart only coturn after preserving logs. Re-run an
off-site relay test. Do not publish TURN REST port 8008, widen the relay range without a
capacity review, or place the shared secret in a browser/runtime.
