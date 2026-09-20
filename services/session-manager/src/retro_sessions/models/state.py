from retro_sessions.errors import ConflictError
from retro_sessions.models.domain import ParticipantState, SessionState

SESSION_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.CREATING: frozenset(
        {SessionState.STARTING, SessionState.OPEN, SessionState.CLOSED, SessionState.ERROR}
    ),
    SessionState.STARTING: frozenset({SessionState.OPEN, SessionState.CLOSED, SessionState.ERROR}),
    SessionState.OPEN: frozenset(
        {SessionState.RUNNING, SessionState.DRAINING, SessionState.CLOSED, SessionState.ERROR}
    ),
    SessionState.RUNNING: frozenset(
        {SessionState.DRAINING, SessionState.CLOSED, SessionState.ERROR}
    ),
    SessionState.DRAINING: frozenset({SessionState.CLOSED, SessionState.ERROR}),
    SessionState.CLOSED: frozenset(),
    SessionState.ERROR: frozenset({SessionState.DRAINING, SessionState.CLOSED}),
}

PARTICIPANT_TRANSITIONS: dict[ParticipantState, frozenset[ParticipantState]] = {
    ParticipantState.ALLOCATING: frozenset(
        {ParticipantState.STARTING, ParticipantState.ACTIVE, ParticipantState.ERROR}
    ),
    ParticipantState.STARTING: frozenset(
        {ParticipantState.STREAM_READY, ParticipantState.ACTIVE, ParticipantState.ERROR}
    ),
    ParticipantState.STREAM_READY: frozenset(
        {ParticipantState.NETPLAY_CONNECTING, ParticipantState.ACTIVE, ParticipantState.ERROR}
    ),
    ParticipantState.NETPLAY_CONNECTING: frozenset(
        {ParticipantState.ACTIVE, ParticipantState.ERROR}
    ),
    ParticipantState.ACTIVE: frozenset({ParticipantState.LEAVING, ParticipantState.ERROR}),
    ParticipantState.LEAVING: frozenset({ParticipantState.LEFT, ParticipantState.ERROR}),
    ParticipantState.LEFT: frozenset(),
    ParticipantState.ERROR: frozenset({ParticipantState.LEAVING, ParticipantState.LEFT}),
}


def require_session_transition(current: SessionState, target: SessionState) -> None:
    if target not in SESSION_TRANSITIONS[current]:
        raise ConflictError(f"invalid session transition: {current} -> {target}")


def require_participant_transition(current: ParticipantState, target: ParticipantState) -> None:
    if target not in PARTICIPANT_TRANSITIONS[current]:
        raise ConflictError(f"invalid participant transition: {current} -> {target}")
