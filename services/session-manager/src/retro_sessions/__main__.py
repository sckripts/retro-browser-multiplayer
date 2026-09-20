import hashlib
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal, cast

import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr

from retro_sessions.api import create_app
from retro_sessions.models import CoreProfile, GameRecord
from retro_sessions.observability import configure_json_logging
from retro_sessions.providers import RomMProvider
from retro_sessions.providers.execution import (
    LocalRuntimeAgentProvider,
    RuntimeAgentProviderConfig,
)
from retro_sessions.providers.romm import HttpRomMProvider, HttpRomMProviderConfig
from retro_sessions.providers.static import StaticCoreRegistry, StaticRomMProvider
from retro_sessions.providers.streaming import SelkiesStreamProvider, SelkiesStreamProviderConfig
from retro_sessions.repositories.valkey import connect_valkey
from retro_sessions.services import SessionService


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _setting(name: str, legacy_name: str) -> str:
    value = os.environ.get(name) or os.environ.get(legacy_name)
    if value is None:
        raise KeyError(name)
    return value


def _trusted_rom() -> tuple[Path, str]:
    root = Path(_setting("SESSION_MANAGER_ROM_ROOT", "M8_ROM_ROOT")).resolve(strict=True)
    path = Path(_setting("SESSION_MANAGER_ROM_PATH", "M8_ROM_PATH"))
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise ValueError("Milestone 8 ROM path is outside the trusted root")
    if path.absolute() != resolved or ".." in path.parts:
        raise ValueError("Milestone 8 ROM path is not canonical")
    digest = _sha256(resolved)
    if digest != _setting("SESSION_MANAGER_ROM_SHA256", "M8_ROM_SHA256"):
        raise ValueError("trusted ROM SHA-256 does not match")
    return resolved, digest


def build_app() -> FastAPI:
    romm: RomMProvider
    romm_api_url = os.environ.get("SESSION_MANAGER_ROMM_API_URL")
    if romm_api_url:
        romm = HttpRomMProvider(
            HttpRomMProviderConfig(
                api_url=romm_api_url,
                service_token=SecretStr(os.environ["SESSION_MANAGER_ROMM_SERVICE_TOKEN"]),
                rom_root=Path(os.environ["SESSION_MANAGER_ROM_ROOT"]),
            )
        )
    else:
        rom_path, rom_sha256 = _trusted_rom()
        game = GameRecord(
            romm_rom_id=int(
                os.environ.get("SESSION_MANAGER_ROMM_ROM_ID")
                or os.environ.get("M8_ROMM_ROM_ID", "1")
            ),
            platform="nes",
            canonical_path=str(rom_path),
            rom_sha256=rom_sha256,
        )
        romm = StaticRomMProvider(game)
    cores = StaticCoreRegistry(
        (
            CoreProfile(
                profile_id="nes-milestone2",
                platform="nes",
                max_players=2,
            ),
            CoreProfile(
                profile_id="snes-bsnes",
                platform="snes",
                max_players=4,
            ),
            CoreProfile(
                profile_id="genesis-blastem",
                platform="genesis",
                max_players=2,
            ),
        )
    )
    execution = LocalRuntimeAgentProvider(
        RuntimeAgentProviderConfig(
            socket_path=Path(
                os.environ.get("M8_RUNTIME_AGENT_SOCKET", "/run/retrobrowser/runtime-agent.sock")
            ),
            image=_setting("SESSION_MANAGER_RUNTIME_IMAGE", "M8_RUNTIME_IMAGE"),
            stream_network=_setting("SESSION_MANAGER_STREAM_NETWORK", "M8_STREAM_NETWORK"),
            netplay_network=_setting("SESSION_MANAGER_NETPLAY_NETWORK", "M8_NETPLAY_NETWORK"),
            gpu_profile=cast(
                Literal["cpu", "nvidia"],
                os.environ.get("SESSION_MANAGER_GPU_PROFILE")
                or os.environ.get("M8_GPU_PROFILE", "cpu"),
            ),
            orchestration_secret=SecretStr(
                _setting("SESSION_MANAGER_ORCHESTRATION_SECRET", "M8_ORCHESTRATION_SECRET")
            ),
        )
    )
    stream = SelkiesStreamProvider(
        SelkiesStreamProviderConfig(
            orchestration_secret=SecretStr(
                _setting("SESSION_MANAGER_ORCHESTRATION_SECRET", "M8_ORCHESTRATION_SECRET")
            ),
        )
    )
    service = SessionService(
        repository=connect_valkey(os.environ["VALKEY_URL"]),
        romm=romm,
        cores=cores,
        execution=execution,
        stream=stream,
        session_ttl=timedelta(
            seconds=int(os.environ.get("SESSION_MANAGER_MAX_SESSION_SECONDS", "14400"))
        ),
        lobby_lease=timedelta(
            seconds=int(os.environ.get("SESSION_MANAGER_LOBBY_LEASE_SECONDS", "120"))
        ),
        participant_idle_timeout=timedelta(
            seconds=int(os.environ.get("SESSION_MANAGER_IDLE_TIMEOUT_SECONDS", "45"))
        ),
        startup_timeout=timedelta(
            seconds=int(
                os.environ.get("SESSION_MANAGER_STARTUP_TIMEOUT")
                or os.environ.get("M8_STARTUP_TIMEOUT", "180")
            )
        ),
        netplay_connect_timeout=timedelta(
            seconds=int(
                os.environ.get("SESSION_MANAGER_NETPLAY_CONNECT_TIMEOUT")
                or os.environ.get("M8_NETPLAY_CONNECT_TIMEOUT", "45")
            )
        ),
        runtime_capacity=int(os.environ.get("SESSION_MANAGER_RUNTIME_CAPACITY", "8")),
        session_capacity=int(os.environ.get("SESSION_MANAGER_SESSION_CAPACITY", "4")),
        per_user_runtime_capacity=int(
            os.environ.get("SESSION_MANAGER_PER_USER_RUNTIME_CAPACITY", "1")
        ),
    )
    return create_app(
        service,
        service_token=SecretStr(os.environ["SESSION_MANAGER_SERVICE_TOKEN"]),
        cleanup_interval=timedelta(
            seconds=int(os.environ.get("SESSION_MANAGER_CLEANUP_INTERVAL_SECONDS", "10"))
        ),
    )


def main() -> None:
    configure_json_logging()
    uvicorn.run(
        build_app(),
        host="0.0.0.0",  # noqa: S104
        port=8080,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
