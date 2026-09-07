"""Where one telling goes: the terminal, the desktop, and every push service
the operator configured.

The services themselves are covered beside their own adapters. What is pinned
here is the fan-out — that a telling reaches every leg, that a leg which is
broken cannot silence the rest, and that a leg is on exactly when its variable
is set — because those are the ways an operator ends up watching a channel
that was never going to say anything.
"""

from naiad.adapters.notify import (
    DesktopNotifications,
    Notifications,
    TerminalNotifications,
    configured_notifier,
    push_legs,
)
from naiad.adapters.ntfy import NtfyNotifications
from naiad.adapters.ntfy import NTFY_TOKEN_VARIABLE, NTFY_URL_VARIABLE
from naiad.domain.notification import Notification

URL = "https://ntfy.sh/naiad-secret-topic"


class RecordingNotifier:
    def __init__(self, failing=None):
        self.notified = []
        self.failing = failing

    def notify(self, title, message, kind):
        self.notified.append((title, message, kind))
        if self.failing is not None:
            raise self.failing


class RecordingPost:
    def __init__(self):
        self.posts = []

    def __call__(self, url, *, headers, body, timeout):
        self.posts.append({"url": url, "headers": headers, "body": body})


def test_a_telling_reaches_every_leg():
    first, second = RecordingNotifier(), RecordingNotifier()

    Notifications(first, second).notify(title="naiad: run-1", message="why", kind=Notification.NOTIFY)

    assert first.notified == [("naiad: run-1", "why", Notification.NOTIFY)]
    assert second.notified == first.notified


def test_a_broken_leg_does_not_silence_the_others(capsys):
    """One dead service must cost its own notification and no other. An
    operator who configured three channels and hears none of them because the
    first raised is worse off than one who configured nothing."""
    broken, working = RecordingNotifier(failing=RuntimeError("boom")), RecordingNotifier()

    Notifications(broken, working).notify(title="naiad: run-1", message="why", kind=Notification.NOTIFY)

    assert len(working.notified) == 1
    reported = capsys.readouterr().err
    assert "boom" in reported
    # Which leg died, not merely that one did: an operator with three
    # configured cannot act on "a notification failed".
    assert "RecordingNotifier" in reported


def test_the_terminal_leg_prints_what_the_banner_cannot_be_scrolled_back_to(capsys):
    """A banner vanishes. An operator reading `naiad watch` in the morning
    finds out what happened in the night from the terminal they left running."""
    TerminalNotifications().notify(title="naiad: run-1", message="why", kind=Notification.FINISH)

    printed = capsys.readouterr().err
    assert "naiad: run-1" in printed and "why" in printed


def test_no_topic_configured_pushes_nothing():
    """The phone leg is off until it is asked for, and everything else about
    a Run is unchanged by its absence."""
    assert push_legs(environ={}) == []


def test_a_blank_topic_is_no_topic():
    """An operator who exported the variable empty — or unset it by exporting
    it empty, which is the same keystroke — has not configured a service."""
    assert push_legs(environ={NTFY_URL_VARIABLE: ""}) == []


def test_a_configured_topic_is_pushed_to():
    post = RecordingPost()

    Notifications(*push_legs(environ={NTFY_URL_VARIABLE: URL}, post=post)).notify(
        title="naiad: run-1", message="why", kind=Notification.NOTIFY
    )

    assert [posted["url"] for posted in post.posts] == [URL]


def test_a_configured_token_reaches_the_service():
    post = RecordingPost()

    legs = push_legs(environ={NTFY_URL_VARIABLE: URL, NTFY_TOKEN_VARIABLE: "tk_secret"}, post=post)
    Notifications(*legs).notify(title="naiad: run-1", message="why", kind=Notification.NOTIFY)

    assert post.posts[0]["headers"]["Authorization"] == "Bearer tk_secret"


def test_the_local_legs_are_never_configured_away():
    """The terminal is the record read in the morning and the desktop is the
    operator still at the machine. Neither is a service, so neither has a
    variable to be turned off by."""
    legs = configured_notifier(environ={}).legs

    assert any(isinstance(leg, TerminalNotifications) for leg in legs)
    assert any(isinstance(leg, DesktopNotifications) for leg in legs)


def test_a_configured_service_joins_the_local_legs_rather_than_replacing_them():
    legs = configured_notifier(environ={NTFY_URL_VARIABLE: URL}).legs

    assert any(isinstance(leg, TerminalNotifications) for leg in legs)
    assert any(isinstance(leg, NtfyNotifications) for leg in legs)
