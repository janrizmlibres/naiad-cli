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

# A newline typed as Enter would submit the Prompt at its first line break.
# Alt-Enter is the TUI's own "newline, don't send", so a multi-line Prompt can
# be typed rather than pasted — and it has to be typed, because Claude Code
# reads a slash command out of typed input only. Bracketed paste arrives as
# `[Pasted text #1]` and is submitted as prose, which silently turns a Prompt
# that runs a skill into one that merely describes it.
NEWLINE = "M-Enter"


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
        for argv in keystrokes_for(pane, text):
            self._run(argv)

    def clear(self, pane: str) -> None:
        """Discard the session's context by typing /clear. Nothing is slept for:
        whether the /clear landed is confirmed by Naiad's own SessionStart hook
        and the Prompt held back until it has (ADR 0019), rather than hoping a
        fixed pause outlasts a terminal that might drop the keystroke anyway."""
        self.send(pane, "/clear")

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
    if spec.model is not None:
        argv += ["--model", spec.model]
    if spec.effort is not None:
        argv += ["--effort", spec.effort]
    if spec.initial_prompt is not None:
        argv.append(spec.initial_prompt)
    return argv


def keystrokes_for(pane: str, text: str) -> list[list[str]]:
    """The tmux commands that put text in the input box and submit it.

    Exposed so what reaches the TUI can be asserted without a session in front
    of it — that a Prompt is typed rather than pasted is the whole point, and
    reading the pane back to check would be the thing ADR 0002 forbids.
    """
    keys: list[list[str]] = []
    for position, line in enumerate(text.split("\n")):
        if position:
            keys.append([TMUX, "send-keys", "-t", pane, NEWLINE])
        if line:
            # `--` unconditionally, not only for lines that open with a dash:
            # it ends tmux's option parsing, and a line is never anything but
            # text. Without it a bulleted Answer types `-l - step` and tmux
            # rejects the bullet as a flag.
            keys.append([TMUX, "send-keys", "-t", pane, "-l", "--", line])
    return keys + [[TMUX, "send-keys", "-t", pane, "Enter"]]


def command_for(spec: SessionSpec) -> list[str]:
    """Exposed so the command a spec produces can be asserted without opening a
    session — the permission mode in particular."""
    return _new_session_argv(spec)


__all__ = ["TmuxError", "TmuxSessions", "command_for", "keystrokes_for"]
