import hashlib
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from session_entrypoint.launcher import (
    RuntimePaths,
    RuntimeValidationError,
    build_retroarch_argv,
    load_runtime_spec,
    mount_options_are_read_only,
    render_retroarch_config,
    resolve_runtime,
)
from session_entrypoint.models import CoreManifest, RuntimeSpec

SESSION_ID = "11111111-1111-4111-8111-111111111111"
PARTICIPANT_ID = "22222222-2222-4222-8222-222222222222"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_spec_data(rom_path: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "session_id": SESSION_ID,
        "participant_id": PARTICIPANT_ID,
        "user_id": "authentik:player-one",
        "player_name": 'Player One "Retro"',
        "game": {
            "canonical_path": str(rom_path),
            "expected_sha256": sha256(b"approved-rom"),
        },
        "emulator": {"core_profile": "nes-mesen"},
        "netplay": {"role": "standalone", "host": None, "port": 55435},
        "stream": {
            "subfolder": f"/stream/{PARTICIPANT_ID}",
            "display_profile": "hd-720p60",
        },
    }


def runtime_fixture(tmp_path: Path) -> tuple[RuntimeSpec, CoreManifest, RuntimePaths]:
    rom_root = tmp_path / "roms"
    core_root = tmp_path / "cores"
    rom_root.mkdir()
    core_root.mkdir()
    rom_path = rom_root / "approved.nes"
    core_path = core_root / "mesen_libretro.so"
    frontend_path = tmp_path / "bin" / "retroarch"
    frontend_path.parent.mkdir()
    rom_path.write_bytes(b"approved-rom")
    core_path.write_bytes(b"approved-core")
    frontend_path.write_bytes(b"approved-frontend")

    spec = RuntimeSpec.model_validate(valid_spec_data(rom_path))
    manifest = CoreManifest.model_validate(
        {
            "schema_version": 1,
            "profiles": {
                "nes-mesen": {
                    "platform": "linux-amd64",
                    "max_players": 4,
                    "controller_topology": "standard-retropad",
                    "netplay_status": "not-tested",
                    "controller_port_devices": {},
                    "frontend": {
                        "name": "RetroArch",
                        "version": "1.22.2",
                        "artifact_path": str(frontend_path),
                        "artifact_sha256": sha256(b"approved-frontend"),
                    },
                    "core": {
                        "name": "Mesen",
                        "version": "0.9.9",
                        "artifact_path": str(core_path),
                        "artifact_sha256": sha256(b"approved-core"),
                    },
                }
            },
        }
    )
    paths = RuntimePaths(
        rom_root=rom_root,
        core_root=core_root,
        frontend_path=frontend_path,
        base_config=tmp_path / "retroarch.cfg",
        core_options=tmp_path / "retroarch-core-options.cfg",
        session_root=tmp_path / "sessions",
    )
    paths.base_config.write_text('video_driver = "gl"\n', encoding="utf-8")
    paths.core_options.write_text('mesen_region = "NTSC"\n', encoding="utf-8")
    return spec, manifest, paths


def test_runtime_spec_is_strict_versioned_and_rejects_commands(tmp_path: Path) -> None:
    data = valid_spec_data(tmp_path / "game.nes")
    RuntimeSpec.model_validate(data)

    for invalid in (
        {**data, "schema_version": 2},
        {**data, "session_id": "not-a-uuid"},
        {**data, "command": "retroarch --appendconfig attacker.cfg"},
        {**data, "player_name": "attacker\nnetplay_password = secret"},
        {**data, "user_id": "bad user id"},
    ):
        with pytest.raises(ValidationError):
            RuntimeSpec.model_validate(invalid)

    too_long_nickname = {**data, "player_name": "x" * 32}
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(too_long_nickname)


def test_runtime_spec_rejects_duplicate_json_keys_and_oversized_input(tmp_path: Path) -> None:
    spec_path = tmp_path / "runtime-spec.json"
    spec_path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(RuntimeValidationError, match="duplicate JSON key"):
        load_runtime_spec(spec_path)

    spec_path.write_bytes(b" " * 65537)
    with pytest.raises(RuntimeValidationError, match="maximum size"):
        load_runtime_spec(spec_path)


