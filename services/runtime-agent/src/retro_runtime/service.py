import hashlib
import hmac
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import RLock
from typing import cast
from uuid import UUID

from retro_runtime.docker import EngineClient
from retro_runtime.errors import (
    ConflictError,
    NotFoundError,
    OwnershipError,
    RuntimeAgentError,
)
from retro_runtime.models import (
    AgentConfig,
    ContainerRecord,
    CreateRuntimeRequest,
    RuntimeCapacity,
    RuntimeRecord,
)
from retro_runtime.observability import MetricsTargetProvider
from retro_runtime.routes import RouteProvider
from retro_runtime.validation import resolve_existing_file_beneath, sha256_file

MANAGED_LABEL = "io.retrobrowser.runtime-agent.managed"
PARTICIPANT_LABEL = "io.retrobrowser.participant-id"
SESSION_LABEL = "io.retrobrowser.session-id"
FINGERPRINT_LABEL = "io.retrobrowser.runtime-request-sha256"
SUBFOLDER_LABEL = "io.retrobrowser.stream-subfolder"
SAVE_KEY_LABEL = "io.retrobrowser.save-key"
LOGGER = logging.getLogger(__name__)


def _assign_runtime_owner(path: Path) -> None:
    if os.name == "posix":
        chown = cast(Callable[[Path, int, int], None], getattr(os, "ch" + "own"))
        chown(path, 1000, 1000)


