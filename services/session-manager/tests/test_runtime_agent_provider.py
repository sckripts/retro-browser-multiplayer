from typing import Any
from uuid import UUID

from pydantic import SecretStr
from retro_sessions.providers import RuntimeHandle, RuntimeRequest
from retro_sessions.providers.execution import (
    LocalRuntimeAgentProvider,
    RuntimeAgentProviderConfig,
)

IMAGE = "retrobrowser/retro-session@sha256:" + "a" * 64
SESSION_ID = UUID("80000000-0000-4000-8000-000000000008")
HOST_ID = UUID("80000000-0000-4000-8000-000000000001")
CLIENT_ID = UUID("80000000-0000-4000-8000-000000000002")


class FakeRequester:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def __call__(
        self, method: str, path: str, payload: dict[str, object] | None
    ) -> tuple[int, object]:
        self.calls.append((method, path, payload))
        return 201, {
            "participant_id": str(CLIENT_ID),
            "state": "running",
            "health_status": "healthy",
        }


def make_provider(requester: FakeRequester) -> LocalRuntimeAgentProvider:
    return LocalRuntimeAgentProvider(
        RuntimeAgentProviderConfig(
            image=IMAGE,
            stream_network="retrobrowser-m8-stream",
            netplay_network="retrobrowser-m8-retro-net",
            orchestration_secret=SecretStr("s" * 32),
        ),
        requester=requester,
    )


def test_client_request_derives_private_host_and_server_only_token() -> None:
    requester = FakeRequester()
    provider = make_provider(requester)
    request = RuntimeRequest(
        session_id=SESSION_ID,
        participant_id=CLIENT_ID,
        user_id="user-2",
        player_name="Player 2",
        rom_path="/srv/retrobrowser/roms/game.nes",
        rom_sha256="b" * 64,
        core_profile="nes-milestone2",
        role="client",
        host_participant_id=HOST_ID,
    )

    first = provider.create(request)
    second = provider.create(request)

    assert first == second
    first_payload = requester.calls[0][2]
    second_payload = requester.calls[1][2]
    assert first_payload is not None and second_payload is not None
    netplay = first_payload["netplay"]
    assert isinstance(netplay, dict)
    assert netplay["host"] == f"retrobrowser-runtime-{HOST_ID.hex}"
    assert first_payload["stream_subfolder"] == f"/stream/{CLIENT_ID.hex}"
    assert first_payload["selkies_master_token"] == second_payload["selkies_master_token"]

    public_shape: dict[str, Any] = first.model_dump(mode="json")
    assert "host" not in public_shape
    assert "token" not in str(public_shape).lower()


def test_remove_is_idempotent_when_agent_reports_missing_runtime() -> None:
    def missing(_method: str, _path: str, _payload: dict[str, object] | None) -> tuple[int, object]:
        return 404, {"error": "not found"}

    provider = LocalRuntimeAgentProvider(
        RuntimeAgentProviderConfig(
            image=IMAGE,
            stream_network="retrobrowser-m8-stream",
            netplay_network="retrobrowser-m8-retro-net",
            orchestration_secret=SecretStr("s" * 32),
        ),
        requester=missing,
    )

    provider.remove(CLIENT_ID)


def test_list_parses_only_provider_neutral_runtime_state() -> None:
    def listed(_method: str, _path: str, _payload: dict[str, object] | None) -> tuple[int, object]:
        return 200, {
            "items": [
                {
                    "participant_id": str(HOST_ID),
                    "container_id": "secret-engine-id",
                    "container_name": "retrobrowser-runtime-secret",
                    "state": "running",
                    "health_status": "healthy",
                    "stream_subfolder": f"/stream/{HOST_ID.hex}",
                    "orphaned": False,
                }
            ]
        }

    provider = LocalRuntimeAgentProvider(
        RuntimeAgentProviderConfig(
            image=IMAGE,
            stream_network="retrobrowser-m8-stream",
            netplay_network="retrobrowser-m8-retro-net",
            orchestration_secret=SecretStr("s" * 32),
        ),
        requester=listed,
    )

    assert provider.list() == [
        RuntimeHandle(
            runtime_id=HOST_ID,
            state="running",
            health_status="healthy",
        )
    ]
