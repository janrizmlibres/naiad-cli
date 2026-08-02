"""Installing the adopt skill into a skills directory on disk.

The document itself is covered in tests/test_adopt_skill.py; what is pinned
here is that installation reaches a real file without disturbing anything else
of the operator's configuration.
"""

import pytest

from naiad.skills.adopt import SKILL_NAME
from naiad.skills.install import install_adopt_skill

NAIAD = "/opt/naiad/bin/naiad"


@pytest.fixture
def skills_root(tmp_path):
    return tmp_path / ".claude" / "skills"


def test_installs_into_a_skills_directory_that_does_not_exist_yet(skills_root):
    path = install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert path == skills_root / SKILL_NAME / "SKILL.md"
    assert f"name: {SKILL_NAME}" in path.read_text()


def test_installing_twice_leaves_one_copy(skills_root):
    install_adopt_skill(skills_root=skills_root, naiad=NAIAD)
    once = (skills_root / SKILL_NAME / "SKILL.md").read_text()

    install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert [path.name for path in (skills_root / SKILL_NAME).iterdir()] == ["SKILL.md"]
    assert (skills_root / SKILL_NAME / "SKILL.md").read_text() == once


def test_an_earlier_naiad_installed_copy_is_replaced(skills_root):
    """The contract is Naiad's, so a copy an older naiad wrote is stale rather
    than the operator's work."""
    stale = install_adopt_skill(skills_root=skills_root, naiad="/old/naiad")

    install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert "/old/naiad" not in stale.read_text()
    assert NAIAD in stale.read_text()


def test_leaves_the_operators_other_skills_alone(skills_root):
    theirs = skills_root / "grilling" / "SKILL.md"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("their own skill\n")

    install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert theirs.read_text() == "their own skill\n"


def test_a_skill_of_the_same_name_that_naiad_did_not_write_is_refused(skills_root):
    """Overwriting it would discard a skill the operator wrote by hand in order
    to install one they can reinstall at any time."""
    theirs = skills_root / SKILL_NAME / "SKILL.md"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("my own adopt notes\n")

    with pytest.raises(ValueError):
        install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert theirs.read_text() == "my own adopt notes\n"


def test_installation_never_touches_the_target_repository(tmp_path, skills_root):
    """Naiad writes nothing into the repository it is driving, and the skill is
    installed independently of any Run."""
    repo = tmp_path / "repo"
    repo.mkdir()

    install_adopt_skill(skills_root=skills_root, naiad=NAIAD)

    assert list(repo.rglob("*")) == []
