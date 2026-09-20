from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@-]*$"),
]
NetworkName = Annotated[
    str,
    Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class NetplayRequest(StrictModel):
    role: Literal["standalone", "host", "client"]
    host: str | None = Field(default=None, min_length=1, max_length=253)
    port: int = Field(ge=1024, le=65535)

    @model_validator(mode="after")
    def validate_host(self) -> Self:
        if self.role == "client" and self.host is None:
            raise ValueError("client Netplay role requires host")
        if self.role != "client" and self.host is not None:
            raise ValueError("Netplay host is allowed only for a client")
        if self.host is not None:
            labels = self.host.split(".")
            if any(
                not label
                or len(label) > 63
                or not label[0].isalnum()
                or not label[-1].isalnum()
                or any(not (character.isalnum() or character == "-") for character in label)
                for label in labels
            ):
                raise ValueError("Netplay host must be an IPv4 address or DNS hostname")
        return self


class CreateRuntimeRequest(StrictModel):
    schema_version: Literal[1]
    session_id: UUID = Field(strict=False)
    participant_id: UUID = Field(strict=False)
    user_id: SafeId
    player_name: str = Field(min_length=1, max_length=64)
    image: str = Field(min_length=1, max_length=512)
    rom_path: str = Field(min_length=1, max_length=4096)
    rom_sha256: Sha256
    core_profile: Annotated[
        str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    ]
    netplay: NetplayRequest
    stream_subfolder: Annotated[
        str,
        Field(min_length=9, max_length=96, pattern=r"^/stream/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"),
    ]
    stream_network: NetworkName
    netplay_network: NetworkName
    gpu_profile: Literal["cpu", "nvidia"]
    selkies_master_token: SecretStr = Field(min_length=32, max_length=512)

    @field_validator("player_name")
    @classmethod
    def validate_player_name(cls, value: str) -> str:
        has_control = any(ord(character) < 32 or ord(character) == 127 for character in value)
        if value != value.strip() or has_control:
            raise ValueError("player_name has surrounding whitespace or control characters")
        return value

    @model_validator(mode="after")
    def networks_must_differ(self) -> Self:
        if self.stream_network == self.netplay_network:
            raise ValueError("stream and Netplay networks must be distinct")
        return self


class ContainerRecord(StrictModel):
    container_id: str
    name: str
    state: str
    health_status: Literal["none", "starting", "healthy", "unhealthy"]
    labels: dict[str, str]
    image: str


class RuntimeRecord(StrictModel):
    participant_id: UUID = Field(strict=False)
    container_id: str
    container_name: str
    state: str
    health_status: Literal["none", "starting", "healthy", "unhealthy"]
    stream_subfolder: str
    orphaned: bool


class RuntimeCapacity(StrictModel):
    maximum: int = Field(ge=1)
    used: int = Field(ge=0)
    available: int = Field(ge=0)
