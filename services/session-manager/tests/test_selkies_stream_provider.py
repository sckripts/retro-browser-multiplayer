import hashlib
import hmac
from uuid import UUID

import pytest
from pydantic import SecretStr
from retro_sessions.errors import OrchestrationError
from retro_sessions.providers.streaming import SelkiesStreamProvider, SelkiesStreamProviderConfig

PARTICIPANT_ID = UUID("90000000-0000-4000-8000-000000000009")
SECRET = "s" * 32


class FakeRequester:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[tuple[str, str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        authority: str,
        path: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> int:
        self.calls.append((authority, path, headers, payload))
        return self.status


def make_provider(requester: FakeRequester) -> SelkiesStreamProvider:
    return SelkiesStreamProvider(
        SelkiesStreamProviderConfig(orchestration_secret=SecretStr(SECRET)),
        requester=requester,
    )


def test_provision_uses_private_runtime_api_and_scoped_controller_token() -> None:
    requester = FakeRequester()
    provider = make_provider(requester)

    first = provider.provision(PARTICIPANT_ID, gamepad_slot=1)
    second = provider.provision(PARTICIPANT_ID, gamepad_slot=1)

    assert first == second
    authority, path, headers, payload = requester.calls[0]
    expected_master = hmac.new(SECRET.encode(), PARTICIPANT_ID.bytes, hashlib.sha256).hexdigest()
    assert authority == f"retrobrowser-runtime-{PARTICIPANT_ID.hex}:8080"
    assert path == f"/stream/{PARTICIPANT_ID.hex}/api/tokens"
    assert headers["Authorization"] == f"Bearer {expected_master}"
    assert payload == {first: {"role": "controller", "slot": 1, "mk_control": True}}
    assert first != expected_master


def test_revoke_replaces_the_entire_token_table_with_empty_object() -> None:
    requester = FakeRequester()
    provider = make_provider(requester)
    provider.revoke(PARTICIPANT_ID)
    assert requester.calls[0][3] == {}


def test_bad_status_and_slot_are_rejected_without_exposing_credentials() -> None:
    requester = FakeRequester(status=401)
    provider = make_provider(requester)
    with pytest.raises(OrchestrationError, match="HTTP 401") as raised:
        provider.provision(PARTICIPANT_ID, gamepad_slot=1)
    assert SECRET not in str(raised.value)
    with pytest.raises(ValueError, match="slot"):
        provider.provision(PARTICIPANT_ID, gamepad_slot=5)


def test_public_provider_shape_contains_no_secret() -> None:
    provider = make_provider(FakeRequester())
    rendered = str(provider.config.orchestration_secret)
    assert rendered
    assert set(rendered) == {"*"}
    assert SECRET not in repr(provider.config)
