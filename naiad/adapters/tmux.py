"""Opening a tmux session. Turns a SessionSpec into commands and runs them;
every rule in the spec was decided in naiad.domain.session (ADR 0004).

Naiad never reads the Claude Code terminal UI (ADR 0002): nothing here captures
a pane or matches against what the TUI is showing. The session's first Prompt
is handed to Claude Code as it starts, so there is nothing to wait for and
nothing to watch.
"""

from __future__ import annotations

import subprocess
import time

from naiad.domain.session import SessionSpec

TMUX = "tmux"
CLAUDE = "claude"
BUFFER = "naiad"

# Multi-line text typed key by key would submit at the first newline, so it is
# pasted instead. The threshold is only about which mechanism types faster.
PASTE_ABOVE = 200

# A Clear is a slash command the TUI must process before the Prompt behind it
# lands in the same input. Empirical, and verified by manual smoke rather than
# by reading the terminal back (ADR 0002).
CLEAR_SETTLE_SECONDS = 1.0


class TmuxError(Exception):
    pass


class TmuxSessions:
    def spawn(self, spec: SessionSpec) -> str:
        """Open the session detached and report back the pane it lives in, so
        the Run can later be resolved from its pane."""
        return self._run(_new_session_argv(spec)).strip()

    def send(self, pane: str, text: str) -> None:
        """Type text into the session and submit it.

        Nothing is read back to check that it landed. v1 verified sends by
        capturing the pane and matching against the TUI's input box, which
        broke on every change to the box's chrome; ADR 0002 rules that out.
        """
        if "\n" in text or len(text) > PASTE_ABOVE:
            self._run([TMUX, "load-buffer", "-b", BUFFER, "-"], stdin=text)
            self._run([TMUX, "paste-buffer", "-p", "-d", "-b", BUFFER, "-t", pane])
        else:
            self._run([TMUX, "send-keys", "-t", pane, "-l", text])
        self._run([TMUX, "send-keys", "-t", pane, "Enter"])

    def clear(self, pane: str) -> None:
        """Discard the session's context, then let the TUI act on it before
        whatever is sent next arrives."""
        self.send(pane, "/clear")
        time.sleep(CLEAR_SETTLE_SECONDS)

    def _run(self, argv: list[str], stdin: str | None = None) -> str:
        finished = subprocess.run(argv, capture_output=True, text=True, input=stdin)
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
