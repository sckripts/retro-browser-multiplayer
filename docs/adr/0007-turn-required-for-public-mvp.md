# ADR 0007: TURN required for the public MVP

- Status: Accepted
- Date: 2026-08-29

## Decision

Deploy coturn from the first public test and treat relayed WebRTC as a supported normal path, not an exceptional fallback.

## Consequences

The deployment needs public TURN/UDP plus TCP/TLS fallback planning, a bounded relay range, short-lived HMAC credentials, abuse controls, and visibility into selected ICE candidate types.
