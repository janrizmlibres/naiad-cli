"""The ntfy adapter: the one request it builds, and what it does when it fails.

Every rule about *whether* to notify was decided in naiad.domain.decide (ADR
0004). What is left here is a request — a URL, three headers and a body — and
an adapter holding nothing else. It is tested rather than smoked because the
request is data: a wrong header name is a notification that never arrives on a
phone nobody is watching, which is the one failure this whole feature exists
to remove.
"""


from http.client import InvalidURL

from naiad.adapters.ntfy import NTFY_TOKEN_VARIABLE, NTFY_URL_VARIABLE, NtfyNotifications
from naiad.domain.notification import Notification

URL = "https://ntfy.sh/naiad-secret-topic"


class RecordingPost:
    """Stands in for the HTTP transport. Records the request rather than
    sending it, which is the whole of what wants asserting here."""

    def __init__(self, failing=None):
        self.posts = []
        self.failing = failing

    def __call__(self, url, *, headers, body, timeout):
        self.posts.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        if self.failing is not None:
            raise self.failing


def notify(post, *, token=None, kind=Notification.NOTIFY, title="naiad: run-1", message="why"):
    NtfyNotifications(URL, token=token, post=post).notify(title=title, message=message, kind=kind)


def test_the_message_is_posted_to_the_topic_url():
    post = RecordingPost()

    notify(post, message="state 'review' is a Gate State and is waiting for you")

    assert len(post.posts) == 1
    assert post.posts[0]["url"] == URL
    assert post.posts[0]["body"] == b"state 'review' is a Gate State and is waiting for you"


def test_the_title_rides_a_header_rather_than_the_body():
    """ntfy takes the body as the message and the title from a header. A title
    folded into the body is a lock screen showing the Run id twice and the
    reason never."""
    post = RecordingPost()

    notify(post, title="naiad: run-1", message="why")

    assert post.posts[0]["headers"]["Title"] == "naiad: run-1"


def test_a_human_is_needed_at_a_higher_priority_than_a_run_that_finished():
    """The two tellings are not equally urgent: one is a Run standing still
    until its operator arrives, the other is good news."""
    needed, finished = RecordingPost(), RecordingPost()

    notify(needed, kind=Notification.NOTIFY)
    notify(finished, kind=Notification.FINISH)

    assert needed.posts[0]["headers"]["Priority"] == "4"
    assert finished.posts[0]["headers"]["Priority"] == "3"


def test_a_token_is_sent_as_a_bearer_header():
    post = RecordingPost()

    notify(post, token="tk_secret")

    assert post.posts[0]["headers"]["Authorization"] == "Bearer tk_secret"


def test_no_token_sends_no_authorization_header():
    """A public topic takes no auth, and an empty Bearer header is rejected by
    some servers that would have accepted no header at all."""
    post = RecordingPost()

    notify(post, token=None)

    assert "Authorization" not in post.posts[0]["headers"]


def test_the_request_cannot_hang_the_tick():
    """The loop calls this synchronously, so an unreachable host must fail
    rather than stop the Run being driven."""
    post = RecordingPost()

    notify(post)

    assert post.posts[0]["timeout"] > 0


def test_a_failed_push_is_reported_rather_than_raised(capsys):
    """The channel you rely on while away is the one whose silence you must
    not have to guess at — and a Run must not die because a phone did."""
    post = RecordingPost(failing=OSError("connection refused"))

    notify(post)

    assert "connection refused" in capsys.readouterr().err


def test_a_url_that_is_not_a_url_is_reported_under_this_service_name(capsys):
    """The likeliest misconfiguration of all: a topic name where a full URL
    was asked for. It reaches the transport as a ValueError rather than a
    failed request, and an operator who mistyped one variable needs to be told
    which one — so it is reported here, where the service has a name, rather
    than by the fan-out's backstop, which does not."""
    post = RecordingPost(failing=ValueError("unknown url type: 'my-topic'"))

    notify(post)

    assert "ntfy" in capsys.readouterr().err


def test_a_url_with_a_bad_port_is_reported_under_this_service_name(capsys):
    """The other half of a mistyped URL. A nonnumeric port never becomes a
    request either, but it arrives as an HTTPException rather than as either of
    the two the rest of the world fails with — and an operator who mistyped one
    variable is owed the same line whichever way they mistyped it."""
    post = RecordingPost(failing=InvalidURL("nonnumeric port: 'notaport'"))

    notify(post)

    assert "ntfy" in capsys.readouterr().err


def test_the_variables_name_the_service_they_configure():
    """Presence of the URL is what turns the phone leg on, so the name an
    operator types is part of the contract rather than an implementation
    detail."""
    assert NTFY_URL_VARIABLE == "NAIAD_NTFY_URL"
    assert NTFY_TOKEN_VARIABLE == "NAIAD_NTFY_TOKEN"


def test_a_report_is_sent_at_a_lower_priority_than_a_gate():
    """A milestone is low enough that it never sounds like a request for the
    operator (ADR 0055)."""
    reported, needed = RecordingPost(), RecordingPost()

    notify(reported, kind=Notification.REPORT)
    notify(needed, kind=Notification.NOTIFY)

    assert reported.posts[0]["headers"]["Priority"] == "2"
    assert int(reported.posts[0]["headers"]["Priority"]) < int(needed.posts[0]["headers"]["Priority"])
