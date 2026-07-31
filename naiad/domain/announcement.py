"""What the agent said, as data.

Announcements are distinct and ordered even when they name the same State
twice: seq is what makes the fifth implement iteration a fifth Announcement
rather than a no-op change of value. Naiad acts once per seq, never twice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Announcement:
    seq: int
    state: str
