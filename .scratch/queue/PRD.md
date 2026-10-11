# Naiad v2 — The Queue

Status: ready-for-agent

## Problem Statement

Naiad drives one Run to completion without a human at each boundary, but it still needs a human at the start of every Run. Work arrives faster than that: an operator finishes a design session with five tickets in hand, or a morning's triage produces three bugs and two features, and every one of them has to be launched by hand at the moment there is a free session to launch it into. So the thing that made a Run unattended — hand it off and go to bed — does not extend to a *night's* work. The operator is back to being the scheduler.

Two smaller frictions come with it. Launching means describing the Run in shell arguments at a terminal, when the person who best understands the task is often an agent in a session that has just finished exploring it. And nothing in Naiad puts a Run on its own git branch: the shipped Workflow's `/implement` commits to whatever branch is checked out and `/hcgps-pr` refuses to open a pull request from `develop`, so a Run assumes someone has already prepared a branch for it. Run several pieces of work in sequence and that preparation — which branch, based on what — becomes a decision per Run that nobody has written down.

## Solution

A Queue: an ordered backlog of Entries, where an Entry is a Run that does not exist yet. One Queue per machine, spanning every repository, taken strictly in order. Exactly one Run is ever live, so there is never more than one agent working in a repository.

A Supervisor takes the first waiting Entry, starts its Run, watches it to a Terminal State, and moves on to the next. It holds a lock for its whole life, which is what makes one-at-a-time structural rather than a rule anyone has to remember. `naiad run` stops spawning a session directly and becomes the way to add one Entry and, if nothing is supervising yet, to supervise — so there is one entrance to starting Runs rather than two (ADR 0014).

Entries are added one at a time or as a batch file, and pre-classified by naming the State they start at — `grill` for a design, `diagnose` for a bug, nothing at all to let the Workflow's classifying State decide. That is the Workflow's own vocabulary rather than a category Naiad has learnt (ADR 0005).

Each Entry carries a Working branch, and Naiad hands each Run the Predecessor its work stands on — the Entry's pinned base, or the Working branch of the preceding Entry for the same repository. Whether to actually stand on it is decided in the Prompt by the agent, which can see whether that work has already landed. Naiad passes branch names around as opaque strings and knows no git (ADR 0015).

A Run that parks — a Gate State, an Escalation, a silent agent — blocks the Queue until a human deals with it. That is the honest consequence of one working tree, and stepping over it is deferred until Runs execute in worktrees (ADR 0012).

## User Stories

