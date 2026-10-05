"""A numbered prompt for choosing States: numbered lines and `input`.

`naiad state next` opens it when given no States: the list is short and the
author knows the names, so a line of numbers is enough, and a picker that
takes over the screen would be a dependency this release does not carry. The
lines are said as every other line is, so the States are styled as States at
a terminal and the words are the same everywhere.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from naiad.cli.style import Styled, say


def pick_states(
    subject: str,
    states: Sequence[str],
    marked: Sequence[str],
    *,
    read: Callable[[str], str] | None = None,
    write: Callable[[str], object] = say,
) -> list[str] | None:
    """The States the author chose for `subject`'s successors, in the order
    they typed them, or None when they left the current ones as they are.

    A bad answer is asked again with the reason: guessing at what a mistyped
    number meant would write an edge the author did not choose.
    """
    ask = read or input
    write(Styled.assemble("Successors of ", (subject, "state"), " (* marks the current ones):"))
    width = len(str(len(states)))
    for number, state in enumerate(states, start=1):
        write(
            Styled.assemble(
                f"  {number:>{width}}  ", (state, "state"), "  *" if state in marked else ""
            )
        )

    while True:
        try:
            answer = ask("Numbers in order, separated by spaces (empty keeps them): ")
        except EOFError:
            return None
        chosen = _numbers(answer, len(states))
        if chosen is None:
            write(f"not a choice: give each number from 1 to {len(states)} once")
            continue
        if not chosen:
            return None
        return [states[number - 1] for number in chosen]


def _numbers(answer: str, count: int) -> list[int] | None:
    words = answer.replace(",", " ").split()
    if not all(word.isdigit() for word in words):
        return None
    numbers = [int(word) for word in words]
    if any(not 1 <= number <= count for number in numbers) or len(set(numbers)) != len(numbers):
        return None
    return numbers


__all__ = ["pick_states"]
