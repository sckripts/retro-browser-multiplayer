from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from retro_sessions.errors import (
    AuthorizationError,
    CapacityError,
    ConflictError,
    OrchestrationError,
)
from retro_sessions.models import (
    Actor,
    CoreProfile,
    CreateSessionRequest,
    GameRecord,
    ParticipantState,
    Session,
    SessionState,
)
from retro_sessions.providers import RuntimeHandle, RuntimeRequest
from retro_sessions.providers.static import StaticCoreRegistry
from retro_sessions.repositories import InMemorySessionRepository
from retro_sessions.services import SessionService

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


class FakeRomM:
    def resolve_game(self, romm_rom_id: int) -> GameRecord:
        if romm_rom_id != 42:
            raise KeyError(romm_rom_id)
        return GameRecord(
            romm_rom_id=42,
            platform="nes",
            canonical_path="/srv/retrobrowser/roms/game.nes",
            rom_sha256="a" * 64,
        )

    def health(self) -> bool:
        return True


class FakeCores:
    def resolve(self, platform: str) -> CoreProfile:
        assert platform == "nes"
        return CoreProfile(profile_id="nes-default", platform="nes", max_players=2)

    def health(self) -> bool:
        return True


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FakeExecution:
    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []
        self.removed: list[UUID] = []
        self.overrides: dict[UUID, RuntimeHandle] = {}

    def create(self, request: RuntimeRequest) -> RuntimeHandle:
        self.requests.append(request)
        return RuntimeHandle(
            runtime_id=request.participant_id,
            state="running",
            health_status="healthy",
        )

    def inspect(self, participant_id: UUID) -> RuntimeHandle:
        if participant_id in self.overrides:
            return self.overrides[participant_id]
        return RuntimeHandle(
            runtime_id=participant_id,
            state="running",
            health_status="healthy",
        )

    def list(self) -> list[RuntimeHandle]:
        return [
            self.inspect(request.participant_id)
            for request in self.requests
            if request.participant_id not in self.removed
        ]

    def remove(self, participant_id: UUID) -> None:
        if participant_id not in self.removed:
            self.removed.append(participant_id)

    def health(self) -> bool:
        return True


class FakeStream:
    def __init__(self) -> None:
        self.provisioned: list[tuple[UUID, int]] = []
        self.revoked: list[UUID] = []

    def provision(self, participant_id: UUID, *, gamepad_slot: int) -> str:
        self.provisioned.append((participant_id, gamepad_slot))
        return f"controller-{participant_id.hex}"

    def revoke(self, participant_id: UUID) -> None:
        self.revoked.append(participant_id)

    def health(self) -> bool:
        return True


def make_service() -> tuple[SessionService, Clock]:
    clock = Clock()
    return (
        SessionService(
            repository=InMemorySessionRepository(),
            romm=FakeRomM(),
            cores=FakeCores(),
            execution=FakeExecution(),
            stream=FakeStream(),
            clock=clock,
            session_ttl=timedelta(hours=4),
        ),
        clock,
    )


def actor(number: int) -> Actor:
    return Actor(user_id=f"user-{number}", display_name=f"Player {number}")


def create(service: SessionService, **changes: Any) -> Session:
    payload: dict[str, Any] = {
        "display_name": "Saturday Night NES",
        "romm_rom_id": 42,
        "max_players": 2,
    }
    payload.update(changes)
    return service.create(actor(1), CreateSessionRequest.model_validate(payload))


def test_create_discover_and_get_session() -> None:
    service, _ = make_service()
    session = create(service)
    assert session.state is SessionState.OPEN
    assert session.owner_user_id == "user-1"
    assert session.player_count == 1
    assert session.participants[0].player_slot == 1
    assert service.discover() == [session]
    assert service.get(session.session_id) == session