1. As an operator, I want to queue several pieces of work at once, so that a night runs a backlog rather than a single Run.
2. As an operator, I want the Queue taken in order without me, so that work queued in the evening is finished by morning.
3. As an operator, I want exactly one Run live at a time, so that two agents never work in the same checkout.
4. As an operator, I want one Queue across all my repositories, so that I never have to ask which Queue something went into.
5. As an operator, I want to add a single Entry with one command, so that queueing a one-off is no harder than starting a Run used to be.
6. As an operator, I want to add many Entries from a batch file, so that I can review a night's work as one document before committing to it.
7. As an operator, I want a batch file rejected whole if any Entry in it is malformed, so that a typo does not leave me with a half-queued night.
8. As an operator, I want each Entry in a batch to be able to differ, so that three bugs and two designs can be queued in one file.
9. As an operator, I want shared settings at the top of a batch file, so that five Entries against one repository do not repeat the same three fields.
10. As an operator, I want to pre-classify an Entry by naming the State it starts at, so that work I have already classified skips the classifying State.
11. As an operator, I want an Entry with no start State to begin at the Workflow's first State, so that unclassified work is the default rather than a special case.
12. As an operator, I want `naiad run` to start supervising when nothing else is, so that a cold terminal needs one command rather than two.
13. As an operator, I want `naiad run` to return immediately when something is already supervising, so that adding work never blocks on work already running.
14. As an operator, I want a second Supervisor refused, so that two of them cannot each take the next Entry and put two agents in one checkout.
15. As an operator, I want the lock released when the Supervisor dies, so that a crash or a `Ctrl-C` leaves nothing to clean up.
16. As an operator, I want `naiad run` to drain the Queue and then exit, so that I get my prompt back rather than having to remember to interrupt it.
17. As an operator, I want a Supervisor I can start in follow mode, so that Entries added later are picked up without me starting anything again.
18. As an operator, I want to list the Queue and see what each Entry is and what became of it, so that I can tell at a glance where the night got to.
19. As an operator, I want to remove an Entry that has not run, so that something queued by mistake can be un-queued.
20. As an operator, I want removing an Entry to leave its Run and session alone, so that removal is a Queue operation rather than a destructive one.
21. As an operator, I want a parked Run to hold the Queue, so that a Run needing me is not built on top of by the next Entry.
22. As an operator, I want to release a parked Run by typing into its session, so that ending it uses the same escape hatch as every other intervention.
23. As an operator, I want an interrupted Supervisor to pick up where it left off, so that restarting it does not restart the Run it was watching.
24. As an operator, I want the Queue to survive the Supervisor being killed, so that stopping the machine pauses the night rather than losing it.
25. As an operator, I want each Entry's work on its own branch, so that Runs do not pile commits onto one branch or onto `develop`.
26. As an operator, I want the branch named by whoever creates the Entry, so that it follows my repository's convention rather than a name Naiad invented.
27. As an operator, I want an Entry with no Working branch refused when I add it, so that I find out standing at the terminal rather than at three in the morning.
28. As an operator, I want two queued Entries refused if they name the same Working branch in the same repository, so that one Entry's work cannot silently land on another's branch.
29. As an operator, I want each Entry's work to stand on the previous Entry's by default, so that a later Entry sees the code an earlier one wrote.
30. As an operator, I want an Entry to be able to pin its own base, so that work unrelated to what came before is not stacked onto it.
31. As an operator, I want the Predecessor taken from the last Entry for the same repository, so that interleaving projects in one Queue does not hand a Run a branch from somewhere else.
32. As an operator, I want the decision to stack made during the Run rather than when I queue it, so that an Entry whose predecessor landed while it waited starts from the base branch instead.
33. As an operator, I want Naiad to run no git commands itself, so that it cannot corrupt a repository it does not understand.
34. As an operator, I want an invalid Workflow, an unknown start State or a missing Subject refused when I add an Entry, so that every failure that used to happen at kickoff now happens at enqueue.
35. As an operator, I want a Run's record to say which Working branch and Predecessor it was given, so that a strange result can be traced back to the branch it was built on.
36. As an operator, I want to run an Entry with Gates skipped, so that routine review points do not park an unattended night.
37. As an operator, I want Gates the agent chose as a destination to park the Queue anyway, so that `handover` still means a person is genuinely needed.
38. As an operator, I want to be notified when the Queue is blocked, so that being needed is something I learn rather than discover.
39. As an agent in a session, I want to add an Entry without becoming a Supervisor, so that queueing work never blocks the turn I am in.
40. As an agent in a session, I want to write the Working branch into the Entry, so that the branch follows the repository's convention that I can read and the operator would have to recall.
41. As an agent in a Run, I want to be told my Working branch and my Predecessor in the Prompt, so that I can prepare the branch without knowing that a Queue exists.
42. As an agent in a Run, I want the branch instruction to be safe to repeat, so that a Run resumed or re-entered does not fail on a branch that already exists.
43. As a workflow author, I want `{branch}` and `{predecessor}` available in every Prompt, so that a State that Clears can still name the branch it is working on.
44. As a workflow author, I want to decide in the Prompt whether to stand on the Predecessor, so that the rule stays with the repository's conventions rather than inside Naiad.
45. As a maintainer, I want the Queue's rules in one pure function, so that they are tested as data in and Action out like every other rule.
46. As a maintainer, I want the Entry to record no status of its own, so that nothing the Queue holds can contradict the Run it describes.
47. As a maintainer, I want the Supervisor to hold no Run of its own, so that a concurrent Queue later is an addition rather than a rewrite.
48. As a maintainer, I want Entries addressed by id rather than position, so that removing one renumbers nothing.
49. As a maintainer, I want the Queue layered above the engine, so that the engine stays ignorant of the Queue as it is ignorant of any Workflow.

