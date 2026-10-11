# The Predecessor is resolved from the Queue

Status: ready-for-agent
Blocked by: 04-a-supervisor-drives-the-queue-in-order
Spec: `.scratch/queue/PRD.md`

## What to build

An Entry that pins no base stands on the work before it. Queue two Entries against one repository, let the Supervisor run them, and the second Run's branch is cut from the first's rather than from the base branch — so the second agent sees the code the first wrote.

**The rule.** The Entry's pinned base if it has one; otherwise the Working branch of the nearest preceding Entry *for the same target repository*; otherwise nothing.

**Repository scoping is the part that is easy to get wrong.** The Queue is global and spans every project, so a Queue interleaving two repositories would otherwise hand a Run a branch name that does not exist where it is standing — the agent runs the ancestry test, gets nothing useful, and quietly bases on the base branch. Silently wrong exactly when the global Queue is used as intended. So Entries for other repositories are walked over.

**Entries for the same repository are never walked over.** Naiad does not skip one on the grounds that its work has already landed, because that is a question about git and the answer belongs to the agent (ADR 0015). The stack collapses correctly without Naiad knowing anything: an Entry built on the one before it carries that one's commits, so merging it carries them into the base branch too, and by the time a later Entry runs the ancestry test the whole chain below it is already there.

**Removed Entries are absent from disk and so are naturally passed over.** That is the intended consequence of removing one rather than an accident — dropped work should not be in the stack — and it means removing an Entry after it has run is a real decision rather than tidying.

**Resolution happens when an Entry starts, not when it is queued,** because Entries may be added or removed in between.

Stacking is the default because the two failures are not symmetrical. Stacking unnecessarily couples unrelated pull requests and costs review friction over work that is nonetheless correct; not stacking when the work depends means the second agent never sees the first's code, may build the same thing differently, and the conflict surfaces at merge, after the night is spent.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] An Entry with a pinned base takes it, whatever precedes it
- [ ] An Entry with no pinned base takes the Working branch of the nearest preceding Entry for the same repository
- [ ] Entries for other repositories are walked over when resolving
- [ ] The first Entry for a repository resolves to no Predecessor
- [ ] An Entry whose immediate predecessor was removed takes the one before it
- [ ] An Entry for the same repository is never skipped on the grounds that its work may have landed
- [ ] The smoke document covers a two-Entry Queue in one repository where the second Entry's branch is cut from the first's
