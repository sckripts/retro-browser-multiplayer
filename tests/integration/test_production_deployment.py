from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE_PATH = ROOT / "compose.yml"
COMPOSE_TEXT = COMPOSE_PATH.read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXT)


def test_single_production_model_contains_the_accepted_services() -> None:
    assert set(COMPOSE["services"]) == {
        "runtime-agent",
        "session-manager",
        "valkey",
        "network-anchor",
        "authentik-postgres",
        "authentik-server",
        "authentik-worker",
        "romm-database",
        "romm",
        "edge",
        "turn-rest",
        "coturn",
        "prometheus",
        "grafana",
    }
    assert "milestone" not in COMPOSE_TEXT.lower()
    assert "mailpit" not in COMPOSE_TEXT.lower()
    assert all("build" not in service for service in COMPOSE["services"].values())


def test_runtime_agent_alone_has_the_docker_socket() -> None:
    socket_holders = []
    for name, service in COMPOSE["services"].items():
        volumes = service.get("volumes", [])
        if any("/var/run/docker.sock" in str(volume) for volume in volumes):
            socket_holders.append(name)
    assert socket_holders == ["runtime-agent"]
    assert COMPOSE["services"]["runtime-agent"]["network_mode"] == "none"


def test_private_networks_and_public_ports_are_explicit() -> None:
    for name in ["control", "romm-data", "observability", "stream", "retro-net"]:
        assert COMPOSE["networks"][name]["internal"] is True
    published = {name for name, service in COMPOSE["services"].items() if service.get("ports")}
    assert published == {"edge", "coturn", "grafana"}
    assert "127.0.0.1" in str(COMPOSE["services"]["grafana"]["ports"])


def test_custom_images_are_operator_supplied_immutable_references() -> None:
    for service, variable in {
        "runtime-agent": "RUNTIME_AGENT_IMAGE",
        "session-manager": "SESSION_MANAGER_IMAGE",
        "network-anchor": "RUNTIME_AGENT_IMAGE",
        "romm": "ROMM_IMAGE",
    }.items():
        assert variable in COMPOSE["services"][service]["image"]
    start_script = (ROOT / "infra/scripts/production/start.ps1").read_text(encoding="utf-8")
    assert "name@sha256" in start_script
    assert "RETRO_SESSION_IMAGE" in start_script


def test_production_and_acceptance_interfaces_are_separated() -> None:
    production = ROOT / "infra/scripts/production"
    for name in ["initialize.ps1", "build-images.ps1", "start.ps1", "verify.ps1", "stop.ps1"]:
        assert (production / name).is_file()
    scripts_root = ROOT / "infra/scripts"
    assert not list(scripts_root.glob("milestone*.ps1"))
    assert list((scripts_root / "acceptance").glob("milestone*.ps1"))
    assert not list((ROOT / "infra/compose").glob("compose.milestone*.yml"))
    assert list((ROOT / "infra/compose/acceptance").glob("compose.milestone*.yml"))


def test_emulator_template_is_planning_only_and_fail_closed() -> None:
    template_path = ROOT / "docs/examples/emulator-profile.example.yaml"
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    runtime_manifest = (ROOT / "images/retro-session/manifests/cores.yaml").read_text(
        encoding="utf-8"
    )
    assert template["core"]["netplay_status"] == "planned"
    assert template["bios"]["required"] is False
    assert template["content"]["layout"] == "single-file"
    assert template["profile_id"] not in runtime_manifest
    assert (ROOT / "docs/adding-emulators.md").is_file()
