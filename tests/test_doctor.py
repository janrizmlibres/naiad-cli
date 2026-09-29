"""What `naiad doctor` reports, and what each entrance refuses for.

One set of checks with one severity each, used by two callers: the doctor
prints every finding and repairs nothing, and the entrances stop at the first
failure. The machine is the environment the checks read — `PATH`, `NAIAD_HOME`,
`CLAUDE_CONFIG_DIR` — so each test builds one from fake `tmux` and `claude`
scripts on a directory of its own and breaks a single thing about it.
"""

import io
import json

import pytest

from fake_machine import (
    install_claude,
    install_healthy,
    install_osascript,
    install_tmux,
)
from naiad.adapters.claude_config import default_settings_path
from naiad.cli.doctor import Severity, diagnose, entrance_refusal, first_failure, render_report
from naiad.cli.main import main
from naiad.hooks.install import install_hooks
from naiad.runtime.home import naiad_home
from naiad.skills.install import install_adopt_skill


THIS_NAIAD = "/opt/naiad-test/bin/naiad"


@pytest.fixture(autouse=True)
def running_as_naiad(monkeypatch):
    """Under pytest argv[0] is pytest, which is not a name the hooks recognise
    as naiad's; a real one is always a path ending in `naiad`."""
    monkeypatch.setattr("sys.argv", [THIS_NAIAD])


@pytest.fixture
def bin_dir(monkeypatch, tmp_path):
    """The only directory on PATH, holding a working tmux and claude."""
    directory = tmp_path / "bin"
    install_healthy(directory)
    monkeypatch.setenv("PATH", str(directory))
    monkeypatch.delenv("NAIAD_NTFY_URL", raising=False)
    return directory


@pytest.fixture
def healthy(bin_dir):
    """A machine with everything installed: hooks naming this naiad, the skill."""
    install_hooks()
    install_adopt_skill()
    return bin_dir


def of(severity, findings=None):
    findings = diagnose() if findings is None else findings
    return [finding for finding in findings if finding.severity is severity]


def said(severity):
    return " | ".join(f"{f.what} {f.fix}" for f in of(severity))


def test_a_healthy_machine_has_nothing_to_fail_or_warn_about(healthy):
    findings = diagnose()

    assert of(Severity.FAIL, findings) == []
    assert of(Severity.WARN, findings) == []
    assert first_failure() is None
    assert entrance_refusal() is None


# fail


def test_a_missing_tmux_fails_with_the_fix(healthy):
    (healthy / "tmux").unlink()

    assert "tmux" in said(Severity.FAIL)
    assert first_failure().what.startswith("tmux")


def test_a_missing_claude_fails_with_the_fix(healthy):
    (healthy / "claude").unlink()

    assert "claude" in said(Severity.FAIL)


def test_a_naiad_home_that_cannot_be_written_fails(healthy, monkeypatch, tmp_path):
    home = tmp_path / "readonly-home"
    home.mkdir()
    home.chmod(0o500)
    monkeypatch.setenv("NAIAD_HOME", str(home))

    try:
        assert "NAIAD_HOME" in said(Severity.FAIL)
        assert str(home) in said(Severity.FAIL)
    finally:
        home.chmod(0o700)


def test_a_naiad_home_that_cannot_be_created_fails(healthy, monkeypatch, tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("")
    monkeypatch.setenv("NAIAD_HOME", str(blocker / "naiad"))

    assert "NAIAD_HOME" in said(Severity.FAIL)


def test_a_naiad_home_that_does_not_exist_yet_is_fine_where_it_can_be_created(
    healthy, monkeypatch, tmp_path
):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "not" / "yet" / "there"))

    assert of(Severity.FAIL) == []


def test_missing_hooks_fail_and_name_naiad_install(bin_dir):
    install_adopt_skill()

    failures = of(Severity.FAIL)

    assert len(failures) == 1
    assert "hooks" in failures[0].what
    assert "naiad install" in failures[0].fix


def test_a_settings_file_missing_only_one_hook_fails(healthy):
    settings = default_settings_path()
    document = json.loads(settings.read_text())
    del document["hooks"]["Stop"]
    settings.write_text(json.dumps(document))

    assert "Stop" in said(Severity.FAIL)


def test_hooks_naming_another_naiad_fail(bin_dir):
    install_hooks(naiad="/old/venv/bin/naiad")
    install_adopt_skill()

    failures = of(Severity.FAIL)

    assert len(failures) == 1
    assert "/old/venv/bin/naiad" in failures[0].what
    assert THIS_NAIAD in failures[0].what
    assert "naiad install" in failures[0].fix


def test_a_settings_file_that_does_not_parse_fails_naming_the_file(healthy):
    default_settings_path().write_text("{ not json")

    assert str(default_settings_path()) in said(Severity.FAIL)


def test_the_settings_file_follows_claude_config_dir(healthy, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "second-account"))

    assert str(tmp_path / "second-account") in said(Severity.FAIL)


# warn


