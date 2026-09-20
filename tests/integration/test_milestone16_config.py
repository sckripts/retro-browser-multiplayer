from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
MANIFEST_PATH = ROOT / "images/retro-session/manifests/cores.yaml"
DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")
COMPOSE_PATH = ROOT / "infra/compose/acceptance/compose.milestone16.yml"


def test_genesis_profile_is_pinned_and_limited_to_supported_input_ports() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    profile = manifest["profiles"]["genesis-blastem"]

    assert profile["max_players"] == 2
    assert profile["netplay_status"] == "validated"
    assert profile["controller_topology"] == "genesis-six-button-two-port"
    assert profile["controller_port_devices"] == {}
    assert "only two controller ports" in profile["core"]["multitap"]
    assert profile["core"]["artifact_path"] == "/opt/libretro/blastem_libretro.so"
    assert len(profile["core"]["source_commit"]) == 40
    assert len(profile["core"]["source_archive_sha256"]) == 64
    assert len(profile["core"]["artifact_sha256"]) == 64
    assert "download_url" not in str(profile)


def test_runtime_image_builds_pinned_blastem_without_runtime_downloads() -> None:
    assert "ARG BLASTEM_COMMIT=b4d75247ebad8852fd9bc385b423df704c6c5af5" in DOCKERFILE
    assert "codeload.github.com/libretro/blastem/tar.gz/${BLASTEM_COMMIT}" in DOCKERFILE
    assert "make -C blastem-source -f Makefile.libretro" in DOCKERFILE
    assert "PYTHONHASHSEED=0" in DOCKERFILE
    assert "platform=linux OPT=-O2" in DOCKERFILE
    assert "/opt/libretro/blastem_libretro.so" in DOCKERFILE


def test_milestone16_helpers_and_acceptance_runbook_exist() -> None:
    for name in ["milestone16-start.ps1", "milestone16-verify.ps1", "milestone16-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    runbook = (ROOT / "docs/milestone-16-genesis.md").read_text(encoding="utf-8")
    for phrase in ["two-player", "multitap", "relay", "reconnect", "RequireClean"]:
        assert phrase in runbook


def test_milestone16_extends_public_project_without_new_ports() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert compose["name"] == "retro-browser-milestone14"
    assert set(compose["services"]) == {"runtime-agent", "session-manager", "network-anchor"}
    assert "ports" not in str(compose)

    start = (ROOT / "infra/scripts/acceptance/milestone16-start.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "infra/scripts/acceptance/milestone16-verify.ps1").read_text(encoding="utf-8")
    assert '"genesis/roms"' in start
    assert '@(".md", ".bin", ".gen")' in start
    assert "Resolve-Path -LiteralPath $managedRom" in start
    assert "OrdinalIgnoreCase.Equals($resolvedRom, $resolvedManagedRom)" in start
    assert '$logs = $logLines -join "`n"' in verify