## Implementation Decisions

### What an Entry is

An Entry carries everything kickoff would otherwise be told, and one field recording what became of it:

- the Workflow file, the task, the target repository
- the Working branch — **required**
- an optional pinned base, an optional start State, an optional Subject, whether Gates are skipped
- the id of the Run it became, absent until it starts

It records nothing else. Whether it is waiting, running, parked or done is read from the Run, which already holds all four (ADR 0013): no Run means waiting, a finished Run log means done, a notice recorded against the current Announcement means parked, anything else is running.

The id is a sortable timestamp built the way a Run id already is, so sorting by id *is* the Queue order and no Entry holds a position.

### Storage

The Queue lives beside the Runs, under the same Naiad-owned root and honouring the same environment override, one file per Entry named by its id. It is never written into a target repository, for the reason a Run's directory is not.

Entries are serialised as JSON, like a Run's metadata. The batch file is TOML, like a Workflow, because it is written by a person or an agent rather than by Naiad.

### The Supervisor and its rules

The Supervisor's rules live in a single pure function in the domain layer, mirroring the decision function the engine already has: signals in, Action out, reading no file and running no subprocess (ADR 0004). Its signals are the Entries in order, which of their Runs have finished, and whether it is following or draining. Its Actions are:

- **Start** an Entry — carrying the Predecessor resolved for it, so that resolution is part of the decision rather than a second thing the loop works out
- **Resume** an Entry whose Run exists and has not finished
- **Drained** — nothing waiting, nothing running, and not following
- **Idle** — nothing to do, come round again

The rule is one scan: take the Entries in id order, find the first that is not done; if it has a Run, Resume it; otherwise Start it. If every Entry is done, Drained or Idle by mode.

That single rule produces three behaviours without special cases. Sequential ordering, because the scan stops at the first unfinished Entry. Blocking on a parked Run (ADR 0012), because a parked Run is not finished, so the scan keeps returning Resume — and watching a Run already never returns while it is parked. And crash recovery, because a restarted Supervisor finds the same Entry and watches its Run again, which the existing watch handles correctly in both directions.

The wiring layer around it holds no rules: it gathers the signals, calls the function, and either starts a Run and watches it, watches one, sleeps, or returns.

### Resolving the Predecessor

Resolved when an Entry starts rather than when it is queued, because Entries may be added or removed in between. The rule: the Entry's pinned base if it has one; otherwise the Working branch of the nearest preceding Entry with the same target repository; otherwise nothing.

Entries for other repositories are walked over — a branch name from another repository is not a fact about this one — but Entries for the same repository never are. Naiad does not skip a same-repository Entry on the grounds that its work has landed, because that is a question about git and the answer belongs to the agent (ADR 0015). Removed Entries are absent from disk and so are naturally passed over, which is the intended consequence of removing one.

### Reaching the Run and the Prompt

A Run gains the Working branch and the Predecessor, copied from the Entry when it starts and recorded in its metadata. They are Run-level facts like the task, so they are interpolated into **every** delivered Prompt rather than only the first, and survive a Clear.

Prompt rendering gains `{branch}` and `{predecessor}` alongside `{task}`, `{next_state}` and `{subject}`, with the same substitution discipline: only placeholders Naiad defines are replaced, an absent value renders as nothing rather than raising.

Once started, a Run is self-contained: nothing during it consults the Queue.

### One entrance, and the lock

`naiad run` adds one Entry and then adopts or becomes: if a Supervisor holds the lock it returns immediately, and if none does it becomes the Supervisor in the foreground, draining and exiting. This replaces spawning a session directly (ADR 0014).

`naiad queue add` adds an Entry and **never** supervises. This is the command an agent inside a session uses, and the distinction is what stops a session's tool call from becoming a process that blocks for hours.

The lock is an advisory file lock held for the Supervisor's life, so the kernel releases it when the process dies and there is no stale record to reconcile. It is an adapter and holds no rules.

