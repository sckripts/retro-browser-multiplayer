from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone12.yml"
ROMM_ROUTE = ROOT / "infra" / "traefik" / "dynamic" / "milestone12-romm.yml"


class ComposeLoader(yaml.SafeLoader):
    pass


def _compose_sequence(loader: ComposeLoader, node: yaml.SequenceNode) -> list[object]:
    return loader.construct_sequence(node)


ComposeLoader.add_constructor("!reset", _compose_sequence)
ComposeLoader.add_constructor("!override", _compose_sequence)


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=ComposeLoader,  # noqa: S506 - this subclasses SafeLoader
    )
    assert isinstance(document, dict)
    return document


def test_romm_and_session_manager_share_only_the_private_api_boundary() -> None:
    services = load_yaml(COMPOSE)["services"]
    assert isinstance(services, dict)
    romm = services["romm"]
    manager = services["session-manager"]
    assert isinstance(romm, dict) and isinstance(manager, dict)
    assert manager["environment"]["SESSION_MANAGER_ROMM_API_URL"] == "http://romm:8080/api"
    assert romm["environment"]["EXTERNAL_MULTIPLAYER_URL"] == "http://session-manager:8080"
    provider_source = (
        ROOT / "services/session-manager/src/retro_sessions/providers/romm/http.py"
    ).read_text()
    assert '"X-External-Multiplayer-Token"' in provider_source
    assert "ports" not in manager
    assert all("docker.sock" not in str(item) for item in romm["volumes"])


def test_browser_uses_one_origin_for_romm_and_dynamic_streams() -> None:
    services = load_yaml(COMPOSE)["services"]
    assert isinstance(services, dict)
    edge = services["edge"]
    romm = services["romm"]
    runtime_agent = services["runtime-agent"]
    assert edge["ports"] == ["127.0.0.1:8096:8080"]
    assert "volumes" not in edge
    assert romm["ports"] == []
    assert (
        runtime_agent["environment"]["RUNTIME_AGENT_ALLOWED_ORIGINS"]
        == "${M12_ROMM_URL:?set in .env.milestone12}"
    )
    route = load_yaml(ROMM_ROUTE)
    router = route["http"]["routers"]["romm"]
    assert router["rule"] == "PathPrefix(`/`)"
    assert route["http"]["services"]["romm"]["loadBalancer"]["servers"] == [
        {"url": "http://romm:8080"}
    ]


def test_romm_image_and_provider_credentials_are_required() -> None:
    services = load_yaml(COMPOSE)["services"]
    assert isinstance(services, dict)
    assert services["romm"]["image"].startswith("${M12_ROMM_IMAGE:?")
    assert (
        "M10_SERVICE_TOKEN"
        in services["session-manager"]["environment"]["SESSION_MANAGER_ROMM_SERVICE_TOKEN"]
    )


def test_milestone12_helpers_exist() -> None:
    start = (ROOT / "infra" / "scripts" / "acceptance" / "milestone12-start.ps1").read_text(
        encoding="utf-8"
    )
    assert 'Join-Path $routeRoot "romm.yml"' in start
    assert "Test-Path -LiteralPath $environmentFile" in start
    assert "Get-OrCreateSecret 'M10_SERVICE_TOKEN'" in start
    assert 'username = "player-one"' in start
    assert 'username = "player-two"' in start
    assert "http://127.0.0.1:9000/api/v3/core/users/" in start
    assert '$romMUrl = "http://localhost:8096"' in start
    assert "Invoke-RestMethod -Method Patch" in start
    assert "url = $callbackUrl" in start
    verify = (ROOT / "infra" / "scripts" / "acceptance" / "milestone12-verify.ps1").read_text(
        encoding="utf-8"
    )
    assert '$expectedCallback = "$($settings.M12_ROMM_URL)/api/oauth/openid"' in verify
    for name in [
        "milestone12-start.ps1",
        "milestone12-verify.ps1",
        "milestone12-stop.ps1",
    ]:
        assert (ROOT / "infra" / "scripts" / "acceptance" / name).is_file()
