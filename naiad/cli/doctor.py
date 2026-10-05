"""Whether this machine can run Naiad, and what to do where it cannot.

One set of checks, each with one severity, used by two callers. `naiad doctor`
runs every one and prints what it found. The entrances run the fail-level ones
and refuse at the first that fails. Two callers over one set, so that an
entrance can never refuse for something the doctor would not have reported, nor
the doctor say all is well of a machine an entrance turns away.

A check is a fact about the machine and never repairs it: what to run is said,
and the operator runs it.

What each severity means:

- fail: Naiad cannot work. A Run started here would die or deliver nothing.
- warn: Naiad works, but something the operator expects to work will not.
- info: something worth knowing, said once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.text import Text

from naiad.adapters.claude_config import default_settings_path, default_skills_root
from naiad.adapters.executable import naiad_command
from naiad.adapters.notify import OSASCRIPT, push_legs
from naiad.adapters.tmux import CLAUDE, TMUX
from naiad.cli.library import LibraryError, resolve_workflow
from naiad.cli.style import Styled, refusal
from naiad.domain.workflow import WorkflowError
from naiad.hooks.settings import installed_hooks
from naiad.runtime.home import default_library_root, naiad_home
from naiad.skills.adopt import SKILL_NAME
from naiad.skills.install import SKILL_FILE

# The release that added `--autocompact`, the newest of the flags Naiad can pass
# to `claude`; every other flag it uses predates it.
CLAUDE_FLOOR = (2, 1, 221)

# Long enough for a `claude` that has to wake up, short enough that a hung one
# cannot make a check hang the command asking.
PROBE_SECONDS = 10.0


class Severity(str, Enum):
    FAIL = "fail"
    WARN = "warn"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    """One thing found: what is so, and what to run about it.

    `why` is what Naiad needs the thing for. Only an entrance says it, because
    someone turned away wants the reason and someone reading the whole report
    does not.
    """

    severity: Severity
    what: str
    fix: str = ""
    why: str = ""


Check = Callable[[], list[Finding]]


def diagnose() -> list[Finding]:
    """Every finding, failures first."""
    return [
        finding
        for check in (*FAIL_CHECKS, *WARN_CHECKS, *INFO_CHECKS)
        for finding in check()
    ]


def first_failure() -> Finding | None:
    """The first fail-level finding, checking no further than it has to."""
    return next(_failures(), None)


def entrance_refusal() -> Styled | None:
    """The one line an entrance refuses with, or None where it may go on: the
    missing thing, why Naiad needs it, the fix, then the doctor.

    `naiad adopt` is an entrance, and an agent reads its refusal, so only the
    `naiad:` is styled, and only a terminal is shown it."""
    failure = first_failure()
    if failure is None:
        return None
    return Styled(
        refusal(f"{failure.what} — {failure.why}; {failure.fix}, then run `naiad doctor`")
    )


def render_report(findings: list[Finding]) -> Styled:
    """One line per finding: its severity, what is so, and what to run.

    The severity is the first word of every line, coloured for how much it
    matters, because a reader — a person scanning, a script gating — finds a
    line by it."""
    return Styled(Text("\n").join(_reported(finding) for finding in findings))


def _reported(finding: Finding) -> Text:
    severity = finding.severity.value
    line = Text.assemble((severity, f"severity.{severity}"), f"  {finding.what}")
    if finding.fix:
        line.append(" — ", style="secondary").append(finding.fix)
    return line


def _failures() -> Iterator[Finding]:
    for check in FAIL_CHECKS:
        yield from check()


# fail


def _tmux_on_path() -> list[Finding]:
    if shutil.which(TMUX):
        return []
    return [
        Finding(
            Severity.FAIL,
            "tmux is not on PATH",
            "install tmux (macOS: brew install tmux)",
            why="naiad runs every Run in a tmux session",
        )
    ]


def _claude_on_path() -> list[Finding]:
    if shutil.which(CLAUDE):
        return []
    return [
        Finding(
            Severity.FAIL,
            "claude is not on PATH",
            "install Claude Code and put claude on PATH",
            why="naiad drives Claude Code sessions, and asks it Questions",
        )
    ]


def _home_writable() -> list[Finding]:
    home = naiad_home()
    # Where a directory would be made: the nearest ancestor that exists.
    nearest = home
    while not nearest.exists() and nearest != nearest.parent:
        nearest = nearest.parent

    fix = f"make {nearest} writable, or point NAIAD_HOME at a directory that is"
    if nearest.is_dir() and os.access(nearest, os.W_OK | os.X_OK):
        return []
    what = (
        f"the Naiad home {home} is not writable"
        if nearest == home
        else f"the Naiad home {home} does not exist and cannot be created"
    )
    return [
        Finding(
            Severity.FAIL,
            what,
            fix,
            why="naiad keeps its Queue, its Runs and its lock there",
        )
    ]


def _hooks() -> list[Finding]:
    """Two facts, present and naming this naiad, told apart because the remedy
    for the second is the same command but the operator's mistake is not: a
    moved naiad looks like an installed one until something fails to run."""
    path = default_settings_path()
    try:
        document = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError) as error:
        return [
            Finding(
                Severity.FAIL,
                f"{path} cannot be read ({error})",
                "repair or remove it, then run `naiad install`",
                why="naiad's hooks live there",
            )
        ]
    if not isinstance(document, dict):
        document = {}

    naiad = naiad_command()
    installed = installed_hooks(document, naiad=naiad)
    findings: list[Finding] = []
    if installed.missing:
        findings.append(
            Finding(
                Severity.FAIL,
                f"naiad's hooks are missing from {path}: {', '.join(installed.missing)}",
                "run `naiad install`",
                why="the hooks are how naiad teaches the Protocol and hears a Turn end",
            )
        )
    if installed.elsewhere:
        findings.append(
            Finding(
                Severity.FAIL,
                f"the hooks in {path} name {', '.join(sorted(_naiads_of(installed.elsewhere)))}, "
                f"not this naiad ({naiad})",
                "run `naiad install`",
                why="the hooks would run a different naiad, or none",
            )
        )
    return findings


def _naiads_of(commands: tuple[str, ...]) -> set[str]:
    return {command.rsplit(" ", 1)[0] for command in commands}


# warn


def _claude_version() -> list[Finding]:
    claude = shutil.which(CLAUDE)
    if claude is None:
        return []  # already a failure, and there is nothing to ask
    floor = ".".join(map(str, CLAUDE_FLOOR))
    found = _version_of(claude)
    if found is None:
        return [
            Finding(
                Severity.WARN,
                f"could not tell which version of claude this is (naiad needs {floor})",
                "run `claude --version`, and `claude update` if it is older",
            )
        ]
    if found < CLAUDE_FLOOR:
        return [
            Finding(
                Severity.WARN,
                f"claude {'.'.join(map(str, found))} is older than {floor}, "
                "which the newest flag naiad can pass needs",
                "run `claude update`",
            )
        ]
    return []


def _version_of(claude: str) -> tuple[int, int, int] | None:
    try:
        finished = subprocess.run(
            [claude, "--version"], capture_output=True, text=True, timeout=PROBE_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    found = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", finished.stdout)
    return None if found is None else (int(found[1]), int(found[2]), int(found[3]))


def _adopt_skill() -> list[Finding]:
    path = default_skills_root() / SKILL_NAME / SKILL_FILE
    if path.is_file():
        return []
    return [
        Finding(
            Severity.WARN,
            f"the adopt skill is missing from {default_skills_root()}",
            "run `naiad install`",
        )
    ]


def _library_entries() -> list[Path]:
    library = default_library_root()
    if not library.is_dir():
        return []
    # Links count whether or not they lead anywhere: a broken one is an entry
    # the operator made, and the thing to report rather than to overlook.
    return sorted(entry for entry in library.glob("*.toml") if entry.is_file() or entry.is_symlink())


def _library_loads() -> list[Finding]:
    findings = []
    for entry in _library_entries():
        try:
            resolve_workflow(entry.stem, library=default_library_root())
        except (LibraryError, WorkflowError, OSError, ValueError) as error:
            findings.append(
                Finding(
                    Severity.WARN,
                    f"the library entry {entry} does not load: {error}",
                    "repair it, or remove it from the library",
                )
            )
    return findings


def _tmux_server_path() -> list[Finding]:
    """A running tmux server hands its own global PATH to every session it
    opens, whatever the shell that ran naiad holds — so a server started before
    claude was installed opens sessions that cannot run it. Skipped where no
    server runs, because then naiad's own one starts from this environment."""
    tmux = shutil.which(TMUX)
    if tmux is None:
        return []
    try:
        finished = subprocess.run(
            [tmux, "show-environment", "-g", "PATH"],
            capture_output=True,
            text=True,
            timeout=PROBE_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    line = finished.stdout.strip()
    if finished.returncode != 0 or not line.startswith("PATH="):
        return []
    directories = line.removeprefix("PATH=").split(os.pathsep)
    if shutil.which(CLAUDE, path=os.pathsep.join(directories)):
        return []
    return [
        Finding(
            Severity.WARN,
            "the running tmux server's PATH does not include claude, "
            "so a session it opens cannot run it",
            'run `tmux set-environment -g PATH "$PATH"`, or `tmux kill-server` and start again',
        )
    ]


# info


def _library_empty() -> list[Finding]:
    if _library_entries():
        return []
    return [
        Finding(
            Severity.INFO,
            f"the library at {default_library_root()} is empty",
            "run `naiad install --starter` for a Workflow to start from",
        )
    ]


def _notification_legs() -> list[Finding]:
    legs = ["terminal"]
    if shutil.which(OSASCRIPT):
        legs.append("desktop")
    if push_legs(os.environ):
        legs.append("push")
    return [Finding(Severity.INFO, f"notifications will fire through: {', '.join(legs)}")]


FAIL_CHECKS: tuple[Check, ...] = (_tmux_on_path, _claude_on_path, _home_writable, _hooks)
WARN_CHECKS: tuple[Check, ...] = (_claude_version, _adopt_skill, _library_loads, _tmux_server_path)
INFO_CHECKS: tuple[Check, ...] = (_library_empty, _notification_legs)

__all__ = [
    "CLAUDE_FLOOR",
    "Finding",
    "Severity",
    "diagnose",
    "entrance_refusal",
    "first_failure",
    "render_report",
]
