import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from retro_sessions.errors import OrchestrationError
from retro_sessions.models import GameRecord

MAX_RESPONSE_BYTES = 64 * 1024
RomMRequester = Callable[[str], tuple[int, object]]


class HttpRomMProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_url: str = Field(min_length=8, max_length=2048)
    service_token: SecretStr = Field(min_length=32, max_length=512)
    rom_root: Path
    timeout_seconds: float = Field(default=10, gt=0, le=60)

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        parsed = urlparse(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("RomM API URL must be an HTTP(S) origin or base path")
        return normalized


class HttpRomMProvider:
    """Resolve trusted game metadata through RomM's private integration API."""

    def __init__(
        self,
        config: HttpRomMProviderConfig,
        *,
        requester: RomMRequester | None = None,
    ) -> None:
        self._config = config
        self._requester = requester or self._request

    def _request(self, path: str) -> tuple[int, object]:
        request = urllib.request.Request(  # noqa: S310
            f"{self._config.api_url}{path}",
            headers={
                "Accept": "application/json",
                "X-External-Multiplayer-Token": self._config.service_token.get_secret_value(),
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request,
                timeout=self._config.timeout_seconds,
            ) as response:
                status = response.status
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            raw = error.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, urllib.error.URLError) as error:
            raise OrchestrationError("RomM is unavailable") from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OrchestrationError("RomM response is too large")
        try:
            document = json.loads(raw) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OrchestrationError("RomM returned invalid JSON") from error
        return status, document

    def _canonical_path(self, relative_path: object) -> Path:
        if not isinstance(relative_path, str):
            raise OrchestrationError("RomM returned an invalid game record")
        relative = Path(relative_path)
        if (
            PurePosixPath(relative_path).is_absolute()
            or PureWindowsPath(relative_path).is_absolute()
            or ".." in relative.parts
        ):
            raise OrchestrationError("RomM returned an unsafe game path")
        try:
            root = self._config.rom_root.resolve(strict=True)
            resolved = (root / relative).resolve(strict=True)
        except OSError as error:
            raise OrchestrationError("RomM game file is unavailable") from error
        if not resolved.is_file() or not resolved.is_relative_to(root):
            raise OrchestrationError("RomM game path escaped the approved root")
        return resolved

    def resolve_game(self, romm_rom_id: int) -> GameRecord:
        status, document = self._requester(f"/multiplayer/games/{romm_rom_id}")
        if status == 404:
            raise KeyError(romm_rom_id)
        if status != 200 or not isinstance(document, dict):
            raise OrchestrationError(f"RomM rejected game resolution with HTTP {status}")
        try:
            returned_id = int(document["romm_rom_id"])
            platform = str(document["platform"])
            rom_sha256 = str(document["rom_sha256"])
            path = self._canonical_path(document["relative_path"])
        except (KeyError, TypeError, ValueError) as error:
            raise OrchestrationError("RomM returned an invalid game record") from error
        if returned_id != romm_rom_id:
            raise OrchestrationError("RomM returned a mismatched game record")
        return GameRecord(
            romm_rom_id=returned_id,
            platform=platform,
            canonical_path=str(path),
            rom_sha256=rom_sha256,
        )

    def health(self) -> bool:
        try:
            status, document = self._requester("/multiplayer/health")
        except OrchestrationError:
            return False
        return status == 200 and document == {"ready": True}