def test_join_is_idempotent_and_capacity_is_enforced() -> None:
    service, _ = make_service()
    session = create(service)
    joined = service.join(session.session_id, actor(2))
    duplicate = service.join(session.session_id, actor(2))
    assert joined == duplicate
    assert joined.player_count == 2
    assert joined.participants[-1].player_slot == 2
    assert service.discover() == [joined]
    with pytest.raises(CapacityError, match="capacity"):
        service.join(session.session_id, actor(3))


def test_leave_targets_active_participant_after_rejoin() -> None:
    execution = FakeExecution()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
    )
    first_join = service.join(create(service).session_id, actor(2))
    first_guest = first_join.participants[-1]
    service.leave(first_join.session_id, actor(2))
    second_join = service.join(first_join.session_id, actor(2))
    second_guest = second_join.participants[-1]

    left = service.leave(first_join.session_id, actor(2))

    assert first_guest.participant_id != second_guest.participant_id
    assert [
        participant.state for participant in left.participants if participant.user_id == "user-2"
    ] == [
        ParticipantState.LEFT,
        ParticipantState.LEFT,
    ]
    assert execution.removed == [first_guest.participant_id, second_guest.participant_id]


def test_overlong_identity_names_use_safe_netplay_slot_names() -> None:
    execution = FakeExecution()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
    )
    owner = Actor(user_id="user-long-1", display_name="a" * 64)
    guest = Actor(user_id="user-long-2", display_name="b" * 64)
    session = service.create(
        owner,
        CreateSessionRequest(display_name="Long identities", romm_rom_id=42, max_players=2),
    )
    service.join(session.session_id, guest)

    assert [request.player_name for request in execution.requests] == ["Player 1", "Player 2"]


def test_leave_is_idempotent_and_reopens_capacity() -> None:
    service, _ = make_service()
    session = service.join(create(service).session_id, actor(2))
    left = service.leave(session.session_id, actor(2))
    duplicate = service.leave(session.session_id, actor(2))
    assert left == duplicate
    assert left.player_count == 1
    replacement = service.join(session.session_id, actor(3))
    assert replacement.participants[-1].player_slot == 2


def test_only_owner_can_close_and_close_is_idempotent() -> None:
    service, _ = make_service()
    session = create(service)
    with pytest.raises(AuthorizationError, match="owner"):
        service.close(session.session_id, actor(2))
    closed = service.close(session.session_id, actor(1))
    assert closed.state is SessionState.CLOSED
    assert closed.player_count == 0
    assert service.close(session.session_id, actor(1)) == closed
    assert service.discover() == []


def test_expiration_closes_session_and_removes_it_from_discovery() -> None:
    service, clock = make_service()
    session = create(service)
    clock.now += timedelta(hours=4, seconds=1)
    assert service.discover() == []
    expired = service.get(session.session_id)
    assert expired.state is SessionState.CLOSED
    assert expired.closed_reason == "expired"


@pytest.mark.parametrize("name", ["", " ", " leading", "trailing ", "bad\nname", "x" * 65])
def test_session_name_validation(name: str) -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest(display_name=name, romm_rom_id=42, max_players=2)


def test_session_name_is_not_used_as_identifier() -> None:
    service, _ = make_service()
    first = create(service, display_name="Same Name")
    second = service.create(
        actor(2),
        CreateSessionRequest(display_name="Same Name", romm_rom_id=42, max_players=2),
    )
    assert isinstance(first.session_id, UUID)
    assert first.session_id != second.session_id


def test_global_and_per_user_quotas_prevent_runtime_allocation() -> None:
    execution = FakeExecution()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
        runtime_capacity=4,
        session_capacity=2,
        per_user_runtime_capacity=1,
    )
    create(service)

    with pytest.raises(CapacityError, match="per-user"):
        service.create(
            actor(1),
            CreateSessionRequest(display_name="Second", romm_rom_id=42, max_players=2),
        )
    second = service.create(
        actor(2),
        CreateSessionRequest(display_name="Other", romm_rom_id=42, max_players=2),
    )
    with pytest.raises(CapacityError, match="per-user"):
        service.join(second.session_id, actor(1))

    with pytest.raises(CapacityError, match="session capacity"):
        service.create(
            actor(3),
            CreateSessionRequest(display_name="Third", romm_rom_id=42, max_players=2),
        )
    assert len(execution.requests) == 2


