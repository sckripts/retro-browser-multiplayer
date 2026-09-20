from pathlib import Path

import pytest
from pydantic import SecretStr
from retro_sessions.errors import OrchestrationError
from retro_sessions.providers.romm import HttpRomMProvider, HttpRomMProviderConfig


class FakeRequester:
    def __init__(self, document: object, status: int = 200) -> None:
        self.document = document
        self.status = status
        self.paths: list[str] = []

    def __call__(self, path: str) -> tuple[int, object]:
        self.paths.append(path)
        return self.status, self.document


def make_provider(root: Path, requester: FakeRequester) -> HttpRomMProvider:
    return HttpRomMProvider(
        HttpRomMProviderConfig(
            api_url="http://romm:8080/api/",
            service_token=SecretStr("s" * 32),
            rom_root=root,
        ),
        requester=requester,
    )


def test_resolve_maps_only_relative_path_below_approved_root(tmp_path: Path) -> None:
    game = tmp_path / "nes" / "roms" / "game.nes"
    game.parent.mkdir(parents=True)
    game.write_bytes(b"legal test fixture")
    requester = FakeRequester(
        {
            "romm_rom_id": 42,
            "platform": "nes",
            "relative_path": "nes/roms/game.nes",
            "rom_sha256": "a" * 64,
        }
    )

    record = make_provider(tmp_path, requester).resolve_game(42)

    assert record.canonical_path == str(game.resolve())
    assert record.platform == "nes"
    assert requester.paths == ["/multiplayer/games/42"]


@pytest.mark.parametrize("relative_path", ["../game.nes", "/game.nes"])
def test_resolve_rejects_unsafe_paths(tmp_path: Path, relative_path: str) -> None:
    requester = FakeRequester(
        {
            "romm_rom_id": 42,
            "platform": "nes",
            "relative_path": relative_path,
            "rom_sha256": "a" * 64,
        }
    )

    with pytest.raises(OrchestrationError, match="unsafe game path"):
        make_provider(tmp_path, requester).resolve_game(42)


def test_resolve_translates_not_found() -> None:
    requester = FakeRequester({"detail": "not found"}, status=404)

    with pytest.raises(KeyError):
        make_provider(Path("."), requester).resolve_game(9)


def test_health_is_fail_closed() -> None:
    requester = FakeRequester({"ready": True})
    provider = make_provider(Path("."), requester)

    assert provider.health() is True
    requester.document = {"ready": False}
    assert provider.health() is False
