"""Telling the operator they are needed.

An adapter and nothing more: whether to notify, and once per what, are rules
and were decided in naiad.domain.decide (ADR 0004). Verified by manual smoke
rather than by tests, which is the deal for anything holding no logic.

The reason is always printed as well as raised as a desktop notification. A
notification is a banner that vanishes and cannot be scrolled back to, and an
operator reading `naiad watch` in the morning needs to find out what happened
in the night from the terminal they left running.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

OSASCRIPT = "osascript"

_SCRIPT = (
    "-e",
    "on run {message, title}",
    "-e",
    "display notification message with title title",
    "-e",
    "end run",
)


class DesktopNotifications:
    """A desktop banner where the platform offers one, and the terminal always."""

    def notify(self, title: str, message: str) -> None:
        print(f"{title}: {message}", file=sys.stderr, flush=True)
        self._banner(title, message)

    def _banner(self, title: str, message: str) -> None:
        if not shutil.which(OSASCRIPT):
            return
        try:
            subprocess.run(
                # The text is passed as arguments rather than interpolated into
                # the script, so there is no AppleScript quoting to get right.
                # A reason carries a State name from a Workflow file, and an
                # adapter is meant to hold no logic worth testing.
                [OSASCRIPT, *_SCRIPT, message, title],
                capture_output=True,
                check=False,
            )
        except OSError:
            # A banner that cannot be raised must not take the Run down with
            # it: the reason has already been printed, and the Run is still
            # alive and waiting for its human.
            pass


__all__ = ["DesktopNotifications"]