def test_max_players_must_fit_core_profile() -> None:
    service, _ = make_service()
    request = CreateSessionRequest(display_name="Too many players", romm_rom_id=42, max_players=3)
    with pytest.raises(ConflictError, match="core profile"):
        service.create(actor(1), request)


def test_core_registry_resolves_platform_profiles() -> None:
    registry = StaticCoreRegistry(
        (
            CoreProfile(profile_id="nes-default", platform="nes", max_players=2),
            CoreProfile(profile_id="snes-bsnes", platform="snes", max_players=4),
            CoreProfile(profile_id="genesis-blastem", platform="genesis", max_players=2),
        )
    )

    assert registry.resolve("nes").profile_id == "nes-default"
    assert registry.resolve("snes").profile_id == "snes-bsnes"
    assert registry.resolve("genesis").profile_id == "genesis-blastem"
    with pytest.raises(KeyError):
        registry.resolve("n64")


def test_core_registry_rejects_duplicate_platforms() -> None:
    with pytest.raises(ValueError, match="duplicate core platform"):
        StaticCoreRegistry(
            (
                CoreProfile(profile_id="snes-a", platform="snes", max_players=4),
                CoreProfile(profile_id="snes-b", platform="snes", max_players=4),
            )
        )


def test_four_player_profile_assigns_and_reuses_stable_slots() -> None:
    class FourPlayerCores:
        def resolve(self, platform: str) -> CoreProfile:
            assert platform == "nes"
            return CoreProfile(profile_id="four-player", platform="nes", max_players=4)

        def health(self) -> bool:
            return True

    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FourPlayerCores(),
        execution=FakeExecution(),
        stream=FakeStream(),
        clock=lambda: NOW,
    )
    session = service.create(
        actor(1),
        CreateSessionRequest(display_name="Four players", romm_rom_id=42, max_players=4),
    )
    for number in (2, 3, 4):
        session = service.join(session.session_id, actor(number))

    assert [item.player_slot for item in session.participants] == [1, 2, 3, 4]
    service.leave(session.session_id, actor(3))
    rejoined = service.join(session.session_id, actor(3))
    assert rejoined.participants[-1].player_slot == 3


def test_create_and_join_generate_host_then_private_client_topology() -> None:
    execution = FakeExecution()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
    )

    session = service.join(create(service).session_id, actor(2))

    assert [request.role for request in execution.requests] == ["host", "client"]
    assert execution.requests[1].host_participant_id == session.participants[0].participant_id
    assert session.participants[1].runtime_id == session.participants[1].participant_id
    response = session.model_dump(mode="json")
    assert "host_participant_id" not in str(response)
    assert "retrobrowser-runtime" not in str(response)


def test_startup_timeout_removes_runtime_and_marks_session_error() -> None:
    class TimedOutExecution(FakeExecution):
        def create(self, request: RuntimeRequest) -> RuntimeHandle:
            self.requests.append(request)
            return RuntimeHandle(
                runtime_id=request.participant_id,
                state="running",
                health_status="starting",
            )

        def inspect(self, participant_id: UUID) -> RuntimeHandle:
            return RuntimeHandle(
                runtime_id=participant_id,
                state="running",
                health_status="starting",
            )

    ticks = iter([0.0, 0.0, 1.0])
    execution = TimedOutExecution()
    repository = InMemorySessionRepository()
    service = SessionService(
        repository=repository,
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
        monotonic_clock=lambda: next(ticks),
        sleeper=lambda _seconds: None,
        startup_timeout=timedelta(seconds=1),
    )

    with pytest.raises(OrchestrationError, match="timed out"):
        create(service)

    failed = repository.list()[0]
    assert failed.state is SessionState.ERROR
    assert failed.participants[0].state.value == "ERROR"
    assert execution.removed == [failed.participants[0].participant_id]


