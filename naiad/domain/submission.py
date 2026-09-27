"""Whether a prompt the Session is about to take is the Prompt Naiad typed
(ADR 0053).

The UserPromptSubmit hook asks this of every prompt submitted in a Run's
Session, and it is a rule, so it lives here rather than in the hook (ADR 0004):
the hook gathers what Naiad typed and when, and carries out the verdict.
"""

from __future__ import annotations

from typing import Literal

from naiad.domain.decide import DELIVERY_CONFIRM_SECONDS

Verdict = Literal["landed", "rejected"]


def judge_submission(
    submitted: str, *, expected: str | None, settled: bool, typed_ago: float
) -> Verdict | None:
    """landed is the Prompt as typed, and confirms the attempt. rejected is a
    prompt that is not it, submitted while the attempt is still in flight — the
    Session took the typing with keystrokes missing — and is turned away so the
    loop can type it again. None is a prompt that is not Naiad's business: a
    human's, typed with no attempt outstanding.

    expected is the Prompt of the latest attempt, or None when Naiad has typed
    none for the current Announcement. settled says that attempt has already
    landed or been turned away, so it answers nothing further.

    A match lands however late it arrives, because it is unambiguous. A
    mismatch is only rejected inside the confirm window: past it the loop has
    stopped waiting on the attempt, and the prompt is a human's, typed into a
    Session Naiad may just have told them to look at."""
    if expected is None or settled:
        return None
    if _same(submitted, expected):
        return "landed"
    if typed_ago < DELIVERY_CONFIRM_SECONDS:
        return "rejected"
    return None


def _same(submitted: str, expected: str) -> bool:
    """Compared with whitespace collapsed. The Session trims the trailing
    newline a Prompt ends with, and whitespace alone never changes what a
    Prompt asks for — where a lost keystroke of anything else does."""
    return submitted.split() == expected.split()


__all__ = ["Verdict", "judge_submission"]
