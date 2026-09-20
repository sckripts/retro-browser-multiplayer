from retro_sessions import __version__


def test_session_package_version_is_milestone_seven_version() -> None:
    assert __version__ == "0.1.0"
