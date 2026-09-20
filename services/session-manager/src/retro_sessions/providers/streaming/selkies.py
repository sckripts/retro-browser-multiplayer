import http.client
import json
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from retro_sessions.errors import OrchestrationError
from retro_sessions.security.tokens import derive_controller_token, derive_master_token

MAX_RESPONSE_BYTES = 64 * 1024
SelkiesRequester = Callable[[str, str, dict[str, str], dict[str, object]], int]


class SelkiesStreamProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    orchestration_secret: SecretStr = Field(min_length=32, max_length=512)
    port: int = Field(default=8080, ge=1, le=65535)
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)


class SelkiesStreamProvider:
    """Manage one scoped controller token through each runtime's private Selkies API."""

    def __init__(
        self,
        config: SelkiesStreamProviderConfig,
        *,
        requester: SelkiesRequester | None = None,
    ) -> None:
        self.config = config
        self._requester = requester or self._request

    @staticmethod
    def _container_name(participant_id: UUID) -> str:
        return f"retrobrowser-runtime-{participant_id.hex}"

    @staticmethod
    def _path(participant_id: UUID) -> str:
        return f"/stream/{participant_id.hex}/api/tokens"

    def _request(
        self,
        authority: str,
        path: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> int:
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        connection = http.client.HTTPConnection(authority, timeout=self.config.timeout_seconds)
        try:
            connection.request("POST", path, body=encoded, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, http.client.HTTPException) as error:
            raise OrchestrationError("Selkies token API is unavailable") from error
        finally:
            connection.close()
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OrchestrationError("Selkies token API response is too large")
        return response.status

    def _replace(self, participant_id: UUID, tokens: dict[str, object]) -> None:
        master_token = derive_master_token(self.config.orchestration_secret, participant_id)
        status = self._requester(
            f"{self._container_name(participant_id)}:{self.config.port}",
            self._path(participant_id),
            {
                "Authorization": f"Bearer {master_token}",
                "Content-Type": "application/json",
            },
            tokens,
        )
        if status < 200 or status >= 300:
            raise OrchestrationError(f"Selkies token API rejected the operation with HTTP {status}")

    def provision(self, participant_id: UUID, *, gamepad_slot: int) -> str:
        if gamepad_slot < 1 or gamepad_slot > 4:
            raise ValueError("Selkies gamepad slot must be between 1 and 4")
        token = derive_controller_token(self.config.orchestration_secret, participant_id)
        self._replace(
            participant_id,
            {token: {"role": "controller", "slot": gamepad_slot, "mk_control": True}},
        )
        return token

    def revoke(self, participant_id: UUID) -> None:
        self._replace(participant_id, {})

    def health(self) -> bool:
        # There is no runtime-independent Selkies endpoint; configuration validation is eager.
        return True
