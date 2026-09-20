import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from retro_runtime.api import RuntimeUnixServer
from retro_runtime.docker import DockerEngineClient
from retro_runtime.models import AgentConfig
from retro_runtime.observability import MetricsTargetProvider, configure_json_logging
from retro_runtime.routes import FileRouteProvider
from retro_runtime.service import RuntimeService


def config_from_environment() -> AgentConfig:
    networks = frozenset(
        item.strip()
        for item in os.environ["RUNTIME_AGENT_APPROVED_NETWORKS"].split(",")
        if item.strip()
    )
    gpu_profiles = frozenset(
        item.strip()
        for item in os.environ.get("RUNTIME_AGENT_GPU_PROFILES", "cpu").split(",")
        if item.strip()
    )
    return AgentConfig(
        docker_socket=Path(os.environ.get("RUNTIME_AGENT_DOCKER_SOCKET", "/var/run/docker.sock")),
        listen_socket=Path(
            os.environ.get("RUNTIME_AGENT_LISTEN_SOCKET", "/run/retrobrowser/runtime-agent.sock")
        ),
        approved_image=os.environ["RUNTIME_AGENT_APPROVED_IMAGE"],
        approved_networks=networks,
        rom_root=Path(os.environ["RUNTIME_AGENT_ROM_ROOT"]),
        user_data_root=Path(os.environ["RUNTIME_AGENT_USER_DATA_ROOT"]),
        save_data_root=(
            Path(value) if (value := os.environ.get("RUNTIME_AGENT_SAVE_DATA_ROOT")) else None
        ),
        docker_rom_root=os.environ.get("RUNTIME_AGENT_DOCKER_ROM_ROOT"),
        docker_user_data_root=os.environ.get("RUNTIME_AGENT_DOCKER_USER_DATA_ROOT"),
        docker_save_data_root=os.environ.get("RUNTIME_AGENT_DOCKER_SAVE_DATA_ROOT"),
        preprovisioned_user_data=(
            os.environ.get("RUNTIME_AGENT_PREPROVISIONED_USER_DATA", "false").lower() == "true"
        ),
        manage_user_data_permissions=(
            os.environ.get("RUNTIME_AGENT_MANAGE_USER_DATA_PERMISSIONS", "true").lower() == "true"
        ),
        route_root=Path(os.environ["RUNTIME_AGENT_ROUTE_ROOT"]),
        metrics_target_root=(
            Path(value) if (value := os.environ.get("RUNTIME_AGENT_METRICS_TARGET_ROOT")) else None
        ),
        allowed_origins=os.environ["RUNTIME_AGENT_ALLOWED_ORIGINS"],
        route_host=os.environ.get("RUNTIME_AGENT_ROUTE_HOST"),
        selkies_mode=cast(
            Literal["websockets", "webrtc"],
            os.environ.get("RUNTIME_AGENT_STREAM_MODE", "websockets"),
        ),
        turn_rest_uri=os.environ.get("RUNTIME_AGENT_TURN_REST_URI"),
        turn_rest_api_key=os.environ.get("RUNTIME_AGENT_TURN_REST_API_KEY"),
        turn_rest_username=os.environ.get("RUNTIME_AGENT_TURN_REST_USERNAME", "retrobrowser"),
        turn_protocol=cast(
            Literal["udp", "tcp"], os.environ.get("RUNTIME_AGENT_TURN_PROTOCOL", "udp")
        ),
        turn_tls=(os.environ.get("RUNTIME_AGENT_TURN_TLS", "false").lower() == "true"),
        stun_host=os.environ.get("RUNTIME_AGENT_STUN_HOST"),
        stun_port=int(os.environ.get("RUNTIME_AGENT_STUN_PORT", "3478")),
        memory_bytes=int(os.environ.get("RUNTIME_AGENT_MEMORY_BYTES", str(4 * 1024**3))),
        nano_cpus=int(os.environ.get("RUNTIME_AGENT_NANO_CPUS", "2000000000")),
        pids_limit=int(os.environ.get("RUNTIME_AGENT_PIDS_LIMIT", "1024")),
        gpu_profiles=gpu_profiles,
        max_runtimes=int(os.environ.get("RUNTIME_AGENT_MAX_RUNTIMES", "8")),
    )


def main() -> None:
    configure_json_logging()
    try:
        config = config_from_environment()
    except (KeyError, ValidationError) as error:
        raise SystemExit(f"invalid Runtime Agent configuration: {error}") from error
    socket_path = config.listen_socket
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        mode = socket_path.lstat().st_mode
        if not stat.S_ISSOCK(mode):
            raise SystemExit("refusing to replace a non-socket listen path")
        socket_path.unlink()
    service = RuntimeService(
        config,
        DockerEngineClient(config.docker_socket),
        FileRouteProvider(config.route_root, host=config.route_host),
        MetricsTargetProvider(config.metrics_target_root),
    )
    service.reconcile_routes()
    server = RuntimeUnixServer(str(socket_path), service)
    chown = cast(Callable[[Path, int, int], None], getattr(os, "ch" + "own"))
    chown(socket_path, config.control_uid, config.control_gid)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        socket_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
