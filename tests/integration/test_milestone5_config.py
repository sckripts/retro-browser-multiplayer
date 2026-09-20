import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infra/compose/acceptance/compose.milestone5.yml"
COMPOSE_TEXT = COMPOSE_PATH.read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXT)
DYNAMIC = (ROOT / "infra/traefik/dynamic/milestone5.yml").read_text(encoding="utf-8")
STATIC = (ROOT / "infra/traefik/static/milestone5.yml").read_text(encoding="utf-8")
START = (ROOT / "infra/scripts/acceptance/milestone5-start.ps1").read_text(encoding="utf-8")
STOP = (ROOT / "infra/scripts/acceptance/milestone5-stop.ps1").read_text(encoding="utf-8")
PUBLIC_COMPOSE = (ROOT / "infra/compose/acceptance/compose.milestone5.public.yml").read_text(
    encoding="utf-8"
)
PUBLIC_CONFIG = yaml.safe_load(PUBLIC_COMPOSE)
PUBLIC_TEMPLATE = (ROOT / "infra/traefik/dynamic/milestone5-public.template.yml").read_text(
    encoding="utf-8"
)
PUBLIC_STATIC = (ROOT / "infra/traefik/static/milestone5-public.yml").read_text(encoding="utf-8")
PUBLIC_START = (ROOT / "infra/scripts/acceptance/milestone5-public-start.ps1").read_text(
    encoding="utf-8"
)
PUBLIC_STOP = (ROOT / "infra/scripts/acceptance/milestone5-public-stop.ps1").read_text(
    encoding="utf-8"
)
HOST_SPEC = json.loads(
    (ROOT / "images/retro-session/specs/milestone5-host.json").read_text(encoding="utf-8")
)
CLIENT_SPEC = json.loads(
    (ROOT / "images/retro-session/specs/milestone5-client.json").read_text(encoding="utf-8")
)


def test_specs_form_one_host_client_session_with_identical_artifacts() -> None:
    assert HOST_SPEC["schema_version"] == CLIENT_SPEC["schema_version"] == 1
    assert HOST_SPEC["session_id"] == CLIENT_SPEC["session_id"]
    assert HOST_SPEC["participant_id"] != CLIENT_SPEC["participant_id"]
    assert HOST_SPEC["game"] == CLIENT_SPEC["game"]
    assert HOST_SPEC["emulator"] == CLIENT_SPEC["emulator"]
    assert HOST_SPEC["netplay"] == {"role": "host", "host": None, "port": 55435}
    assert CLIENT_SPEC["netplay"] == {
        "role": "client",
        "host": "retro-host",
        "port": 55435,
    }
    assert HOST_SPEC["stream"]["subfolder"] == "/stream/m5-host"
    assert CLIENT_SPEC["stream"]["subfolder"] == "/stream/m5-client"


def test_two_runtimes_share_only_an_internal_netplay_network() -> None:
    services = COMPOSE["services"]
    host = services["retro-host"]
    client = services["retro-client"]
    assert host["image"] == client["image"] == "retrobrowser/retro-session:milestone5"
    assert host["networks"] == ["host-stream", "retro-net"]
    assert client["networks"] == ["client-stream", "retro-net"]
    assert COMPOSE["networks"]["retro-net"]["internal"] is True
    assert COMPOSE["networks"]["host-stream"]["internal"] is True
    assert COMPOSE["networks"]["client-stream"]["internal"] is True
    assert "ports" not in host
    assert "ports" not in client
    assert "network_mode" not in host
    assert "network_mode" not in client
    assert "/var/run/docker.sock" not in COMPOSE_TEXT
    assert "privileged: true" not in COMPOSE_TEXT


