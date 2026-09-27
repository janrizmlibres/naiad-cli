"""The UserPromptSubmit hook's work over a Run's records (ADR 0053).

Gathers what the loop typed last and whether the hook has already judged it,
asks naiad.domain.submission for the verdict, and keeps the verdict for the loop
to read. What the verdict means for the Session — let through or turned away —
is the command's to carry out; what it means for the Run is the decision's.
"""

from __future__ import annotations

from pathlib import Path

from naiad.domain.submission import Verdict, judge_submission
from naiad.runtime.records import Deliveries, Submissions


def judge(run_root: Path, prompt: str, *, now: float) -> Verdict | None:
    typed = Deliveries(run_root).latest()
    if typed is None:
        return None
    submissions = Submissions(run_root)
    verdict = judge_submission(
        prompt,
        expected=typed.prompt,
        settled=submissions.verdict(seq=typed.seq, attempt=typed.attempt) is not None,
        typed_ago=now - typed.at,
    )
    if verdict is not None:
        submissions.record(seq=typed.seq, attempt=typed.attempt, verdict=verdict)
    return verdict


__all__ = ["judge"]