def test_stream_is_provisioned_and_launch_is_actor_scoped() -> None:
    execution = FakeExecution()
    stream = FakeStream()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=stream,
        clock=lambda: NOW,
    )
    session = create(service)
    participant = session.participants[0]

    assert stream.provisioned == [(participant.participant_id, 1)]
    assert participant.stream_path == f"/stream/{participant.participant_id.hex}"
    launch = service.launch(session.session_id, actor(1))
    assert launch.stream_path == participant.stream_path + "/"
    assert launch.access_token == f"controller-{participant.participant_id.hex}"
    assert launch.expires_at == session.expires_at
    assert stream.provisioned[-1] == (participant.participant_id, 1)

    with pytest.raises(AuthorizationError, match="active participant"):
        service.launch(session.session_id, actor(2))


def test_leave_kick_close_and_expiry_revoke_before_removal() -> None:
    events: list[tuple[str, UUID]] = []

    class OrderedExecution(FakeExecution):
        def remove(self, participant_id: UUID) -> None:
            events.append(("remove", participant_id))
            super().remove(participant_id)

    class OrderedStream(FakeStream):
        def revoke(self, participant_id: UUID) -> None:
            events.append(("revoke", participant_id))
            super().revoke(participant_id)

    clock = Clock()
    execution = OrderedExecution()
    stream = OrderedStream()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=stream,
        clock=clock,
        session_ttl=timedelta(hours=4),
    )
    first = service.join(create(service).session_id, actor(2))
    guest = first.participants[1]
    service.leave(first.session_id, actor(2))
    assert events[-2:] == [("revoke", guest.participant_id), ("remove", guest.participant_id)]

    second = service.join(create(service).session_id, actor(2))
    kicked = second.participants[1]
    service.kick(second.session_id, actor(1), kicked.participant_id)
    assert events[-2:] == [("revoke", kicked.participant_id), ("remove", kicked.participant_id)]

    third = create(service)
    owner = third.participants[0]
    service.close(third.session_id, actor(1))
    assert events[-2:] == [("revoke", owner.participant_id), ("remove", owner.participant_id)]

    fourth = create(service)
    expiring_owner = fourth.participants[0]
    clock.now += timedelta(hours=4, seconds=1)
    service.expire_due()
    assert events[-2:] == [
        ("revoke", expiring_owner.participant_id),
        ("remove", expiring_owner.participant_id),
    ]


def test_only_owner_can_kick_and_owner_cannot_kick_self() -> None:
    service, _ = make_service()
    session = service.join(create(service).session_id, actor(2))
    guest = session.participants[1]
    with pytest.raises(AuthorizationError, match="owner"):
        service.kick(session.session_id, actor(2), guest.participant_id)
    with pytest.raises(ConflictError, match="owner"):
        service.kick(session.session_id, actor(1), session.participants[0].participant_id)


def test_token_provision_failure_removes_runtime_and_marks_error() -> None:
    class FailingStream(FakeStream):
        def provision(self, participant_id: UUID, *, gamepad_slot: int) -> str:
            raise OrchestrationError("token endpoint failed")

    execution = FakeExecution()
    repository = InMemorySessionRepository()
    service = SessionService(
        repository=repository,
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FailingStream(),
        clock=lambda: NOW,
    )
    with pytest.raises(OrchestrationError, match="token endpoint"):
        create(service)
    failed = repository.list()[0]
    assert failed.state is SessionState.ERROR
    assert execution.removed == [failed.participants[0].participant_id]


def test_unreachable_revocation_still_removes_runtime_fail_closed() -> None:
    class FailingRevokeStream(FakeStream):
        def revoke(self, participant_id: UUID) -> None:
            raise OrchestrationError("runtime already unavailable")

    execution = FakeExecution()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FailingRevokeStream(),
        clock=lambda: NOW,
    )
    session = create(service)
    left = service.leave(session.session_id, actor(1))
    assert left.participants[0].state.value == "LEFT"
    assert execution.removed == [session.participants[0].participant_id]