def test_rom_and_specs_are_fixed_read_only_mounts() -> None:
    for service_name, spec_name in (
        ("retro-host", "milestone5-host.json"),
        ("retro-client", "milestone5-client.json"),
    ):
        volumes = COMPOSE["services"][service_name]["volumes"]
        assert volumes[0]["target"] == "/run/roms/milestone2.nes"
        assert volumes[0]["read_only"] is True
        assert volumes[1]["source"].endswith(spec_name)
        assert volumes[1]["target"] == "/run/retro-session/runtime-spec.json"
        assert volumes[1]["read_only"] is True


def test_edge_has_distinct_routes_and_no_runtime_port_is_public() -> None:
    edge = COMPOSE["services"]["edge"]
    assert edge["networks"] == ["edge", "host-stream", "client-stream"]
    assert "${M5_HTTP_PORT:-8090}:8080" in COMPOSE_TEXT
    assert "PathPrefix(`/stream/m5-host`)" in DYNAMIC
    assert "PathPrefix(`/stream/m5-client`)" in DYNAMIC
    assert "url: http://retro-host:8080" in DYNAMIC
    assert "url: http://retro-client:8080" in DYNAMIC
    assert "filename: /etc/traefik/dynamic/milestone5.yml" in STATIC


def test_client_waits_for_healthy_host_and_both_have_scoped_tokens() -> None:
    depends_on = COMPOSE["services"]["retro-client"]["depends_on"]
    assert depends_on["retro-host"]["condition"] == "service_healthy"
    assert "M5_HOST_MASTER_TOKEN" in COMPOSE_TEXT
    assert "M5_CLIENT_MASTER_TOKEN" in COMPOSE_TEXT
    assert "M5_HOST_SESSION_TOKEN" in START
    assert "M5_CLIENT_SESSION_TOKEN" in START
    assert START.count('role = "controller"') == 2
    assert START.count("slot = 1") == 2
    assert "/stream/m5-host" in START
    assert "/stream/m5-client" in START
    assert ".env.milestone5" in STOP


def test_public_profile_routes_both_secure_webrtc_streams() -> None:
    for service_name in ("retro-host", "retro-client"):
        environment = PUBLIC_CONFIG["services"][service_name]["environment"]
        assert environment["SELKIES_MODE"] == "webrtc"
        assert environment["SELKIES_TURN_REST_URI"] == "http://turn-rest:8008/"
    assert "PathPrefix(`/stream/m5-host`)" in PUBLIC_TEMPLATE
    assert "PathPrefix(`/stream/m5-client`)" in PUBLIC_TEMPLATE
    assert PUBLIC_TEMPLATE.count("entryPoints:\n        - websecure") == 2
    assert "filename: /etc/traefik/dynamic/milestone5.yml" in PUBLIC_STATIC
    assert 'address: ":8443"' in PUBLIC_STATIC


def test_public_profile_keeps_netplay_private_and_turn_credentials_server_side() -> None:
    assert "retro-net:\n    internal: true" in PUBLIC_COMPOSE
    assert "target: /run/retro-session/runtime-spec.json" in PUBLIC_COMPOSE
    assert PUBLIC_COMPOSE.count("target: /run/roms/milestone2.nes") == 2
    assert "55435:55435" not in PUBLIC_COMPOSE
    assert "/var/run/docker.sock" not in PUBLIC_COMPOSE
    assert "M5_TURN_SHARED_SECRET" not in PUBLIC_COMPOSE.split("\n  turn-rest:", maxsplit=1)[0]
    assert "TURN_SHARED_SECRET: ${M5_TURN_SHARED_SECRET:" in PUBLIC_COMPOSE


def test_public_helpers_issue_distinct_tokens_without_printing_them() -> None:
    assert "M5_HOST_SESSION_TOKEN" in PUBLIC_START
    assert "M5_CLIENT_SESSION_TOKEN" in PUBLIC_START
    assert '"retro-host", "python3", "-c"' in PUBLIC_START
    assert '"retro-client", "python3", "-c"' in PUBLIC_START
    assert "__M5_PUBLIC_HOSTNAME__" in PUBLIC_START
    assert ".env.milestone5-public" in PUBLIC_STOP
