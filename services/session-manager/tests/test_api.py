import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from retro_sessions.api import create_app
from retro_sessions.models import CoreProfile, GameRecord
from retro_sessions.providers import RuntimeHandle, RuntimeRequest
from retro_sessions.repositories import InMemorySessionRepository
from retro_sessions.services import SessionService

SERVICE_TOKEN = "s" * 32


class FakeRomM:
    def resolve_game(self, romm_rom_id: int) -> GameRecord:
        return GameRecord(
            romm_rom_id=romm_rom_id,
            platform="nes",
            canonical_path="/srv/retrobrowser/roms/game.nes",
            rom_sha256="a" * 64,
        )

    def health(self) -> bool:
        return True


class FakeCores:
    def resolve(self, platform: str) -> CoreProfile:
        return CoreProfile(profile_id="nes-default", platform=platform, max_players=2)

    def health(self) -> bool:
        return True


class FakeExecution:
    def create(self, request: RuntimeRequest) -> RuntimeHandle:
        return RuntimeHandle(
            runtime_id=request.participant_id,
            state="running",
            health_status="healthy",
        )

    def inspect(self, participant_id: UUID) -> RuntimeHandle:
        return RuntimeHandle(
            runtime_id=participant_id,
            state="running",
            health_status="healthy",
        )

    def list(self) -> list[RuntimeHandle]:
        return []

    def remove(self, participant_id: UUID) -> None:
        return

    def health(self) -> bool:
        return True


class FakeStream:
    def provision(self, participant_id: UUID, *, gamepad_slot: int) -> str:
        assert gamepad_slot == 1
        return f"controller-{participant_id.hex}"

    def revoke(self, participant_id: UUID) -> None:
        return

    def health(self) -> bool:
        return True


def headers(user: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {SERVICE_TOKEN}",
        "X-Authenticated-User-Id": f"user-{user}",
        "X-Authenticated-User-Display-Name": f"Player {user}",
    }


def make_client() -> TestClient:
    service = SessionService(
        repository=InMemorySessionRepository(),
        romm=FakeRomM(),
        cores=FakeCores(),
        execution=FakeExecution(),
        stream=FakeStream(),
        clock=lambda: datetime(2026, 9, 2, tzinfo=UTC),
        session_ttl=timedelta(hours=4),
    )
    return TestClient(create_app(service, service_token=SecretStr(SERVICE_TOKEN)))


def test_health_and_readiness() -> None:
    client = make_client()
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/readyz").json() == {"ready": True}


def test_private_metrics_and_capacity_are_reported() -> None:
    client = make_client()
    assert client.get("/v1/operations/capacity", headers=headers(1)).json() == {
        "maximum": 8,
        "used": 0,
        "available": 8,
    }
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "retrobrowser_runtime_capacity 8.0" in metrics.text
    assert 'retrobrowser_sessions{state="OPEN"} 0.0' in metrics.text


def test_session_api_lifecycle() -> None:
    client = make_client()
    created_response = client.post(
        "/v1/sessions",
        headers=headers(1),
        json={"display_name": "API Lobby", "romm_rom_id": 7, "max_players": 2},
    )
    assert created_response.status_code == 201
    session_id = created_response.json()["session_id"]
    assert (
        client.get("/v1/sessions", headers=headers(1)).json()["items"][0]["session_id"]
        == session_id
    )
    assert client.get(f"/v1/sessions/{session_id}", headers=headers(1)).status_code == 200
    diagnostics = client.get(f"/v1/sessions/{session_id}/diagnostics", headers=headers(1)).json()
    assert diagnostics["session_id"] == session_id
    assert diagnostics["participants"][0]["runtime_health"] == "healthy"
    assert "container_id" not in str(diagnostics)
    assert client.post(f"/v1/sessions/{session_id}/join", headers=headers(2)).status_code == 200
    launch = client.post(f"/v1/sessions/{session_id}/launch", headers=headers(2))
    assert launch.status_code == 200
    assert launch.json()["stream_path"].startswith("/stream/")
    assert launch.json()["access_token"].startswith("controller-")
    assert "?token=" not in launch.json()["stream_path"]
    heartbeat = client.post(f"/v1/sessions/{session_id}/heartbeat", headers=headers(2))
    assert heartbeat.status_code == 200
    assert heartbeat.json()["participants"][1]["user_id"] == "user-2"

    participant_id = client.get(f"/v1/sessions/{session_id}", headers=headers(1)).json()[
        "participants"
    ][1]["participant_id"]
    assert (
        client.post(
            f"/v1/sessions/{session_id}/participants/{participant_id}/kick",
            headers=headers(1),
        ).status_code
        == 200
    )
    assert client.post(f"/v1/sessions/{session_id}/leave", headers=headers(2)).status_code == 200
    assert client.delete(f"/v1/sessions/{session_id}", headers=headers(2)).status_code == 403
    assert client.delete(f"/v1/sessions/{session_id}", headers=headers(1)).status_code == 204


def test_mutating_api_requires_private_identity_assertion() -> None:
    client = make_client()
    response = client.post(
        "/v1/sessions",
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}"},
        json={"display_name": "No identity", "romm_rom_id": 7, "max_players": 2},
    )
    assert response.status_code == 422


def test_v1_api_requires_service_credential() -> None:
    client = make_client()
    assert client.get("/v1/sessions").status_code == 401
    assert client.get("/v1/sessions", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_lifecycle_audit_event_pseudonymizes_actor(caplog: pytest.LogCaptureFixture) -> None:
    client = make_client()
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/v1/sessions",
            headers=headers(1),
            json={"display_name": "Audited Lobby", "romm_rom_id": 7, "max_players": 2},
        )
    assert response.status_code == 201
    records = [record for record in caplog.records if getattr(record, "event", None) == "audit"]
    assert len(records) == 1
    record = records[0]
    assert getattr(record, "action", None) == "session.create"
    assert getattr(record, "outcome", None) == "success"
    actor_id = getattr(record, "actor_id", None)
    assert actor_id != "user-1"
    assert isinstance(actor_id, str) and len(actor_id) == 24
    assert str(getattr(record, "session_id", None)) == response.json()["session_id"]
