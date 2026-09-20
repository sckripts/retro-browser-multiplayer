import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml
from pydantic import ValidationError

from session_entrypoint.models import CoreManifest, CoreProfile, RuntimeSpec

MAX_SPEC_BYTES = 65536


class RuntimeValidationError(Exception):
    """A safe-to-report runtime validation failure."""


@dataclass(frozen=True)
class RuntimePaths:
    rom_root: Path
    core_root: Path
    frontend_path: Path
    base_config: Path
    core_options: Path
    session_root: Path
    persistent_save_root: Path = Path("/run/retro-saves")


@dataclass(frozen=True)
class ResolvedRuntime:
    spec: RuntimeSpec
    profile: CoreProfile
    rom_path: Path
    rom_sha256: str
    core_path: Path
    core_sha256: str
    frontend_path: Path
    frontend_sha256: str
    session_home: Path


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _validation_locations(error: ValidationError) -> str:
    locations = {
        ".".join(str(component) for component in item["loc"]) or "document"
        for item in error.errors(include_input=False)
    }
    return ", ".join(sorted(locations))


def load_runtime_spec(path: Path) -> RuntimeSpec:
    try:
        stat = path.lstat()
    except OSError as error:
        raise RuntimeValidationError("RuntimeSpec file is unavailable") from error
    if path.is_symlink() or not path.is_file():
        raise RuntimeValidationError("RuntimeSpec must be a regular non-symlink file")
    if stat.st_size > MAX_SPEC_BYTES:
        raise RuntimeValidationError("RuntimeSpec exceeds maximum size")
    try:
        document = json.loads(path.read_bytes(), object_pairs_hook=_reject_duplicate_keys)
    except RuntimeValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeValidationError("RuntimeSpec is not valid UTF-8 JSON") from error
    try:
        return RuntimeSpec.model_validate(document)
    except ValidationError as error:
        locations = _validation_locations(error)
        raise RuntimeValidationError(f"RuntimeSpec validation failed at: {locations}") from None


def load_core_manifest(path: Path) -> CoreManifest:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CoreManifest.model_validate(document)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise RuntimeValidationError("core manifest is unavailable or malformed") from error
    except ValidationError as error:
        locations = _validation_locations(error)
        raise RuntimeValidationError(f"core manifest validation failed at: {locations}") from None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise RuntimeValidationError("approved artifact could not be read") from error
    return digest.hexdigest()


def _resolve_approved_file(candidate: Path, root: Path, label: str) -> Path:
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise RuntimeValidationError(f"{label} does not exist") from error
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise RuntimeValidationError(f"{label} is outside the approved {label} root") from None
    if not resolved.is_file():
        raise RuntimeValidationError(f"{label} is not a regular file")
    if ".." in candidate.parts or candidate.absolute() != resolved:
        raise RuntimeValidationError(f"{label} path is not canonical")
    return resolved


def resolve_runtime(
    spec: RuntimeSpec, manifest: CoreManifest, paths: RuntimePaths
) -> ResolvedRuntime:
    profile = manifest.profiles.get(spec.emulator.core_profile)
    if profile is None:
        raise RuntimeValidationError("RuntimeSpec does not select an approved core profile")

    rom_path = _resolve_approved_file(Path(spec.game.canonical_path), paths.rom_root, "ROM")
    rom_sha256 = _sha256(rom_path)
    if rom_sha256 != spec.game.expected_sha256:
        raise RuntimeValidationError("ROM SHA-256 mismatch")

    core_path = _resolve_approved_file(profile.core.artifact_path, paths.core_root, "core")
    core_sha256 = _sha256(core_path)
    if core_sha256 != profile.core.artifact_sha256:
        raise RuntimeValidationError("core SHA-256 mismatch")

    try:
        frontend_path = paths.frontend_path.resolve(strict=True)
        manifest_frontend_path = profile.frontend.artifact_path.resolve(strict=True)
    except OSError as error:
        raise RuntimeValidationError("approved RetroArch artifact does not exist") from error
    if manifest_frontend_path != frontend_path or not frontend_path.is_file():
        raise RuntimeValidationError("core profile selects an unapproved RetroArch artifact")
    frontend_sha256 = _sha256(frontend_path)
    if frontend_sha256 != profile.frontend.artifact_sha256:
        raise RuntimeValidationError("RetroArch SHA-256 mismatch")

    session_home = paths.session_root / str(spec.session_id) / str(spec.participant_id)
    return ResolvedRuntime(
        spec=spec,
        profile=profile,
        rom_path=rom_path,
        rom_sha256=rom_sha256,
        core_path=core_path,
        core_sha256=core_sha256,
        frontend_path=frontend_path,
        frontend_sha256=frontend_sha256,
        session_home=session_home,
    )


