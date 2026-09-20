# Orphan runtime

## Trigger

Runtime Agent lists a participant runtime that no live session owns, or a route/metrics
target remains after the runtime is gone.

## Diagnose

1. Run the Milestone 18 verifier and preserve Runtime Agent structured logs.
2. Compare Session Manager diagnostics, `retro_runtime.client list`, generated route
   filenames, and generated metrics-target filenames by participant UUID.
3. Do not inspect through or expose the Docker socket from Session Manager.

## Recover

Restart Session Manager once to run startup reconciliation. If a managed runtime remains,
remove that exact participant UUID through `retro_runtime.client remove`. Restart Runtime
Agent to reconcile orphan route/target files. Confirm strict clean verification. Never use
broad container deletion or delete the route/target roots recursively.
