import os
from pathlib import Path
from typing import Protocol
from uuid import UUID

import yaml


class RouteProvider(Protocol):
    def publish(self, participant_id: UUID, subfolder: str, container_name: str) -> None: ...

    def remove(self, participant_id: UUID) -> None: ...

    def exists(self, participant_id: UUID) -> bool: ...

    def list_participants(self) -> set[UUID]: ...


class FileRouteProvider:
    def __init__(self, route_root: Path, *, host: str | None = None) -> None:
        self.route_root = route_root
        self.host = host
        self.route_root.mkdir(parents=True, exist_ok=True)

    def _path(self, participant_id: UUID) -> Path:
        return self.route_root / f"runtime-{participant_id}.yml"

    def publish(self, participant_id: UUID, subfolder: str, container_name: str) -> None:
        key = f"runtime-{participant_id}"
        path_rule = f"PathPrefix(`{subfolder}`)"
        rule = f"Host(`{self.host}`) && {path_rule}" if self.host else path_rule
        document = {
            "http": {
                "routers": {
                    key: {
                        "entryPoints": ["web"],
                        "rule": rule,
                        "service": key,
                        "middlewares": ["runtime-response-headers"],
                    }
                },
                "middlewares": {
                    "runtime-response-headers": {
                        "headers": {
                            "contentTypeNosniff": True,
                            "customResponseHeaders": {
                                "Referrer-Policy": "no-referrer",
                                "X-Robots-Tag": "noindex, nofollow",
                            },
                        }
                    }
                },
                "services": {
                    key: {
                        "loadBalancer": {
                            "passHostHeader": True,
                            "healthCheck": {
                                "path": f"{subfolder}/api/health",
                                "interval": "5s",
                                "timeout": "2s",
                            },
                            "servers": [{"url": f"http://{container_name}:8080"}],
                        }
                    }
                },
            }
        }
        destination = self._path(participant_id)
        temporary = destination.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            yaml.safe_dump(document, output, sort_keys=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o640)
        os.replace(temporary, destination)

    def remove(self, participant_id: UUID) -> None:
        self._path(participant_id).unlink(missing_ok=True)

    def exists(self, participant_id: UUID) -> bool:
        return self._path(participant_id).is_file()

    def list_participants(self) -> set[UUID]:
        participants: set[UUID] = set()
        for path in self.route_root.glob("runtime-*.yml"):
            try:
                participants.add(UUID(path.stem.removeprefix("runtime-")))
            except ValueError:
                continue
        return participants