def test_heartbeat_renews_lobby_lease_but_not_maximum_lifetime() -> None:
    clock = Clock()
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=FakeExecution(),
        stream=FakeStream(),
        clock=clock,
        session_ttl=timedelta(hours=4),
        lobby_lease=timedelta(hours=2),
        participant_idle_timeout=timedelta(hours=2),
    )
    session = create(service)
    assert session.expires_at == NOW + timedelta(hours=2)

    for hours in (1, 2, 3):
        clock.now = NOW + timedelta(hours=hours)
        session = service.heartbeat(session.session_id, actor(1))

    assert session.expires_at == NOW + timedelta(hours=4)
    assert session.participants[0].last_heartbeat == NOW + timedelta(hours=3)


def test_sweep_retires_idle_guest_and_abandoned_owner() -> None:
    service, clock = make_service()
    joined = service.join(create(service).session_id, actor(2))
    clock.now += timedelta(seconds=30)
    service.heartbeat(joined.session_id, actor(1))
    clock.now += timedelta(seconds=20)

    assert service.sweep() == 1
    after_guest_timeout = service.get(joined.session_id)
    assert after_guest_timeout.participants[1].state is ParticipantState.LEFT

    clock.now += timedelta(seconds=26)
    assert service.sweep() == 1
    abandoned = service.get(joined.session_id)
    assert abandoned.state is SessionState.CLOSED
    assert abandoned.closed_reason == "owner_abandoned"


def test_sweep_closes_failed_host_and_retires_failed_guest() -> None:
    execution = FakeExecution()
    repository = InMemorySessionRepository()
    service = SessionService(
        repository=repository,
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=FakeStream(),
        clock=lambda: NOW,
    )
    first = service.join(create(service).session_id, actor(2))
    guest = first.participants[1]
    execution.overrides[guest.participant_id] = RuntimeHandle(
        runtime_id=guest.participant_id,
        state="exited",
        health_status="unhealthy",
    )
    assert service.sweep() == 1
    assert service.get(first.session_id).participants[1].state is ParticipantState.ERROR

    retried = service.join(first.session_id, actor(2))
    assert retried.player_count == 2
    assert retried.participants[-1].state is ParticipantState.ACTIVE
    assert retried.participants[-1].user_id == "user-2"

    second = create(service)
    owner = second.participants[0]
    execution.overrides[owner.participant_id] = RuntimeHandle(
        runtime_id=owner.participant_id,
        state="exited",
        health_status="unhealthy",
    )
    assert service.sweep() == 1
    assert service.get(second.session_id).closed_reason == "owner_runtime_failed"


@pytest.mark.parametrize("state", [SessionState.CREATING, SessionState.STARTING])
def test_transitional_session_can_fail_closed(state: SessionState) -> None:
    service, _ = make_service()
    session = create(service)
    transitional = session.model_copy(update={"state": state, "revision": session.revision + 1})
    service._repository.save(transitional, expected_revision=session.revision)  # noqa: SLF001

    closed = service.close(session.session_id, actor(1))
    assert closed.state is SessionState.CLOSED


def test_startup_reconciliation_closes_sessions_and_removes_orphan_runtimes() -> None:
    execution = FakeExecution()
    stream = FakeStream()
    repository = InMemorySessionRepository()
    service = SessionService(
        repository=repository,
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=execution,
        stream=stream,
        clock=lambda: NOW,
    )
    session = create(service)
    orphan_id = UUID("90000000-0000-4000-8000-000000000009")
    execution.requests.append(
        execution.requests[0].model_copy(update={"participant_id": orphan_id})
    )

    assert service.reconcile_startup() == 2
    reconciled = service.get(session.session_id)
    assert reconciled.state is SessionState.CLOSED
    assert reconciled.closed_reason == "manager_restarted"
    assert set(execution.removed) == {session.participants[0].participant_id, orphan_id}
    assert set(stream.revoked) >= {session.participants[0].participant_id, orphan_id}
