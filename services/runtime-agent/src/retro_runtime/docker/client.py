import http.client
import json
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import quote, urlencode

from retro_runtime.errors import ConflictError, EngineError, NotFoundError
from retro_runtime.models import ContainerRecord


class EngineClient(Protocol):
    def ping(self) -> bool: ...

    def create_container(self, name: str, payload: Mapping[str, object]) -> str: ...

    def start_container(self, container_id: str) -> None: ...

    def inspect_container(self, container_id: str) -> ContainerRecord: ...

    def stop_container(self, container_id: str) -> None: ...

    def remove_container(self, container_id: str) -> None: ...

    def list_managed_containers(self) -> list[ContainerRecord]: ...


class UnixSocketConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: Path) -> None:
        super().__init__("localhost", timeout=30)
        self.socket_path = socket_path

    def connect(self) -> None:
        address_family = socket.AddressFamily(1)
        connection = socket.socket(address_family, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        connection.connect(str(self.socket_path))
        self.sock = connection


class DockerEngineClient:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        version = self._request("GET", "/version", versioned=False)
        api_version = version.get("ApiVersion")
        if not isinstance(api_version, str) or not api_version.replace(".", "").isdigit():
            raise EngineError("Docker Engine returned an invalid API version")
        self.api_prefix = f"/v{api_version}"

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
        *,
        expected: frozenset[int] = frozenset({200}),
        versioned: bool = True,
    ) -> dict[str, Any]:
        connection = UnixSocketConnection(self.socket_path)
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"} if encoded is not None else {}
        request_path = f"{getattr(self, 'api_prefix', '') if versioned else ''}{path}"
        try:
            connection.request(method, request_path, body=encoded, headers=headers)
            response = connection.getresponse()
            raw = response.read(1024 * 1024)
        except OSError as error:
            raise EngineError(f"Docker Engine connection failed: {error}") from error
        finally:
            connection.close()
        if response.status not in expected:
            message = raw.decode("utf-8", errors="replace")[:512]
            if response.status == 404:
                raise NotFoundError("Docker object was not found")
            if response.status == 409:
                raise ConflictError("Docker object conflicts with existing state")
            raise EngineError(f"Docker Engine returned HTTP {response.status}: {message}")
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise EngineError("Docker Engine returned invalid JSON") from error
        if not isinstance(parsed, dict):
            return {"items": parsed}
        return cast(dict[str, Any], parsed)

    def ping(self) -> bool:
        connection = UnixSocketConnection(self.socket_path)
        try:
            connection.request("GET", "/_ping")
            response = connection.getresponse()
            return response.status == 200 and response.read(16) == b"OK"
        except OSError:
            return False
        finally:
            connection.close()

    def create_container(self, name: str, payload: Mapping[str, object]) -> str:
        result = self._request(
            "POST",
            f"/containers/create?{urlencode({'name': name})}",
            payload,
            expected=frozenset({201}),
        )
        container_id = result.get("Id")
        if not isinstance(container_id, str):
            raise EngineError("Docker Engine did not return a container ID")
        return container_id

    def start_container(self, container_id: str) -> None:
        self._request(
            "POST",
            f"/containers/{quote(container_id, safe='')}/start",
            expected=frozenset({204, 304}),
        )

    def inspect_container(self, container_id: str) -> ContainerRecord:
        item = self._request("GET", f"/containers/{quote(container_id, safe='')}/json")
        config = item.get("Config", {})
        state = item.get("State", {})
        health = state.get("Health") or {}
        health_status = str(health.get("Status", "none"))
        if health_status not in {"none", "starting", "healthy", "unhealthy"}:
            health_status = "none"
        return ContainerRecord(
            container_id=str(item.get("Id", "")),
            name=str(item.get("Name", "")).removeprefix("/"),
            state=str(state.get("Status", "unknown")),
            health_status=cast(Any, health_status),
            labels=dict(config.get("Labels") or {}),
            image=str(config.get("Image", "")),
        )

    def stop_container(self, container_id: str) -> None:
        self._request(
            "POST",
            f"/containers/{quote(container_id, safe='')}/stop?t=20",
            expected=frozenset({204, 304}),
        )

    def remove_container(self, container_id: str) -> None:
        self._request(
            "DELETE",
            f"/containers/{quote(container_id, safe='')}?v=1",
            expected=frozenset({204}),
        )

    def list_managed_containers(self) -> list[ContainerRecord]:
        filters = json.dumps({"label": ["io.retrobrowser.runtime-agent.managed=true"]})
        result = self._request(
            "GET", f"/containers/json?{urlencode({'all': '1', 'filters': filters})}"
        )
        records: list[ContainerRecord] = []
        for item in result.get("items", []):
            names = item.get("Names") or [""]
            records.append(
                ContainerRecord(
                    container_id=str(item.get("Id", "")),
                    name=str(names[0]).removeprefix("/"),
                    state=str(item.get("State", "unknown")),
                    health_status="none",
                    labels=dict(item.get("Labels") or {}),
                    image=str(item.get("Image", "")),
                )
            )
        return records
