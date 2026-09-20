from threading import RLock
from uuid import UUID

from retro_sessions.errors import ConflictError, RepositoryConflict
from retro_sessions.models.domain import Session


class InMemorySessionRepository:
    """Deterministic fake repository used by Milestone 7 tests."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}
        self._lock = RLock()

    def add(self, session: Session) -> None:
        with self._lock:
            if session.session_id in self._sessions:
                raise ConflictError("session already exists")
            self._sessions[session.session_id] = session

    def get(self, session_id: UUID) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda item: item.created_at)

    def save(self, session: Session, *, expected_revision: int) -> None:
        with self._lock:
            current = self._sessions.get(session.session_id)
            if current is None:
                raise RepositoryConflict("session disappeared during update")
            if current.revision != expected_revision:
                raise RepositoryConflict("session revision changed during update")
            if session.revision != expected_revision + 1:
                raise RepositoryConflict("new session revision is invalid")
            self._sessions[session.session_id] = session

    def health(self) -> bool:
        return True
