# The matt-pocock loop spawns per ready ticket

Status: resolved
Blocked by: 03, 08
Spec: `.scratch/children/PRD.md`

## What to build

The shipped matt-pocock Workflow uses Children, as ADR 0063 decided. The change is Prompt prose in the Workflow file plus documentation. Naiad learns nothing about tickets.

**`implement`** gains `join = true`. It keeps `clear = true` and its next-States. Each pass does three things, in order.

1. **Take in** each Child its `{children}` slot names.
   - A completed Child: merge its ticket branch into the Working branch, and merge any companion ticket branch into that companion's feature branch, creating it on first need. Run the tests, remove its worktrees, and delete its branches with `git branch -d`. The Parent resolves a merge conflict itself, with tests, or hands over when it cannot.
   - A cancelled Child: remove its worktree, keep its branch, and set the ticket aside for handover by name.
2. **Scan**, treating `claimed` as open. For every open ticket that is unblocked and ready-for-agent:
   - set it `claimed` and commit that on the Working branch;
   - cut `<working-branch>--<NN>` into a sibling worktree named `<repo>-wt-<working-branch-slug>--<NN>`;
   - copy in the untracked setup the repository needs (`.env` files, or its README's setup step);
   - spawn it at `build`, with the ticket as Subject and the Working branch as base.

   Never have more Children in flight than the `children` key in `.matt-pocock.toml` allows.
3. **Route.**
   - A needs-triage ticket goes to `triage`.
   - With Children in flight, announce `implement`.
   - Any other status, once nothing is in flight, goes to `handover`.
   - With no open ticket and nothing in flight, go to `pull-request`.

**`build`** is a new State. It sits after the Terminal State, is entered only by name, and has `clear = false`. In order, it:
- clones dependency directories from the Parent's checkout copy-on-write (`cp -c -R` on macOS, `cp -R --reflink=auto` on Linux), then runs the install;
- runs `/implement {subject}` on its own branch;
- for a ticket that reaches a companion, works in a sibling worktree of the companion, on a branch named the same as its ticket branch and cut from the companion's feature branch, or from its base when that feature branch does not exist yet;
- sets the ticket resolved, commits, and announces `done`.

Its Prompt also forbids leaving watchers or dev servers running, and forbids tests that need a service the other Children share unless the repository allows it.

**Other States:**
- `tickets` announces `implement` with no subject.
- `triage` announces `implement` with no subject for a ready-for-agent ticket.
- `pull-request` sweeps first: `git worktree prune`, then deletes any `<working-branch>--<NN>` branches already merged into the Working branch.

The workflow-authoring documentation describes Spawn. It also documents the `children` key under the project-file settings.

## Acceptance criteria

- [ ] The shipped-workflow invariant tests pass with `build` and the Join State present: every Prompt renders with no slot left, and every exit is named.
- [ ] The docs-drift test passes.
- [ ] Manual smoke run, on a scratch repository with a ticket set made of two independent tickets and a third blocked by both:
  - the two independent tickets build at the same time in sibling worktrees;
  - the third is spawned only after both are merged;
  - worktrees and ticket branches are gone at the end;
  - `pull-request` is reached once.
- [ ] Manual smoke run: `children = 1` in `.matt-pocock.toml` builds the same set one ticket at a time.
- [ ] Manual smoke run: cancelling one Child mid-build leads to a handover naming its ticket, with its branch kept and its worktree removed.
- [ ] Refactor: candidates considered (e.g. the scan-and-route paragraph now shared by `implement`, `triage` and `tickets`) and a verdict recorded.

## Comments

- Refactor verdict. Candidates: (1) the scan-and-route paragraph shared by `implement`, `triage` and `tickets` — **collapsed**: `tickets` now only announces `implement`, and `triage` routes only to another needs-triage ticket or back to `implement`, so flight-aware routing lives in `implement` alone; (2) the companion definition and the `<working-branch>--<NN>` naming repeated across `implement`, `build` and `pull-request` — **keep**: each State starts after a Clear or in a fresh Child and must stand alone; (3) the shipped-workflow test's literal slot list — **tidied** to import the renderer's named placeholders where they exist.
- Manual smoke runs (parallel set, `children = 1`, cancelled Child) not executed by the agent; the procedure is written into the maintainer smoke doc as Run 5.