@pytest.mark.parametrize(
    ("role", "host", "valid"),
    (
        ("standalone", None, True),
        ("host", None, True),
        ("client", "retro-host", True),
        ("client", "10.20.0.2", True),
        ("client", None, False),
        ("host", "retro-host", False),
        ("standalone", "retro-host", False),
        ("client", "host;touch /tmp/pwned", False),
    ),
)
def test_netplay_role_host_invariants(
    tmp_path: Path, role: str, host: str | None, valid: bool
) -> None:
    data = valid_spec_data(tmp_path / "game.nes")
    data["netplay"] = {"role": role, "host": host, "port": 55435}
    if valid:
        RuntimeSpec.model_validate(data)
    else:
        with pytest.raises(ValidationError):
            RuntimeSpec.model_validate(data)


def test_stream_subfolder_and_display_profile_are_allowlisted(tmp_path: Path) -> None:
    data = valid_spec_data(tmp_path / "game.nes")
    data["stream"]["subfolder"] = "/stream/../../admin"
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(data)

    data = valid_spec_data(tmp_path / "game.nes")
    data["stream"]["display_profile"] = "3840x2160-user-value"
    with pytest.raises(ValidationError):
        RuntimeSpec.model_validate(data)


def test_rom_must_resolve_inside_approved_root_and_match_hash(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    resolve_runtime(spec, manifest, paths)

    outside = tmp_path / "outside.nes"
    outside.write_bytes(b"approved-rom")
    escaped = spec.model_copy(
        update={"game": spec.game.model_copy(update={"canonical_path": str(outside)})}
    )
    with pytest.raises(RuntimeValidationError, match="approved ROM root"):
        resolve_runtime(escaped, manifest, paths)

    mismatch = spec.model_copy(
        update={"game": spec.game.model_copy(update={"expected_sha256": "0" * 64})}
    )
    with pytest.raises(RuntimeValidationError, match="ROM SHA-256 mismatch"):
        resolve_runtime(mismatch, manifest, paths)


def test_rom_symlink_cannot_escape_approved_root(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    outside = tmp_path / "outside.nes"
    outside.write_bytes(b"approved-rom")
    link = paths.rom_root / "escape.nes"
    try:
        os.symlink(outside, link)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")
    escaped = spec.model_copy(
        update={"game": spec.game.model_copy(update={"canonical_path": str(link)})}
    )
    with pytest.raises(RuntimeValidationError, match="approved ROM root"):
        resolve_runtime(escaped, manifest, paths)


def test_core_profile_and_frontend_artifacts_are_allowlisted_and_hashed(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    unknown = spec.model_copy(
        update={"emulator": spec.emulator.model_copy(update={"core_profile": "unknown-core"})}
    )
    with pytest.raises(RuntimeValidationError, match="approved core profile"):
        resolve_runtime(unknown, manifest, paths)

    profile = manifest.profiles["nes-mesen"]
    profile.core.artifact_path.write_bytes(b"modified-core")
    with pytest.raises(RuntimeValidationError, match="core SHA-256 mismatch"):
        resolve_runtime(spec, manifest, paths)

    profile.core.artifact_path.write_bytes(b"approved-core")
    paths.frontend_path.write_bytes(b"modified-frontend")
    with pytest.raises(RuntimeValidationError, match="RetroArch SHA-256 mismatch"):
        resolve_runtime(spec, manifest, paths)


def test_core_artifact_cannot_escape_approved_root(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    outside = tmp_path / "outside-core.so"
    outside.write_bytes(b"approved-core")
    profile = manifest.profiles["nes-mesen"]
    profile = manifest.profiles["nes-mesen"]
    escaped_core = profile.core.model_copy(
        update={
            "artifact_path": outside,
            "artifact_sha256": sha256(b"approved-core"),
        }
    )
    escaped_profile = profile.model_copy(update={"core": escaped_core})
    escaped_manifest = manifest.model_copy(update={"profiles": {"nes-mesen": escaped_profile}})
    with pytest.raises(RuntimeValidationError, match="approved core root"):
        resolve_runtime(spec, escaped_manifest, paths)
    assert profile.core.artifact_path != outside


def test_config_and_argv_are_deterministic_and_never_use_a_shell(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    resolved = resolve_runtime(spec, manifest, paths)
    first = render_retroarch_config(paths.base_config.read_text(encoding="utf-8"), resolved)
    second = render_retroarch_config(paths.base_config.read_text(encoding="utf-8"), resolved)
    assert first == second
    assert 'netplay_nickname = "Player One \\"Retro\\""' in first
    assert 'netplay_ip_port = "55435"' in first
    assert 'netplay_public_announce = "false"' in first
    assert 'netplay_client_swap_input = "false"' in first
    assert 'netplay_delay_frames = "0"' in first
    assert 'netplay_allow_pausing = "false"' in first
    assert 'block_sram_overwrite = "true"' in first

    config_path = paths.session_root / "generated.cfg"
    assert build_retroarch_argv(resolved, config_path) == [
        str(paths.frontend_path),
        "--verbose",
        "--config",
        str(config_path),
        "-L",
        str(resolved.core_path),
        str(resolved.rom_path),
    ]

    host_spec = spec.model_copy(
        update={"netplay": spec.netplay.model_copy(update={"role": "host"})}
    )
    host = resolve_runtime(host_spec, manifest, paths)
    assert "--host" in build_retroarch_argv(host, config_path)

    client_data = valid_spec_data(Path(spec.game.canonical_path))
    client_data["netplay"] = {"role": "client", "host": "retro-host", "port": 55435}
    client = resolve_runtime(RuntimeSpec.model_validate(client_data), manifest, paths)
    client_argv = build_retroarch_argv(client, config_path)
    assert "--connect=retro-host" in client_argv
    assert "--port=55435" in client_argv
    assert all(";" not in argument for argument in client_argv)


def test_host_authoritative_save_uses_only_image_defined_mount(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    data = spec.model_dump(mode="json")
    data["netplay"] = {"role": "host", "host": None, "port": 55435}
    data["persistence"] = {"save_mode": "host-authoritative"}
    runtime = resolve_runtime(RuntimeSpec.model_validate(data), manifest, paths)

    rendered = render_retroarch_config(paths.base_config.read_text(encoding="utf-8"), runtime)

    assert 'savefile_directory = "/run/retro-saves"' in rendered
    assert str(paths.session_root) not in next(
        line for line in rendered.splitlines() if line.startswith("savefile_directory")
    )


def test_client_cannot_select_host_authoritative_persistence(tmp_path: Path) -> None:
    data = valid_spec_data(tmp_path / "game.nes")
    data["netplay"] = {"role": "client", "host": "runtime-host", "port": 55435}
    data["persistence"] = {"save_mode": "host-authoritative"}

    with pytest.raises(ValidationError, match="allowed only for the Netplay host"):
        RuntimeSpec.model_validate(data)


def test_profile_controller_devices_are_rendered_as_trusted_config(tmp_path: Path) -> None:
    spec, manifest, paths = runtime_fixture(tmp_path)
    profile = manifest.profiles["nes-mesen"].model_copy(
        update={"controller_port_devices": {2: 257}}
    )
    manifest = manifest.model_copy(update={"profiles": {"nes-mesen": profile}})
    runtime = resolve_runtime(spec, manifest, paths)

    rendered = render_retroarch_config(paths.base_config.read_text(encoding="utf-8"), runtime)

    assert 'input_libretro_device_p2 = "257"' in rendered


@pytest.mark.parametrize(
    "devices",
    ({0: 257}, {17: 257}, {2: -1}, {2: 65536}),
)
def test_profile_controller_devices_are_bounded(devices: dict[int, int]) -> None:
    with pytest.raises(ValidationError):
        CoreManifest.model_validate(
            {
                "schema_version": 1,
                "profiles": {
                    "snes-bsnes": {
                        "platform": "linux-amd64",
                        "max_players": 4,
                        "controller_topology": "snes-multitap-port-2",
                        "controller_port_devices": devices,
                        "netplay_status": "not-tested",
                        "frontend": {
                            "name": "RetroArch",
                            "version": "1.22.2",
                            "artifact_path": "/usr/local/bin/retroarch",
                            "artifact_sha256": "a" * 64,
                        },
                        "core": {
                            "name": "bsnes",
                            "version": "260f523",
                            "artifact_path": "/opt/libretro/bsnes_libretro.so",
                            "artifact_sha256": "b" * 64,
                        },
                    }
                },
            }
        )


@pytest.mark.parametrize(
    ("options", "expected"),
    (("rw,nosuid,nodev", False), ("ro,nosuid,nodev", True), ("rw,rootcontext=ro", False)),
)
def test_read_only_mount_option_is_an_exact_token(options: str, expected: bool) -> None:
    assert mount_options_are_read_only(options) is expected
