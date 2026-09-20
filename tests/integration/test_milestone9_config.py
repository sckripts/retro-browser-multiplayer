from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone9.yml"


def load_compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_session_manager_can_reach_private_stream_api_without_public_port() -> None:
    services = load_compose()["services"]
    manager = services["session-manager"]
    assert manager["networks"] == ["control", "stream"]
    assert "ports" not in manager
    assert all("docker.sock" not in str(volume) for volume in manager["volumes"])
    assert services["runtime-agent"]["network_mode"] == "none"


def test_only_runtime_agent_has_docker_socket_and_only_edge_publishes() -> None:
    services = load_compose()["services"]
    socket_holders = [
        name
        for name, service in services.items()
        if any("docker.sock" in str(volume) for volume in service.get("volumes", []))
    ]
    publishers = [name for name, service in services.items() if "ports" in service]
    assert socket_holders == ["runtime-agent"]
    assert publishers == ["edge"]
    assert services["edge"]["ports"] == ["127.0.0.1:8093:8080"]
    assert services["edge"]["networks"] == ["ingress", "stream"]


def test_stream_and_netplay_networks_remain_private_and_distinct() -> None:
    compose = load_compose()
    assert compose["networks"]["stream"]["internal"] is True
    assert compose["networks"]["retro-net"]["internal"] is True
    assert compose["networks"]["ingress"] == {}
    environment = compose["services"]["session-manager"]["environment"]
    assert environment["SESSION_MANAGER_STREAM_NETWORK"] == "retrobrowser-m9-stream"
    assert environment["SESSION_MANAGER_NETPLAY_NETWORK"] == "retrobrowser-m9-retro-net"


def test_runtime_security_settings_are_server_controlled() -> None:
    environment = load_compose()["services"]["runtime-agent"]["environment"]
    assert environment["RUNTIME_AGENT_ALLOWED_ORIGINS"] == "http://127.0.0.1:8093"
    source = (
        ROOT / "services" / "runtime-agent" / "src" / "retro_runtime" / "service.py"
    ).read_text(encoding="utf-8")
    for setting in (
        "SELKIES_ENABLE_BASIC_AUTH=false",
        "SELKIES_ENABLE_SHARING=false",
        "SELKIES_ENABLE_COLLAB=false",
        "SELKIES_ENABLE_CLIPBOARD=false",
        "SELKIES_COMMAND_ENABLED=false",
        "SELKIES_FILE_TRANSFERS=none",
    ):
        assert setting in source


def test_access_logs_are_disabled_and_verifier_checks_websocket_auth() -> None:
    traefik = (ROOT / "infra" / "traefik" / "static" / "milestone9.yml").read_text(encoding="utf-8")
    verifier = (ROOT / "infra" / "scripts" / "acceptance" / "milestone9-verify.ps1").read_text(
        encoding="utf-8"
    )
    client = (
        ROOT / "services" / "session-manager" / "src" / "retro_sessions" / "client.py"
    ).read_text(encoding="utf-8")
    assert "accessLog:" not in traefik
    assert "verify-stream" in verifier
    assert "!= 401" in client
    assert "!= 101" in client
    assert "Write-Host $launch" not in verifier


def test_stop_helper_removes_dynamic_runtimes_through_agent() -> None:
    script = (ROOT / "infra" / "scripts" / "acceptance" / "milestone9-stop.ps1").read_text(
        encoding="utf-8"
    )
    assert "retro_runtime.client list" in script
    assert "retro_runtime.client remove" in script
    assert "docker rm" not in script
