# The implement loop spawns a Child per ready ticket

> Builds on ADR 0060, ADR 0061, ADR 0051 and ADR 0058. Amended by ADR 0066.

ADR 0060 gave Naiad Spawn and the Join State and left tickets, edges and git to the Workflow. This is what the matt-pocock Workflow does with them. Until now `implement` did one ticket per Announcement in one Session, scanning for the next lowest-numbered ready ticket after each. A feature whose tickets mostly do not block one another took as long as all of them added together.

## `implement` coordinates; `build` does a ticket

`implement` becomes the Parent's Join State, and it no longer implements anything. Each pass does three things, in order:

1. **Take in** every Child the `{children}` slot names. A completed one has its ticket branch merged into the Working branch, the tests run, its worktree removed and its branch deleted with `git branch -d`. A cancelled one has its worktree removed and its branch kept, and its ticket goes to handover by name, since a person stopped it for a reason the loop cannot know.
2. **Scan.** A ticket is spawned when it is open, its blocking edges are all satisfied, and its Status reads ready-for-agent. Every such ticket is spawned in the same pass, not only the lowest-numbered one.
3. **Route.** A needs-triage ticket on the frontier goes to `triage`, which stays in the Parent and ends with the same scan. Any other status goes to handover, but only once nothing is in flight, so one ticket waiting on a person does not stop the others. With Children in flight, the Parent announces `implement` again and is held there. With no open ticket left and no Child in flight, it announces `pull-request`.

`build` is a new State, entered by name and placed after the Terminal State beside the Wayfinder loop. Its Prompt is `/implement {subject}`, set the ticket's Status to resolved, commit, and announce `done`. It works in its own worktree and on its own ticket branch, and it knows nothing about the other tickets. Its Prompt pins two things: no watchers or dev servers left running, and no tests that need a service the other Children share unless the repository says they may share it.

`tickets` now announces `implement` without picking a ticket, because `implement` with no Children is delivered at once and does its own scan.

## The claim is committed before the branch is cut

Before spawning, the Parent sets the ticket's Status to `claimed` and commits that on the Working branch. Then it runs `git worktree add -b <working-branch>--<NN> <path> <working-branch>`, where `NN` is the ticket's number. The Parent's context is Cleared every pass, and the ticket files are the only memory it has (ADR 0001). Without the claim, the next pass would see the ticket as ready and spawn it again. The scan treats `claimed` as open, so a feature with Children in flight never reads as finished.

The Child sees its own ticket as `claimed` and changes it to `resolved`. The Parent never touches that line again, so the merge is clean. Two tickets are two files, so siblings do not conflict over their Status lines. Where their code conflicts, the Parent resolves it during the merge and runs the tests. If it cannot, it hands over.

## Where a Child's worktree lives

A Child's worktree is a sibling of the repository's checkout: `<repo>-wt-<working-branch-slug>--<NN>`, next to `<repo>`. For example, `tatallo-backend-core-wt-feat-partner-transfers--03` sits next to `tatallo-backend-core`. This is the convention the maintainer already uses by hand. A person checking out a ticket branch, or looking at what a Run left behind, finds it by eye in the same directory as the repository.

Being outside the checkout is what keeps the worktree from being anything else. It is not an untracked directory in the repository's status. `git add -A` cannot embed it as a gitlink. Test runners, type checkers, linters and file watchers rooted at the repository do not walk into a second copy of the source. No repository needs an exclude line for it.

## Making a worktree usable

A fresh worktree has the tracked files and nothing else. The Parent copies in what the repository needs but does not track, such as its `.env` files or whatever its README names as a setup step, when it cuts the worktree. The Child clones the dependency directories from the Parent's checkout copy-on-write (`cp -c -R` on APFS, `cp -R --reflink=auto` on Linux) and then runs the repository's install, which only has to reconcile the difference. Git's objects are already shared between worktrees. So a Child costs its checked-out source plus whatever its install changed, and not a second set of dependencies.

A repository that cannot take many Children at once, for example because its tests share one database, says so with a `children` key in its `.matt-pocock.toml`. The Parent never has more than that many in flight. That limit belongs to the repository. The Entry's Child limit (ADR 0060) belongs to the operator, and Capacity (ADR 0061) belongs to the machine. All three apply.

## Companions

A Child whose ticket reaches a companion makes a worktree of the companion beside it, named the same way. The branch it uses there has the same name as its ticket branch. It is cut from the companion's feature branch, which carries the Working branch's name, or from the companion's base branch when that feature branch does not exist yet. At the Join, the Parent merges it into the companion's feature branch, creating that branch on first need. It then removes the companion worktree and deletes the ticket branch the same way it does here. The pull-request tail already weighs every branch of a companion (ADR 0051), so it finds the feature branch with nothing new to learn.

## Who cleans up

- **The Join State** removes everything a completed Child left: its worktrees here and in companions, and its ticket branches.
- **A cancelled Child** keeps its branch, so the person who stopped it can see how far it got. Only its worktree goes.
- **A cancelled Parent** cancels its Children (ADR 0060), and Naiad tells the operator which working trees are left. Naiad knows the paths but not what to do with them.
- **The pull-request tail** sweeps as a safety net before it opens anything. It runs `git worktree prune` and deletes any `<working-branch>--<NN>` branch that is already merged into the Working branch.

## Considered options

**Worktrees under `.git/`.** They are invisible to every tool and to the repository's status, and a session in the fixed permission mode can write there. Rejected, because a person cannot find them. Finder and most editors hide `.git`, and checking out a ticket branch by hand is exactly when someone goes looking.

**Worktrees under `.claude/worktrees/`, as Claude Code's own worktree tool makes them.** Rejected. They are inside the checkout, so every repository needs an exclude line, and test runners and watchers that do not honour the exclude walk into them. Two repositories here already exclude that path and two do not.

**Worktrees in an in-repository directory such as `.worktrees/`.** Rejected. It shows as untracked, and `git add -A` stages it as an embedded repository.

**The Child cutting its own worktree.** Rejected. The Parent would spawn first and claim later, so two passes could both spawn the same ticket. The Parent would also have no record of a path it never made.

**No claim, with the Parent asking Naiad which tickets are in flight.** Rejected. Naiad knows Subjects, not tickets, and ADR 0060 already turned down the Parent reading the Queue.

**Spawning in waves.** Rejected, because rolling is faster on uneven tickets (ADR 0060). A repository that wants one ticket at a time sets `children = 1`, which keeps the old order exactly.

## Consequences

The scan-and-route paragraph that ADR 0045 noted is repeated across States now appears in `implement`, `triage` and `tickets`, and the copies have begun to differ: only `implement` spawns. Keeping them aligned is a cost every edit to the loop pays.

A ticket in the middle of the set that is waiting on a person no longer stops the night. Everything not blocked by it is still built, and the handover comes when nothing else can move.
