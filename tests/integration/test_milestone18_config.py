import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
COMPOSE = (ROOT / "infra/compose/acceptance/compose.milestone18.yml").read_text(encoding="utf-8")
PROMETHEUS = (ROOT / "infra/prometheus/prometheus.yml").read_text(encoding="utf-8")
DASHBOARD_PATH = ROOT / "infra/grafana/dashboards/retrobrowser-overview.json"
RUNTIME_DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")


def test_observability_plane_is_private_and_pinned() -> None:
    assert "prom/prometheus:v3.7.3@sha256:" in COMPOSE
    assert "grafana/grafana:12.3.0@sha256:" in COMPOSE
    assert "127.0.0.1}:${M18_GRAFANA_PORT:-3000}:3000" in COMPOSE
    assert "9090:9090" not in COMPOSE
    assert "docker.sock" not in COMPOSE
    assert "observability:\n    internal: true" in COMPOSE
    assert "networks: [observability, ingress]" in COMPOSE
    assert 'user: "65534:0"' in COMPOSE


def test_scrapes_control_turn_and_dynamic_selkies_targets() -> None:
    for phrase in [
        "session-manager:8080",
        "coturn:9641",
        "/etc/prometheus/runtime-targets/*.json",
    ]:
        assert phrase in PROMETHEUS
    coturn_overlay = COMPOSE.split("  coturn:", 1)[1].split("\n  prometheus:", 1)[0]
    assert "observability" not in coturn_overlay
    assert "--allowed-peer-ip=$$(detect-external-ip)" in coturn_overlay
    assert "--prometheus-address=0.0.0.0" in COMPOSE
    assert "RUNTIME_AGENT_METRICS_TARGET_ROOT" in COMPOSE
    assert "/etc/service/metrics-proxy/run" in RUNTIME_DOCKERFILE


def test_dashboard_and_all_required_runbooks_exist() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    assert dashboard["uid"] == "retrobrowser-operations"
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {
        "Runtime capacity used",
        "WebRTC client latency",
        "TURN allocations and traffic",
    } <= titles
    for name in [
        "stream-will-not-connect.md",
        "turn-relay-failure.md",
        "controller-not-detected.md",
        "netplay-hash-mismatch.md",
        "orphan-runtime.md",
        "auth-login-failure.md",
        "gpu-encoder-exhaustion.md",
    ]:
        assert (ROOT / "docs/runbooks" / name).is_file()


def test_helpers_and_observability_runbook_exist() -> None:
    for name in ["milestone18-start.ps1", "milestone18-verify.ps1", "milestone18-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    runbook = (ROOT / "docs/milestone-18-observability.md").read_text(encoding="utf-8")
    for phrase in ["WebRTC", "TURN", "runtime capacity", "diagnostics", "RequireClean"]:
        assert phrase in runbook