`naiad watch` continues to drive a single named Run, and refuses while the lock is held — because the Queue is sequential, a held lock means the Supervisor is driving the only live Run, and two tickers on one Run would deliver everything twice.

### Command surface

- `naiad run <workflow> <task> --branch B [--repo] [--at] [--subject] [--base] [--skip-gates]` — add one Entry, then adopt or become
- `naiad queue add …` — the same options, plus `--file <batch.toml>`; never supervises
- `naiad queue watch` — supervise in follow mode
- `naiad queue list` — the Entries in order, each with what became of it
- `naiad queue rm <entry-id>` — remove an Entry

### Validation at enqueue

Everything that could fail at kickoff now fails at enqueue, before the Entry exists, on the principle the existing missing-Subject check established: the operator is standing there and pays the error message only. An enqueue is refused when the Workflow file is invalid, the start State is not declared by it, the start State's Prompt names a Subject and none was given, the Working branch is missing, or another queued Entry for the same repository already claims that Working branch.

A batch file is validated whole and rejected whole, naming the file and the offending Entry's position the way Workflow parsing names a State's. Top-level keys act as defaults for every Entry; per-Entry keys override them.

### The shipped Workflow

`matt-pocock.toml` changes in two places, and only in Prompt prose — no new States.

The `grill` and `diagnose` Prompts each gain a paragraph that checks out `{branch}`, creating it if absent, based on `{predecessor}` when that branch is not yet an ancestor of the repository's base branch and on the base branch when it is. It goes at both branch heads rather than in a State of its own, because a State of its own would be skipped by exactly the Entries that pre-classify; the classifying State writes nothing and needs none, and a checked-out branch survives the Clear both heads perform.

The `pull-request` Prompt gains the base: it applies the same ancestor test again — the Predecessor may have landed during the Run — and passes the result to the pull request skill, which already accepts an explicit base for stacked work.

## Testing Decisions

Work test-first throughout: **Red** — write a failing test for the intended behaviour and confirm it fails for the expected reason; **Green** — the minimal code to pass; **Refactor** — improve with tests green, naming the refactor candidates considered and recording a verdict even when the verdict is to keep as-is. Where a unit test is not possible the Refactor check still happens and verification is by manual smoke.

A good test here asserts external behaviour only: given these Entries and these finished Runs, this Action. Never how the decision was reached. A test that breaks on an internal rename is testing the wrong thing.

### The seam

**One new seam: the Queue decision function.** It is the highest point available and it is the same seam the engine's rules already use, so the Queue adds a sibling rather than a new kind of test. Resolving the Predecessor is deliberately *not* a second seam — it is returned on the Start Action, so the rule that picks an Entry and the rule that decides what it stands on are exercised by one table of cases.

Cases to cover, all as plain data with no tmux, no subprocess and no clock:

- an empty Queue drains when draining and idles when following
- the first Entry with no Run starts
- an Entry whose Run has not finished resumes, and the next Entry is *not* started — the sequential rule and the parked-blocks-the-Queue behaviour are the same case
- every Entry done drains, or idles when following
- a restarted Supervisor resumes the same Entry rather than starting the next
- the Predecessor is the pinned base when one is set
- the Predecessor is the nearest preceding Entry for the same repository, skipping Entries for others
- the Predecessor is absent for the first Entry in a repository
- an Entry whose predecessor was removed takes the one before it

### Existing seams reused

**Parsing and validation**, in the shape Workflow parsing is already tested: a well-formed batch file produces the expected Entries; a malformed one is rejected naming the file and the position; top-level defaults are applied and overridden. The enqueue refusals — missing Working branch, duplicate Working branch in a repository, unknown start State, missing Subject, invalid Workflow — belong here, tested against a temporary Naiad root.

**Loop termination**, in the shape the watch loop is already tested, with sleep and reporting injected so no test waits on a clock: draining exits, following does not, and a Start is followed by watching the Run it created. The existing tests use an interrupt exception to show that a loop meant to keep ticking keeps ticking; the same device applies.

