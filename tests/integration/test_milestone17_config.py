from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE_PATH = ROOT / "infra/compose/acceptance/compose.milestone17.yml"
DOCKERFILE = (ROOT / "images/retro-session/Dockerfile").read_text(encoding="utf-8")
RETROARCH_CONFIG = (ROOT / "images/retro-session/config/retroarch.cfg").read_text(encoding="utf-8")
RETROARCH_RUN = (ROOT / "images/retro-session/entrypoint/run").read_text(encoding="utf-8")
SAVE_FLUSHER = (ROOT / "images/retro-session/entrypoint/save-flusher-run").read_text(
    encoding="utf-8"
)


def test_milestone17_extends_public_stack_with_private_save_root() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert compose["name"] == "retro-browser-milestone14"
    assert set(compose["services"]) == {"runtime-agent", "session-manager", "network-anchor"}
    agent = compose["services"]["runtime-agent"]
    assert agent["environment"]["RUNTIME_AGENT_SAVE_DATA_ROOT"] == "/srv/retrobrowser/saves"
    assert agent["volumes"] == [
        {
            "type": "bind",
            "source": "${M17_DOCKER_SAVE_ROOT:?set in .env.milestone14}",
            "target": "/srv/retrobrowser/saves",
        }
    ]
    assert "ports" not in str(compose)
    assert "docker.sock" not in str(compose)


def test_milestone17_helpers_and_policy_runbook_exist() -> None:
    for name in ["milestone17-start.ps1", "milestone17-verify.ps1", "milestone17-stop.ps1"]:
        assert (ROOT / "infra/scripts/acceptance" / name).is_file()
    runbook = (ROOT / "docs/milestone-17-persistence.md").read_text(encoding="utf-8")
    for phrase in [
        "host's save is authoritative",
        "exactly one managed runtime",
        "Save states are session-ephemeral",
        "preferences",
        "RequirePersistentHost",
    ]:
        assert phrase in runbook


def test_milestone17_start_requires_clean_upgrade_and_ignored_save_root() -> None:
    start = (ROOT / "infra/scripts/acceptance/milestone17-start.ps1").read_text(encoding="utf-8")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "Close active lobbies before enabling persistence" in start
    assert '"local/runtime-agent-m17/saves"' in start
    assert "local/runtime-agent-m17/" in ignore


def test_netplay_save_flush_uses_private_main_thread_command_fifo() -> None:
    assert 'stdin_cmd_enable = "true"' in RETROARCH_CONFIG
    assert 'network_cmd_enable = "false"' in RETROARCH_CONFIG
    assert "readonly COMMAND_PIPE=/tmp/retroarch-command" in RETROARCH_RUN
    assert 'mkfifo -m 0600 "${COMMAND_PIPE}"' in RETROARCH_RUN
    assert "SAVE_FILES\\n" in SAVE_FLUSHER
    assert "sleep 10" in SAVE_FLUSHER
    assert "/etc/service/save-flusher/run" in DOCKERFILE
