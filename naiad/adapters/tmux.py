"""Opening a tmux session. Turns a SessionSpec into commands and runs them;
every rule in the spec was decided in naiad.domain.session (ADR 0004).

Naiad never reads the Claude Code terminal UI (ADR 0002): nothing here captures
a pane or matches against what the TUI is showing. The session's first Prompt
is handed to Claude Code as it starts, so there is nothing to wait for and
nothing to watch.
"""

from __future__ import annotations

import subprocess

from naiad.domain.session import SessionSpec

TMUX = "tmux"
CLAUDE = "claude"


class TmuxError(Exception):
    pass


class TmuxSessions:
    def spawn(self, spec: SessionSpec) -> str:
        """Open the session detached and report back the pane it lives in, so
        the Run can later be resolved from its pane."""
        return self._run(_new_session_argv(spec)).strip()

    def _run(self, argv: list[str]) -> str:
        finished = subprocess.run(argv, capture_output=True, text=True)
        if finished.returncode != 0:
            raise TmuxError(f"{' '.join(argv)} failed: {(finished.stderr or '').strip()}")
        return finished.stdout


def _new_session_argv(spec: SessionSpec) -> list[str]:
    argv = [TMUX, "new-session", "-d", "-s", spec.name, "-c", str(spec.cwd)]
    for key, value in spec.environ.items():
        argv += ["-e", f"{key}={value}"]
    argv += ["-P", "-F", "#{pane_id}"]
    return argv + _claude_argv(spec)


def _claude_argv(spec: SessionSpec) -> list[str]:
    argv = [
        CLAUDE,
        "--permission-mode",
        spec.permission_mode,
        "--session-id",
        spec.claude_session_id,
    ]
    if spec.initial_prompt is not None:
        argv.append(spec.initial_prompt)
    return argv


def command_for(spec: SessionSpec) -> list[str]:
    """Exposed so the command a spec produces can be asserted without opening a
    session — the permission mode in particular."""
    return _new_session_argv(spec)


__all__ = ["TmuxError", "TmuxSessions", "command_for"]
