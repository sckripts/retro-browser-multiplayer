from pathlib import Path
from uuid import UUID

import yaml
from retro_runtime.routes import FileRouteProvider


def test_file_route_provider_publishes_and_removes_atomic_route(tmp_path: Path) -> None:
    participant_id = UUID("60000000-0000-4000-8000-000000000001")
    provider = FileRouteProvider(tmp_path)

    provider.publish(participant_id, "/stream/player-one", "retrobrowser-runtime-safe")

    route_path = tmp_path / f"runtime-{participant_id}.yml"
    route = yaml.safe_load(route_path.read_text(encoding="utf-8"))
    router = route["http"]["routers"][f"runtime-{participant_id}"]
    service = route["http"]["services"][f"runtime-{participant_id}"]
    assert router["rule"] == "PathPrefix(`/stream/player-one`)"
    assert service["loadBalancer"]["servers"] == [{"url": "http://retrobrowser-runtime-safe:8080"}]
    assert not list(tmp_path.glob("*.tmp"))
    assert provider.exists(participant_id)

    provider.remove(participant_id)

    assert not provider.exists(participant_id)


def test_file_route_provider_scopes_public_route_to_host(tmp_path: Path) -> None:
    participant_id = UUID("60000000-0000-4000-8000-000000000001")
    provider = FileRouteProvider(tmp_path, host="arcade.example.test")

    provider.publish(participant_id, "/stream/player-one", "retrobrowser-runtime-safe")

    route = yaml.safe_load((tmp_path / f"runtime-{participant_id}.yml").read_text(encoding="utf-8"))
    assert route["http"]["routers"][f"runtime-{participant_id}"]["rule"] == (
        "Host(`arcade.example.test`) && PathPrefix(`/stream/player-one`)"
    )
