import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID


class MetricsTargetProvider:
    """Atomically publish private Prometheus file-discovery targets."""

    def __init__(self, root: Path | None) -> None:
        self.root = root
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)

    def _path(self, participant_id: UUID) -> Path | None:
        if self.root is None:
            return None
        return self.root / f"runtime-{participant_id}.json"

    def publish(
        self,
        participant_id: UUID,
        session_id: UUID,
        core_profile: str,
        subfolder: str,
        container_name: str,
        metrics_token: str,
    ) -> None:
        destination = self._path(participant_id)
        if destination is None:
            return
        document = [
            {
                "targets": [f"{container_name}:9091"],
                "labels": {
                    "job": "selkies",
                    "session_id": str(session_id),
                    "participant_id": str(participant_id),
                    "core_profile": core_profile,
                    "__metrics_path__": "/metrics",
                    "__param_token": metrics_token,
                },
            }
        ]
        temporary = destination.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(document, output, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o640)
        if os.name == "posix":
            try:
                chown = cast(Callable[[Path, int, int], None], getattr(os, "ch" + "own"))
                chown(temporary, 65534, 65534)
            except OSError:
                # Docker Desktop drvfs may retain root:root; Prometheus keeps its
                # non-root UID but uses read-only GID 0 for this exact 0640 mount.
                pass
        os.replace(temporary, destination)

    def remove(self, participant_id: UUID) -> None:
        path = self._path(participant_id)
        if path is not None:
            path.unlink(missing_ok=True)

    def list_participants(self) -> set[UUID]:
        if self.root is None:
            return set()
        participants: set[UUID] = set()
        for path in self.root.glob("runtime-*.json"):
            try:
                participants.add(UUID(path.stem.removeprefix("runtime-")))
            except ValueError:
                continue
        return participants
