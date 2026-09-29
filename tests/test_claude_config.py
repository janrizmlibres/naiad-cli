"""Where Naiad installs into Claude Code's configuration: the directory Claude
Code itself reads, which `CLAUDE_CONFIG_DIR` moves.

One function computes it, so the hooks and the skill cannot disagree about
which configuration they mean.
"""

from pathlib import Path

from naiad.adapters.claude_config import (
    claude_config_dir,
    default_settings_path,
    default_skills_root,
)


def test_with_the_variable_set_the_configuration_is_where_it_points(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))

    assert claude_config_dir() == tmp_path / "elsewhere"
    assert default_settings_path() == tmp_path / "elsewhere" / "settings.json"
    assert default_skills_root() == tmp_path / "elsewhere" / "skills"


def test_unset_the_configuration_is_dot_claude_in_the_home_directory(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    assert claude_config_dir() == Path.home() / ".claude"
    assert default_settings_path() == Path.home() / ".claude" / "settings.json"
    assert default_skills_root() == Path.home() / ".claude" / "skills"


def test_an_empty_variable_is_no_override(monkeypatch):
    """A shell that exported it empty means to have unset it, and a relative
    path of nothing would be the working directory."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")

    assert claude_config_dir() == Path.home() / ".claude"
