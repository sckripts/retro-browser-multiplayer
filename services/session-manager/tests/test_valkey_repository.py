from collections.abc import Set as AbstractSet
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from retro_sessions.models import Participant, ParticipantState, Session, SessionState
from retro_sessions.repositories import ValkeySessionRepository

SESSION_ID = UUID("70000000-0000-4000-8000-000000000001")
PARTICIPANT_ID = UUID("70000000-0000-4000-8000-000000000002")


class FakePipeline:
    def __init__(self, client: FakeValkey) -> None:
        self.client = client
        self.queued: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.in_transaction = False

    def watch(self, key: str) -> object:
        return key

    def get(self, key: str) -> str | bytes | None:
        return self.client.get(key)

    def multi(self) -> object:
        self.in_transaction = True
        return True

    def set(self, key: str, value: str, *, ex: int) -> object:
        self.queued.append(("set", (key, value), {"ex": ex}))
        return self

    def sadd(self, key: str, value: str) -> object:
        self.queued.append(("sadd", (key, value), {}))
        return self

    def execute(self) -> list[object]:
        results = [
            getattr(self.client, name)(*args, **kwargs) for name, args, kwargs in self.queued
        ]
        return results

    def reset(self) -> None:
        self.queued.clear()


class FakeValkey:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.ttls: dict[str, int] = {}

    def set(self, key: str, value: str, *, ex: int, nx: bool = False) -> object:
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex
        return True

    def get(self, key: str) -> str | bytes | None:
        return self.values.get(key)

    def smembers(self, key: str) -> AbstractSet[str] | AbstractSet[bytes]:
        return self.sets.get(key, set())

    def sadd(self, key: str, value: str) -> object:
        self.sets.setdefault(key, set()).add(value)
        return 1

    def srem(self, key: str, value: str) -> object:
        self.sets.setdefault(key, set()).discard(value)
        return 1

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction is True
        return FakePipeline(self)

    def ping(self) -> bool:
        return True


def make_session() -> Session:
    now = datetime.now(UTC)
    participant = Participant(
        participant_id=PARTICIPANT_ID,
        session_id=SESSION_ID,
        user_id="owner",
        display_name="Owner",
        player_slot=1,
        state=ParticipantState.ACTIVE,
        joined_at=now,
        last_heartbeat=now,
    )
    return Session(
        session_id=SESSION_ID,
        display_name="Stored Lobby",
        owner_user_id="owner",
        romm_rom_id=42,
        platform="nes",
        rom_sha256="a" * 64,
        core_profile_id="nes-default",
        max_players=2,
        state=SessionState.OPEN,
        participants=(participant,),
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_valkey_repository_round_trip_and_optimistic_save() -> None:
    client = FakeValkey()
    repository = ValkeySessionRepository(client)
    session = make_session()

    repository.add(session)
    assert repository.get(SESSION_ID) == session
    assert repository.list() == [session]

    updated = session.model_copy(update={"display_name": "Updated", "revision": 1})
    repository.save(updated, expected_revision=0)
    assert repository.get(SESSION_ID) == updated
    assert client.ttls[f"retrobrowser:sessions:{SESSION_ID}"] >= 300
    assert repository.health() is True
