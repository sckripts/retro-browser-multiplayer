from collections.abc import Iterable

from retro_sessions.models import CoreProfile, GameRecord


class StaticRomMProvider:
    """Milestone 8 trusted single-game harness; replaced by RomM integration later."""

    def __init__(self, game: GameRecord) -> None:
        self._game = game

    def resolve_game(self, romm_rom_id: int) -> GameRecord:
        if romm_rom_id != self._game.romm_rom_id:
            raise KeyError(romm_rom_id)
        return self._game

    def health(self) -> bool:
        return True


class StaticCoreRegistry:
    """Server-owned core profiles selected only by trusted platform metadata."""

    def __init__(self, profiles: CoreProfile | Iterable[CoreProfile]) -> None:
        items = (profiles,) if isinstance(profiles, CoreProfile) else tuple(profiles)
        self._profiles: dict[str, CoreProfile] = {}
        for profile in items:
            if profile.platform in self._profiles:
                raise ValueError(f"duplicate core platform: {profile.platform}")
            self._profiles[profile.platform] = profile
        if not self._profiles:
            raise ValueError("at least one core profile is required")

    def resolve(self, platform: str) -> CoreProfile:
        return self._profiles[platform]

    def health(self) -> bool:
        return True
