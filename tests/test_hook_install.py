"""Installing the hooks into a settings file on disk.

The document itself is covered in tests/test_hook_settings.py; what is pinned
here is that installation reaches a real file without destroying what was in it.
"""

import json

import pytest

from naiad.hooks.install import install_hooks

NAIAD = "/opt/naiad/bin/naiad"


@pytest.fixture
def settings_path(tmp_path):
    return tmp_path / ".claude" / "settings.json"


def read(path):
    return json.loads(path.read_text())


def test_installs_into_a_settings_file_that_does_not_exist_yet(settings_path):
    install_hooks(settings_path=settings_path, naiad=NAIAD)

    assert "SessionStart" in read(settings_path)["hooks"]


def test_leaves_the_operators_other_settings_intact(settings_path):
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"model": "opus"}))

    install_hooks(settings_path=settings_path, naiad=NAIAD)

    assert read(settings_path)["model"] == "opus"


def test_installing_twice_leaves_one_set_of_hooks(settings_path):
    install_hooks(settings_path=settings_path, naiad=NAIAD)
    once = read(settings_path)

    install_hooks(settings_path=settings_path, naiad=NAIAD)

    assert read(settings_path) == once


def test_a_settings_file_that_is_not_valid_json_is_refused_rather_than_overwritten(
    settings_path,
):
    """Overwriting it would silently discard the operator's whole configuration
    to install two hooks."""
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{ not json")

    with pytest.raises(ValueError):
        install_hooks(settings_path=settings_path, naiad=NAIAD)

    assert settings_path.read_text() == "{ not json"


def test_installation_never_touches_the_target_repository(tmp_path, settings_path):
    """Naiad writes nothing into the repository it is driving, and hooks are
    installed independently of any Run."""
    repo = tmp_path / "repo"
    repo.mkdir()

    install_hooks(settings_path=settings_path, naiad=NAIAD)

    assert list(repo.rglob("*")) == []