**Round-tripping**, extending the Run store tests: a Run saves and reloads its Working branch and Predecessor, and a Run written before they existed still loads.

**Prompt rendering**, extending the existing prompt tests: the two new placeholders substitute, absent values render as nothing, and text that merely looks like a placeholder is left alone.

### Manual smoke only

The lock adapter, the Supervisor against a real Queue, and the Workflow's new Prompt prose. The last is the important one and it is a prediction until it is run: the branch paragraph and the base test are instructions to an agent, and ADR 0006 already records that Prompt behaviour is unverified until a smoke run says otherwise. Extend the existing smoke document with a two-Entry Queue whose second Entry stacks on the first.

### Seams rejected

- **A fake git.** There is nothing to fake: Naiad runs no git commands. The ancestor test lives in a Prompt and is exercised by the smoke run.
- **Two real Supervisors racing for the lock.** Flaky, slow, and the lock adapter holds no rules — what would be asserted is the operating system's.
- **An end-to-end Queue over a fake tmux.** Rejected for the reason the engine's spec already recorded: fakes have to stay honest to be worth anything, and green tests over a system that does not work is the specific failure being avoided.
- **Status transition tests.** There is no status to transition (ADR 0013); asserting one would invent the field the design refused.

## Out of Scope

- **A non-sequential Queue.** Stepping over a parked Run needs a worktree per Run (ADR 0012). The three properties that keep it possible — Entries addressed by id, no Run held by the Supervisor, parked distinguishable from running — are in scope; the feature is not.
- **Concurrent Runs and worktrees.** Same reason, same deferral.
- **Per-repository Queues.** The global Queue plus a filter and a second Supervisor, and a bigger claim than one-at-a-time.
- **Priority, reordering, and front-insertion.** FIFO with append. `--next` is one comparison key away if it is missed.
- **A Batch as a domain concept.** A batch file produces N Entries and the Queue does not know they arrived together. Cancelling or reporting on a batch would make it a concept; nothing asks for that yet.
- **Naiad knowing git or GitHub.** No branch creation, no merge queries, no pull request state.
- **Deriving a Working branch.** No slug, no prefix; the field is required (ADR 0015).
- **Detecting an abandoned Predecessor.** A pull request closed without merging is not an ancestor of the base, so the next Entry stacks on it. Accepted; the pinned base is the answer when it happens.
- **Retrying or re-running a failed Entry.** A Run that ended badly is dealt with in its session, or a new Entry is queued.
- **Starting a Run from inside an existing session.** Still deferred; adding an Entry from a session needs nothing built, adopting one does.
- **Any display beyond a list.** No dashboard, no TUI, no progress rendering.

## Further Notes

The `--skip-gates` mitigation is load-bearing and unverified. ADR 0012 accepts blocking partly because Gates on the declared path can be skipped, leaving only the Gates a Branching State named as destinations — `handover`, `no-repro` — to park an unattended Queue. That is gate-skipping working as designed, and it has never run for real. If it behaves differently in practice, blocking is a worse trade than the ADR argues.

The rules that matter most now live in Prompt prose. The base test, the idempotent checkout, and passing the base to the pull request skill are instructions an agent must read correctly, exactly like every other rule in the Workflow file. The difference is the blast radius: a misread here corrupts the *next* Entry's stack rather than only its own Run, and the symptom appears at review time.

Because Runs share one working tree and a finished Run's session is deliberately left alive, an old session typed into after the Queue has moved on is operating on the wrong branch. This is the price of one working tree and the same worktree work is the eventual answer to both it and the non-sequential Queue.

Four ADRs cover the decisions behind this spec and should be read before implementing: `0012-a-parked-run-blocks-the-queue`, `0013-the-queue-records-no-status-of-its-own`, `0014-one-entrance-to-starting-runs`, `0015-naiad-carries-branch-names-not-git-knowledge`. The glossary terms they use — Queue, Entry, Supervisor, Working branch, Predecessor — are defined in `CONTEXT.md`, and `Working branch` is deliberately distinct from `Branch`, which means a path through a Workflow.
