"""What the UserPromptSubmit hook makes of a prompt the Session is about to
take, as data in and a verdict out (ADR 0053). No hook, no files, no clock."""

from naiad.domain.decide import DELIVERY_CONFIRM_SECONDS
from naiad.domain.submission import judge_submission

PROMPT = "Before anything else, work out which repositories this Run's work reached.\n\nThen open them."


def test_the_prompt_naiad_typed_lands():
    assert judge_submission(PROMPT, expected=PROMPT, settled=False, typed_ago=0.5) == "landed"


def test_a_prompt_that_lost_its_head_is_rejected():
    """The failure this exists for: the Session dropped the keystrokes that
    arrived while it was still handling a Switch, and took the rest."""
    cut = PROMPT[40:]

    assert judge_submission(cut, expected=PROMPT, settled=False, typed_ago=0.5) == "rejected"


def test_a_prompt_that_lost_characters_in_the_middle_is_rejected():
    holed = PROMPT[:20] + PROMPT[30:]

    assert judge_submission(holed, expected=PROMPT, settled=False, typed_ago=0.5) == "rejected"


def test_whitespace_the_session_trims_is_not_a_difference():
    """The Session drops the Prompt's trailing newline, and a typed line break
    is not guaranteed to come back byte for byte. Whitespace alone never
    changes what a Prompt asks for."""
    trimmed = PROMPT.replace("\n\n", "\n \n") + "  "

    assert judge_submission(trimmed, expected=PROMPT + "\n", settled=False, typed_ago=0.5) == (
        "landed"
    )


def test_nothing_is_judged_when_naiad_has_typed_nothing():
    """A human typing into a Run's Session between deliveries is not Naiad's
    to stop."""
    human = "please also fix the typo"

    assert judge_submission(human, expected=None, settled=False, typed_ago=0.5) is None


def test_nothing_is_judged_once_the_attempt_is_settled():
    """The attempt already landed or was already turned away; whatever comes
    next is the human's, or the next attempt's."""
    assert judge_submission("yes", expected=PROMPT, settled=True, typed_ago=0.5) is None


def test_a_different_prompt_past_the_confirm_window_is_let_through():
    """Past the window the loop has given up on the attempt, so a prompt that
    is not it is a human's — and blocking it would lock them out of the
    Session Naiad has just asked them to look at."""
    assert (
        judge_submission(
            "what happened?", expected=PROMPT, settled=False, typed_ago=DELIVERY_CONFIRM_SECONDS
        )
        is None
    )


def test_the_prompt_itself_lands_however_late_it_arrives():
    """A match is unambiguous, so a slow landing still confirms the attempt."""
    assert (
        judge_submission(
            PROMPT, expected=PROMPT, settled=False, typed_ago=DELIVERY_CONFIRM_SECONDS * 3
        )
        == "landed"
    )
