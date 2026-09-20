from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone8.yml"
SESSION_DOCKERFILE = ROOT / "services" / "session-manager" / "Dockerfile"


def load_compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_only_runtime_agent_receives_docker_socket() -> None:
    services = load_compose()["services"]
    holders = [
        name
        for name, service in services.items()
        if any("docker.sock" in str(volume) for volume in service.get("volumes", []))
    ]
    assert holders == ["runtime-agent"]
    assert services["runtime-agent"]["network_mode"] == "none"
    assert "ports" not in services["runtime-agent"]
    assert services["runtime-agent"]["cap_add"] == ["CHOWN"]


def test_session_manager_has_only_private_control_plane_access() -> None:
    services = load_compose()["services"]
    manager = services["session-manager"]
    assert "ports" not in manager
    assert manager["networks"] == ["control"]
    assert all("docker.sock" not in str(volume) for volume in manager["volumes"])
    assert any("runtime-agent-control:/run/retrobrowser" in str(v) for v in manager["volumes"])
    assert manager["read_only"] is True
    assert manager["cap_drop"] == ["ALL"]
    assert "cap_add" not in manager


def test_runtime_networks_are_private_and_host_is_not_configurable_by_api() -> None:
    compose = load_compose()
    networks = compose["networks"]
    assert networks["stream"]["internal"] is True
    assert networks["retro-net"]["internal"] is True
    manager_environment = compose["services"]["session-manager"]["environment"]
    assert "NETPLAY_HOST" not in manager_environment
    assert manager_environment["M8_NETPLAY_NETWORK"] == "retrobrowser-m8-retro-net"


def test_only_local_edge_publishes_a_port_and_has_no_docker_socket() -> None:
    services = load_compose()["services"]
    publishers = [name for name, service in services.items() if "ports" in service]
    assert publishers == ["edge"]
    assert services["edge"]["ports"] == ["127.0.0.1:8092:8080"]
    assert all("docker.sock" not in str(v) for v in services["edge"]["volumes"])


def test_images_and_python_dependencies_are_immutable() -> None:
    compose = load_compose()
    valkey_image = compose["services"]["valkey"]["image"]
    assert valkey_image.startswith("valkey/valkey:9.1.2-alpine@sha256:")
    dockerfile = SESSION_DOCKERFILE.read_text(encoding="utf-8")
    assert "python:3.14.7-slim-trixie@sha256:" in dockerfile
    assert "--require-hashes" in dockerfile
    assert ":latest" not in dockerfile
    assert compose["services"]["valkey"]["user"] == "999:1000"


def test_stop_helper_removes_dynamic_runtimes_through_agent() -> None:
    script = (ROOT / "infra" / "scripts" / "acceptance" / "milestone8-stop.ps1").read_text(
        encoding="utf-8"
    )
    assert "retro_runtime.client list" in script
    assert "retro_runtime.client remove" in script
    assert "docker rm" not in script
