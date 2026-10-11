# A companion is a repository, not a checkout

ADR 0048 had the tail find a companion's work by looking at the checkout its path names: a branch other than the base, commits ahead of it, contents that answer the Run's task. That reads *what the path has checked out*, and a path names one worktree of a repository, not the repository. Observed: a Run's frontend half sat finished in a second worktree of the companion, on its own feature branch, while the checkout at the configured path stood on an unrelated prototype branch. The tail looked at the prototype, judged it somebody else's work — correctly — and left the companion untouched. The backend pull request went up with a sentence in its body saying no frontend pull request existed yet, the Run announced `done`, and the finished half stayed unpushed.

Worktrees are the ordinary way to run several features of one repository side by side, which is exactly when a Run's work lands somewhere other than the main checkout. So the rule 0048 wrote was wrong for the common case, not an edge.

We decided the companion path names a **repository**, and the tail weighs every branch of it. It lists the repository's worktrees and local branches, applies 0048's test to each branch rather than to the checked-out one, and pushes and opens from the worktree that has the matching branch checked out. The judgment that a branch is somebody else's unfinished work stays where 0048 put it, per branch.

A second sentence closes the silence the failure produced. When this repository's own changes break what a companion reads and no companion branch carries the counterpart, the tail asks the human before opening anything. In the observed Run the break was known and written into the pull request body as a follow-up, which is prose nobody is assigned to; a Question parks the Run until a person has seen it.

## Considered alternatives

**Listing worktree paths in `companions`** would need no Prompt change, but a worktree is made per feature and removed when it lands, so the list would be wrong the next week and silently so, the failure 0048 rejected unaided discovery for.

**Matching branch names across repositories** was rejected in 0048 and stays rejected: the halves of one feature need not share a name.

## Consequences

The tail now reads more of a companion than one `git status`, and may see several branches that each have commits ahead of base. It still opens only for a branch whose contents answer this Run's task, and says in the session which branches it weighed, so a wrong pick is visible rather than silent.

Work on a branch with no worktree gets pushed without being checked out; opening from it needs no working tree, because the pull request is made from the branch.

The breaking-change Question makes a Run that knowingly ships half a contract stop rather than end. That costs a park on a Run that would otherwise have finished, which is the point.