@pytest.mark.parametrize(
    ("says", "warns"),
    [
        ("2.1.220 (Claude Code)", True),
        ("2.0.999 (Claude Code)", True),
        ("2.1.221 (Claude Code)", False),
        ("2.1.284 (Claude Code)", False),
        ("3.0.0 (Claude Code)", False),
    ],
)
def test_a_claude_below_the_floor_warns_and_at_or_above_it_says_nothing(healthy, says, warns):
    install_claude(healthy, says=says)

    warnings = of(Severity.WARN)

    assert bool(warnings) is warns
    if warns:
        assert "2.1.221" in warnings[0].what
        assert says.split()[0] in warnings[0].what


@pytest.mark.parametrize("says", ["banana", "", None])
def test_a_claude_whose_version_cannot_be_read_warns_could_not_tell(healthy, says):
    install_claude(healthy, says=says)

    assert "could not tell" in said(Severity.WARN)


def test_a_missing_claude_does_not_also_warn_about_its_version(healthy):
    (healthy / "claude").unlink()

    assert of(Severity.WARN) == []


def test_a_missing_adopt_skill_warns_with_the_fix(bin_dir):
    install_hooks()

    warnings = of(Severity.WARN)

    assert len(warnings) == 1
    assert "adopt skill" in warnings[0].what
    assert "naiad install" in warnings[0].fix


def _library():
    library = naiad_home() / "workflows"
    library.mkdir(parents=True, exist_ok=True)
    return library


GOOD = 'name = "{name}"\n[[states]]\nname = "done"\nterminal = true\n'


def test_a_library_entry_that_does_not_load_warns_naming_the_file(healthy):
    library = _library()
    (library / "fine.toml").write_text(GOOD.format(name="fine"))
    (library / "broken.toml").write_text("this is [not toml")

    warnings = of(Severity.WARN)

    assert len(warnings) == 1
    assert str(library / "broken.toml") in warnings[0].what
    assert "fine.toml" not in warnings[0].what


def test_a_broken_link_in_the_library_warns_naming_the_file(healthy, tmp_path):
    library = _library()
    (library / "gone.toml").symlink_to(tmp_path / "nowhere.toml")

    assert str(library / "gone.toml") in said(Severity.WARN)


def test_a_misfiled_library_entry_warns_naming_the_file(healthy):
    library = _library()
    (library / "one.toml").write_text(GOOD.format(name="another"))

    assert str(library / "one.toml") in said(Severity.WARN)


