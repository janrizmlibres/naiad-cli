"""Stand-ins for the programs the doctor asks about.

Two shell scripts on a directory the test puts on `PATH`: a `tmux` that says
whether a server is running and what its global `PATH` holds, and a `claude`
that says what version it is. Scripts rather than monkeypatched functions,
because what the doctor does is run the programs an operator has.
"""

from pathlib import Path

HEALTHY_CLAUDE = "2.1.284 (Claude Code)"


def _script(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


def install_tmux(directory: Path, *, server_path: str | None = None) -> Path:
    """A tmux with no server running, or one whose global PATH is `server_path`."""
    if server_path is None:
        body = 'echo "no server running on /tmp/tmux-0/default" >&2\nexit 1'
    else:
        body = f'echo "PATH={server_path}"'
    return _script(directory, "tmux", body)


def install_claude(directory: Path, *, says: str | None = HEALTHY_CLAUDE) -> Path:
    """A claude answering `--version` with `says`, or failing to when None."""
    body = "exit 1" if says is None else f'echo "{says}"'
    return _script(directory, "claude", body)


def install_osascript(directory: Path) -> Path:
    return _script(directory, "osascript", "exit 0")


def install_healthy(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    install_tmux(directory)
    install_claude(directory)
