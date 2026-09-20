from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
MANIFEST_PATH = ROOT / "images/retro-session/manifests/cores.yaml"
DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")
COMPOSE_PATH = ROOT / "infra/compose/acceptance/compose.milestone15.yml"


def test_snes_profile_is_pinned_and_owns_multitap_configuration() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    profile = manifest["profiles"]["snes-bsnes"]

    assert profile["max_players"] == 4
    assert profile["netplay_status"] == "validated"
    assert profile["controller_topology"] == "snes-multitap-port-2"
    assert profile["controller_port_devices"] == {2: 257}
    assert profile["core"]["artifact_path"] == "/opt/libretro/bsnes_libretro.so"
    assert len(profile["core"]["source_commit"]) == 40
    assert len(profile["core"]["source_archive_sha256"]) == 64
    assert len(profile["core"]["artifact_sha256"]) == 64
    assert "download_url" not in str(profile)


def test_runtime_image_builds_the_pinned_bsnes_core_without_runtime_downloads() -> None:
    assert "ARG BSNES_COMMIT=260f5234410d0899f8446882c63d17f891b686e0" in DOCKERFILE
    assert "codeload.github.com/libretro/bsnes-libretro/tar.gz/${BSNES_COMMIT}" in DOCKERFILE
    assert "COPY --from=builder" in DOCKERFILE
    assert "/opt/libretro/bsnes_libretro.so" in DOCKERFILE


def test_runtime_bounds_bsnes_openmp_workers_to_its_cpu_quota() -> None:
    assert "OMP_NUM_THREADS=2" in DOCKERFILE
    assert "OMP_THREAD_LIMIT=2" in DOCKERFILE
    assert "OMP_DYNAMIC=false" in DOCKERFILE
    assert "OMP_WAIT_POLICY=PASSIVE" in DOCKERFILE


def test_milestone15_helpers_and_acceptance_runbook_exist() -> None:
    for name in ["milestone15-start.ps1", "milestone15-verify.ps1", "milestone15-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    runbook = (ROOT / "docs/milestone-15-snes.md").read_text(encoding="utf-8")
    for phrase in ["four-player", "multitap", "relay", "reconnect", "RequireClean"]:
        assert phrase in runbook

    verifier = (ROOT / "infra/scripts/acceptance/milestone15-verify.ps1").read_text(
        encoding="utf-8"
    )
    assert "$baseArguments = @{" in verifier
    assert "RequireRomMUsers = $RequireRomMUsers" in verifier
    assert "RequireClean = $RequireClean" in verifier


def test_milestone15_extends_the_public_project_without_new_ports() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert compose["name"] == "retro-browser-milestone14"
    assert set(compose["services"]) == {"runtime-agent", "session-manager", "network-anchor"}
    assert "ports" not in str(compose)

    start = (ROOT / "infra/scripts/acceptance/milestone15-start.ps1").read_text(encoding="utf-8")
    assert "[string]$UserCEmail" in start
    assert "[string]$UserDEmail" in start
    assert '"snes/roms"' in start
    assert '@(".sfc", ".smc")' in start
    assert "Resolve-Path -LiteralPath $managedRom" in start
    assert "OrdinalIgnoreCase.Equals($resolvedRom, $resolvedManagedRom)" in start
