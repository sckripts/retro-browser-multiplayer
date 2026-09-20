# GPU encoder exhaustion

## Trigger

New streams fail encoder startup, fall back unexpectedly, or existing streams degrade as
runtime use approaches the host's encoder capacity.

## Diagnose

1. Compare configured runtime use/capacity with Selkies GPU utilization and error logs.
2. Check the host driver and container GPU visibility, then identify the selected Selkies
   encoder for affected runtimes.
3. Distinguish session-capacity exhaustion from the known Docker Desktop WSL
   `cuGraphicsEGLRegisterImage` limitation documented in the session handoff.

## Recover

Close abandoned sessions first. If policy permits, use the explicitly configured CPU
profile for new sessions; do not mutate a running participant's encoder. Reduce the
configured runtime capacity to the measured safe concurrency. Do not grant extra devices,
privileges, or Docker access to Session Manager. Encoder-specific admission limits remain
a Milestone 19 hardening item.
