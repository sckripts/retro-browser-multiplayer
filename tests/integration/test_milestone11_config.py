from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "compose" / "acceptance" / "compose.milestone11.yml"
BLUEPRINT = ROOT / "infra" / "authentik" / "blueprints" / "milestone11-romm.yaml"


def load_compose() -> dict[str, object]:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_identity_images_are_immutable_and_no_service_has_docker_access() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    for service in services.values():
        assert isinstance(service, dict)
        image = service.get("image")
        assert isinstance(image, str) and "@sha256:" in image
        assert all("docker.sock" not in str(volume) for volume in service.get("volumes", []))


def test_only_browser_facing_services_publish_loopback_ports() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    assert set(name for name, value in services.items() if "ports" in value) == {
        "authentik-server",
        "mailpit",
        "romm",
    }
    for name in ("authentik-server", "mailpit", "romm"):
        assert all(str(port).startswith("127.0.0.1:") for port in services[name]["ports"])


def test_romm_uses_oidc_subject_as_its_stable_username() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    romm = services["romm"]
    assert isinstance(romm, dict)
    environment = romm["environment"]
    assert environment["OIDC_ENABLED"] == "true"
    assert environment["OIDC_USERNAME_ATTRIBUTE"] == "sub"
    assert environment["OIDC_AUTOLOGIN"] == "false"
    assert environment["OIDC_REDIRECT_URI"].endswith("/api/oauth/openid")
    assert romm["extra_hosts"] == ["auth.127.0.0.1.nip.io:host-gateway"]


def test_blueprint_uses_authorization_code_and_exact_redirect() -> None:
    source = BLUEPRINT.read_text(encoding="utf-8")
    assert "grant_types: [authorization_code, refresh_token]" in source
    assert "matching_mode: strict" in source
    assert "sub_mode: hashed_user_id" in source
    assert "email_verified" in source
    assert "pretend_user_exists: true" in source
    assert "token_expiry: minutes=10" in source


def test_milestone11_helpers_exist() -> None:
    for name in [
        "milestone11-start.ps1",
        "milestone11-verify.ps1",
        "milestone11-stop.ps1",
    ]:
        assert (ROOT / "infra" / "scripts" / "acceptance" / name).is_file()
