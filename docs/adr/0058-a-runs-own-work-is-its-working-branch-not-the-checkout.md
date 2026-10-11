# A Run's own work is its Working branch, not the checkout

ADR 0051 stopped the tail reading a companion's work off what its path has checked out, and left the Run's own repository reading exactly that. The `pull-request` Prompt never received the Working branch: it opened "its branch", which in practice meant whatever the target repository's checkout stood on when the tail began. The `implement` Prompt did not receive it either, so each ticket was committed to whatever was checked out when its Session started.

Observed: a Run declared its Working branch at `grill` and began its ticket queue in the target repository's main checkout. Midway, the operator started a second feature by hand in that same checkout, branching from it, so the checkout now stood on the operator's branch and that branch held the Run's first four tickets. The remaining tickets were moved to a second worktree by a note written into a ticket, because nothing in the Prompt said where they belonged. When the queue ran out, the tail looked at the main checkout, found the operator's branch with six of its seven commits answering the Run's task, judged it the Run's work, and opened the pull request from it. The Run's last three tickets, and the frontend branch paired with them, got no pull request at all, and nothing said so until someone went looking eleven days later.

A checkout is shared. The operator, another Run on the same repository, or the Run's own earlier tickets can all leave it on a branch that is not the Run's. The Working branch is the one fact Naiad holds about where the Run's work lives (ADR 0022), and it is the only reading that does not change under the Run's feet.

We decided the Working branch is delivered to every State that commits or ships the Run's work, and each of them acts on that branch wherever it is checked out. `implement` finds the worktree that has the Working branch checked out and works there; it checks the branch out here if no worktree has it; it hands over rather than create the branch from whatever is checked out. The tail pushes and opens from the worktree that has the Working branch, and asks the human before opening anything when the branch is missing, undeclared, or carries commits that do not answer the Run's task.

## Considered alternatives

**Having Naiad check out the Working branch before each delivery** would need no Prompt change, but Naiad knows no git (ADR 0015) and a checkout can hold uncommitted work that is not Naiad's to move.

**Weighing every branch of the Run's own repository, as 0051 does for a companion** would find the right branch in the observed case, but it guesses at something Naiad already knows, and the guess is the step that went wrong.

**Refusing to start a Run in a checkout that stands on another branch** would not have helped: the checkout was switched after the Run started.

## Consequences

A Run that entered at `implement` without a Working branch now derives and declares one before its first ticket, as a head State does, because the announce command refuses a branchless Run once a Prompt carrying the branch has gone out.

Two features in one checkout are still a hazard for the humans involved. The Run no longer follows the checkout, but an operator who branches from a checkout mid-Run still takes the Run's commits with them, and the tail's Question is where that surfaces.
