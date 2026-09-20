from pathlib import Path

ROOT = Path(__file__).parents[2]
COMPOSE = (ROOT / "infra/compose/acceptance/compose.milestone19.yml").read_text(encoding="utf-8")
ROUTES = (ROOT / "infra/traefik/dynamic/milestone19-base.template.yml").read_text(encoding="utf-8")
ROMM_CONFIG = (ROOT / "infra/romm/config.milestone19.yml").read_text(encoding="utf-8")
SECURITY_WORKFLOW = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
CI_WORKFLOW = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_runtime_and_admission_limits_are_explicit() -> None:
    for setting in [
        "RUNTIME_AGENT_MEMORY_BYTES",
        "RUNTIME_AGENT_NANO_CPUS",
        "RUNTIME_AGENT_PIDS_LIMIT",
        "RUNTIME_AGENT_MAX_RUNTIMES",
        "SESSION_MANAGER_SESSION_CAPACITY",
        "SESSION_MANAGER_PER_USER_RUNTIME_CAPACITY",
    ]:
        assert setting in COMPOSE


def test_public_routes_have_rate_request_and_browser_policy_controls() -> None:
    for setting in [
        "rateLimit:",
        "maxRequestBodyBytes:",
        "contentSecurityPolicyReportOnly:",
        "permissionsPolicy:",
        "stsPreload: true",
    ]:
        assert setting in ROUTES
    assert "milestone14:" in ROUTES
    assert "PathPrefix(`/api/saves`)" in ROUTES
    assert "PathPrefix(`/api/states`)" in ROUTES
    assert "PathPrefix(`/static/`)" in ROUTES
    assert "milestone19-auth-static-limit" in ROUTES
    assert "burst: 200" in ROUTES
    assert ROUTES.count("priority: 1") == 2
    assert "maxRequestBodyBytes: 33554432" in ROUTES
    assert "milestone19-auth-csp:" in ROUTES
    assert "milestone19-romm-csp:" in ROUTES
    auth_policy = ROUTES.split("milestone19-auth-csp:", 1)[1].split("milestone19-romm-csp:", 1)[0]
    romm_policy = ROUTES.split("milestone19-romm-csp:", 1)[1].split("milestone19-auth-limit:", 1)[0]
    assert "unsafe-eval" not in auth_policy
    assert "worker-src 'self' blob:" in romm_policy
    assert "script-src 'self' blob: 'unsafe-inline' 'unsafe-eval'" in romm_policy


def test_solo_play_uses_upstream_cartridge_save_sync() -> None:
    assert "auto_save_sync: false" in ROMM_CONFIG
    assert "config.milestone19.yml:/romm/config/config.yml:ro" in COMPOSE
    start = (ROOT / "infra/scripts/acceptance/milestone19-start.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "infra/scripts/acceptance/milestone19-verify.ps1").read_text(encoding="utf-8")
    assert "retrobrowser/romm:milestone19" in start
    assert "auto_save_sync" in verify
    assert '"$publicBase/api/saves?rom_id=1"' in verify


def test_security_workflow_scans_every_custom_image_and_emits_sboms() -> None:
    for image in ["session-manager", "runtime-agent", "retro-session"]:
        assert f"name: {image}" in SECURITY_WORKFLOW
    assert "anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610" in SECURITY_WORKFLOW
    assert "anchore/scan-action@e1165082ffb1fe366ebaf02d8526e7c4989ea9d2" in SECURITY_WORKFLOW
    assert "only-fixed: true" in SECURITY_WORKFLOW
    assert "actions/checkout@v" not in SECURITY_WORKFLOW + CI_WORKFLOW
    assert "actions/setup-python@v" not in CI_WORKFLOW


def test_milestone_helpers_and_documentation_exist() -> None:
    for name in ["milestone19-start.ps1", "milestone19-verify.ps1", "milestone19-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    document = (ROOT / "docs/milestone-19-production-hardening.md").read_text(encoding="utf-8")
    for phrase in ["in progress", "SBOM", "rate limiting", "Remaining work"]:
        assert phrase in document
