from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone6.yml"
DOCKERFILE = ROOT / "services" / "runtime-agent" / "Dockerfile"


def load_compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_only_runtime_agent_receives_docker_socket() -> None:
    compose = load_compose()
    services = compose["services"]

    holders = []
    for name, service in services.items():
        volumes = service.get("volumes", [])
        if any("/var/run/docker.sock" in str(volume) for volume in volumes):
            holders.append(name)

    assert holders == ["runtime-agent"]
    assert services["runtime-agent"]["network_mode"] == "none"
    assert "ports" not in services["runtime-agent"]


def test_control_client_has_socket_but_no_engine_or_network_access() -> None:
    compose = load_compose()
    client = compose["services"]["runtime-agent-client"]
    volumes = client["volumes"]

    assert any("runtime-agent-control:/run/retrobrowser" in str(volume) for volume in volumes)
    assert all("docker.sock" not in str(volume) for volume in volumes)
    assert client["network_mode"] == "none"
    assert client["read_only"] is True


def test_agent_configuration_is_allowlisted_and_digest_driven() -> None:
    compose = load_compose()
    environment = compose["services"]["runtime-agent"]["environment"]

    assert environment["RUNTIME_AGENT_APPROVED_IMAGE"].startswith("${M6_RUNTIME_IMAGE:")
    networks = set(environment["RUNTIME_AGENT_APPROVED_NETWORKS"].split(","))
    assert networks == {"retrobrowser-m6-stream", "retrobrowser-m6-retro-net"}
    assert "host" not in networks
    assert environment["RUNTIME_AGENT_GPU_PROFILES"] == "cpu"


def test_agent_image_has_immutable_base_and_no_floating_tag() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "python:3.14.7-slim-trixie@sha256:" in dockerfile
    assert ":latest" not in dockerfile
    assert ":main" not in dockerfile


def test_no_agent_service_defines_arbitrary_runtime_inputs() -> None:
    compose = load_compose()
    agent = compose["services"]["runtime-agent"]
    environment = agent["environment"]

    forbidden = {"COMMAND", "ENTRYPOINT", "MOUNTS", "ENVIRONMENT", "PRIVILEGED"}
    assert forbidden.isdisjoint(environment)
    assert agent["cap_drop"] == ["ALL"]
    assert agent["security_opt"] == ["no-new-privileges:true"]
