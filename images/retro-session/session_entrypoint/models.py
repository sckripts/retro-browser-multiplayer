from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@-]*$"),
]
CoreProfileId = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$"),
]
ControllerPort = Annotated[int, Field(ge=1, le=16)]
ControllerDevice = Annotated[int, Field(ge=0, le=65535)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class GameSpec(StrictModel):
    canonical_path: str = Field(min_length=1, max_length=4096)
    expected_sha256: Sha256


class EmulatorSpec(StrictModel):
    core_profile: CoreProfileId


class NetplaySpec(StrictModel):
    role: Literal["standalone", "host", "client"]
    host: str | None = Field(default=None, min_length=1, max_length=253)
    port: int = Field(ge=1024, le=65535)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        labels = value.split(".")
        if any(
            not label
            or len(label) > 63
            or not label[0].isalnum()
            or not label[-1].isalnum()
            or any(not (character.isalnum() or character == "-") for character in label)
            for label in labels
        ):
            raise ValueError("host must be an IPv4 address or DNS hostname")
        return value

    @model_validator(mode="after")
    def validate_role_host(self) -> Self:
        if self.role == "client" and self.host is None:
            raise ValueError("client Netplay role requires host")
        if self.role != "client" and self.host is not None:
            raise ValueError("host is allowed only for client Netplay role")
        return self


class StreamSpec(StrictModel):
    subfolder: Annotated[
        str,
        Field(
            min_length=9,
            max_length=96,
            pattern=r"^/stream/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
        ),
    ]
    display_profile: Literal["hd-720p60"]


class PersistenceSpec(StrictModel):
    save_mode: Literal["ephemeral", "host-authoritative"] = "ephemeral"


class RuntimeSpec(StrictModel):
    schema_version: Literal[1]
    session_id: UUID = Field(strict=False)
    participant_id: UUID = Field(strict=False)
    user_id: SafeId
    player_name: str = Field(min_length=1, max_length=31)
    game: GameSpec
    emulator: EmulatorSpec
    netplay: NetplaySpec
    stream: StreamSpec
    persistence: PersistenceSpec = Field(default_factory=PersistenceSpec)

    @field_validator("player_name")
    @classmethod
    def validate_player_name(cls, value: str) -> str:
        has_control = any(ord(character) < 32 or ord(character) == 127 for character in value)
        if value != value.strip() or has_control:
            raise ValueError(
                "player_name must not contain surrounding whitespace or control characters"
            )
        return value

    @model_validator(mode="after")
    def persistent_save_belongs_to_host(self) -> Self:
        if self.persistence.save_mode == "host-authoritative" and self.netplay.role != "host":
            raise ValueError("host-authoritative persistence is allowed only for the Netplay host")
        return self


class ManifestArtifact(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)

    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    artifact_path: Path = Field(strict=False)
    artifact_sha256: Sha256


class CoreProfile(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)

    platform: Literal["linux-amd64"]
    max_players: int = Field(ge=1, le=16)
    controller_topology: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    controller_port_devices: dict[ControllerPort, ControllerDevice] = Field(
        default_factory=dict, max_length=16
    )
    netplay_status: Literal["not-tested", "validated"]
    frontend: ManifestArtifact
    core: ManifestArtifact


class CoreManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1]
    profiles: dict[CoreProfileId, CoreProfile] = Field(min_length=1)
