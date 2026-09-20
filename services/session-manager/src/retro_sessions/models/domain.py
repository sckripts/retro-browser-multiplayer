from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from unicodedata import category, normalize
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

SafeUserId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@-]*$"),
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def validate_friendly_name(value: str) -> str:
    normalized = normalize("NFC", value)
    if normalized != normalized.strip():
        raise ValueError("name must not have surrounding whitespace")
    if any(category(character).startswith("C") for character in normalized):
        raise ValueError("name must not contain control characters")
    return normalized


class SessionState(StrEnum):
    CREATING = "CREATING"
    STARTING = "STARTING"
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    DRAINING = "DRAINING"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class ParticipantState(StrEnum):
    ALLOCATING = "ALLOCATING"
    STARTING = "STARTING"
    STREAM_READY = "STREAM_READY"
    NETPLAY_CONNECTING = "NETPLAY_CONNECTING"
    ACTIVE = "ACTIVE"
    LEAVING = "LEAVING"
    LEFT = "LEFT"
    ERROR = "ERROR"


class Actor(StrictModel):
    user_id: SafeUserId
    display_name: str = Field(min_length=1, max_length=64)

    @field_validator("display_name")
    @classmethod
    def friendly_display_name(cls, value: str) -> str:
        return validate_friendly_name(value)


class GameRecord(StrictModel):
    romm_rom_id: int = Field(gt=0)
    platform: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    canonical_path: str = Field(min_length=1, max_length=4096)
    rom_sha256: Sha256


class CoreProfile(StrictModel):
    profile_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    platform: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    max_players: int = Field(ge=2, le=16)


class CreateSessionRequest(StrictModel):
    display_name: str = Field(min_length=1, max_length=64)
    romm_rom_id: int = Field(gt=0)
    max_players: int = Field(ge=2, le=16)

    @field_validator("display_name")
    @classmethod
    def friendly_session_name(cls, value: str) -> str:
        return validate_friendly_name(value)


class Participant(StrictModel):
    participant_id: UUID = Field(strict=False)
    session_id: UUID = Field(strict=False)
    user_id: SafeUserId
    display_name: str = Field(min_length=1, max_length=64)
    player_slot: int = Field(ge=1, le=16)
    runtime_id: UUID | None = Field(default=None, strict=False)
    stream_path: str | None = Field(default=None, max_length=96)
    state: ParticipantState
    joined_at: datetime
    last_heartbeat: datetime


class Session(StrictModel):
    session_id: UUID = Field(strict=False)
    display_name: str = Field(min_length=1, max_length=64)
    owner_user_id: SafeUserId
    romm_rom_id: int = Field(gt=0)
    platform: str
    rom_sha256: Sha256
    core_profile_id: str
    max_players: int = Field(ge=2, le=16)
    state: SessionState
    participants: tuple[Participant, ...]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    closed_reason: str | None = Field(default=None, max_length=64)
    revision: int = Field(default=0, ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def player_count(self) -> int:
        return sum(
            participant.state not in {ParticipantState.LEFT, ParticipantState.ERROR}
            for participant in self.participants
        )

    @model_validator(mode="after")
    def consistent_participants(self) -> Self:
        if any(item.session_id != self.session_id for item in self.participants):
            raise ValueError("participant belongs to another session")
        active = [
            item
            for item in self.participants
            if item.state not in {ParticipantState.LEFT, ParticipantState.ERROR}
        ]
        if len({item.user_id for item in active}) != len(active):
            raise ValueError("active participant users must be unique")
        if len({item.player_slot for item in active}) != len(active):
            raise ValueError("active player slots must be unique")
        if any(item.player_slot > self.max_players for item in active):
            raise ValueError("participant slot exceeds session capacity")
        if self.player_count > self.max_players:
            raise ValueError("participant count exceeds session capacity")
        if not self.created_at.tzinfo or not self.updated_at.tzinfo or not self.expires_at.tzinfo:
            raise ValueError("session timestamps must be timezone-aware")
        return self


class SessionList(StrictModel):
    items: list[Session]


class StreamLaunch(StrictModel):
    """Browser-safe launch material for exactly one active participant runtime."""

    stream_path: str = Field(
        min_length=10,
        max_length=97,
        pattern=r"^/stream/[a-f0-9]{32}/$",
    )
    access_token: str = Field(min_length=32, max_length=512)
    expires_at: datetime

    @model_validator(mode="after")
    def expiry_is_timezone_aware(self) -> Self:
        if not self.expires_at.tzinfo:
            raise ValueError("launch expiry must be timezone-aware")
        return self


class RuntimeCapacity(StrictModel):
    maximum: int = Field(ge=1)
    used: int = Field(ge=0)
    available: int = Field(ge=0)


class ParticipantDiagnostic(StrictModel):
    participant_id: UUID = Field(strict=False)
    player_slot: int = Field(ge=1, le=16)
    participant_state: ParticipantState
    runtime_state: str | None = None
    runtime_health: Literal["none", "starting", "healthy", "unhealthy"] | None = None


class SessionDiagnostic(StrictModel):
    session_id: UUID = Field(strict=False)
    session_state: SessionState
    platform: str
    core_profile_id: str
    player_count: int = Field(ge=0)
    max_players: int = Field(ge=2)
    closed_reason: str | None = None
    expires_at: datetime
    runtime_capacity: RuntimeCapacity
    participants: tuple[ParticipantDiagnostic, ...]