class RuntimeService:
    def __init__(
        self,
        config: AgentConfig,
        engine: EngineClient,
        routes: RouteProvider,
        metrics_targets: MetricsTargetProvider | None = None,
    ) -> None:
        self.config = config
        self.engine = engine
        self.routes = routes
        self.metrics_targets = metrics_targets or MetricsTargetProvider(None)
        self._lifecycle_lock = RLock()

    @staticmethod
    def container_name(participant_id: UUID) -> str:
        return f"retrobrowser-runtime-{participant_id.hex}"

    def _validate_request(self, request: CreateRuntimeRequest) -> Path:
        if request.image != self.config.approved_image:
            raise ValueError("image is not the approved digest-qualified runtime image")
        requested_networks = {request.stream_network, request.netplay_network}
        if not requested_networks <= self.config.approved_networks:
            raise ValueError("runtime requested a network outside the allowlist")
        if "host" in requested_networks:
            raise ValueError("host networking is forbidden")
        if request.gpu_profile not in self.config.gpu_profiles:
            raise ValueError("GPU profile is not approved")
        rom_path = resolve_existing_file_beneath(request.rom_path, self.config.rom_root)
        if sha256_file(rom_path) != request.rom_sha256:
            raise ValueError("ROM SHA-256 does not match")
        return rom_path

    @staticmethod
    def _fingerprint(request: CreateRuntimeRequest) -> str:
        data = request.model_dump(mode="json", exclude={"selkies_master_token"})
        token_hash = hashlib.sha256(
            request.selkies_master_token.get_secret_value().encode()
        ).hexdigest()
        data["selkies_master_token_sha256"] = token_hash
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _metrics_token(request: CreateRuntimeRequest) -> str:
        return hmac.new(
            request.selkies_master_token.get_secret_value().encode(),
            b"retrobrowser-metrics-proxy-v1",
            hashlib.sha256,
        ).hexdigest()

    def _runtime_directory(self, participant_id: UUID) -> Path:
        root = self.config.user_data_root.resolve(strict=True)
        directory = root / str(participant_id)
        if self.config.preprovisioned_user_data and not directory.is_dir():
            raise ValueError("participant user-data directory was not pre-provisioned")
        # Native Linux assigns the directory to fixed runtime UID 1000. Docker
        # Desktop's drvfs bind mount rejects that ownership model, so its
        # operator-selected compatibility mode makes only this opaque leaf
        # namespace writable; the parent save root is never mounted into a runtime.
        directory_mode = 0o700 if self.config.manage_user_data_permissions else 0o777
        directory.mkdir(mode=directory_mode, exist_ok=True)
        resolved = directory.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("generated user-data path escaped the approved root")
        if not self.config.preprovisioned_user_data and self.config.manage_user_data_permissions:
            resolved.chmod(0o700)
        elif not self.config.preprovisioned_user_data:
            resolved.chmod(0o755)
        if not self.config.preprovisioned_user_data and self.config.manage_user_data_permissions:
            _assign_runtime_owner(resolved)
        return resolved

    @staticmethod
    def _persistence_key(request: CreateRuntimeRequest) -> str | None:
        if request.netplay.role != "host":
            return None
        material = "\0".join(
            ("retrobrowser-save-v1", request.user_id, request.core_profile, request.rom_sha256)
        )
        return hashlib.sha256(material.encode()).hexdigest()

    def _persistence_directory(self, save_key: str) -> Path:
        if self.config.save_data_root is None:
            raise ValueError("persistent saves are not configured")
        root = self.config.save_data_root.resolve(strict=True)
        rom_root = self.config.rom_root.resolve(strict=True)
        if root == rom_root or root.is_relative_to(rom_root) or rom_root.is_relative_to(root):
            raise ValueError("save-data root must not overlap the read-only ROM root")
        directory = root / save_key
        directory_mode = 0o700 if self.config.manage_user_data_permissions else 0o755
        directory.mkdir(mode=directory_mode, exist_ok=True)
        resolved = directory.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("generated save-data path escaped the approved root")
        if self.config.manage_user_data_permissions:
            resolved.chmod(0o700)
            _assign_runtime_owner(resolved)
        else:
            resolved.chmod(0o777)
        return resolved

    def _require_available_persistence(self, save_key: str) -> None:
        for summary in self.engine.list_managed_containers():
            if summary.labels.get(SAVE_KEY_LABEL) == save_key:
                raise ConflictError("persistent save is already mounted by another runtime")

    @staticmethod
    def _docker_path(root: str, relative: Path) -> str:
        path_class = (
            PureWindowsPath if "\\" in root or PureWindowsPath(root).drive else PurePosixPath
        )
        return str(path_class(root).joinpath(*relative.parts))

    def _write_runtime_spec(self, request: CreateRuntimeRequest, directory: Path) -> None:
        suffix = Path(request.rom_path).suffix.lower()
        container_rom = f"/run/roms/game{suffix}"
        specification = {
            "schema_version": 1,
            "session_id": str(request.session_id),
            "participant_id": str(request.participant_id),
            "user_id": request.user_id,
            "player_name": request.player_name,
            "game": {
                "canonical_path": container_rom,
                "expected_sha256": request.rom_sha256,
            },
            "emulator": {"core_profile": request.core_profile},
            "netplay": request.netplay.model_dump(mode="json"),
            "stream": {
                "subfolder": request.stream_subfolder,
                "display_profile": "hd-720p60",
            },
            "persistence": {
                "save_mode": (
                    "host-authoritative"
                    if self.config.save_data_root is not None and request.netplay.role == "host"
                    else "ephemeral"
                )
            },
        }
        destination = directory / "runtime-spec.json"
        temporary = directory / ".runtime-spec.json.tmp"
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(specification, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        if not self.config.preprovisioned_user_data and self.config.manage_user_data_permissions:
            destination.chmod(0o600)
        elif not self.config.preprovisioned_user_data:
            destination.chmod(0o644)
        if not self.config.preprovisioned_user_data and self.config.manage_user_data_permissions:
            _assign_runtime_owner(destination)

    def _environment(self, request: CreateRuntimeRequest) -> list[str]:
        use_cpu = "true" if request.gpu_profile == "cpu" else "false"
        environment = [
            "START_LXQT=false",
            f"SELKIES_ALLOWED_ORIGINS={self.config.allowed_origins}",
            "SELKIES_ENABLE_HTTPS=false",
            "SELKIES_ENABLE_BASIC_AUTH=false",
            f"SELKIES_MODE={self.config.selkies_mode}",
            "SELKIES_ENABLE_DUAL_MODE=false",
            "SELKIES_ENCODER=h264enc",
            f"SELKIES_USE_CPU={use_cpu}",
            "SELKIES_AUTO_GPU=false",
            "SELKIES_FRAMERATE=60-60",
            "SELKIES_MANUAL_RESOLUTION=true",
            "SELKIES_MANUAL_WIDTH=1280",
            "SELKIES_MANUAL_HEIGHT=720",
            "SELKIES_ENABLE_RESIZE=false",
            "SELKIES_USE_CSS_SCALING=true|locked",
            "SELKIES_SECOND_SCREEN=false",
            "SELKIES_AUDIO_ENABLED=true",
            "SELKIES_MICROPHONE_ENABLED=false",
            "SELKIES_GAMEPAD_ENABLED=true",
            "SELKIES_UINPUT_GAMEPAD=false",
            "SELKIES_WEBCAM_ENABLED=false",
            "SELKIES_WEBCAM_DEVICE=false",
            "SELKIES_WEBCAM_PIPEWIRE=false",
            "SELKIES_ENABLE_CLIPBOARD=false",
            "SELKIES_ENABLE_BINARY_CLIPBOARD=false",
            "SELKIES_COMMAND_ENABLED=false",
            "SELKIES_FILE_TRANSFERS=none",
            "SELKIES_ENABLE_SHARING=false",
            "SELKIES_ENABLE_COLLAB=false",
            "SELKIES_UI_SIDEBAR_SHOW_CLIPBOARD=false",
            "SELKIES_UI_SIDEBAR_SHOW_FILES=false",
            "SELKIES_UI_SIDEBAR_SHOW_SHARING=false",
            "SELKIES_UI_SIDEBAR_SHOW_WEBCAM=false",
            "SELKIES_ENABLE_INTERNAL_TURN=false",
            f"SELKIES_MASTER_TOKEN={request.selkies_master_token.get_secret_value()}",
            f"SELKIES_SUBFOLDER={request.stream_subfolder}",
        ]
        if self.config.metrics_target_root is not None:
            environment.append("SELKIES_ENABLE_METRICS_HTTP=true")
            environment.append(f"RETROBROWSER_METRICS_TOKEN={self._metrics_token(request)}")
        return environment + self._webrtc_environment(request)

    def _webrtc_environment(self, request: CreateRuntimeRequest) -> list[str]:
        if self.config.selkies_mode != "webrtc":
            return []
        if (
            self.config.turn_rest_uri is None
            or self.config.turn_rest_api_key is None
            or self.config.stun_host is None
        ):
            raise ValueError("WebRTC configuration is incomplete")
        return [
            f"SELKIES_TURN_REST_URI={self.config.turn_rest_uri}",
            f"SELKIES_TURN_REST_API_KEY={self.config.turn_rest_api_key}",
            f"SELKIES_TURN_REST_USERNAME={self.config.turn_rest_username}-{request.participant_id.hex}",
            f"SELKIES_TURN_PROTOCOL={self.config.turn_protocol}",
            f"SELKIES_TURN_TLS={str(self.config.turn_tls).lower()}",
            f"SELKIES_STUN_HOST={self.config.stun_host}",
            f"SELKIES_STUN_PORT={self.config.stun_port}",
            "SELKIES_ENABLE_WEBRTC_STATISTICS=true",
            "SELKIES_WEBRTC_STATISTICS_DIR=/tmp",
        ]

    def _payload(
        self,
        request: CreateRuntimeRequest,
        rom_path: Path,
        runtime_directory: Path,
        fingerprint: str,
        persistence_directory: Path | None,
        save_key: str | None,
    ) -> dict[str, object]:
        suffix = rom_path.suffix.lower()
        labels = {
            MANAGED_LABEL: "true",
            PARTICIPANT_LABEL: str(request.participant_id),
            SESSION_LABEL: str(request.session_id),
            FINGERPRINT_LABEL: fingerprint,
            SUBFOLDER_LABEL: request.stream_subfolder,
        }
        if save_key is not None:
            labels[SAVE_KEY_LABEL] = save_key
        rom_relative = rom_path.relative_to(self.config.rom_root.resolve(strict=True))
        user_data_relative = runtime_directory.relative_to(
            self.config.user_data_root.resolve(strict=True)
        )
        docker_rom_root = self.config.docker_rom_root or str(
            self.config.rom_root.resolve(strict=True)
        )
        docker_user_data_root = self.config.docker_user_data_root or str(
            self.config.user_data_root.resolve(strict=True)
        )
        host_config: dict[str, object] = {
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": self._docker_path(docker_rom_root, rom_relative),
                    "Target": f"/run/roms/game{suffix}",
                    "ReadOnly": True,
                },
                {
                    "Type": "bind",
                    "Source": self._docker_path(docker_user_data_root, user_data_relative),
                    "Target": "/run/retro-session",
                    "ReadOnly": False,
                },
            ],
            "NetworkMode": request.stream_network,
            "Memory": self.config.memory_bytes,
            "NanoCpus": self.config.nano_cpus,
            "PidsLimit": self.config.pids_limit,
            "ShmSize": 2 * 1024**3,
            "Init": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Privileged": False,
        }
        if persistence_directory is not None:
            save_data_root = self.config.save_data_root
            if save_data_root is None:
                raise ValueError("persistent saves are not configured")
            resolved_save_root = save_data_root.resolve(strict=True)
            save_relative = persistence_directory.relative_to(resolved_save_root)
            docker_save_data_root = self.config.docker_save_data_root or str(resolved_save_root)
            mounts = cast(list[dict[str, object]], host_config["Mounts"])
            mounts.append(
                {
                    "Type": "bind",
                    "Source": self._docker_path(docker_save_data_root, save_relative),
                    "Target": "/run/retro-saves",
                    "ReadOnly": False,
                }
            )
        if request.gpu_profile == "nvidia":
            host_config["DeviceRequests"] = [
                {
                    "Driver": "nvidia",
                    "Count": -1,
                    "Capabilities": [["gpu", "utility", "video"]],
                    "Options": {},
                }
            ]
        health_url = f"http://127.0.0.1:8080{request.stream_subfolder}/api/health"
        netplay_state = "0A" if request.netplay.role == "host" else "01"
        netplay_column = 1 if request.netplay.role == "host" else 2
        netplay_port = f"{request.netplay.port:04X}"
        netplay_probe = (
            "import pathlib,sys;"
            f"p='{netplay_port}';s='{netplay_state}';"
            "rows=sum((pathlib.Path(f'/proc/net/{n}').read_text().splitlines()[1:] "
            "for n in ('tcp','tcp6')),[]);"
            f"sys.exit(0 if any((c:=r.split())[{netplay_column}].endswith(':'+p) "
            "and c[3]==s for r in rows) else 1)"
        )
        health_command = (
            "pgrep -x retroarch >/dev/null && "
            f'python3 -c "import urllib.request; '
            f"urllib.request.urlopen('{health_url}', timeout=2)\" && "
            f'python3 -c "{netplay_probe}"'
        )
        return {
            "Image": request.image,
            "Env": self._environment(request),
            "Labels": labels,
            "ExposedPorts": {"8080/tcp": {}, f"{request.netplay.port}/tcp": {}},
            "Healthcheck": {
                "Test": [
                    "CMD-SHELL",
                    health_command,
                ],
                "Interval": 5_000_000_000,
                "Timeout": 3_000_000_000,
                "Retries": 3,
                "StartPeriod": 45_000_000_000,
            },
            "HostConfig": host_config,
            "NetworkingConfig": {
                "EndpointsConfig": {
                    request.stream_network: {},
                    request.netplay_network: {},
                }
            },
        }

    @staticmethod
    def _require_owned(record: ContainerRecord, participant_id: UUID) -> None:
        if record.labels.get(MANAGED_LABEL) != "true":
            raise OwnershipError("container is not owned by Runtime Agent")
        if record.labels.get(PARTICIPANT_LABEL) != str(participant_id):
            raise OwnershipError("container ownership labels do not match the runtime ID")

    def _record(self, container: ContainerRecord, participant_id: UUID) -> RuntimeRecord:
        return RuntimeRecord(
            participant_id=participant_id,
            container_id=container.container_id,
            container_name=container.name,
            state=container.state,
            health_status=container.health_status,
            stream_subfolder=container.labels.get(SUBFOLDER_LABEL, ""),
            orphaned=not self.routes.exists(participant_id),
        )

    def create_runtime(self, request: CreateRuntimeRequest) -> RuntimeRecord:
        with self._lifecycle_lock:
            return self._create_runtime(request)

    def _create_runtime(self, request: CreateRuntimeRequest) -> RuntimeRecord:
        rom_path = self._validate_request(request)
        fingerprint = self._fingerprint(request)
        name = self.container_name(request.participant_id)
        try:
            existing = self.engine.inspect_container(name)
        except NotFoundError:
            existing = None
        if existing is not None:
            self._require_owned(existing, request.participant_id)
            if existing.labels.get(FINGERPRINT_LABEL) != fingerprint:
                raise ConflictError("runtime ID already exists with a different request")
            return self._record(existing, request.participant_id)

        if len(self.list_managed_runtimes()) >= self.config.max_runtimes:
            raise ConflictError("runtime capacity is exhausted")

        save_key = (
            self._persistence_key(request) if self.config.save_data_root is not None else None
        )
        persistence_directory = None
        if save_key is not None:
            self._require_available_persistence(save_key)
            persistence_directory = self._persistence_directory(save_key)
        runtime_directory = self._runtime_directory(request.participant_id)
        self._write_runtime_spec(request, runtime_directory)
        payload = self._payload(
            request,
            rom_path,
            runtime_directory,
            fingerprint,
            persistence_directory,
            save_key,
        )
        try:
            container_id = self.engine.create_container(name, payload)
        except ConflictError:
            existing = self.engine.inspect_container(name)
            self._require_owned(existing, request.participant_id)
            if existing.labels.get(FINGERPRINT_LABEL) != fingerprint:
                raise
            return self._record(existing, request.participant_id)
        try:
            self.engine.start_container(container_id)
            self.routes.publish(request.participant_id, request.stream_subfolder, name)
            self.metrics_targets.publish(
                request.participant_id,
                request.session_id,
                request.core_profile,
                request.stream_subfolder,
                name,
                self._metrics_token(request),
            )
        except Exception:
            self.metrics_targets.remove(request.participant_id)
            try:
                self.routes.remove(request.participant_id)
            except OSError as cleanup_error:
                LOGGER.warning("route cleanup failed: %s", type(cleanup_error).__name__)
            try:
                self.engine.stop_container(container_id)
            except RuntimeAgentError as cleanup_error:
                LOGGER.warning("runtime stop cleanup failed: %s", type(cleanup_error).__name__)
            try:
                self.engine.remove_container(container_id)
            except RuntimeAgentError as cleanup_error:
                LOGGER.warning("runtime remove cleanup failed: %s", type(cleanup_error).__name__)
            raise
        return self._record(self.engine.inspect_container(container_id), request.participant_id)

    def inspect_runtime(self, participant_id: UUID) -> RuntimeRecord:
        container = self.engine.inspect_container(self.container_name(participant_id))
        self._require_owned(container, participant_id)
        return self._record(container, participant_id)

    def stop_runtime(self, participant_id: UUID) -> RuntimeRecord:
        container = self.engine.inspect_container(self.container_name(participant_id))
        self._require_owned(container, participant_id)
        self.engine.stop_container(container.container_id)
        return self._record(self.engine.inspect_container(container.container_id), participant_id)

    def remove_runtime(self, participant_id: UUID) -> None:
        with self._lifecycle_lock:
            self._remove_runtime(participant_id)

    def _remove_runtime(self, participant_id: UUID) -> None:
        try:
            container = self.engine.inspect_container(self.container_name(participant_id))
        except NotFoundError:
            self.routes.remove(participant_id)
            self.metrics_targets.remove(participant_id)
            raise
        self._require_owned(container, participant_id)
        if container.state == "running":
            self.engine.stop_container(container.container_id)
        self.engine.remove_container(container.container_id)
        self.routes.remove(participant_id)
        self.metrics_targets.remove(participant_id)

    def list_managed_runtimes(self) -> list[RuntimeRecord]:
        records: list[RuntimeRecord] = []
        for summary in self.engine.list_managed_containers():
            participant_value = summary.labels.get(PARTICIPANT_LABEL)
            try:
                participant_id = UUID(participant_value or "")
            except ValueError:
                continue
            container = self.engine.inspect_container(summary.container_id)
            self._require_owned(container, participant_id)
            records.append(self._record(container, participant_id))
        return records

    def reconcile_routes(self) -> int:
        managed = {record.participant_id for record in self.list_managed_runtimes()}
        orphaned = self.routes.list_participants() - managed
        for participant_id in orphaned:
            self.routes.remove(participant_id)
        orphaned_targets = self.metrics_targets.list_participants() - managed
        for participant_id in orphaned_targets:
            self.metrics_targets.remove(participant_id)
        return len(orphaned | orphaned_targets)

    def capacity(self) -> RuntimeCapacity:
        used = len(self.list_managed_runtimes())
        return RuntimeCapacity(
            maximum=self.config.max_runtimes,
            used=used,
            available=max(0, self.config.max_runtimes - used),
        )

    def health(self) -> bool:
        return self.engine.ping()
