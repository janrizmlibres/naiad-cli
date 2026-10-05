"""The short form an Entry is shown by, and the Entries a short form names.

An Entry id is long because it has to sort: a timestamp to the microsecond, the
Workflow's name, the process id. What tells one Entry from the next on an
operator's screen is mostly the last part, so that is what is shown — but a
process id is not unique on its own. One agent queueing a night's work in a
single turn gives every Entry the same one, and process ids come round again.
So the short form is the fewest trailing parts of the id, counted at its
dashes, that no other id on the Queue ends in; and where every tail is shared,
the id in full.

Reading a name back is the same rule run the other way: the id it equals, or
else every id it is a whole-part tail of. A short form shown in a listing
therefore names one Entry for as long as no Entry that ends the same way is
added, and a name that has come to name several is the caller's to refuse
rather than to choose between.

Pure: ids in, ids out. Which ids — the Queue's, at the moment of asking — is the
caller's to say.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

SEPARATOR = "-"


def short_ids(ids: Iterable[str]) -> dict[str, str]:
    """Each id with the shortest form that names it among these ids alone."""
    every = list(ids)
    return {full: _shortest(full, every) for full in every}


def named_by(ids: Sequence[str], name: str) -> list[str]:
    """The ids a name stands for, in the order given: the one it equals, or
    every one it ends at a dash. A full id always names itself alone, even
    where another id ends in it, so that a full id is never refused."""
    if not name:
        return []
    if name in ids:
        return [name]
    return [full for full in ids if full.endswith(SEPARATOR + name)]


def _shortest(full: str, ids: Sequence[str]) -> str:
    parts = full.split(SEPARATOR)
    for count in range(1, len(parts)):
        tail = SEPARATOR.join(parts[-count:])
        if named_by(ids, tail) == [full]:
            return tail
    return full


__all__ = ["named_by", "short_ids"]
