# API Documentation

Milestone 6 implements the private Runtime Agent API over a local UNIX socket. It is
not an Internet-facing or browser-facing API.

| Method | Path | Operation |
|---|---|---|
| `POST` | `/v1/runtimes` | Create or return an idempotent managed runtime |
| `GET` | `/v1/runtimes` | List agent-managed runtimes and route-orphan status |
| `GET` | `/v1/runtimes/{participant_id}` | Inspect one managed runtime |
| `POST` | `/v1/runtimes/{participant_id}/stop` | Gracefully stop one managed runtime |
| `DELETE` | `/v1/runtimes/{participant_id}` | Stop/remove one managed runtime and its route |
| `GET` | `/v1/health` | Check Docker Engine reachability |

Create requests are strict versioned JSON, limited to 64 KiB, and reject duplicate
keys and unknown fields. The only caller-selectable runtime inputs are the typed fields
in `CreateRuntimeRequest`. Image, networks, ROM root, user-data root, GPU profiles, and
resource bounds must also match agent-owned configuration. Commands, entrypoints,
arbitrary environment variables, mounts, labels, host ports, and Docker flags are not
part of the contract.

When Milestone 17 persistence is configured, Runtime Agent derives an opaque
user/core/ROM save key from those already-trusted request fields. A host gets the one
generated writable save mount; a client gets none. Save paths and mount controls are
not added to the request contract, and a second managed writer receives HTTP `409`.

The socket defaults to `/run/retrobrowser/runtime-agent.sock` with mode `0660`. The
Session Manager will consume this private contract in a later milestone.
