import json
from pathlib import Path
from uuid import UUID

from retro_runtime.observability import MetricsTargetProvider


def test_metrics_target_is_atomic_scoped_and_removable(tmp_path: Path) -> None:
    participant_id = UUID("60000000-0000-4000-8000-000000000001")
    session_id = UUID("60000000-0000-4000-8000-000000000006")
    provider = MetricsTargetProvider(tmp_path)

    provider.publish(
        participant_id,
        session_id,
        "nes-milestone2",
        "/stream/player-one",
        "retrobrowser-runtime-safe",
        "m" * 64,
    )

    path = tmp_path / f"runtime-{participant_id}.json"
    target = json.loads(path.read_text(encoding="utf-8"))[0]
    assert target["targets"] == ["retrobrowser-runtime-safe:9091"]
    assert target["labels"]["session_id"] == str(session_id)
    assert target["labels"]["__metrics_path__"] == "/metrics"
    assert target["labels"]["__param_token"] == "m" * 64
    assert not list(tmp_path.glob("*.tmp"))
    assert provider.list_participants() == {participant_id}

    provider.remove(participant_id)
    assert not path.exists()
