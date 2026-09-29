"""Running the Answerer: a headless Claude session in the target repository.

Turns a ConsultationSpec into a command and runs it. Every rule about what the
Answerer may settle, and what its reply means, was decided in
naiad.domain.answerer; nothing here branches on the outcome.

Headless rather than a second tmux session because nobody is going to watch it,
and because its reply must come back as a value rather than as pixels — reading
it off a terminal is exactly what Naiad never does.
"""

from __future__ import annotations

import subprocess

from naiad.domain.answerer import (
    CONSULTATION_TIMEOUT_SECONDS,
    Answered,
    ConsultationSpec,
    Escalated,
    parse_outcome,
)
from naiad.domain.session import BYPASS_PERMISSIONS

CLAUDE = "claude"


class HeadlessAnswerer:
    def consult(self, spec: ConsultationSpec) -> Answered | Escalated:
        """Put one Question to the Answerer and read what comes back.

        Every failure resolves to an Escalation rather than an exception. A
        consultation that could not be run or could not be understood is
        precisely 'nobody here can settle this', which is what Escalation
        already means — and it keeps the Run alive and the operator informed,
        where raising would kill the tick loop mid-Run.
        """
        try:
            finished = subprocess.run(
                command_for(spec),
                capture_output=True,
                text=True,
                cwd=str(spec.cwd),
                timeout=CONSULTATION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return Escalated(
                reason=f"the Answerer did not reply within "
                f"{int(CONSULTATION_TIMEOUT_SECONDS)}s"
            )
        except OSError as error:
            return Escalated(reason=f"the Answerer could not be run: {_why_not_launched(error)}")

        if finished.returncode != 0:
            return Escalated(
                reason=f"the Answerer failed: {(finished.stderr or '').strip() or 'no output'}"
            )
        return parse_outcome(finished.stdout)


def _why_not_launched(error: OSError) -> str:
    """The launch failure as a sentence rather than an exception's text.

    A `claude` that is not on PATH is told apart by the file the failure names,
    because the same FileNotFoundError also reports a working directory that is
    gone, and that is not what to send the operator to fix.
    """
    if isinstance(error, FileNotFoundError) and error.filename == CLAUDE:
        return f"`{CLAUDE}` is not on PATH"
    return f"`{CLAUDE}` could not be launched ({error.strerror or error})"


def command_for(spec: ConsultationSpec) -> list[str]:
    """Exposed so the command a spec produces can be asserted without spending
    a consultation — the resumption in particular.

    The Answerer reads the repository and is told to, so it runs in the same
    permission mode as the Run's own session; a consultation that stops to ask
    for permission to read a file has nobody to ask.
    """
    argv = [CLAUDE, "-p", "--permission-mode", BYPASS_PERMISSIONS]
    if spec.resume:
        argv += ["--resume", spec.claude_session_id]
    else:
        argv += ["--session-id", spec.claude_session_id]
    if spec.model is not None:
        argv += ["--model", spec.model]
    if spec.effort is not None:
        argv += ["--effort", spec.effort]
    if spec.fallback is not None:
        argv += ["--fallback-model", spec.fallback]
    return argv + [spec.text]


__all__ = ["CONSULTATION_TIMEOUT_SECONDS", "HeadlessAnswerer", "command_for"]
