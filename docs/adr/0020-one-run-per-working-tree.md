# One Run per working tree

> Revised by ADR 0061.

The Queue was strictly sequential: one Run live on the machine, everything else waiting behind it. ADR 0012 gave the reason and it was never the Queue — it was the working tree, because two agents driving one checkout fight over the index, the branch and the build. But the Queue is global across repositories, and the rule was broader than its reason: a Run in one repository made an Entry for a different repository wait, though the collision the rule exists to prevent cannot happen between two checkouts.

We decided the exclusion unit is the working tree, named by the Entry's normalized `target_repo` path. The Queue stays one per machine and strictly id-ordered within a path; different paths run concurrently. Two worktrees of one repository are two working trees and run side by side, which is not a loophole but the rule meaning what it says — and it is the line the Predecessor rule already draws, since it too compares paths and never asks git what they have in common (ADR 0015). Enqueue already resolves the path to one spelling, so one tree cannot appear as two lanes.

What this is not: concurrency within a checkout. Two Entries for the same path still run one after the other, and stepping over a parked one still means worktree-per-Run machinery that remains deferred exactly as ADR 0012 left it. Stacking survives untouched for the same reason it works at all — same-path Entries are still sequential, so an Entry built on the one before it still finds that one's commits.

One Supervisor drives all of it. The single process and its single advisory lock survive (ADR 0014) — the alternative, a Supervisor per repository, breaks the following Queue, because an Entry for a repository with no Supervisor sits forever, and fixing that means a supervisor of Supervisors, which is one Supervisor with extra steps. Its scan yields one Action per path instead of one Action total, and the loop ticks every live Run once per pass rather than blocking in a watch — driving a Run was always repeated calls to a pure tick, so the interleaving hoists the loop a level without threads or child processes, and the decision core keeps its shape (ADR 0004). Threads were rejected because Ctrl-C, the lock's lifetime and the operator's terminal would all cross them; subprocesses because a parent managing children is the pid reconciliation the advisory lock was chosen to avoid.

There is no cap on how many paths run at once. Concurrency is bounded by what the operator queues, which they chose deliberately when they wrote the batch file; if rate limits ever bite, a cap is one counter in the scan, and starting without one keeps the scan a single rule.

## Consequences

A parked Run blocks only its own lane. ADR 0012's title narrows to the lane and its reasoning survives verbatim; a Queue of five across three repositories parked at `review` in one of them keeps working in the other two, which is the cost that ADR accepted now being paid only where its reason applies.

Drain mode exits when every lane is drained, and a following Supervisor idles only when no lane has anything to do. `naiad run` keeps its adopt-or-become meaning unchanged.

Runs in different lanes report into one terminal and their lines interleave. The lines already name their Entry, so this is noise rather than ambiguity, and the honest cost of one process rather than one window per lane.
