# ADR 0005: Valkey for ephemeral state

- Status: Accepted
- Date: 2026-08-29

## Decision

Use Valkey for active sessions, participants, TTL leases, locks, idempotency keys, and runtime mappings.

## Consequences

Session state is intentionally ephemeral at first and remains independent of RomM's database. Durable history can justify a relational store later.
