from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    docker_socket: Path = Path("/var/run/docker.sock")
    listen_socket: Path = Path("/run/retrobrowser/runtime-agent.sock")
    approved_image: str = Field(pattern=r"^(?:[^\s@]+@)?sha256:[0-9a-f]{64}$")
    approved_networks: frozenset[str] = Field(min_length=1)
    rom_root: Path
    user_data_root: Path
    save_data_root: Path | None = None
    docker_rom_root: str | None = None
    docker_user_data_root: str | None = None
    docker_save_data_root: str | None = None
    preprovisioned_user_data: bool = False
    manage_user_data_permissions: bool = True
    control_uid: int = Field(default=0, ge=0, le=65535)
    control_gid: int = Field(default=1000, ge=1, le=65535)
    route_root: Path
    metrics_target_root: Path | None = None
    allowed_origins: str
    route_host: str | None = Field(
        default=None,
        max_length=253,
        pattern=r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$",
    )
    selkies_mode: Literal["websockets", "webrtc"] = "websockets"
    turn_rest_uri: str | None = Field(default=None, pattern=r"^https?://[^\s]+/$")
    turn_rest_api_key: str | None = Field(default=None, min_length=32, max_length=512)
    turn_rest_username: str = Field(
        default="retrobrowser",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    turn_protocol: Literal["udp", "tcp"] = "udp"
    turn_tls: bool = False
    stun_host: str | None = Field(
        default=None,
        max_length=253,
        pattern=r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$",
    )
    stun_port: int = Field(default=3478, ge=1, le=65535)
    memory_bytes: int = Field(default=4 * 1024**3, ge=512 * 1024**2, le=16 * 1024**3)
    nano_cpus: int = Field(default=2_000_000_000, ge=500_000_000, le=8_000_000_000)
    pids_limit: int = Field(default=1024, ge=128, le=4096)
    max_runtimes: int = Field(default=8, ge=1, le=256)
    gpu_profiles: frozenset[str] = frozenset({"cpu"})

    @field_validator("approved_networks")
    @classmethod
    def reject_unsafe_networks(cls, value: frozenset[str]) -> frozenset[str]:
        forbidden = {"host", "none", "bridge", "default"}
        if value & forbidden:
            raise ValueError("approved networks must be project-owned named networks")
        return value

    @field_validator("gpu_profiles")
    @classmethod
    def validate_gpu_profiles(cls, value: frozenset[str]) -> frozenset[str]:
        if not value or not value <= {"cpu", "nvidia"}:
            raise ValueError("gpu profiles must contain only cpu and/or nvidia")
        return value

    @field_validator("docker_socket", "listen_socket", "rom_root", "user_data_root", "route_root")
    @classmethod
    def require_absolute_paths(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("agent filesystem paths must be absolute")
        return value

    @field_validator("metrics_target_root")
    @classmethod
    def require_absolute_metrics_path(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("metrics target root must be absolute")
        return value

    @field_validator("save_data_root")
    @classmethod
    def require_absolute_optional_path(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("agent save-data root must be absolute")
        return value

    @model_validator(mode="after")
    def require_matching_save_roots(self) -> Self:
        if self.docker_save_data_root is not None and self.save_data_root is None:
            raise ValueError("Docker save-data root requires an agent save-data root")
        return self

    @model_validator(mode="after")
    def require_webrtc_services(self) -> Self:
        configured = (self.turn_rest_uri, self.turn_rest_api_key, self.stun_host)
        if self.selkies_mode == "webrtc" and any(value is None for value in configured):
            raise ValueError("WebRTC mode requires TURN REST URI/API key and a STUN hostname")
        if self.selkies_mode != "webrtc" and any(value is not None for value in configured):
            raise ValueError("TURN/STUN settings are allowed only in WebRTC mode")
        return self
