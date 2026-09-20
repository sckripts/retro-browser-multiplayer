# ADR 0008: Wolf is an optional ExecutionProvider

- Status: Accepted
- Date: 2026-08-29

## Decision

The initial implementation uses LocalRuntimeAgentProvider. Wolf may be evaluated later only behind the ExecutionProvider interface.

## Consequences

Wolf and Moonlight are not in the critical browser-client path. Any later adoption must demonstrate operational value without adding a native client requirement or leaking Wolf-specific concepts into lobby logic.
