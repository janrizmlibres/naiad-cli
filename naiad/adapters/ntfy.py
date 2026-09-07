"""Pushing a telling to a phone through ntfy.

An adapter and nothing more: whether to notify, and once per what, are rules
and were decided in naiad.domain.decide (ADR 0004). What is here is one POST —
the message as the body, the title and the priority as headers — and the
mapping from Naiad's two tellings onto ntfy's scale of five.

Turned on by the presence of NAIAD_NTFY_URL holding the full topic URL, which
is what keeps a self-hosted server free: the operator moves the host and
nothing here changes. NAIAD_NTFY_TOKEN is sent as a Bearer header where the
topic is access-controlled, and omitted entirely where it is not.
"""

from __future__ import annotations

import sys
from http.client import HTTPException

from naiad.adapters.posting import Post, post
from naiad.domain.notification import Notification

NTFY_URL_VARIABLE = "NAIAD_NTFY_URL"
NTFY_TOKEN_VARIABLE = "NAIAD_NTFY_TOKEN"

# The tick calls this synchronously, so this is roughly how long a Run stands
# still for a notification it may not even get. Roughly, because it bounds the
# socket and not the name lookup before it: a resolver that hangs — a dropped
# VPN, a captive portal — stalls the tick past this. Survivable because the
# once-per-Announcement rule (ADR 0004) means a parked Run pays it once rather
# than every tick, and worth watching if a push service is ever added to a
# Lane-heavy Supervisor, whose lanes tick one after another.
TIMEOUT_SECONDS = 5.0

# ntfy grades 1 (min) to 5 (max). A human who is needed gets 4, which is a
# push loud enough to notice; 5 breaks through Do Not Disturb and a Gate State
# waiting until morning does not deserve that. Good news travels at 3.
PRIORITIES = {Notification.NOTIFY: "4", Notification.FINISH: "3"}


class NtfyNotifications:
    """A push to whatever phone is subscribed to one ntfy topic."""

    def __init__(self, url: str, *, token: str | None = None, post: Post = post) -> None:
        self._url = url
        self._token = token
        self._post = post

    def notify(self, title: str, message: str, kind: Notification) -> None:
        try:
            self._post(
                self._url,
                headers=self._headers(title, kind),
                body=message.encode("utf-8"),
                timeout=TIMEOUT_SECONDS,
            )
        except (OSError, ValueError, HTTPException) as error:
            # Reported rather than swallowed, unlike the desktop banner: the
            # phone is the channel an operator relies on precisely when they
            # are not at the terminal, and a leg that has gone quiet must not
            # look the same as one with nothing to say. Printed rather than
            # raised because a Run must not die because a phone did.
            #
            # Three types because a URL can be wrong in three ways and only
            # one of them is a failed request: a topic name where a full URL
            # was asked for raises ValueError, a nonnumeric port raises
            # HTTPException, and everything that reaches the network raises
            # OSError. All of them are the same mistake to the operator who
            # made it, so all of them are reported here, where the service has
            # a name to be reported under. Not `except Exception`, which would
            # blame the network for a bug in this adapter.
            print(f"naiad: ntfy notification failed: {error}", file=sys.stderr, flush=True)

    def _headers(self, title: str, kind: Notification) -> dict[str, str]:
        headers = {
            "Title": title,
            "Priority": PRIORITIES[kind],
            # Set explicitly because urllib otherwise calls a plain-text body
            # form-encoded, which is a claim about the message that is not true.
            "Content-Type": "text/plain; charset=utf-8",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers


__all__ = ["NTFY_TOKEN_VARIABLE", "NTFY_URL_VARIABLE", "NtfyNotifications"]
