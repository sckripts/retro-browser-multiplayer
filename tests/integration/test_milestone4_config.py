from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")
SERVICE_RUN = (ROOT / "images/retro-session/entrypoint/run").read_text(encoding="utf-8")
MANIFEST = (ROOT / "images/retro-session/manifests/cores.yaml").read_text(encoding="utf-8")


def test_runtime_image_installs_the_project_session_entrypoint_and_pinned_dependencies() -> None:
    assert "images/retro-session/session_entrypoint" in DOCKERFILE
    assert "images/retro-session/requirements-runtime.txt" in DOCKERFILE
    assert "--require-hashes" in DOCKERFILE
    assert "python3 -m session_entrypoint" in SERVICE_RUN


def test_service_uses_a_fixed_structured_spec_path_without_shell_arguments() -> None:
    assert "/run/retro-session/runtime-spec.json" in SERVICE_RUN
    assert "RETRO_SESSION_ROM_SHA256" not in SERVICE_RUN
    assert "readonly ROM_PATH=" not in SERVICE_RUN
    assert "eval " not in SERVICE_RUN
    assert "bash -c" not in SERVICE_RUN


def test_core_manifest_contains_runtime_artifact_paths_and_no_download_url() -> None:
    assert "artifact_path: /usr/local/bin/retroarch" in MANIFEST
    assert "artifact_path: /opt/libretro/mesen_libretro.so" in MANIFEST
    assert "max_players: 4" in MANIFEST
    assert "controller_topology: standard-retropad" in MANIFEST
    assert "download_url:" not in MANIFEST
