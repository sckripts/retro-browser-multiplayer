import http.client
import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from retro_sessions.errors import OrchestrationError
from retro_sessions.providers.interfaces import RuntimeHandle, RuntimeRequest
from retro_sessions.security.tokens import derive_master_token

MAX_RESPONSE_BYTES = 1024 * 1024
AgentRequester = Callable[[str, str, dict[str, object] | None], tuple[int, object]]


class RuntimeAgentProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    socket_path: Path = Path("/run/retrobrowser/runtime-agent.sock")
    image: str = Field(pattern=r"^(?:[^\s@]+@)?sha256:[0-9a-f]{64}$")
    stream_network: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    netplay_network: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    gpu_profile: Literal["cpu", "nvidia"] = "cpu"
    netplay_port: int = Field(default=55435, ge=1024, le=65535)
    orchestration_secret: SecretStr = Field(min_length=32, max_length=512)


class _UnixSocketConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: Path) -> None:
        super().__init__("localhost", timeout=30)
        self.socket_path = socket_path

    def connect(self) -> None:
        connection = socket.socket(socket.AddressFamily(1), socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        connection.connect(str(self.socket_path))
        self.sock = connection


class LocalRuntimeAgentProvider:
    """Narrow ExecutionProvider adapter for Runtime Agent's UNIX-socket API."""

    def __init__(
        self,
        config: RuntimeAgentProviderConfig,
        *,
        requester: AgentRequester | None = None,
    ) -> None:
        if config.stream_network == config.netplay_network:
            raise ValueError("stream and Netplay networks must differ")
        self._config = config
        self._requester = requester or self._request

    @staticmethod
    def _container_name(participant_id: UUID) -> str:
        return f"retrobrowser-runtime-{participant_id.hex}"

    def _master_token(self, participant_id: UUID) -> str:
        return derive_master_token(self._config.orchestration_secret, participant_id)

    def _request(
        self, method: str, path: str, payload: dict[str, object] | None
    ) -> tuple[int, object]:
        connection = _UnixSocketConnection(self._config.socket_path)
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, http.client.HTTPException) as error:
            raise OrchestrationError("Runtime Agent is unavailable") from error
        finally:
            connection.close()
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OrchestrationError("Runtime Agent response is too large")
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OrchestrationError("Runtime Agent returned invalid JSON") from error
        return response.status, document

    @staticmethod
    def _handle(status: int, document: object) -> RuntimeHandle:
        if status < 200 or status >= 300:
            raise OrchestrationError(f"Runtime Agent rejected the operation with HTTP {status}")
        if not isinstance(document, dict):
            raise OrchestrationError("Runtime Agent returned an invalid runtime record")
        try:
            participant_id = UUID(str(document["participant_id"]))
            state = str(document["state"])
            health_status = cast(Any, document["health_status"])
            return RuntimeHandle(
                runtime_id=participant_id,
                state=state,
                health_status=health_status,
            )
        except (KeyError, ValueError) as error:
            raise OrchestrationError("Runtime Agent returned an invalid runtime record") from error

    def create(self, request: RuntimeRequest) -> RuntimeHandle:
        if request.role == "host" and request.host_participant_id is not None:
            raise ValueError("host runtime cannot select a Netplay host")
        if request.role == "client" and request.host_participant_id is None:
            raise ValueError("client runtime requires a Netplay host participant")
        host = (
            self._container_name(request.host_participant_id)
            if request.host_participant_id is not None
            else None
        )
        payload: dict[str, object] = {
            "schema_version": 1,
            "session_id": str(request.session_id),
            "participant_id": str(request.participant_id),
            "user_id": request.user_id,
            "player_name": request.player_name,
            "image": self._config.image,
            "rom_path": request.rom_path,
            "rom_sha256": request.rom_sha256,
            "core_profile": request.core_profile,
            "netplay": {
                "role": request.role,
                "host": host,
                "port": self._config.netplay_port,
            },
            "stream_subfolder": f"/stream/{request.participant_id.hex}",
            "stream_network": self._config.stream_network,
            "netplay_network": self._config.netplay_network,
            "gpu_profile": self._config.gpu_profile,
            "selkies_master_token": self._master_token(request.participant_id),
        }
        status, document = self._requester("POST", "/v1/runtimes", payload)
        return self._handle(status, document)

    def inspect(self, participant_id: UUID) -> RuntimeHandle:
        status, document = self._requester("GET", f"/v1/runtimes/{participant_id}", None)
        return self._handle(status, document)

    def list(self) -> list[RuntimeHandle]:
        status, document = self._requester("GET", "/v1/runtimes", None)
        if status != 200:
            raise OrchestrationError(f"Runtime Agent rejected the operation with HTTP {status}")
        if not isinstance(document, dict) or not isinstance(document.get("items"), list):
            raise OrchestrationError("Runtime Agent returned an invalid runtime list")
        return [self._handle(200, item) for item in document["items"]]

    def remove(self, participant_id: UUID) -> None:
        status, _document = self._requester("DELETE", f"/v1/runtimes/{participant_id}", None)
        if status not in {200, 404}:
            raise OrchestrationError(f"Runtime Agent rejected removal with HTTP {status}")

    def health(self) -> bool:
        try:
            status, document = self._requester("GET", "/v1/health", None)
        except OrchestrationError:
            return False
        return status == 200 and document == {"ok": True}
