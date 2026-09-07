"""One HTTP POST, and nothing else.

Kept apart from the services that use it so that a service adapter can be
tested for the request it builds without a network anywhere near it, and so
that a second service inherits the transport rather than a copy of it. The
standard library is the whole of the implementation: Naiad has no runtime
dependencies, and one POST is not the place to acquire the first.

Verified by manual smoke, which is the deal for anything holding no logic.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Mapping, Protocol


class Post(Protocol):
    """The seam every push service is given and every test replaces."""

    def __call__(
        self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float
    ) -> None: ...


def post(url: str, *, headers: Mapping[str, str], body: bytes, timeout: float) -> None:
    """Send one request and read nothing back.

    What a push service answers with is of no use to Naiad: the operator is
    either reachable or they are not, and the failure — not the reply — is the
    only outcome a caller acts on. Raised rather than swallowed here, because
    which failures are survivable is the caller's judgment and not a
    transport's.
    """
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            pass
    except urllib.error.HTTPError as error:
        # An error status is raised rather than returned, and the exception is
        # itself the response — it holds the socket, and the `with` above never
        # bound it to close it. A stale token answers 401 to every notification
        # a supervisor sends, so the ones this closes are unbounded rather than
        # occasional.
        error.close()
        raise


__all__ = ["Post", "post"]
