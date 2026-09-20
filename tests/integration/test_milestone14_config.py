from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra/compose/acceptance/compose.milestone14.yml"
STATIC = ROOT / "infra/traefik/static/milestone14.yml"
ROUTE_TEMPLATE = ROOT / "infra/traefik/dynamic/milestone14-base.template.yml"


class ComposeLoader(yaml.SafeLoader):
    pass


def _compose_sequence(loader: ComposeLoader, node: yaml.SequenceNode) -> list[object]:
    return loader.construct_sequence(node)


ComposeLoader.add_constructor("!reset", _compose_sequence)
ComposeLoader.add_constructor("!override", _compose_sequence)


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.load(path.read_text(encoding="utf-8"), Loader=ComposeLoader)  # noqa: S506
    assert isinstance(document, dict)
    return document


def test_only_edge_and_coturn_publish_public_ports() -> None:
    services = load_yaml(COMPOSE)["services"]
    assert isinstance(services, dict)
    public_services = {name for name, service in services.items() if "ports" in service}
    assert public_services == {"romm", "authentik-server", "mailpit", "edge", "coturn"}
    assert services["romm"]["ports"] == []
    assert services["authentik-server"]["ports"] == []
    assert services["mailpit"]["ports"] == []
    assert services["edge"]["ports"] == [
        "${M14_BIND_ADDRESS:-0.0.0.0}:${M14_HTTP_PORT:-80}:8080",
        "${M14_BIND_ADDRESS:-0.0.0.0}:${M14_HTTPS_PORT:-443}:8443",
    ]
    assert all(
        "docker.sock" not in str(services[name]) for name in services if name != "runtime-agent"
    )


def test_dynamic_runtimes_are_server_configured_for_private_turn_rest() -> None:
    agent = load_yaml(COMPOSE)["services"]["runtime-agent"]
    environment = agent["environment"]
    assert environment["RUNTIME_AGENT_STREAM_MODE"] == "webrtc"
    assert environment["RUNTIME_AGENT_TURN_REST_URI"] == "http://turn-rest:8008/"
    assert environment["RUNTIME_AGENT_ROUTE_HOST"].startswith("${M14_PUBLIC_HOSTNAME:")
    turn_rest = load_yaml(COMPOSE)["services"]["turn-rest"]
    assert "ports" not in turn_rest
    assert turn_rest["networks"] == ["stream"]


def test_public_edge_uses_tls_and_host_scoped_control_routes() -> None:
    static = load_yaml(STATIC)
    assert static["entryPoints"]["web"]["http"]["tls"]["options"] == "milestone14@file"
    assert "accessLog" not in static
    route = load_yaml(ROUTE_TEMPLATE)
    routers = route["http"]["routers"]
    assert "Host(`__M14_AUTH_HOSTNAME__`)" == routers["milestone14-authentik"]["rule"]
    assert "Host(`__M14_PUBLIC_HOSTNAME__`)" in routers["milestone14-romm"]["rule"]


def test_public_helpers_and_acceptance_runbook_exist() -> None:
    for name in ["milestone14-start.ps1", "milestone14-verify.ps1", "milestone14-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    runbook = (ROOT / "docs/milestone-14-remote-mvp.md").read_text(encoding="utf-8")
    assert "Contra Night" in runbook
    assert "RequireClean" in runbook
