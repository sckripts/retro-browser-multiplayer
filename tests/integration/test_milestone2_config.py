from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "infra/compose/acceptance/compose.milestone2.yml").read_text(encoding="utf-8")
GPU_OVERRIDE = (ROOT / "infra/compose/acceptance/compose.milestone2.gpu.yml").read_text(
    encoding="utf-8"
)
DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")
ENTRYPOINT = (ROOT / "images/retro-session/entrypoint/run").read_text(encoding="utf-8")
CONFIG = (ROOT / "images/retro-session/config/retroarch.cfg").read_text(encoding="utf-8")
CORE_OPTIONS = (ROOT / "images/retro-session/config/retroarch-core-options.cfg").read_text(
    encoding="utf-8"
)
MANIFEST = (ROOT / "images/retro-session/manifests/cores.yaml").read_text(encoding="utf-8")
RUNTIME_SPEC = (ROOT / "images/retro-session/specs/milestone2.json").read_text(encoding="utf-8")
FETCH_SCRIPT = (ROOT / "tools/test-roms/fetch-super-tilt-bro.ps1").read_text(encoding="utf-8")
START_SCRIPT = (ROOT / "infra/scripts/acceptance/milestone2-start.ps1").read_text(encoding="utf-8")

ROM_SHA256 = "847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d"


def test_runtime_is_derived_from_the_immutable_selkies_image() -> None:
    assert "desktop:main-ubuntu26.04@sha256:" in DOCKERFILE
    assert "ARG RETROARCH_COMMIT=69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576" in DOCKERFILE
    assert "ARG MESEN_COMMIT=f3a18bed018fa853627e0e15d02a3f2ba4960222" in DOCKERFILE
    assert "sha256sum --check" in DOCKERFILE
    assert "entrypoint/finish /etc/service/selkies/finish" in DOCKERFILE
    assert "chown -R ubuntu:ubuntu /etc/service/retroarch" in DOCKERFILE
    assert "rm -f /usr/local/bin/selkies-proot" in DOCKERFILE
    assert ":latest" not in DOCKERFILE


def test_rom_is_external_fixed_and_read_only() -> None:
    assert "M2_ROM_PATH" in COMPOSE
    assert "target: /run/roms/milestone2.nes" in COMPOSE
    assert "read_only: true" in COMPOSE
    assert "target: /run/retro-session/runtime-spec.json" in COMPOSE
    assert "/run/roms/milestone2.nes" in RUNTIME_SPEC
    assert ROM_SHA256 in RUNTIME_SPEC
    assert "*.nes" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.nes" in (ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_retroarch_launch_is_direct_and_validates_artifacts() -> None:
    assert 'START_LXQT: "false"' in COMPOSE
    assert "python3 -m session_entrypoint" in ENTRYPOINT
    assert "/run/retro-session/runtime-spec.json" in ENTRYPOINT
    assert "RETRO_SESSION_ROM_SHA256" not in ENTRYPOINT
    assert "bash -c" not in ENTRYPOINT
    assert "lxqt-session" not in ENTRYPOINT


def test_browser_surface_is_fixed_and_unrelated_features_are_disabled() -> None:
    required = (
        "SELKIES_SUBFOLDER: /stream/m2",
        "SELKIES_MODE: websockets",
        'SELKIES_ENABLE_CLIPBOARD: "false"',
        "SELKIES_FILE_TRANSFERS: none",
        'SELKIES_ENABLE_SHARING: "false"',
        'SELKIES_COMMAND_ENABLED: "false"',
        'SELKIES_GAMEPAD_ENABLED: "true"',
        'SELKIES_MANUAL_WIDTH: "1280"',
        'SELKIES_MANUAL_HEIGHT: "720"',
        "SELKIES_FRAMERATE: 60-60",
    )
    for setting in required:
        assert setting in COMPOSE
    assert "ports:" in COMPOSE.split("  retro-session:", maxsplit=1)[0]
    assert "ports:" not in COMPOSE.split("  retro-session:", maxsplit=1)[1]
    assert "/var/run/docker.sock" not in COMPOSE
    assert 'SELKIES_USE_CPU: "false"' in GPU_OVERRIDE
    assert "pgrep -x retroarch" in COMPOSE


def test_retroarch_config_is_deterministic_for_milestone2() -> None:
    required = (
        'video_driver = "gl"',
        'audio_driver = "pulse"',
        'input_joypad_driver = "udev"',
        'video_fullscreen = "true"',
        'video_windowed_fullscreen = "false"',
        'video_force_aspect = "true"',
        'video_vsync = "true"',
        'video_refresh_rate = "60.000000"',
        'video_max_swapchain_images = "2"',
        'menu_driver = "null"',
        'config_save_on_exit = "false"',
        'network_cmd_enable = "false"',
        'input_exit_emulator = "nul"',
        'input_player1_up_btn = "h0up"',
        'input_player1_down_btn = "h0down"',
        'input_player1_left_btn = "h0left"',
        'input_player1_right_btn = "h0right"',
        'input_player1_up_axis = "-1"',
        'input_player1_left_axis = "-0"',
    )
    for setting in required:
        assert setting in CONFIG
    required_subfolder = (
        'readonly STREAM_SUBFOLDER="${SELKIES_SUBFOLDER:?SELKIES_SUBFOLDER is required}"'
    )
    assert required_subfolder in ENTRYPOINT
    assert 'xrandr --output screen --mode "1280x720_60.00"' in ENTRYPOINT
    assert ENTRYPOINT.index("${STREAM_SUBFOLDER}/api/health") < ENTRYPOINT.index(
        'xrandr --output screen --mode "1280x720_60.00"'
    )
    assert 'mesen_region = "NTSC"' in CORE_OPTIONS
    assert 'mesen_audio_sample_rate = "48000"' in CORE_OPTIONS


def test_core_and_legal_rom_provenance_are_pinned() -> None:
    for value in (
        "retroarch_version: 1.22.2",
        "mesen_version: 0.9.9",
        "f3a18bed018fa853627e0e15d02a3f2ba4960222",
        "GPL-3.0-only",
        'super_tilt_bro_version: "2.6"',
        "WTFPL-2.0",
        ROM_SHA256,
    ):
        assert value in MANIFEST
    assert "16311760" in FETCH_SCRIPT
    assert ROM_SHA256 in FETCH_SCRIPT


def test_launcher_refreshes_proxy_after_runtime_recreation() -> None:
    assert "$composeBaseArgs" in START_SCRIPT
    assert '@("up", "-d", "--no-deps", "--force-recreate", "--wait", "edge")' in START_SCRIPT