def _quote_config(value: str | Path) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_retroarch_config(base_config: str, runtime: ResolvedRuntime) -> str:
    spec = runtime.spec
    save_directory = (
        "/run/retro-saves"
        if spec.persistence.save_mode == "host-authoritative"
        else runtime.session_home / "saves"
    )
    values: list[tuple[str, str | Path]] = [
        ("netplay_nickname", spec.player_name),
        ("netplay_ip_port", str(spec.netplay.port)),
        ("netplay_mode", "true" if spec.netplay.role == "client" else "false"),
        ("netplay_ip_address", spec.netplay.host or ""),
        ("netplay_public_announce", "false"),
        ("netplay_use_mitm_server", "false"),
        ("netplay_nat_traversal", "false"),
        ("netplay_spectator_mode_enable", "false"),
        ("netplay_client_swap_input", "false"),
        ("netplay_delay_frames", "0"),
        ("netplay_allow_pausing", "false"),
        ("netplay_max_connections", str(max(runtime.profile.max_players - 1, 1))),
        ("config_save_on_exit", "false"),
        ("block_sram_overwrite", "true"),
        ("core_options_path", runtime.session_home / "config" / "retroarch-core-options.cfg"),
        ("savefile_directory", save_directory),
        ("savestate_directory", runtime.session_home / "states"),
        ("system_directory", runtime.session_home / "system"),
    ]
    values.extend(
        (f"input_libretro_device_p{port}", str(device))
        for port, device in sorted(runtime.profile.controller_port_devices.items())
    )
    managed = "\n".join(f"{key} = {_quote_config(value)}" for key, value in values)
    return (
        base_config.rstrip()
        + "\n\n# Generated by session-entrypoint; do not edit.\n"
        + managed
        + "\n"
    )


def build_retroarch_argv(runtime: ResolvedRuntime, config_path: Path) -> list[str]:
    spec = runtime.spec
    arguments = [
        str(runtime.frontend_path),
        "--verbose",
        "--config",
        str(config_path),
    ]
    if spec.netplay.role == "host":
        arguments.extend(("--host", f"--port={spec.netplay.port}", f"--nick={spec.player_name}"))
    elif spec.netplay.role == "client":
        arguments.extend(
            (
                f"--connect={spec.netplay.host}",
                f"--port={spec.netplay.port}",
                f"--nick={spec.player_name}",
            )
        )
    arguments.extend(("-L", str(runtime.core_path), str(runtime.rom_path)))
    return arguments


def mount_options_are_read_only(options: str) -> bool:
    return "ro" in options.split(",")


def _validate_read_only_mount(path: Path) -> None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable and validated path
            ["/usr/bin/findmnt", "--json", "--target", str(path), "--output", "OPTIONS"],
            check=True,
            capture_output=True,
            text=True,
        )
        document = json.loads(result.stdout)
        options = document["filesystems"][0]["options"]
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
    ) as error:
        raise RuntimeValidationError("ROM mount options could not be verified") from error
    if not isinstance(options, str) or not mount_options_are_read_only(options):
        raise RuntimeValidationError("ROM must be mounted read-only")


