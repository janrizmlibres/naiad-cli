# A parked Run blocks the Queue

A Run does not only end. It parks: a Gate State reached, an Answerer escalating, an agent gone silent past two Nudges, a session hung. All four resolve to `Notify`, and a notified Run stays alive and keeps ticking, because only a Terminal State ends one. So a Queue taken strictly in order stops at the first Entry that parks and does not move again until a human types into that Run's session.

The cost is exactly the thing the project exists to remove. A queue of five started at eleven at night can spend the whole night parked at `review` on the first Entry, having done nothing since midnight.

We decided the Queue blocks anyway, and that stepping over a parked Run is a separate feature that is not being built.

The reason is not the Queue, it is the working tree. Stepping over a parked Entry means starting the next Run while the parked one is still live, and both Runs drive an agent against the same checkout of the same repository. That is not "one at a time with an exception"; it is concurrency with the concurrency control removed, and the two agents would fight over the index, the branch and the build. The honest prerequisite is a disposable worktree per Run, which is a larger piece of work than the Queue and one the storage rules were already written in anticipation of.

Blocking also costs nothing to implement, which is worth saying plainly because it is evidence rather than convenience. Watching a Run already never returns while that Run is parked — that is what keeps a Run tickable so a human's typing revives it. A Supervisor that simply watches each Entry in turn therefore blocks on a parked one with no code written for it at all, in the same way a Gate State needed no gate feature.

The routine case has a mitigation that already exists. Gates on the declared path are resolved past by an Entry running with Gates skipped, so the review checkpoints do not park an unattended Queue. What remains are the Gates a Branching State named as candidates — `handover`, `no-repro` — which are never skipped because they are destinations the agent chose. Parking there is the design working: they mean the agent cannot proceed, not that a review is optional.

## Consequences

A parked Entry needs a way to stop blocking, and killing the Supervisor is not one — restarting it finds an Entry whose Run has not finished and blocks again. Two mechanisms answer two different situations. A Run that exists is ended by typing into its session and having the agent announce the Terminal State, which is the existing escape hatch working as designed and adds nothing to Naiad. An Entry that has never run has no session to type into, so it is removed from the Queue instead. Removing an Entry that already ran moves the Predecessor of everything after it past that Entry, which is correct — dropped work should not be in the stack — but it makes removal a decision rather than tidying.

Three properties keep the non-sequential Queue possible, and all three are cheap now and unrecoverable later. An Entry is addressed by its id and never by its position, so stepping over one renumbers nothing. The Supervisor holds no Run of its own, so which Run is live stays derivable from the Entries. And parked is distinguishable from running — not because the sequential Queue needs the distinction, which it does not, but because a Queue that never recorded it would have nothing to step over. That third one costs nothing to satisfy: parked is already recorded per Announcement, so that a persisting condition notifies once rather than on every tick.