def test_a_tmux_server_whose_path_lacks_claude_warns(healthy, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    install_tmux(healthy, server_path=str(elsewhere))

    warnings = of(Severity.WARN)

    assert len(warnings) == 1
    assert "tmux server" in warnings[0].what
    assert "claude" in warnings[0].what


def test_a_tmux_server_whose_path_holds_claude_says_nothing(healthy):
    install_tmux(healthy, server_path=str(healthy))

    assert of(Severity.WARN) == []


def test_no_running_tmux_server_says_nothing_about_its_path(healthy):
    assert of(Severity.WARN) == []


def test_the_tmux_server_path_is_not_an_entrance_check(healthy, tmp_path):
    install_tmux(healthy, server_path=str(tmp_path))

    assert entrance_refusal() is None


# info


def test_an_empty_library_is_reported_pointing_at_the_starter(healthy):
    infos = of(Severity.INFO)

    assert any("naiad install --starter" in f.fix and "library" in f.what for f in infos)


def test_a_missing_library_is_as_empty_as_an_empty_one(healthy):
    assert not (naiad_home() / "workflows").exists()

    assert any("library" in f.what for f in of(Severity.INFO))


def test_a_library_holding_a_workflow_is_not_reported_empty(healthy):
    (_library() / "mine.toml").write_text(GOOD.format(name="mine"))

    assert not any("library" in f.what for f in of(Severity.INFO))


def _legs():
    (line,) = [f.what for f in of(Severity.INFO) if "notif" in f.what]
    return line


def test_the_terminal_is_always_a_notification_leg(healthy):
    assert "terminal" in _legs()
    assert "desktop" not in _legs()
    assert "push" not in _legs()


def test_the_desktop_leg_fires_where_osascript_exists(healthy):
    install_osascript(healthy)

    assert "desktop" in _legs()


def test_the_push_leg_fires_when_the_ntfy_url_is_set(healthy, monkeypatch):
    monkeypatch.setenv("NAIAD_NTFY_URL", "https://ntfy.sh/some-topic")

    assert "push" in _legs()


def test_an_empty_ntfy_url_turns_no_push_leg_on(healthy, monkeypatch):
    monkeypatch.setenv("NAIAD_NTFY_URL", "")

    assert "push" not in _legs()


# the report and the command


def test_the_report_is_one_line_per_finding_with_its_severity(healthy):
    (healthy / "tmux").unlink()
    findings = diagnose()

    lines = render_report(findings).splitlines()

    assert len(lines) == len(findings)
    assert lines[0].startswith("fail")
    assert all(line.split()[0] in {"fail", "warn", "info"} for line in lines)


def test_failures_are_reported_before_warnings_before_info(healthy):
    (healthy / "tmux").unlink()
    install_claude(healthy, says="1.0.0 (Claude Code)")

    order = [f.severity for f in diagnose()]

    assert order == sorted(order, key=[Severity.FAIL, Severity.WARN, Severity.INFO].index)


def test_doctor_exits_zero_when_nothing_fails_even_with_warnings(bin_dir, capsys):
    install_hooks()  # no skill: a warning

    assert main(["doctor"]) == 0
    assert "warn" in capsys.readouterr().out


def test_doctor_exits_one_when_a_check_fails(bin_dir, capsys):
    assert main(["doctor"]) == 1
    assert capsys.readouterr().out.startswith("fail")


def test_doctor_prints_to_stdout_and_repairs_nothing(bin_dir, capsys):
    main(["doctor"])

    assert not default_settings_path().exists()
    assert not naiad_home().exists()
    assert capsys.readouterr().err == ""


# the entrances


@pytest.fixture
def real_entrances(monkeypatch):
    """The suite stubs the entrance check so that every other test meets a
    ready machine; these tests are about the check itself."""
    monkeypatch.setattr("naiad.cli.main.entrance_refusal", entrance_refusal)


WORKFLOW = 'name = "w"\n[[states]]\nname = "a"\nprompt = "/x {task}"\n' + (
    '[[states]]\nname = "done"\nterminal = true\n'
)

ENTRANCES = [
    ["run", "{workflow}", "a task"],
    ["watch"],
    ["adopt", "{workflow}", "--task", "a task"],
    ["queue", "watch"],
]


@pytest.mark.parametrize("entrance", ENTRANCES, ids=lambda e: " ".join(e[:2]))
def test_each_entrance_refuses_when_tmux_is_missing(
    healthy, real_entrances, entrance, tmp_path, monkeypatch, capsys
):
    (healthy / "tmux").unlink()
    monkeypatch.setenv("TMUX_PANE", "%1")
    workflow = tmp_path / "w.toml"
    workflow.write_text(WORKFLOW)

    code = main([part.format(workflow=workflow) for part in entrance])

    err = capsys.readouterr().err
    assert code == 2
    assert len(err.strip().splitlines()) == 1
    assert "tmux" in err
    assert "naiad doctor" in err


def test_the_refusal_says_the_thing_why_it_is_needed_the_fix_and_then_doctor(healthy):
    (healthy / "tmux").unlink()

    refusal = entrance_refusal()

    assert refusal.startswith("naiad: tmux is not on PATH")
    assert "tmux session" in refusal
    assert "install tmux" in refusal
    assert refusal.endswith("then run `naiad doctor`")
    assert "\n" not in refusal


def test_an_entrance_stops_at_the_first_failure(bin_dir):
    (bin_dir / "tmux").unlink()
    (bin_dir / "claude").unlink()

    refusal = entrance_refusal()

    assert "tmux" in refusal
    assert "claude" not in refusal.replace("Claude Code", "")


def test_an_entrance_does_not_refuse_for_a_warning(healthy):
    install_claude(healthy, says="1.0.0 (Claude Code)")

    assert entrance_refusal() is None


def test_queue_add_never_checks(real_entrances, bin_dir, tmp_path, capsys):
    (bin_dir / "tmux").unlink()
    workflow = tmp_path / "w.toml"
    workflow.write_text(WORKFLOW)
    repo = tmp_path / "repo"
    repo.mkdir()

    code = main(["queue", "add", str(workflow), "a task", "--repo", str(repo)])

    assert code == 0, capsys.readouterr().err


@pytest.mark.parametrize(
    "verb",
    [
        ["stopped"],
        ["submitted"],
        ["protocol"],
        ["announce", "done"],
        ["ask", "which?", "--option", "a"],
        ["wait", "a build", "--seconds", "5"],
        ["hold", "the human said stop"],
        ["branch", "some-branch"],
    ],
    ids=lambda verb: verb[0],
)
def test_the_hook_and_protocol_verbs_never_check(real_entrances, bin_dir, verb, monkeypatch, capsys):
    """They may fail for having no Run to speak to; what they never do is turn
    the agent or Claude Code away for the machine's sake."""
    (bin_dir / "tmux").unlink()
    monkeypatch.delenv("NAIAD_RUN_ID", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    main(verb)

    assert "naiad doctor" not in capsys.readouterr().err


# install


def test_install_ends_by_printing_the_report_after_its_own_lines(bin_dir, capsys):
    (bin_dir / "claude").unlink()

    code = main(["install"])

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines[0].startswith("installed naiad's hooks")
    assert lines[1].startswith("installed the adopt skill")
    assert any(line.startswith("fail") and "claude" in line for line in lines[2:])


def test_install_keeps_its_own_exit_code_whatever_the_report_says(bin_dir, capsys):
    (bin_dir / "claude").unlink()

    assert main(["install"]) == 0


def test_a_failed_install_still_prints_the_report_and_exits_two(bin_dir, capsys):
    default_settings_path().parent.mkdir(parents=True)
    default_settings_path().write_text("{ not json")

    code = main(["install"])

    captured = capsys.readouterr()
    assert code == 2
    assert "not valid JSON" in captured.err
    assert "fail" in captured.out
