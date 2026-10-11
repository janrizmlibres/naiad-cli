# Naiad carries branch names, not git knowledge

> Amended by ADR 0022.

Each Entry's work belongs on its own Working branch, and because the Queue is sequential an Entry usually wants to stand on the one before it — unless that work has already landed, in which case it wants the repository's base branch instead. Only the Queue knows which Entry came before. Only the repository knows whether that work has landed. The temptation is to have Naiad ask both.

We decided Naiad carries branch names and nothing else. It supplies the Predecessor as an opaque string, exactly as it supplies a Subject, and the Prompt carries the rule for what to do with it.

Teaching Naiad the rule fails for the reason a State that waits on external state was left to its Prompt: the answer is not stable. A Predecessor unmerged when an Entry starts can land twenty minutes later, and a Naiad that computed the base at kickoff has a stale answer and no mechanism to revise it. The agent re-reads the truth at the moment it matters, which is when the pull request is opened and the branch is rebased onto its base — a skill that already accepts an explicit base for exactly this stacked case, and needs only to be told one.

It would also be the wrong knowledge to hold. That the base is `develop` and never `main`, that work arrives as pull requests, that a branch is named for an application and an issue number — these are conventions of one repository, and the Queue spans every repository on the machine. A Naiad holding them would know what one project means, which is the thing it is built not to know.

The same reasoning settles the branch's name. Naiad cannot derive one, because a correct one needs the issue number and the affected application, and any slug it invented would be as off-convention as a prefix of its own and just as visible on a team's pull request list. So the Working branch is required when the Entry is made and rejected when absent, refused before the Entry exists, as a Run whose first Prompt needs a Subject already is. This is less of a chore than it reads: whatever makes the Entry — an agent in a session, or the agent writing a batch file — has the task and the repository's own conventions in front of it, and typing it by hand is the fallback rather than the norm.

The alternative was letting the running agent name its branch and report it back. That puts the agent in charge of a fact the *next* Entry depends on, and its failure is the silent kind: the agent forgets, the Predecessor renders empty, the next Entry quietly bases on the base branch, and the stack is wrong until somebody reads the diff. Every single-writer rule here exists to prevent that shape.

## Consequences

The test the Prompt carries is whether the Predecessor is already an ancestor of the base branch, not whether its pull request is merged. Ancestry is one question with a terminal answer and needs no API, where merge status is a taxonomy — open, closed, merged, closed-unmerged — that has to be enumerated correctly to be safe, and answers wrongly for the case that matters most: a Run parked at `handover` has commits and no pull request at all, and "not merged" would send the next Entry to the base branch and drop that work from under it.

The known hole is a Predecessor whose pull request was closed without merging. It is not an ancestor, so the next Entry stands on abandoned commits. This is accepted rather than solved; an Entry may pin its own base, and abandonment mid-Queue is rare enough that a human is there when it happens.

Stacking is the default because the two failures are not symmetrical. Stacking unnecessarily couples unrelated pull requests and costs review friction over work that is nonetheless correct. Not stacking when the work depends means the second agent never sees the first's code, may build the same thing differently, and the conflict surfaces at merge — after the night is spent. The pin exists for the case the enqueuer can see and the agent cannot.

The branch is created at the two heads of the Workflow's branches rather than in a State of its own, because a State of its own would be skipped by exactly the Entries that pre-classify, which are most of them. The classifying State changes nothing and needs none; both heads Clear, and a checked-out branch survives a Clear. The instruction is idempotent, so a resumed Run does not fail on a branch that already exists.

Because Runs share one working tree, a finished Run's session — which is deliberately left alive — is on whatever branch it ended on, and the next Entry checks out a different one underneath it. Typing into an old session after the Queue has moved on operates on the wrong branch. That is the price of one working tree, and the worktree per Run that ADR 0012 defers is the eventual answer to both.
