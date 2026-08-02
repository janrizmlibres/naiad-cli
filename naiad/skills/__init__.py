"""The user skills Naiad ships to the operator's Claude configuration.

A skill is how the operator's prose becomes one of Naiad's commands: they state
an intent and the agent reaches for the skill whose description matches. The
contract each skill teaches is Naiad's own, so the file teaching it is versioned
here and reinstalled with Naiad rather than hand-maintained and left to drift
(ADR 0028).

Installed beside the hooks, into the operator's configuration rather than into
the repository Naiad drives (PRD, 'Storage'), and for the same reason: a skill
belongs to the machine rather than to any one Run.
"""
