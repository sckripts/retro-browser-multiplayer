import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from retro_runtime.errors import ConflictError, NotFoundError, OwnershipError
from retro_runtime.models import AgentConfig, ContainerRecord, CreateRuntimeRequest
from retro_runtime.service import (
    FINGERPRINT_LABEL,
    MANAGED_LABEL,
    PARTICIPANT_LABEL,
    SAVE_KEY_LABEL,
    SUBFOLDER_LABEL,
    RuntimeService,
)

IMAGE = "retrobrowser/retro-session@sha256:" + "a" * 64
PARTICIPANT_ID = UUID("60000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("60000000-0000-4000-8000-000000000006")


class FakeEngine:
    def __init__(self) -> None:
        self.containers: dict[str, ContainerRecord] = {}
        self.create_calls = 0
        self.last_payload: Mapping[str, object] | None = None

    def ping(self) -> bool:
        return True

    def create_container(self, name: str, payload: Mapping[str, object]) -> str:
        self.create_calls += 1
        self.last_payload = payload
        config = dict(payload)
        labels_object = config["Labels"]
        assert isinstance(labels_object, dict)
        labels = {str(key): str(value) for key, value in labels_object.items()}
        container_id = f"container-{self.create_calls}"
        record = ContainerRecord(
            container_id=container_id,
            name=name,
            state="created",
            health_status="starting",
            labels=labels,
            image=str(config["Image"]),
        )
        self.containers[container_id] = record
        self.containers[name] = record
        return container_id

    def start_container(self, container_id: str) -> None:
        self._set_state(container_id, "running")

    def inspect_container(self, container_id: str) -> ContainerRecord:
        try:
            return self.containers[container_id]
        except KeyError as error:
            raise NotFoundError("not found") from error

    def stop_container(self, container_id: str) -> None:
        self._set_state(container_id, "exited")

    def remove_container(self, container_id: str) -> None:
        record = self.inspect_container(container_id)
        for key in [record.container_id, record.name]:
            self.containers.pop(key, None)

    def list_managed_containers(self) -> list[ContainerRecord]:
        unique = {record.container_id: record for record in self.containers.values()}
        return [record for record in unique.values() if record.labels.get(MANAGED_LABEL) == "true"]

    def _set_state(self, container_id: str, state: str) -> None:
        old = self.inspect_container(container_id)
        new = old.model_copy(update={"state": state})
        self.containers[old.container_id] = new
        self.containers[old.name] = new


class FakeRoutes:
    def __init__(self) -> None:
        self.participants: set[UUID] = set()

    def publish(self, participant_id: UUID, subfolder: str, container_name: str) -> None:
        assert subfolder.startswith("/stream/")
        assert container_name.startswith("retrobrowser-runtime-")
        self.participants.add(participant_id)

    def remove(self, participant_id: UUID) -> None:
        self.participants.discard(participant_id)

    def exists(self, participant_id: UUID) -> bool:
        return participant_id in self.participants

    def list_participants(self) -> set[UUID]:
        return set(self.participants)


def make_config(tmp_path: Path) -> AgentConfig:
    rom_root = tmp_path / "roms"
    user_data_root = tmp_path / "userdata"
    route_root = tmp_path / "routes"
    for directory in [rom_root, user_data_root, route_root]:
        directory.mkdir()
    return AgentConfig(
        approved_image=IMAGE,
        approved_networks=frozenset({"runtime-stream", "retro-net"}),
        rom_root=rom_root,
        user_data_root=user_data_root,
        route_root=route_root,
        allowed_origins="https://arcade.example.test",
        gpu_profiles=frozenset({"cpu", "nvidia"}),
        manage_user_data_permissions=False,
    )


def make_request(config: AgentConfig, **changes: Any) -> CreateRuntimeRequest:
    rom_path = config.rom_root / "game.nes"
    if not rom_path.exists():
        rom_path.write_bytes(b"legal-test-content")
    data: dict[str, Any] = {
        "schema_version": 1,
        "session_id": str(SESSION_ID),
        "participant_id": str(PARTICIPANT_ID),
        "user_id": "test-user",
        "player_name": "PlayerOne",
        "image": IMAGE,
        "rom_path": str(rom_path),
        "rom_sha256": hashlib.sha256(rom_path.read_bytes()).hexdigest(),
        "core_profile": "nes-milestone2",
        "netplay": {"role": "host", "host": None, "port": 55435},
        "stream_subfolder": "/stream/m6-player",
        "stream_network": "runtime-stream",
        "netplay_network": "retro-net",
        "gpu_profile": "cpu",
        "selkies_master_token": "t" * 32,
    }
    data.update(changes)
    return CreateRuntimeRequest.model_validate(data)


def make_service(
    config: AgentConfig, engine: FakeEngine | None = None, routes: FakeRoutes | None = None
) -> tuple[RuntimeService, FakeEngine, FakeRoutes]:
    selected_engine = engine or FakeEngine()
    selected_routes = routes or FakeRoutes()
    return (
        RuntimeService(config, selected_engine, selected_routes),
        selected_engine,
        selected_routes,
    )


def test_invalid_image_is_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    request = make_request(config, image="evil.example/runtime@sha256:" + "b" * 64)
    service, engine, _ = make_service(config)

    with pytest.raises(ValueError, match="approved digest"):
        service.create_runtime(request)

    assert engine.create_calls == 0


def test_capacity_is_reported_and_enforced(tmp_path: Path) -> None:
    config = make_config(tmp_path).model_copy(update={"max_runtimes": 1})
    service, _engine, _routes = make_service(config)
    service.create_runtime(make_request(config))

    assert service.capacity().model_dump() == {"maximum": 1, "used": 1, "available": 0}
    second = make_request(
        config,
        participant_id="60000000-0000-4000-8000-000000000002",
        stream_subfolder="/stream/m6-player-two",
    )
    with pytest.raises(ConflictError, match="capacity"):
        service.create_runtime(second)


def test_missing_mount_is_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    request = make_request(config, rom_path=str(config.rom_root / "missing.nes"))
    service, engine, _ = make_service(config)

    with pytest.raises((ValueError, FileNotFoundError)):
        service.create_runtime(request)

    assert engine.create_calls == 0


def test_traversal_outside_rom_root_is_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    outside = tmp_path / "outside.nes"
    outside.write_bytes(b"outside")
    request = make_request(
        config,
        rom_path=str(config.rom_root / ".." / outside.name),
        rom_sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
    )
    service, engine, _ = make_service(config)

    with pytest.raises(ValueError, match="escapes"):
        service.create_runtime(request)

    assert engine.create_calls == 0


def test_host_network_is_rejected(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    request = make_request(config, stream_network="host")
    service, engine, _ = make_service(config)

    with pytest.raises(ValueError, match="network"):
        service.create_runtime(request)

    assert engine.create_calls == 0


def test_preprovisioned_user_data_must_exist(tmp_path: Path) -> None:
    config = make_config(tmp_path).model_copy(update={"preprovisioned_user_data": True})
    service, engine, _ = make_service(config)

    with pytest.raises(ValueError, match="not pre-provisioned"):
        service.create_runtime(make_request(config))

    assert engine.create_calls == 0


def test_managed_permissions_assign_runtime_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path).model_copy(update={"manage_user_data_permissions": True})
    assigned: list[Path] = []
    monkeypatch.setattr("retro_runtime.service._assign_runtime_owner", assigned.append)
    service, _engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    directory = config.user_data_root / str(PARTICIPANT_ID)
    assert assigned == [directory, directory / "runtime-spec.json"]
    if os.name == "posix":
        assert directory.stat().st_mode & 0o777 == 0o700
        assert (directory / "runtime-spec.json").stat().st_mode & 0o777 == 0o600


def test_admin_can_disable_posix_owner_assignment_for_docker_desktop(tmp_path: Path) -> None:
    config = make_config(tmp_path).model_copy(update={"manage_user_data_permissions": False})
    service, _engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    directory = config.user_data_root / str(PARTICIPANT_ID)
    expected_directory_mode = 0o755 if os.name == "posix" else 0o777
    expected_file_mode = 0o644 if os.name == "posix" else 0o666
    assert directory.stat().st_mode & 0o777 == expected_directory_mode
    assert (directory / "runtime-spec.json").stat().st_mode & 0o777 == expected_file_mode


def test_runtime_locks_css_scaling_on_for_fixed_resolution_stream(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    service, engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    assert engine.last_payload is not None
    environment = engine.last_payload["Env"]
    assert isinstance(environment, list)
    assert "SELKIES_USE_CSS_SCALING=true|locked" in environment


def test_public_runtime_receives_only_short_lived_turn_service_configuration(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path).model_copy(
        update={
            "selkies_mode": "webrtc",
            "turn_rest_uri": "http://turn-rest:8008/",
            "turn_rest_api_key": "k" * 32,
            "turn_rest_username": "m14",
            "stun_host": "turn.example.test",
        }
    )
    service, engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    assert engine.last_payload is not None
    environment = engine.last_payload["Env"]
    assert isinstance(environment, list)
    assert "SELKIES_MODE=webrtc" in environment
    assert "SELKIES_TURN_REST_URI=http://turn-rest:8008/" in environment
    assert "SELKIES_TURN_REST_API_KEY=" + "k" * 32 in environment
    assert f"SELKIES_TURN_REST_USERNAME=m14-{PARTICIPANT_ID.hex}" in environment
    assert "SELKIES_STUN_HOST=turn.example.test" in environment
    assert not any("TURN_SHARED_SECRET" in item for item in environment)


def test_webrtc_configuration_fails_closed_without_private_turn_service(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    data = config.model_dump()
    data["docker_socket"] = tmp_path / "docker.sock"
    data["listen_socket"] = tmp_path / "runtime-agent.sock"
    data["selkies_mode"] = "webrtc"

    with pytest.raises(ValidationError, match="requires TURN REST URI"):
        AgentConfig.model_validate(data)


def test_websocket_configuration_rejects_unused_turn_credentials(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    data = config.model_dump()
    data["docker_socket"] = tmp_path / "docker.sock"
    data["listen_socket"] = tmp_path / "runtime-agent.sock"
    data["turn_rest_uri"] = "http://turn-rest:8008/"
    data["turn_rest_api_key"] = "k" * 32
    data["stun_host"] = "turn.example.test"

    with pytest.raises(ValidationError, match="only in WebRTC mode"):
        AgentConfig.model_validate(data)


def test_unmanaged_container_cannot_be_removed(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    engine = FakeEngine()
    name = RuntimeService.container_name(PARTICIPANT_ID)
    unmanaged = ContainerRecord(
        container_id="unmanaged-id",
        name=name,
        state="running",
        health_status="healthy",
        labels={},
        image=IMAGE,
    )
    engine.containers[name] = unmanaged
    engine.containers[unmanaged.container_id] = unmanaged
    service, _, _ = make_service(config, engine=engine)

    with pytest.raises(OwnershipError, match="not owned"):
        service.remove_runtime(PARTICIPANT_ID)

    assert engine.inspect_container("unmanaged-id").state == "running"


def test_duplicate_runtime_request_is_idempotent(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    service, engine, routes = make_service(config)
    request = make_request(config)

    first = service.create_runtime(request)
    second = service.create_runtime(request)

    assert first.container_id == second.container_id
    assert engine.create_calls == 1
    assert PARTICIPANT_ID in routes.participants


def test_managed_container_without_route_is_reported_as_orphan(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    engine = FakeEngine()
    name = RuntimeService.container_name(PARTICIPANT_ID)
    managed = ContainerRecord(
        container_id="orphan-id",
        name=name,
        state="running",
        health_status="healthy",
        labels={
            MANAGED_LABEL: "true",
            PARTICIPANT_LABEL: str(PARTICIPANT_ID),
            SUBFOLDER_LABEL: "/stream/orphan",
            FINGERPRINT_LABEL: "f" * 64,
        },
        image=IMAGE,
    )
    engine.containers[name] = managed
    engine.containers[managed.container_id] = managed
    service, _, _ = make_service(config, engine=engine)

    records = service.list_managed_runtimes()

    assert len(records) == 1
    assert records[0].orphaned is True
    assert records[0].health_status == "healthy"


def test_created_payload_has_only_generated_mounts_and_fixed_hardening(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    service, engine, _ = make_service(config)

    service.create_runtime(make_request(config))

    assert engine.last_payload is not None
    payload = dict(engine.last_payload)
    assert "Cmd" not in payload
    assert "Entrypoint" not in payload
    host_config_object = payload["HostConfig"]
    assert isinstance(host_config_object, dict)
    host_config = host_config_object
    assert host_config["NetworkMode"] == "runtime-stream"
    assert host_config["Privileged"] is False
    assert host_config["CapDrop"] == ["ALL"]
    assert host_config["Memory"] == config.memory_bytes
    assert host_config["NanoCpus"] == config.nano_cpus
    mounts = host_config["Mounts"]
    assert isinstance(mounts, list)
    assert len(mounts) == 2
    assert mounts[0]["Target"] == "/run/roms/game.nes"
    assert mounts[0]["ReadOnly"] is True
    assert mounts[1]["Target"] == "/run/retro-session"
    assert mounts[1]["ReadOnly"] is False
    healthcheck = payload["Healthcheck"]
    assert isinstance(healthcheck, dict)
    command = healthcheck["Test"][-1]
    assert healthcheck["Retries"] == 3
    assert "/proc/net/" in command
    assert "tcp6" in command
    assert "D88B" in command  # TCP 55435 in hexadecimal.


def test_host_gets_opaque_durable_save_mount_when_configured(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    save_root = tmp_path / "persistent-saves"
    save_root.mkdir()
    config = config.model_copy(
        update={
            "save_data_root": save_root,
            "docker_save_data_root": "/host/persistent-saves",
        }
    )
    service, engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    assert engine.last_payload is not None
    labels = engine.last_payload["Labels"]
    assert isinstance(labels, dict)
    save_key = labels[SAVE_KEY_LABEL]
    assert len(save_key) == 64
    assert "test-user" not in save_key
    mounts = engine.last_payload["HostConfig"]["Mounts"]  # type: ignore[index]
    assert mounts[-1] == {
        "Type": "bind",
        "Source": f"/host/persistent-saves/{save_key}",
        "Target": "/run/retro-saves",
        "ReadOnly": False,
    }
    spec = (config.user_data_root / str(PARTICIPANT_ID) / "runtime-spec.json").read_text()
    assert '"save_mode":"host-authoritative"' in spec


def test_docker_desktop_mode_makes_only_save_namespace_writable(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    save_root = tmp_path / "persistent-saves"
    save_root.mkdir(mode=0o700)
    config = config.model_copy(
        update={"save_data_root": save_root, "manage_user_data_permissions": False}
    )
    service, _engine, _routes = make_service(config)

    service.create_runtime(make_request(config))

    namespace = next(save_root.iterdir())
    expected_namespace_mode = 0o777
    expected_root_mode = 0o700 if os.name == "posix" else 0o777
    assert namespace.stat().st_mode & 0o777 == expected_namespace_mode
    assert save_root.stat().st_mode & 0o777 == expected_root_mode


def test_client_save_data_remains_ephemeral(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    save_root = tmp_path / "persistent-saves"
    save_root.mkdir()
    config = config.model_copy(update={"save_data_root": save_root})
    service, engine, _routes = make_service(config)
    request = make_request(
        config,
        netplay={"role": "client", "host": "runtime-host", "port": 55435},
    )

    service.create_runtime(request)

    assert engine.last_payload is not None
    labels = engine.last_payload["Labels"]
    assert isinstance(labels, dict)
    assert SAVE_KEY_LABEL not in labels
    mounts = engine.last_payload["HostConfig"]["Mounts"]  # type: ignore[index]
    assert len(mounts) == 2
    spec = (config.user_data_root / str(PARTICIPANT_ID) / "runtime-spec.json").read_text()
    assert '"save_mode":"ephemeral"' in spec


def test_save_root_cannot_overlap_read_only_rom_root(tmp_path: Path) -> None:
    base_config = make_config(tmp_path)
    config = base_config.model_copy(update={"save_data_root": base_config.rom_root})
    service, engine, _routes = make_service(config)

    with pytest.raises(ValueError, match="must not overlap"):
        service.create_runtime(make_request(config))

    assert engine.create_calls == 0


def test_second_runtime_cannot_mount_same_persistent_save(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    save_root = tmp_path / "persistent-saves"
    save_root.mkdir()
    config = config.model_copy(update={"save_data_root": save_root})
    service, engine, _routes = make_service(config)
    first = make_request(config)
    second = make_request(
        config,
        participant_id="60000000-0000-4000-8000-000000000002",
        session_id="60000000-0000-4000-8000-000000000007",
    )
    service.create_runtime(first)

    with pytest.raises(ConflictError, match="already mounted"):
        service.create_runtime(second)

    assert engine.create_calls == 1


def test_persistent_save_can_be_reopened_after_runtime_removal(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    save_root = tmp_path / "persistent-saves"
    save_root.mkdir()
    config = config.model_copy(update={"save_data_root": save_root})
    service, engine, _routes = make_service(config)
    first = make_request(config)
    service.create_runtime(first)
    assert engine.last_payload is not None
    first_labels = engine.last_payload["Labels"]
    assert isinstance(first_labels, dict)
    save_key = first_labels[SAVE_KEY_LABEL]
    service.remove_runtime(PARTICIPANT_ID)

    service.create_runtime(
        make_request(
            config,
            participant_id="60000000-0000-4000-8000-000000000002",
            session_id="60000000-0000-4000-8000-000000000007",
        )
    )

    assert engine.last_payload is not None
    second_labels = engine.last_payload["Labels"]
    assert isinstance(second_labels, dict)
    assert second_labels[SAVE_KEY_LABEL] == save_key
    assert (save_root / save_key).is_dir()


def test_unknown_command_field_is_not_representable(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    request = make_request(config).model_dump(mode="json")
    request["command"] = ["sh", "-c", "id"]

    with pytest.raises(ValidationError, match="Extra inputs"):
        CreateRuntimeRequest.model_validate(request)


def test_missing_container_removal_still_removes_route(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    routes = FakeRoutes()
    routes.participants.add(PARTICIPANT_ID)
    service, _engine, _routes = make_service(config, routes=routes)

    with pytest.raises(NotFoundError):
        service.remove_runtime(PARTICIPANT_ID)

    assert PARTICIPANT_ID not in routes.participants


def test_startup_route_reconciliation_removes_only_routes_without_containers(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    routes = FakeRoutes()
    service, _engine, _routes = make_service(config, routes=routes)
    service.create_runtime(make_request(config))
    orphan_id = UUID("60000000-0000-4000-8000-000000000099")
    routes.participants.add(orphan_id)

    assert service.reconcile_routes() == 1
    assert routes.participants == {PARTICIPANT_ID}
