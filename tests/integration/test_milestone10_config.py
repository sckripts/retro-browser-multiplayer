from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone10.yml"
SESSION_SOURCE = (
    ROOT
    / "services"
    / "session-manager"
    / "src"
    / "retro_sessions"
    / "services"
    / "session_service.py"
)
API_SOURCE = ROOT / "services" / "session-manager" / "src" / "retro_sessions" / "api" / "app.py"


def load_compose() -> dict[str, object]:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_lifecycle_harness_keeps_privileged_boundary() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    runtime_agent = services["runtime-agent"]
    session_manager = services["session-manager"]
    edge = services["edge"]
    assert isinstance(runtime_agent, dict)
    assert isinstance(session_manager, dict)
    assert isinstance(edge, dict)
    assert any("docker.sock" in str(item) for item in runtime_agent["volumes"])
    assert all("docker.sock" not in str(item) for item in session_manager["volumes"])
    assert all("docker.sock" not in str(item) for item in edge["volumes"])
    assert "ports" not in session_manager
    assert "ports" not in runtime_agent


def test_harness_uses_bounded_cleanup_settings() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    session_manager = services["session-manager"]
    assert isinstance(session_manager, dict)
    environment = session_manager["environment"]
    assert isinstance(environment, dict)
    assert environment["SESSION_MANAGER_MAX_SESSION_SECONDS"] == "300"
    assert environment["SESSION_MANAGER_LOBBY_LEASE_SECONDS"] == "60"
    assert environment["SESSION_MANAGER_IDLE_TIMEOUT_SECONDS"] == "30"
    assert environment["SESSION_MANAGER_CLEANUP_INTERVAL_SECONDS"] == "5"


def test_lifecycle_worker_and_heartbeat_are_wired() -> None:
    service_source = SESSION_SOURCE.read_text(encoding="utf-8")
    api_source = API_SOURCE.read_text(encoding="utf-8")
    assert "def heartbeat(" in service_source
    assert "def sweep(" in service_source
    assert "def reconcile_startup(" in service_source
    assert '"/sessions/{session_id}/heartbeat"' in api_source
    assert "lifespan=lifespan" in api_source


def test_milestone10_helpers_exist() -> None:
    for name in [
        "milestone10-start.ps1",
        "milestone10-verify.ps1",
        "milestone10-stop.ps1",
    ]:
        assert (ROOT / "infra" / "scripts" / "acceptance" / name).is_file()
