import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from time import monotonic, sleep
from typing import Literal
from uuid import UUID, uuid4

from retro_sessions.errors import (
    AuthorizationError,
    CapacityError,
    ConflictError,
    NotFoundError,
    OrchestrationError,
)
from retro_sessions.models.domain import (
    Actor,
    CoreProfile,
    CreateSessionRequest,
    GameRecord,
    Participant,
    ParticipantDiagnostic,
    ParticipantState,
    RuntimeCapacity,
    Session,
    SessionDiagnostic,
    SessionState,
    StreamLaunch,
)
from retro_sessions.models.state import require_participant_transition, require_session_transition
from retro_sessions.providers.interfaces import (
    CoreRegistry,
    ExecutionProvider,
    RomMProvider,
    RuntimeHandle,
    RuntimeRequest,
    StreamProvider,
)
from retro_sessions.repositories.interfaces import SessionRepository

Clock = Callable[[], datetime]
MonotonicClock = Callable[[], float]
Sleeper = Callable[[float], None]
LOGGER = logging.getLogger(__name__)


class SessionService:
    """Lobby state machine with bounded participant runtime orchestration."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        romm: RomMProvider,
        cores: CoreRegistry,
        execution: ExecutionProvider,
        stream: StreamProvider,
        clock: Clock | None = None,
        monotonic_clock: MonotonicClock = monotonic,
        sleeper: Sleeper = sleep,
        session_ttl: timedelta = timedelta(hours=4),
        lobby_lease: timedelta = timedelta(minutes=2),
        participant_idle_timeout: timedelta = timedelta(seconds=45),
        startup_timeout: timedelta = timedelta(minutes=3),
        netplay_connect_timeout: timedelta = timedelta(seconds=45),
        poll_interval: timedelta = timedelta(seconds=2),
        runtime_capacity: int = 8,
        session_capacity: int = 4,
        per_user_runtime_capacity: int = 8,
    ) -> None:
        durations = (
            session_ttl,
            lobby_lease,
            participant_idle_timeout,
            startup_timeout,
            netplay_connect_timeout,
            poll_interval,
        )
        if any(value <= timedelta(0) for value in durations):
            raise ValueError("session and orchestration durations must be positive")
        if runtime_capacity < 1:
            raise ValueError("runtime capacity must be positive")
        if session_capacity < 1 or session_capacity > runtime_capacity:
            raise ValueError("session capacity must be positive and not exceed runtime capacity")
        if per_user_runtime_capacity < 1 or per_user_runtime_capacity > runtime_capacity:
            raise ValueError(
                "per-user runtime capacity must be positive and not exceed runtime capacity"
            )
        self._repository = repository
        self._romm = romm
        self._cores = cores
        self._execution = execution
        self._stream = stream
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic_clock
        self._sleep = sleeper
        self._session_ttl = session_ttl
        self._lobby_lease = lobby_lease
        self._participant_idle_timeout = participant_idle_timeout
        self._startup_timeout = startup_timeout
        self._netplay_connect_timeout = netplay_connect_timeout
        self._poll_interval = poll_interval
        self._runtime_capacity = runtime_capacity
        self._session_capacity = session_capacity
        self._per_user_runtime_capacity = per_user_runtime_capacity
        self._lock = RLock()

    def ready(self) -> bool:
        try:
            return (
                self._repository.health()
                and self._romm.health()
                and self._cores.health()
                and self._execution.health()
                and self._stream.health()
            )
        except Exception:
            return False

    def operational_snapshot(self) -> tuple[list[Session], int, int]:
        """Return a bounded snapshot for metrics without exposing runtime internals."""
        with self._lock:
            sessions = self._repository.list()
            runtime_used = len(self._execution.list())
            return sessions, runtime_used, self._runtime_capacity

    def capacity(self) -> RuntimeCapacity:
        with self._lock:
            used = len(self._execution.list())
            return RuntimeCapacity(
                maximum=self._runtime_capacity,
                used=used,
                available=max(0, self._runtime_capacity - used),
            )

    def diagnostics(self, session_id: UUID) -> SessionDiagnostic:
        """Build a sanitized session/runtime view for authenticated operators."""
        with self._lock:
            session = self._required(session_id)
            participant_diagnostics: list[ParticipantDiagnostic] = []
            for item in session.participants:
                handle = None
                if item.runtime_id is not None:
                    try:
                        handle = self._execution.inspect(item.runtime_id)
                    except Exception:
                        handle = None
                participant_diagnostics.append(
                    ParticipantDiagnostic(
                        participant_id=item.participant_id,
                        player_slot=item.player_slot,
                        participant_state=item.state,
                        runtime_state=handle.state if handle is not None else None,
                        runtime_health=handle.health_status if handle is not None else None,
                    )
                )
            return SessionDiagnostic(
                session_id=session.session_id,
                session_state=session.state,
                platform=session.platform,
                core_profile_id=session.core_profile_id,
                player_count=session.player_count,
                max_players=session.max_players,
                closed_reason=session.closed_reason,
                expires_at=session.expires_at,
                runtime_capacity=self.capacity(),
                participants=tuple(participant_diagnostics),
            )

    def _resolve(self, romm_rom_id: int) -> tuple[GameRecord, CoreProfile]:
        try:
            game = self._romm.resolve_game(romm_rom_id)
        except KeyError as error:
            raise NotFoundError("game not found") from error
        try:
            core = self._cores.resolve(game.platform)
        except KeyError as error:
            raise ConflictError("no approved core profile for game platform") from error
        if core.platform != game.platform:
            raise ConflictError("core profile platform does not match game")
        return game, core

    def _require_runtime_capacity(self) -> None:
        if len(self._execution.list()) >= self._runtime_capacity:
            raise CapacityError("runtime capacity is exhausted")

    def _active_sessions(self) -> list[Session]:
        return [
            session
            for session in self._repository.list()
            if session.state not in {SessionState.CLOSED, SessionState.ERROR}
        ]

    def _require_session_capacity(self) -> None:
        if len(self._active_sessions()) >= self._session_capacity:
            raise CapacityError("session capacity is exhausted")

    def _require_user_runtime_capacity(self, user_id: str) -> None:
        active = sum(
            participant.user_id == user_id
            and participant.state not in {ParticipantState.LEFT, ParticipantState.ERROR}
            for session in self._active_sessions()
            for participant in session.participants
        )
        if active >= self._per_user_runtime_capacity:
            raise CapacityError("per-user runtime capacity is exhausted")

    def create(self, actor: Actor, request: CreateSessionRequest) -> Session:
        with self._lock:
            self.expire_due()
            self._require_session_capacity()
            self._require_user_runtime_capacity(actor.user_id)
            self._require_runtime_capacity()
            game, core = self._resolve(request.romm_rom_id)
            if request.max_players > core.max_players:
                raise ConflictError("requested capacity exceeds core profile capacity")

            now = self._clock()
            session_id = uuid4()
            owner = Participant(
                participant_id=uuid4(),
                session_id=session_id,
                user_id=actor.user_id,
                display_name=actor.display_name,
                player_slot=1,
                state=ParticipantState.ALLOCATING,
                joined_at=now,
                last_heartbeat=now,
            )
            session = Session(
                session_id=session_id,
                display_name=request.display_name,
                owner_user_id=actor.user_id,
                romm_rom_id=game.romm_rom_id,
                platform=game.platform,
                rom_sha256=game.rom_sha256,
                core_profile_id=core.profile_id,
                max_players=request.max_players,
                state=SessionState.CREATING,
                participants=(owner,),
                created_at=now,
                updated_at=now,
                expires_at=now + min(self._lobby_lease, self._session_ttl),
            )
            self._repository.add(session)
            return self._start_participant(session, owner, game, core, role="host")

    def discover(self) -> list[Session]:
        self.expire_due()
        return [
            session for session in self._repository.list() if session.state is SessionState.OPEN
        ]

    def get(self, session_id: UUID) -> Session:
        with self._lock:
            session = self._required(session_id)
            return self._expire(session)

    def join(self, session_id: UUID, actor: Actor) -> Session:
        with self._lock:
            session = self._expire(self._required(session_id))
            for participant in session.participants:
                if participant.user_id == actor.user_id:
                    if participant.state is ParticipantState.ACTIVE:
                        return session
            if session.state is not SessionState.OPEN:
                raise ConflictError("session is not open")
            if session.player_count >= session.max_players:
                raise CapacityError("session is at capacity")
            self._require_user_runtime_capacity(actor.user_id)
            self._require_runtime_capacity()

            game, core = self._resolve(session.romm_rom_id)
            if (
                game.platform != session.platform
                or game.rom_sha256 != session.rom_sha256
                or core.profile_id != session.core_profile_id
            ):
                raise ConflictError("trusted game or core metadata changed during the session")
            occupied = {
                participant.player_slot
                for participant in session.participants
                if participant.state not in {ParticipantState.LEFT, ParticipantState.ERROR}
            }
            player_slot = next(
                slot for slot in range(1, session.max_players + 1) if slot not in occupied
            )
            now = self._clock()
            participant = Participant(
                participant_id=uuid4(),
                session_id=session.session_id,
                user_id=actor.user_id,
                display_name=actor.display_name,
                player_slot=player_slot,
                state=ParticipantState.ALLOCATING,
                joined_at=now,
                last_heartbeat=now,
            )
            updated = self._replace_participant(
                session,
                participant,
                append=True,
                state=session.state,
            )
            host = next(item for item in session.participants if item.player_slot == 1)
            return self._start_participant(
                updated,
                participant,
                game,
                core,
                role="client",
                host_participant_id=host.participant_id,
            )

    def _start_participant(
        self,
        session: Session,
        participant: Participant,
        game: GameRecord,
        core: CoreProfile,
        *,
        role: Literal["host", "client"],
        host_participant_id: UUID | None = None,
    ) -> Session:
        starting_participant = participant.model_copy(update={"state": ParticipantState.STARTING})
        target_session_state = (
            SessionState.STARTING if session.state is SessionState.CREATING else session.state
        )
        require_participant_transition(participant.state, ParticipantState.STARTING)
        if session.state is SessionState.CREATING:
            require_session_transition(session.state, target_session_state)
        current = self._replace_participant(
            session,
            starting_participant,
            state=target_session_state,
        )
        runtime_request = RuntimeRequest(
            session_id=current.session_id,
            participant_id=participant.participant_id,
            user_id=participant.user_id,
            player_name=self._netplay_player_name(participant),
            rom_path=game.canonical_path,
            rom_sha256=game.rom_sha256,
            core_profile=core.profile_id,
            role=role,
            host_participant_id=host_participant_id,
        )
        try:
            handle = self._execution.create(runtime_request)
            with_runtime = starting_participant.model_copy(update={"runtime_id": handle.runtime_id})
            current = self._replace_participant(current, with_runtime, state=current.state)
            timeout = self._startup_timeout if role == "host" else self._netplay_connect_timeout
            self._wait_ready(handle, timeout)
            self._stream.provision(participant.participant_id, gamepad_slot=1)
        except Exception as error:
            self._cleanup_failed_runtime(participant.participant_id)
            failed = self._repository.get(current.session_id) or current
            failed_participant = next(
                item
                for item in failed.participants
                if item.participant_id == participant.participant_id
            ).model_copy(update={"state": ParticipantState.ERROR})
            failed_state = SessionState.ERROR if role == "host" else failed.state
            self._replace_participant(failed, failed_participant, state=failed_state)
            if isinstance(error, OrchestrationError):
                raise
            raise OrchestrationError("participant runtime startup failed") from error

        require_participant_transition(ParticipantState.STARTING, ParticipantState.ACTIVE)
        active_at = self._clock()
        active = with_runtime.model_copy(
            update={
                "state": ParticipantState.ACTIVE,
                "last_heartbeat": active_at,
                "stream_path": f"/stream/{participant.participant_id.hex}",
            }
        )
        final_state = SessionState.OPEN if current.state is SessionState.STARTING else current.state
        if current.state is SessionState.STARTING:
            require_session_transition(current.state, final_state)
        return self._replace_participant(
            current,
            active,
            state=final_state,
            expires_at=self._lease_expiry(current, active_at),
        )

    @staticmethod
    def _netplay_player_name(participant: Participant) -> str:
        """Keep user-friendly short names without overflowing RetroArch's wire field."""
        if len(participant.display_name.encode("utf-8")) <= 31:
            return participant.display_name
        return f"Player {participant.player_slot}"

    def _wait_ready(self, handle: RuntimeHandle, timeout: timedelta) -> None:
        deadline = self._monotonic() + timeout.total_seconds()
        current = handle
        while True:
            if current.state == "running" and current.health_status == "healthy":
                return
            if current.state not in {"created", "running", "restarting"}:
                raise OrchestrationError("participant runtime stopped during startup")
            if current.health_status == "unhealthy":
                raise OrchestrationError("participant runtime became unhealthy")
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise OrchestrationError("participant runtime readiness timed out")
            self._sleep(min(self._poll_interval.total_seconds(), remaining))
            current = self._execution.inspect(handle.runtime_id)

    def _cleanup_failed_runtime(self, participant_id: UUID) -> None:
        self._best_effort_revoke(participant_id)
        try:
            self._execution.remove(participant_id)
        except Exception:
            return

    def _best_effort_revoke(self, participant_id: UUID) -> None:
        try:
            self._stream.revoke(participant_id)
        except Exception as error:
            LOGGER.warning(
                "Selkies token revocation failed for participant %s: %s",
                participant_id,
                type(error).__name__,
            )

    def _retire_runtime(self, participant_id: UUID) -> None:
        # Revocation is attempted first so connected browsers are rejected before teardown.
        self._best_effort_revoke(participant_id)
        self._execution.remove(participant_id)

    def launch(self, session_id: UUID, actor: Actor) -> StreamLaunch:
        with self._lock:
            session = self._expire(self._required(session_id))
            participant = next(
                (
                    item
                    for item in session.participants
                    if item.user_id == actor.user_id and item.state is ParticipantState.ACTIVE
                ),
                None,
            )
            if participant is None or participant.stream_path is None:
                raise AuthorizationError("actor is not an active participant")
            token = self._stream.provision(participant.participant_id, gamepad_slot=1)
            return StreamLaunch(
                stream_path=participant.stream_path + "/",
                access_token=token,
                expires_at=session.expires_at,
            )

    def heartbeat(self, session_id: UUID, actor: Actor) -> Session:
        """Renew one active participant and the bounded lobby lease."""
        with self._lock:
            session = self._expire(self._required(session_id))
            participant = next(
                (
                    item
                    for item in session.participants
                    if item.user_id == actor.user_id and item.state is ParticipantState.ACTIVE
                ),
                None,
            )
            if participant is None:
                raise AuthorizationError("actor is not an active participant")
            now = self._clock()
            renewed = participant.model_copy(update={"last_heartbeat": now})
            return self._replace_participant(
                session,
                renewed,
                state=session.state,
                expires_at=self._lease_expiry(session, now),
            )

    def leave(self, session_id: UUID, actor: Actor) -> Session:
        with self._lock:
            session = self._expire(self._required(session_id))
            matching = next(
                (
                    item
                    for item in session.participants
                    if item.user_id == actor.user_id
                    and item.state not in {ParticipantState.LEFT, ParticipantState.ERROR}
                ),
                None,
            )
            if matching is None:
                if any(item.user_id == actor.user_id for item in session.participants):
                    return session
                raise NotFoundError("participant not found")
            if session.state is SessionState.CLOSED:
                return session
            self._retire_runtime(matching.participant_id)
            left = self._left_participant(matching, self._clock())
            return self._replace_participant(session, left, state=session.state)

    def kick(self, session_id: UUID, actor: Actor, participant_id: UUID) -> Session:
        with self._lock:
            session = self._expire(self._required(session_id))
            if session.owner_user_id != actor.user_id:
                raise AuthorizationError("only the session owner may kick a participant")
            participant = next(
                (item for item in session.participants if item.participant_id == participant_id),
                None,
            )
            if participant is None:
                raise NotFoundError("participant not found")
            if participant.user_id == session.owner_user_id:
                raise ConflictError("session owner cannot be kicked; close the session instead")
            if participant.state in {ParticipantState.LEFT, ParticipantState.ERROR}:
                return session
            self._retire_runtime(participant.participant_id)
            left = self._left_participant(participant, self._clock())
            return self._replace_participant(session, left, state=session.state)

    def close(self, session_id: UUID, actor: Actor) -> Session:
        with self._lock:
            session = self._required(session_id)
            if session.owner_user_id != actor.user_id:
                raise AuthorizationError("only the session owner may close it")
            return self._close(session, reason="owner_closed")

    def expire_due(self) -> int:
        """Compatibility wrapper for callers that only need the cleanup count."""
        return self.sweep()

    def sweep(self) -> int:
        """Retire expired, abandoned, and unhealthy sessions and participants."""
        cleaned = 0
        with self._lock:
            for session in self._repository.list():
                if session.state is SessionState.CLOSED:
                    continue
                now = self._clock()
                if session.expires_at <= now or session.created_at + self._session_ttl <= now:
                    self._close(session, reason="expired")
                    cleaned += 1
                    continue

                active = tuple(
                    item for item in session.participants if item.state is ParticipantState.ACTIVE
                )
                stale = tuple(
                    item
                    for item in active
                    if item.last_heartbeat + self._participant_idle_timeout <= now
                )
                owner = next(
                    (item for item in active if item.user_id == session.owner_user_id),
                    None,
                )
                if owner is None or owner in stale:
                    self._close(session, reason="owner_abandoned")
                    cleaned += 1
                    continue

                current = session
                for participant in active:
                    if participant in stale:
                        current = self._retire_participant(current, participant, failed=False)
                        cleaned += 1
                        continue
                    try:
                        runtime = self._execution.inspect(participant.participant_id)
                    except OrchestrationError:
                        # Missing or unreachable runtime state fails closed.
                        runtime = None
                    if (
                        runtime is None
                        or runtime.state != "running"
                        or runtime.health_status != "healthy"
                    ):
                        if participant.user_id == current.owner_user_id:
                            self._close(current, reason="owner_runtime_failed")
                            cleaned += 1
                            break
                        current = self._retire_participant(current, participant, failed=True)
                        cleaned += 1
        return cleaned

    def reconcile_startup(self) -> int:
        """Fail closed after manager restart; live restoration is not implemented."""
        cleaned = 0
        with self._lock:
            for session in self._repository.list():
                if session.state is not SessionState.CLOSED:
                    self._close(session, reason="manager_restarted")
                    cleaned += 1
            for runtime in self._execution.list():
                self._best_effort_revoke(runtime.runtime_id)
                self._execution.remove(runtime.runtime_id)
                cleaned += 1
        return cleaned

    def _required(self, session_id: UUID) -> Session:
        session = self._repository.get(session_id)
        if session is None:
            raise NotFoundError("session not found")
        return session

    def _lease_expiry(self, session: Session, now: datetime) -> datetime:
        return min(now + self._lobby_lease, session.created_at + self._session_ttl)

    def _expire(self, session: Session) -> Session:
        if session.state is not SessionState.CLOSED and session.expires_at <= self._clock():
            return self._close(session, reason="expired")
        return session

    def _close(self, session: Session, *, reason: str) -> Session:
        if session.state is SessionState.CLOSED:
            return session
        require_session_transition(session.state, SessionState.CLOSED)
        now = self._clock()
        for participant in session.participants:
            if participant.state not in {ParticipantState.LEFT, ParticipantState.ERROR}:
                self._retire_runtime(participant.participant_id)
        participants = tuple(self._left_participant(item, now) for item in session.participants)
        updated = session.model_copy(
            update={
                "state": SessionState.CLOSED,
                "participants": participants,
                "updated_at": now,
                "closed_reason": reason,
                "revision": session.revision + 1,
            }
        )
        self._repository.save(updated, expected_revision=session.revision)
        return updated

    def _replace_participant(
        self,
        session: Session,
        participant: Participant,
        *,
        state: SessionState,
        append: bool = False,
        expires_at: datetime | None = None,
    ) -> Session:
        participants = (
            (*session.participants, participant)
            if append
            else tuple(
                participant if item.participant_id == participant.participant_id else item
                for item in session.participants
            )
        )
        updated = session.model_copy(
            update={
                "state": state,
                "participants": participants,
                "updated_at": self._clock(),
                "expires_at": expires_at or session.expires_at,
                "revision": session.revision + 1,
            }
        )
        self._repository.save(updated, expected_revision=session.revision)
        return updated

    def _retire_participant(
        self, session: Session, participant: Participant, *, failed: bool
    ) -> Session:
        self._retire_runtime(participant.participant_id)
        now = self._clock()
        retired = (
            participant.model_copy(update={"state": ParticipantState.ERROR, "last_heartbeat": now})
            if failed
            else self._left_participant(participant, now)
        )
        return self._replace_participant(session, retired, state=session.state)

    @staticmethod
    def _left_participant(participant: Participant, now: datetime) -> Participant:
        if participant.state in {ParticipantState.LEFT, ParticipantState.ERROR}:
            return participant
        require_participant_transition(participant.state, ParticipantState.LEAVING)
        require_participant_transition(ParticipantState.LEAVING, ParticipantState.LEFT)
        return participant.model_copy(
            update={"state": ParticipantState.LEFT, "last_heartbeat": now}
        )
