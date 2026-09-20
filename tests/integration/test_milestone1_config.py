from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infra/compose/acceptance/compose.milestone1.yml").read_text(encoding="utf-8")
GPU_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone1.gpu.yml").read_text(
    encoding="utf-8"
)
TRAEFIK_STATIC = (ROOT / "infra/traefik/static/milestone1.yml").read_text(encoding="utf-8")
TRAEFIK_DYNAMIC = (ROOT / "infra/traefik/dynamic/milestone1.yml").read_text(encoding="utf-8")


def test_images_are_immutable_digest_pins() -> None:
    assert "traefik:v3.7.12@sha256:" in COMPOSE
    assert "desktop:main-ubuntu26.04@sha256:" in COMPOSE
    assert ":latest" not in COMPOSE


def test_only_reverse_proxy_publishes_a_host_port() -> None:
    edge, selkies = COMPOSE.split("  selkies:", maxsplit=1)
    assert "ports:" in edge
    assert "ports:" not in selkies
    assert "expose:" in selkies
    assert "/var/run/docker.sock" not in COMPOSE
    assert "providers:\n  file:" in TRAEFIK_STATIC
    assert "docker:" not in TRAEFIK_STATIC


def test_selkies_secure_subfolder_and_browser_controls_are_locked() -> None:
    required = (
        "SELKIES_MASTER_TOKEN:",
        "SELKIES_SUBFOLDER: /stream/m1",
        "SELKIES_MODE: websockets",
        'SELKIES_ENABLE_CLIPBOARD: "false"',
        "SELKIES_FILE_TRANSFERS: none",
        'SELKIES_ENABLE_SHARING: "false"',
        'SELKIES_MICROPHONE_ENABLED: "false"',
        'SELKIES_WEBCAM_ENABLED: "false"',
        'SELKIES_GAMEPAD_ENABLED: "true"',
        'SELKIES_MANUAL_WIDTH: "1280"',
        'SELKIES_MANUAL_HEIGHT: "720"',
        "SELKIES_FRAMERATE: 60-60",
    )
    for setting in required:
        assert setting in COMPOSE
    assert "PathPrefix(`/stream/m1`)" in TRAEFIK_DYNAMIC


def test_gpu_override_and_software_fallback_are_explicit() -> None:
    assert 'SELKIES_USE_CPU: "true"' in COMPOSE
    assert "gpus: all" in GPU_OVERRIDE
    assert 'SELKIES_USE_CPU: "false"' in GPU_OVERRIDE
    assert "NVIDIA_DRIVER_CAPABILITIES: compute,graphics,utility,video" in GPU_OVERRIDE


def test_milestone_does_not_add_emulation_or_public_turn() -> None:
    all_config = "\n".join((COMPOSE, GPU_OVERRIDE, TRAEFIK_STATIC, TRAEFIK_DYNAMIC)).lower()
    assert "retroarch" not in all_config
    assert "docker.sock" not in all_config
    assert 'selkies_enable_internal_turn: "false"' in all_config
