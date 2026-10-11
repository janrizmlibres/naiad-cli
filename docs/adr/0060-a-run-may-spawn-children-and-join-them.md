# A Run may spawn Children and join them

> Narrows ADR 0045. Builds on ADR 0012 and ADR 0020.

The implement loop takes a feature's tickets one after another, one Announcement each, in one Session. A long ticket queue takes as long as all of its tickets added together, even where most of them do not depend on one another. ADR 0045 turned down `/wayfinder`'s parallel subagents on the ground that "the skill's parallelism serves a human's clock, and a Run has no clock to serve". That has stopped being true. A night's Queue that has not finished by morning has failed at the thing it was queued for. We decided a Run may work on several of its items at once, and that it does so through Runs of its own rather than by becoming several things at once.

## Two general ideas, and nothing about tickets

Naiad learns two things. It learns no ticket, edge, frontier or git.

A Run may **Spawn**. This is the fifth Protocol verb. The agent runs it from inside its Session, it resolves the calling Run the way `announce`, `wait` and `branch` do, and it enqueues an Entry recorded as that Run's **Child**. The Child carries exactly what any Entry carries: a working tree, a Working branch, a pinned base, the State to start at, a Subject, and settings. All of it is the agent's to name and opaque to Naiad, and it is checked when queued as any Entry is. A Child takes its Parent's settings and whether Gates are skipped, unless the Spawn names its own. A Child runs in a working tree of its own, so by ADR 0020 it is a Lane of its own and already runs beside its Parent and its siblings. The worktree that ADR 0012 named as the prerequisite for stepping past a parked Run is made by the agent, in the Prompt, because Naiad knows no git (ADR 0015).

A State may be a **Join State**. Naiad holds back its Prompt while the Run's Children are working. The rule has three cases:

- It is **delivered** once a Child has finished that the Parent has not yet been told of. A `{children}` slot names every such Child by its Subject, its Working branch, its working tree, and whether it completed or was cancelled, and each Child is named exactly once.
- It is **delivered at once**, with nothing named, when the Run has no unfinished Child. So the same State can make the first Spawn and can notice the end.
- It is **held** otherwise. Holding is waiting, not silence: the decision function returns Nothing, and no Nudge or hang Notify reaches a Run that is waiting on its Children.

## Rolling, not waves

A Join State is released by any one Child finishing, not by all of them. The Parent takes in what has finished, scans again, and spawns whatever has just become unblocked while the others are still working. On an uneven set of items that is the faster shape. Waves are still available, because a Prompt can decline to spawn until everything in flight has been taken in. So Naiad needs one waiting rule, not two.

## The Child limit is a number, not a mode

An Entry may carry a **Child limit**: how many of its Run's Children may work at once. A Child over the limit waits in the Queue like any Entry, and the Queue is ordered by id, so a limit of one takes the Children one at a time in the order they were spawned. When no limit is given there is none of the Run's own, so working in parallel is the default. Naiad cannot know what "serial mode" means for a Workflow, but it can count. A Batch file may give the limit as a default like any other key.

## Edges of the relationship

- **Only one level.** Spawn refuses from inside a Child. Nothing needs nesting, and refusing it rules out a fan-out spawning more fan-outs by accident. Allowing it later only means removing one refusal.
- **A parked Child** notifies as any Run does. Its Parent is not told, because a parked Child has not finished. The person who needs to act already has the notification.
- **Cancelling a Parent cancels its Children.** It is the same Cancellation applied to each of them, and every Session is released. A Child exists to serve its Parent, and an orphaned one would build work nobody will take in. The operator is told which of the Children's working trees are now theirs to remove. Naiad knows those paths without knowing that they are worktrees.
- **A Parent cannot end over unfinished Children.** Announcing a Terminal State is refused while any Child is unfinished, and the refusal tells the agent to announce its Join State instead.
- **A cancelled Child** reaches its Parent as cancelled. What the Parent does about it is the Workflow's business.
- **A Prune skips a done Child its Parent has not been told of.** Otherwise it would delete the record the Join State is waiting to deliver.
- **The Queue listing** shows a Parent held at a Join State as `joining`, derived like every other status (ADR 0013), with its Children listed under it.

## Considered options

**One Run with several Sessions.** Rejected. Every per-Run rule assumes one Session and one ordered stream of Announcements: the State file's single writer, the one Standing State, one Question at a time (ADR 0044), the Belief, the Nudge count, the per-Subject Run log. A Run with N Sessions breaks every one of them, and Naiad would have to track which items are in flight, which is the ticket list ADR 0001 keeps out of it.

**Subagents inside one Run.** This needs no change to Naiad. Rejected, because a subagent cannot announce, ask a Question or be handed to a human, and no item gets a Clear of its own.

**A Wait on Children.** That is a Wait with no expiry and no budget, after which a Nudge wakes the agent in the context that did the spawning. Rejected, because it undoes the reason a Wait has a budget, and because taking finished work in should start from a Cleared context, the way each pass of a loop does.

**A `--parent` flag on `naiad run`.** Rejected. It hands the agent its own Run id to carry and type, which is the clerical work ADR 0001 moved into commands.

**Having the Parent read the Queue to learn which Children finished.** Rejected. It reads two sources for one fact, and a Child finishing during the Parent's turn is either taken in twice or stranded.

## Consequences

ADR 0045's line now holds only for what it was written about. `wayfind` stays one ticket per Announcement in one Session, because its strict stop at a HITL ticket is a reason of its own. It could adopt Children later with nothing new in Naiad.

One Entry can now become many concurrent Sessions. That is what makes Capacity necessary (ADR 0061), and it is why a completed Child's Session is closed rather than kept (ADR 0062).