def _validate_persistent_save_mount(path: Path) -> None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable and image-defined path
            [
                "/usr/bin/findmnt",
                "--json",
                "--target",
                str(path),
                "--output",
                "TARGET,OPTIONS",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        filesystem = json.loads(result.stdout)["filesystems"][0]
        target = filesystem["target"]
        options = filesystem["options"]
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
    ) as error:
        raise RuntimeValidationError("persistent save mount could not be verified") from error
    if target != str(path) or not isinstance(options, str) or "rw" not in options.split(","):
        raise RuntimeValidationError("persistent save directory must be an exact writable mount")


def _prepare_session(runtime: ResolvedRuntime, paths: RuntimePaths) -> Path:
    try:
        for directory in (
            runtime.session_home,
            runtime.session_home / "config",
            runtime.session_home / "saves",
            runtime.session_home / "states",
            runtime.session_home / "system",
        ):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path = runtime.session_home / "config" / "retroarch.cfg"
        config = render_retroarch_config(paths.base_config.read_text(encoding="utf-8"), runtime)
        temporary_path = config_path.with_suffix(".tmp")
        temporary_path.write_text(config, encoding="utf-8")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, config_path)
        shutil.copyfile(
            paths.core_options,
            runtime.session_home / "config" / "retroarch-core-options.cfg",
        )
    except OSError as error:
        raise RuntimeValidationError("per-session configuration could not be generated") from error
    return config_path


def _validate_stream_environment(spec: RuntimeSpec) -> None:
    expected = {
        "SELKIES_SUBFOLDER": spec.stream.subfolder,
        "SELKIES_MANUAL_WIDTH": "1280",
        "SELKIES_MANUAL_HEIGHT": "720",
        "SELKIES_FRAMERATE": "60-60",
    }
    mismatches = [name for name, value in expected.items() if os.environ.get(name) != value]
    if mismatches:
        raise RuntimeValidationError(
            "Selkies environment does not match RuntimeSpec fields: " + ", ".join(mismatches)
        )


def run() -> NoReturn:
    paths = RuntimePaths(
        rom_root=Path("/run/roms"),
        core_root=Path("/opt/libretro"),
        frontend_path=Path("/usr/local/bin/retroarch"),
        base_config=Path("/etc/retro-session/retroarch.cfg"),
        core_options=Path("/etc/retro-session/retroarch-core-options.cfg"),
        # The unprivileged runtime has an isolated /tmp; UUID components prevent collisions.
        session_root=Path("/tmp/retro-sessions"),  # noqa: S108
        persistent_save_root=Path("/run/retro-saves"),
    )
    spec = load_runtime_spec(Path("/run/retro-session/runtime-spec.json"))
    manifest = load_core_manifest(Path("/etc/retro-session/cores.yaml"))
    _validate_stream_environment(spec)
    runtime = resolve_runtime(spec, manifest, paths)
    _validate_read_only_mount(runtime.rom_path)
    if spec.persistence.save_mode == "host-authoritative":
        _validate_persistent_save_mount(paths.persistent_save_root)
    config_path = _prepare_session(runtime, paths)

    print(
        "session-entrypoint: validated "
        f"schema={spec.schema_version} session={spec.session_id} "
        f"participant={spec.participant_id} profile={spec.emulator.core_profile} "
        f"role={spec.netplay.role}",
        flush=True,
    )
    print(
        f"session-entrypoint: RetroArch {runtime.profile.frontend.version} "
        f"SHA-256 {runtime.frontend_sha256}",
        flush=True,
    )
    print(
        f"session-entrypoint: core {runtime.profile.core.name} "
        f"{runtime.profile.core.version} SHA-256 {runtime.core_sha256}",
        flush=True,
    )
    print(f"session-entrypoint: ROM SHA-256 {runtime.rom_sha256}", flush=True)
    print(
        f"session-entrypoint: encoder {os.environ.get('SELKIES_ENCODER', 'unknown')} "
        f"CPU={os.environ.get('SELKIES_USE_CPU', 'unknown')}",
        flush=True,
    )

    argv = build_retroarch_argv(runtime, config_path)
    os.execv(argv[0], argv)  # noqa: S606 - executable is hash-verified and pinned


def main() -> int:
    try:
        run()
    except RuntimeValidationError as error:
        print(f"session-entrypoint: validation failed: {error}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
