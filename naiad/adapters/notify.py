"""Telling the operator they are needed, everywhere they might be.

Adapters and nothing more: whether to notify, and once per what, are rules and
were decided in naiad.domain.decide (ADR 0004). What is here is a set of legs
one telling goes down, and the reading of the environment that says which of
them exist.

Three kinds of leg, for three places an operator can be. The terminal is
always one, because a banner vanishes and cannot be scrolled back to, and
somebody reading `naiad watch` in the morning needs to find out what happened
in the night from the terminal they left running. The desktop is the second,
for an operator at the machine. A push service is the third, for one who is
not — which is the only leg that reaches somebody who has walked away.

Verified by manual smoke where a leg talks to the world, and by tests where it
decides which legs there are.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Mapping, Protocol

from naiad.adapters.ntfy import NTFY_TOKEN_VARIABLE, NTFY_URL_VARIABLE, NtfyNotifications
from naiad.adapters.posting import Post, post
from naiad.domain.notification import Notification

OSASCRIPT = "osascript"

_SCRIPT = (
    "-e",
    "on run {message, title}",
    "-e",
    "display notification message with title title",
    "-e",
    "end run",
)


class Leg(Protocol):
    """One place a telling goes."""

    def notify(self, title: str, message: str, kind: Notification) -> None: ...


class TerminalNotifications:
    """The record of the night, in the terminal the Run was driven from.

    The one leg that is never configured away, because it is the only one that
    can still be read hours later.
    """

    def notify(self, title: str, message: str, kind: Notification) -> None:
        print(f"{title}: {message}", file=sys.stderr, flush=True)


class DesktopNotifications:
    """A desktop banner, where the platform offers one."""

    def notify(self, title: str, message: str, kind: Notification) -> None:
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
            # it: the reason has already been printed by the terminal leg, and
            # the Run is still alive and waiting for its human.
            pass


class Notifications:
    """Every leg one telling goes down.

    Each leg is called even when the one before it failed, so that a single
    broken channel costs its own notification rather than all of them. A leg
    that knows how it can fail reports that itself, in its own words; the guard
    here is the backstop for what none of them saw coming, and names the leg,
    because an operator with three configured cannot act on being told that one
    of them died.
    """

    def __init__(self, *legs: Leg) -> None:
        self.legs = legs

    def notify(self, title: str, message: str, kind: Notification) -> None:
        for leg in self.legs:
            try:
                leg.notify(title=title, message=message, kind=kind)
            except Exception as error:  # noqa: BLE001 - a leg must not take the rest down
                print(
                    f"naiad: {type(leg).__name__} failed to notify: {error}",
                    file=sys.stderr,
                    flush=True,
                )


def push_legs(environ: Mapping[str, str], *, post: Post = post) -> list[Leg]:
    """The push services this environment turned on, and no others.

    Presence is what selects one: setting its variable is the whole of turning
    it on, and there is no second selector to keep in step with it. Adding
    another service is another adapter and another clause here.

    Apart from the local legs so that what an operator configured can be
    exercised without the two that need no configuring — a test of which
    services are on has no business raising desktop banners to find out.
    """
    legs: list[Leg] = []
    url = environ.get(NTFY_URL_VARIABLE)
    if url:
        legs.append(
            NtfyNotifications(url, token=environ.get(NTFY_TOKEN_VARIABLE) or None, post=post)
        )
    return legs


def configured_notifier(
    environ: Mapping[str, str] | None = None, *, post: Post = post
) -> Notifications:
    """Every leg this machine has: the two local ones, and whatever the
    operator configured beside them."""
    environ = os.environ if environ is None else environ
    return Notifications(
        TerminalNotifications(), DesktopNotifications(), *push_legs(environ, post=post)
    )


__all__ = [
    "DesktopNotifications",
    "Leg",
    "Notifications",
    "TerminalNotifications",
    "configured_notifier",
    "push_legs",
]
