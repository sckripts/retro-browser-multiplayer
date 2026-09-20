# ADR 0002: RomM as control plane

- Status: Accepted
- Date: 2026-08-29

## Decision

RomM owns library browsing and the user-facing multiplayer entry points. Custom lobby logic remains in Session Manager behind a private API.

## Consequences

RomM changes live in a separate AGPL-3.0 fork. RomM does not learn Docker, TURN, Netplay, private addresses, or Selkies master-token details.
