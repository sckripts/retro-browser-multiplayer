from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from retro_sessions.models.domain import CoreProfile, GameRecord, SafeUserId, Sha256


class RuntimeRequest(BaseModel):
    """Trusted provider input; no field is populated from browser runtime parameters."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    session_id: UUID = Field(strict=False)
    participant_id: UUID = Field(strict=False)
    user_id: SafeUserId
    # RetroArch's netplay protocol stores nicknames in a 32-byte field,
    # including its terminating NUL.
    player_name: str = Field(min_length=1, max_length=31)
    rom_path: str = Field(min_length=1, max_length=4096)
    rom_sha256: Sha256
    core_profile: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    role: Literal["host", "client"]
    host_participant_id: UUID | None = Field(default=None, strict=False)


class RuntimeHandle(BaseModel):
    """Provider-neutral runtime state safe to retain in the control plane."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    runtime_id: UUID = Field(strict=False)
    state: str
    health_status: Literal["none", "starting", "healthy", "unhealthy"]


class ExecutionProvider(Protocol):
    """Participant runtime lifecycle boundary, implemented in Milestone 8."""

    def create(self, request: RuntimeRequest) -> RuntimeHandle: ...

    def inspect(self, participant_id: UUID) -> RuntimeHandle: ...

    def list(self) -> list[RuntimeHandle]: ...

    def remove(self, participant_id: UUID) -> None: ...

    def health(self) -> bool: ...


class StreamProvider(Protocol):
    """Browser stream credential boundary."""

    def provision(self, participant_id: UUID, *, gamepad_slot: int) -> str: ...

    def revoke(self, participant_id: UUID) -> None: ...

    def health(self) -> bool: ...


class RouteProvider(Protocol):
    """Stream route publication boundary."""

    def publish(self, participant_id: UUID, stream_path: str) -> None: ...

    def remove(self, participant_id: UUID) -> None: ...

    def health(self) -> bool: ...


class RomMProvider(Protocol):
    """Trusted RomM game resolution boundary."""

    def resolve_game(self, romm_rom_id: int) -> GameRecord: ...

    def health(self) -> bool: ...


class CoreRegistry(Protocol):
    """Approved platform-to-core profile resolution boundary."""

    def resolve(self, platform: str) -> CoreProfile: ...

    def health(self) -> bool: ...
