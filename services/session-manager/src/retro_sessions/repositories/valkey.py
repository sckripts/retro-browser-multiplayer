from collections.abc import Set as AbstractSet
from datetime import UTC, datetime
from math import ceil
from typing import Protocol, cast
from uuid import UUID

from valkey.exceptions import WatchError

from retro_sessions.errors import ConflictError, RepositoryConflict
from retro_sessions.models.domain import Session, SessionState


class Pipeline(Protocol):
    def watch(self, key: str) -> object: ...

    def get(self, key: str) -> str | bytes | None: ...

    def multi(self) -> object: ...

    def set(self, key: str, value: str, *, ex: int) -> object: ...

    def sadd(self, key: str, value: str) -> object: ...

    def execute(self) -> list[object]: ...

    def reset(self) -> None: ...


class ValkeyClient(Protocol):
    def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> object: ...

    def get(self, key: str) -> str | bytes | None: ...

    def smembers(self, key: str) -> AbstractSet[str] | AbstractSet[bytes]: ...

    def sadd(self, key: str, value: str) -> object: ...

    def srem(self, key: str, value: str) -> object: ...

    def pipeline(self, *, transaction: bool) -> Pipeline: ...

    def ping(self) -> bool: ...


class ValkeySessionRepository:
    """Valkey JSON repository with optimistic WATCH/MULTI updates and bounded retention."""

    def __init__(
        self,
        client: ValkeyClient,
        *,
        namespace: str = "retrobrowser:sessions",
        closed_retention_seconds: int = 300,
    ) -> None:
        self._client = client
        self._namespace = namespace
        self._index_key = f"{namespace}:index"
        self._closed_retention_seconds = closed_retention_seconds

    def _key(self, session_id: UUID) -> str:
        return f"{self._namespace}:{session_id}"

    def _ttl(self, session: Session) -> int:
        if session.state is SessionState.CLOSED:
            return self._closed_retention_seconds
        remaining = (session.expires_at - datetime.now(UTC)).total_seconds()
        return max(self._closed_retention_seconds, ceil(remaining) + self._closed_retention_seconds)

    @staticmethod
    def _encode(session: Session) -> str:
        return session.model_dump_json(exclude_computed_fields=True)

    @staticmethod
    def _decode(value: str | bytes) -> Session:
        return Session.model_validate_json(value)

    def add(self, session: Session) -> None:
        key = self._key(session.session_id)
        created = self._client.set(key, self._encode(session), ex=self._ttl(session), nx=True)
        if not created:
            raise ConflictError("session already exists")
        self._client.sadd(self._index_key, key)

    def get(self, session_id: UUID) -> Session | None:
        value = self._client.get(self._key(session_id))
        return None if value is None else self._decode(value)

    def list(self) -> list[Session]:
        sessions: list[Session] = []
        keys = self._client.smembers(self._index_key)
        for raw_key in keys:
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            value = self._client.get(key)
            if value is None:
                self._client.srem(self._index_key, key)
                continue
            sessions.append(self._decode(value))
        return sorted(sessions, key=lambda item: item.created_at)

    def save(self, session: Session, *, expected_revision: int) -> None:
        key = self._key(session.session_id)
        pipeline = self._client.pipeline(transaction=True)
        try:
            pipeline.watch(key)
            raw = pipeline.get(key)
            if raw is None:
                raise RepositoryConflict("session disappeared during update")
            current = self._decode(raw)
            if current.revision != expected_revision or session.revision != expected_revision + 1:
                raise RepositoryConflict("session revision changed during update")
            pipeline.multi()
            pipeline.set(key, self._encode(session), ex=self._ttl(session))
            pipeline.sadd(self._index_key, key)
            pipeline.execute()
        except RepositoryConflict:
            raise
        except WatchError as error:
            raise RepositoryConflict("session revision changed during update") from error
        finally:
            pipeline.reset()

    def health(self) -> bool:
        return bool(self._client.ping())


def connect_valkey(url: str) -> ValkeySessionRepository:
    import valkey

    client = valkey.Valkey.from_url(url, decode_responses=True)
    return ValkeySessionRepository(cast(ValkeyClient, client))
