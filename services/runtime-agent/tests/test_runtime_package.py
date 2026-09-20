from retro_runtime import __version__


def test_runtime_package_version_is_foundation_version() -> None:
    assert __version__ == "0.1.0"
