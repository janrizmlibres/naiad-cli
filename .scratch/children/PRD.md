# Children: a Run spawns Runs of its own, joins them, and the machine bounds how many start

Status: ready-for-agent

## Problem Statement

The matt-pocock implement loop takes a feature's tickets one after another, one Announcement each, in one Session. A long ticket set takes as long as all its tickets added together, even when most of them do not block one another, and a night's Queue that has not finished by morning has failed at the thing it was queued for. The operator wants independent tickets built at the same time.

Naiad cannot do this today without learning tickets, and it must not (ADR 0001, ADR 0015). It has no way for a Run to start other Runs, no way for a Run to wait for them, and no bound on how many Runs start at once (ADR 0020 deliberately has none). Lifting the last of those as things stand would let one Entry become a dozen Sessions on a machine that is already swapping because of the browser and editor. Separately, the Queue listing misreports a Run that is Held: it reads `running` when it is parked.

## Solution

Naiad learns two general ideas and nothing about tickets (ADR 0060):

- **Spawn**, the fifth Protocol verb. A Run enqueues an Entry as its own **Child** from inside its Session, and that Child runs in a working tree of its own, so in a Lane of its own, beside its Parent and its siblings.
- **Join State**, a State whose Prompt is held while the Run's Children are working. It is delivered once a Child has finished that the Parent has not yet been told of, with a `{children}` slot naming each such Child exactly once. It is delivered at once when no Child is unfinished. Holding is waiting, not silence, so nothing is Nudged.

An Entry may carry a **Child limit**. Parallel is the default.

The Supervisor starts Runs only within **Capacity** (ADR 0061). Capacity is a ceiling derived from the machine's memory unless the operator sets one, plus a check that memory pressure is normal and free disk is above the larger of 10% and 10 GB. Children count toward it. A Parent held at a Join State does not. Nothing already working is ever stopped.

A completed Child's Session is closed once its Parent has been told of it (ADR 0062). Cancelling a Parent cancels its Children.

The matt-pocock Workflow uses all of this (ADR 0063). `implement` becomes the coordinating Join State, which takes in finished Children, scans, spawns every ready ticket into a sibling worktree, and routes. A new `build` State does one ticket.

The Queue listing reads a Held Run as parked.

## User Stories

### Spawning

1. As an agent coordinating a feature, I want to spawn a Child from inside my Session with one command, so that independent work runs beside me without the operator queueing it.
2. As an agent spawning a Child, I want the command to resolve my Run the way `announce`, `wait` and `branch` do, so that I never carry or type my own Run id.
3. As an agent spawning a Child, I want to name its working tree, Working branch, pinned base, start State and Subject, so that the Child starts exactly where its work is.
4. As an agent spawning a Child, I want it to take my Workflow, my settings and whether Gates are skipped unless I name otherwise, so that a Child behaves like the rest of my Run.
5. As an agent spawning a Child, I want the Child's task to default to my own, so that I name only what differs.
6. As an agent, I want Spawn to return at once with the Child's Entry id and never supervise anything, so that my turn is not blocked.
7. As an agent, I want a Spawn whose Working branch another Entry in the same working tree already holds to be refused, exactly as `naiad queue add` refuses it, so that a Child is checked like any Entry.
8. As an agent, I want a Spawn naming my own working tree to be refused with the reason, so that I never create a Child that would wait behind me in my own Lane forever.
9. As an agent inside a Child, I want Spawn to be refused, so that a fan-out cannot spawn more fan-outs by accident.
10. As an agent outside any Run, I want Spawn to be refused with the same message the other Protocol verbs give, so that I know why.
11. As an agent whose Run has ended, I want Spawn to be refused, so that no Child is created that nobody will take in.
12. As an agent, I want Spawn's refusals to reach me as error messages inside my own turn, so that I can correct myself without stalling the Run.
13. As an agent reading the injected Protocol, I want it to describe Spawn alongside the other verbs, so that a Workflow author never has to explain it in a Prompt.

### Joining

14. As a Workflow author, I want to declare a State a Join State in the Workflow file, so that Naiad knows to hold its Prompt.
15. As a Workflow author, I want a `{children}` slot in a Join State's Prompt, so that the agent is told which Children finished and how.
16. As a Workflow author, I want a Workflow that uses `{children}` outside a Join State, or declares a Join State with no Prompt, to be refused when it is loaded, so that the mistake is caught before a Run starts.
17. As a Parent, I want my Join State's Prompt held while Children are working and none has finished untold, so that I am not woken to nothing.
18. As a Parent, I want it delivered as soon as any one Child finishes, so that I can take that work in and spawn whatever it unblocked while the others keep working.
19. As a Parent, I want each finished Child named by its Subject, Working branch, working tree and outcome (completed or cancelled), so that I can merge it and clean up after it.
20. As a Parent, I want every Child named exactly once across my Join deliveries, even across a Supervisor restart, so that no work is taken in twice or stranded.
21. As a Parent, I want a redelivery of the same Join Prompt to name the same Children it named the first time, so that a lost keystroke does not drop or duplicate a Child.
22. As a Parent with no unfinished Children, I want my Join State delivered at once with nothing named, so that the same State can make the first Spawn and notice the end.
23. As a Parent held at a Join State, I want no Nudge and no hang Notify, so that waiting on my Children is never mistaken for silence.
24. As a Parent, I want a Child that parks not to release my Join State, so that I am woken only for finished work.
25. As a Parent, I want a cancelled Child to reach me as cancelled, so that my Workflow can decide what to do about it.
26. As a Parent, I want an Announcement of a Terminal State refused while I still have unfinished Children, so that I cannot end and leave Children building work nobody will take in.

### Child limit

27. As an operator, I want to give an Entry a Child limit with `--child-limit N` on `naiad run` and `naiad queue add`, so that one feature can be held to fewer Children than the machine allows.
28. As an operator writing a Batch file, I want a `child-limit` key, both as a default at the top and per Entry, so that a night's backlog can carry it.
29. As an operator, I want no limit of the Run's own when none is given, so that parallel is the default.
30. As an operator, I want a Child limit of one to take the Children one at a time in the order they were spawned, so that I get the old serial behaviour without a mode.
31. As an operator, I want a Child over its Parent's limit to read `waiting` like any Entry waiting its turn, so that the listing tells the truth.
32. As an operator, I want a Child limit that is not a positive whole number refused at the entrance, so that a typo does not silently mean "no limit".

### Capacity

33. As an operator, I want the Supervisor to derive a ceiling from my machine's memory when it starts, so that a fresh install is safe with no configuration.
34. As an operator, I want to set the ceiling myself with a Supervisor option or an environment variable, so that I can run 20 on a machine I know.
35. As an operator, I want the option to beat the environment variable and both to beat the derived ceiling, so that the nearest instruction wins.
36. As an operator, I want a ceiling that is not a positive whole number refused when the Supervisor starts, so that a typo does not stop everything.
37. As an operator, I want no Run started while the operating system reports memory pressure above normal, so that Naiad does not push a swapping machine further.
38. As an operator, I want no Run started into a working tree whose volume has less free disk than the larger of 10% and 10 GB, so that worktrees and installs never fill the disk.
39. As an operator on a system that offers no pressure reading, I want the ceiling alone to apply, so that Naiad still works there.
40. As an operator, I want at most one Run started per Supervisor pass, so that the pressure reading can catch up before the next start.
41. As an operator, I want every live Run counted toward the ceiling, Children included, so that a fan-out cannot exceed what the machine was sized for.
42. As an operator, I want a Parent held at a Join State not counted, so that a ceiling of one cannot deadlock a Parent against its only Child.
43. As an operator, I want live Runs always ticked whatever Capacity says, so that nothing working is stopped and a released Parent is never held back.
44. As an operator, I want a Run waiting on Capacity to read `waiting`, so that the listing has no new word to learn.
45. As an operator, I want the Supervisor to say once why it is not starting anything (ceiling reached, memory strained, disk low), so that I can tell a full machine from a stuck Queue.
46. As an operator, I want the Sessions I started by hand left out of the count but felt through the pressure check, so that Naiad stays out of Claude Code's internals (ADR 0002).

### Sessions, cancellation, prune, listing

47. As an operator, I want a completed Child's Session closed once its Parent has been told of it, so that a thirty-ticket night does not leave thirty idle sessions eating memory.
48. As an operator, I want the Child's transcript, Run log and Answer log kept on disk when its Session closes, so that the evidence survives.
49. As an operator, I want a cancelled, parked or not-yet-told Child's Session left alive, so that I can type into what I stopped.
50. As an operator, I want a top-level Run's Session never closed, so that the escape hatch I rely on stays.
51. As an operator cancelling a Parent, I want each of its Children cancelled with it, both started and not yet started, so that no orphan builds unwanted work.
52. As an operator cancelling a Parent, I want to be told which Children's working trees are left for me to remove, so that I can clean up without hunting.
53. As an operator cancelling one Child, I want its Parent told of it as cancelled at its next Join, so that the Parent does not wait forever.
54. As an operator pruning, I want a done Child skipped while its Parent is live and has not yet been told of it, so that Prune never deletes what a Join is waiting to deliver.
55. As an operator pruning, I want a done Child pruned normally once its Parent has been told of it or its Parent has ended, so that nothing lingers forever.
56. As an operator, I want a Child found by its Parent even after a Cancellation or Prune removes its Entry, so that a Join never loses track of one.
57. As an operator reading `naiad queue list`, I want a Parent held at a Join State shown as `joining`, so that I can see it is waiting on its Children and not stuck.
58. As an operator reading `naiad queue list`, I want each Child listed indented under its Parent, so that a fan-out reads as one piece of work.

### The Hold reading

59. As an operator, I want a Held Run to read `parked` in `naiad queue list`, so that a Run waiting on me does not look like a Run working.
60. As an operator, I want a Run that parked after a Hold to read parked in a Prune's judgment of Orphaned Runs too, so that the listing and the Prune never disagree.

### The matt-pocock Workflow

61. As the operator of a feature, I want `implement` to spawn every ready-for-agent ticket whose edges are satisfied, not only the lowest-numbered one, so that independent tickets build at once.
62. As the operator, I want each finished ticket merged into the Working branch, with tests run, as soon as it finishes, so that work that was unblocked gets spawned while the others build.
63. As the operator, I want each spawned ticket claimed (`Status: claimed`) and committed on the Working branch before its branch is cut, so that a Cleared Parent never spawns the same ticket twice.
64. As the operator, I want each ticket's worktree as a sibling of the repository, named `<repo>-wt-<working-branch-slug>--<NN>` on branch `<working-branch>--<NN>`, so that I can find it by eye when I check a branch out.
65. As the operator, I want the Parent to copy into each worktree the untracked setup the repository needs (`.env` files or its README's setup step), so that a Child can build and test.
66. As the operator, I want each Child to clone dependency directories copy-on-write before installing, so that a worktree does not cost a second full set of dependencies.
67. As the operator, I want a `build` State that does one ticket with `/implement`, marks it resolved, commits and announces `done`, so that a Child knows nothing of the other tickets.
68. As the operator, I want `build` to start no watchers or dev servers, and to run no tests needing a shared service unless the repository allows it, so that siblings do not collide.
69. As the operator, I want a repository to cap its own Children with a `children` key in `.matt-pocock.toml`, so that a repository whose tests share one database can say how many it takes.
70. As the operator, I want a needs-triage ticket on the frontier triaged in the Parent, so that triage keeps its Questions in one place.
71. As the operator, I want a handover only once nothing is in flight, so that one ticket waiting on a person does not stop the others.
72. As the operator, I want a cancelled Child's ticket handed over by name, with its worktree removed and its branch kept, so that I can see how far it got.
73. As the operator, I want a merge conflict between siblings resolved by the Parent with tests, or handed over when it cannot be, so that the Working branch stays green.
74. As the operator, I want `pull-request` reached only when no open ticket remains and no Child is in flight, so that the pull request is the whole feature.
75. As the operator of a feature that spans companions, I want a Child that touches a companion to work there on a branch named like its ticket branch, merged by the Parent into the companion's feature branch, so that the pull-request tail finds the companion's work as before.
76. As the operator, I want completed Children's worktrees and ticket branches removed at the Join, and the pull-request tail to prune worktrees and delete already-merged `<working-branch>--<NN>` branches as a safety net, so that nothing is left behind.
77. As the operator, I want `tickets` to announce `implement` without picking a ticket, so that the one scan lives in `implement`.

## Implementation Decisions

### Entry and Queue

- An Entry gains two optional fields, both persisted in the Queue document and read as absent from documents written before this change:
  - **parent**: the Run id of the Run that spawned it. Present only on a Child.
  - **child_limit**: a positive integer. Absent means no limit of the Run's own.
- The Parent's Run keeps a **Children record**: each Child's Entry id, its Subject, given Working branch and working tree (copied at Spawn, so a Child whose Entry is gone before it started can still be named), and once started its Run id. Spawn writes the first part and the Supervisor writes the second when it starts the Child. A Child stays findable from its Parent after a Cancellation or Prune removes its Entry, and the Join reads its Children from this record rather than from the Queue (ADR 0060 rejects the Parent reading the Queue).
- A Child's outcome comes from its Run's ending: **completed** when its Run log records reaching a Terminal State, and **cancelled** when it records a Cancellation, or when its Entry is gone and it never started.

### Spawn (new Protocol verb and command)

- `naiad spawn` takes:
  - the task (optional, defaulting to the Parent's),
  - `--repo` (the Child's working tree, required),
  - `--branch`,
  - `--base`,
  - `--at`,
  - `--subject`,
  - the per-State settings flags and `--skip-gates`, which override what the Child takes from the Parent.
- It resolves the calling Run through the existing Run-resolution chain.
- It refuses when:
  - no Run resolves,
  - the Run has ended,
  - the Run is itself a Child,
  - the working tree normalises to the Parent's own,
  - or the ordinary enqueue checks fail (branch claim per working tree, unknown State, missing Subject).
- It enqueues through the same enqueue path as `naiad queue add`, so it cannot accept what the other entrances refuse. It prints `queued <id>` and returns without supervising.
- The Child takes the Parent Entry's Workflow file, settings and Gates-skipped unless the command names its own. It takes no Child limit, because it can have no Children.
- The injected Protocol text gains a Spawn rule beside the others. It says that Spawn is for a Workflow that asks for it, and that a Child's working tree must be its own.

### Join State (Workflow file, prompt, decision function)

- A State declares `join = true` in the Workflow file. When the file is loaded:
  - a Join State without a Prompt is refused,
  - a Terminal State marked join is refused,
  - a `{children}` slot in a State that is not a Join State is refused.
- The prompt renderer fills `{children}`. Each Child takes one line giving its Subject, Working branch (given or declared), working tree and outcome. The slot is empty when no Child is named. (This adds the working tree to ADR 0060's list, so the Parent can clean up without deriving paths.)
- The engine's decision function gains Join signals: the number of the Run's Children that are unfinished, and the finished Children not yet told. When the owed Prompt belongs to a Join State:
  - **delivered**, naming them, if there are untold finished Children;
  - **delivered with nothing named**, if no Child is unfinished;
  - **otherwise, Nothing.** Holding comes before any Clear, so the Session is untouched until release. While held, the silence rule (Nudge, then Notify after the limit, then the hang Notify) does not apply, exactly as it does not apply while holding (the Hold verb) or waiting.
- **Told-once.** The set of Children named is recorded against the Announcement before its Prompt is sent. A redelivery or delivery retry of the same Announcement renders from the recorded set, not from a fresh reading. The next Announcement of the Join State takes only Children outside every earlier recorded set.
- `naiad announce` of a Terminal State is refused while the announcing Run has unfinished Children. The message names them and tells the agent to announce its Join State.
- A parked Child is unfinished. It does not release the Join, and it notifies on its own as any Run does.

### Supervisor and Queue scan (pure)

- The Queue scan's Signals gain:
  - **ceiling** (a positive int),
  - **strained** (memory pressure is above normal; false when unknown),
  - **low_disk** (the working trees whose volume is below the free-disk floor),
  - **joining** (the ids of Runs held at a Join State).
- The scan's order of rules:
  1. Every Entry with a live Run is Resumed, as today, whatever Capacity says.
  2. **Live** means started and not finished. Parked Runs count, because their Session is live. Runs in **joining** do not count.
  3. A Start is emitted only when live is below the ceiling and **strained** is false. Its Entry must be the first waiting Entry in id order that heads its Lane, is not in **low_disk**, and is not a Child whose Parent already has `child_limit` live Children.
  4. There is at most one Start per scan.
- When nothing starts because of Capacity, the scan says why (ceiling, memory, disk) on the result. The Supervisor reports the reason once per change of reason, not every pass.
- Lanes are unchanged: a Child is a Lane of its own because its working tree differs. Predecessor resolution is unchanged and normally yields the Child's pinned base.
- The ceiling is resolved once, when the Supervisor starts, in this order:
  1. the Supervisor commands' `--capacity N` option,
  2. the `NAIAD_CAPACITY` environment variable,
  3. `max(1, ⌊(total memory − 8 GiB) ÷ 1.5 GiB⌋)`.

### Machine reading (new adapter)

- One adapter answers three questions. The Supervisor loop calls it each pass, except total memory, which it reads once.
  - **Total memory.** macOS: `sysctl -n hw.memsize`. Linux: `MemTotal` in `/proc/meminfo`.
  - **Memory strained.** macOS: `sysctl -n kern.memorystatus_vm_pressure_level` above 1. Linux: the `some avg10` figure in `/proc/pressure/memory` above 10, or `MemAvailable` below 10% of `MemTotal` when no pressure file exists. It returns unknown when neither is readable.
  - **Free disk** for a path, as the filesystem reports it.
- It runs the programs an operator has and reads the files a system exposes. Unknown is a value, never an exception. The Supervisor turns unknown pressure into not strained, and an unreadable disk into not low.

### Sessions

- The Session adapter gains `close(pane)`. A failure because the Session is already gone is ignored.
- After a Join delivery is sent, the Parent's tick closes the Session of each **completed** Child named in it and records the closing on the Child's Run, so it is not repeated. Cancelled Children are never closed. A top-level Run's Session is never closed.

### Cancellation, Prune, listing, status

- Cancelling a Parent cancels each Child it has: a started Child's Run gets the same Cancellation written onto it, and an unstarted Child's Entry is removed. The result carries the Children's working trees, and the command prints them as left for the operator to remove.
- Cancelling one Child is an ordinary Cancellation. The Parent reads it as cancelled from the Children record.
- Prune skips a done Child while its Parent's Run is live and the Child is not in any told set. Once the Parent has been told, or the Parent's Run has ended, the Child is pruned like any done Entry.
- A new derived status, `joining`: a live Run whose latest Announcement names a Join State whose Prompt is being held. The status reading and the Supervisor share one reading of it, as they already share one for parked and running.
- `naiad queue list` lists Children indented under their Parent, each with its own status.
- **The Hold bug.** The status reading passes the Announcement's Hold count to the notice lookup alongside the Wait count, exactly as the loop does when it writes the notice. A Held Run, and one parked after a Hold, then reads `parked` in the listing and in a Prune's judgment of Orphaned Runs.

### Entrances

- `naiad run` and `naiad queue add` take `--child-limit N`. A Batch file takes `child-limit`, as a top-level default and per Entry. Any value that is not a positive integer is refused at the entrance with the usual remedy vocabulary.

### The matt-pocock Workflow (shipped file, prose only)

- `implement` gets `join = true`, keeps `clear = true`, and its next-States are unchanged: `implement`, `triage`, `handover`, `pull-request`. Its Prompt does three things in order:
  1. **Take in** each Child in `{children}`:
     - completed: merge its ticket branch into the Working branch (and its companion branches into the companions' feature branches, creating them on first need), run tests, remove its worktrees, `git branch -d`;
     - cancelled: remove its worktree, keep its branch, and note the ticket for handover.
  2. **Scan**, treating `claimed` as open. For every open, unblocked, ready-for-agent ticket:
     - set it `claimed` and commit on the Working branch,
     - `git worktree add -b <working-branch>--<NN> <sibling path> <working-branch>`,
     - copy the untracked setup,
     - `naiad spawn --repo <sibling path> --branch <working-branch>--<NN> --base <working-branch> --at build --subject <ticket>`.
     It never has more in flight than the `children` key in `.matt-pocock.toml` allows.
  3. **Route**:
     - needs-triage goes to `triage`;
     - Children in flight: announce `implement`;
     - another status with nothing in flight goes to `handover`;
     - no open ticket and nothing in flight goes to `pull-request`.
- `build` is a new State after the Terminal State, entered only by name, with `clear = false`. It is the Child's first State. Its Prompt:
  - clones dependency directories from the Parent's checkout copy-on-write (`cp -c -R` on macOS, `cp -R --reflink=auto` on Linux), then installs;
  - runs `/implement {subject}` on its own branch;
  - starts no watchers or servers, and runs no tests needing shared services unless the repository allows it;
  - for a companion ticket, works in a sibling worktree of the companion on a branch of the same name;
  - sets the ticket resolved, commits, and announces `done`.
- `tickets` announces `implement` with no subject.
- `triage` keeps its scan, but announces `implement` for a ready-for-agent ticket without a subject, since `implement` does its own spawning.
- `pull-request` gains a sweep before it opens anything: `git worktree prune` and deleting `<working-branch>--<NN>` branches already merged into the Working branch.
- The workflow-authoring documentation gains `join`, `{children}` and Spawn. The docs-drift test must keep passing.

## Testing Decisions

- A good test asserts what a caller can observe: the Action returned, what lands on disk, what is printed and the exit status. It never asserts which helper was called or how a record file is laid out. Every rule is tested at the highest seam that can see it, and new seams are kept to one.
- **Decision function** (prior art: the existing decision-function tests, data in, Action out):
  - held gives Nothing, with no Nudge or Notify at any idle time;
  - released by one untold Child;
  - delivered at once with no unfinished Child;
  - a parked Child does not release;
  - a cancelled Child releases as cancelled;
  - Clear happens only on release.
- **Queue scan** (prior art: the existing Queue-scan tests):
  - ceiling reached means no Start but Resumes continue;
  - strained means no Start;
  - a low-disk tree is skipped while a later Lane starts;
  - one Start per scan;
  - joining Parents are not counted, and a ceiling of one with a joining Parent starts its Child;
  - parked Runs are counted;
  - the Child limit holds Children in id order and a limit of one serialises;
  - a Child is a Lane of its own;
  - the "why nothing started" reason.
- **Commands over a temporary Naiad home** (prior art: the Queue-command and Protocol-command tests):
  - Spawn: queued output, inheritance, every refusal, and its use of the enqueue checks;
  - `--child-limit` and the batch `child-limit` key, valid and refused;
  - the Terminal-State announce refusal;
  - the listing showing `joining` with Children indented;
  - the cancel cascade and its printed working trees;
  - the Prune skip and later prune;
  - a Held Run and a Run parked after a Hold reading `parked`. Write this test first, and confirm it fails for the expected reason before the fix.
- **Tick over real Run files, with a recorded Session** (prior art: the existing loop tests):
  - `{children}` rendered from the Children record;
  - told-once across two Join deliveries;
  - a redelivery naming the same set;
  - a completed Child's Session closed after delivery and not before, never for a cancelled Child;
  - the Supervisor loop recording a Child's Run id on its Parent at Start.
- **Machine reading** (prior art: the fake-machine helper that installs stand-in programs on `PATH`):
  - a fake `sysctl` answering memory size and pressure level;
  - a fake proc directory for Linux with and without a pressure file;
  - unknown on failure;
  - the ceiling formula at several memory sizes;
  - the order in which the option, the environment variable and the derived value win.
- **Workflow file**:
  - Workflow parser tests for `join` validation and the `{children}` slot rule;
  - the shipped-workflow invariant tests, which run unchanged and must still pass with `build` and `join` present;
  - what `implement` and `build` say is checked by a manual smoke run, never by a test that reads Prompt prose.
- TDD throughout: Red, then Green, then a named Refactor verdict per ticket. Test runs keep the worker cap.

## Out of Scope

- Nesting: a Child spawning Children. The refusal is the whole of it, and lifting it later means removing one check.
- Naiad creating, removing or knowing about worktrees, branches or tickets. All of that is the Workflow's work in its Prompts.
- Moving `wayfind` to Children. It stays one ticket per Announcement in one Session (ADR 0045, as narrowed by ADR 0060).
- Stopping or pausing a live Run under pressure. Capacity bounds starting only.
- Counting manually started Claude Code sessions, or reading anything inside Claude Code.
- Windows support for the machine reading. There, pressure is unknown and the ceiling alone applies.
- Sparse checkout, shared dependency stores, or any storage optimisation beyond copy-on-write cloning and removal at the Join.
- Waves as a Naiad mode. A Prompt can still choose to wait for everything in flight.

## Further Notes

- Governing decisions: ADR 0060 (Spawn and Join), ADR 0061 (Capacity), ADR 0062 (closing a completed Child's Session), ADR 0063 (the matt-pocock loop). Glossary: Spawn, Child, Child limit, Capacity and Join State, plus the amended Session, Entry, Supervisor, Prune and Cancellation entries in CONTEXT.md. This spec adds two things the ADRs did not state, and both are written back to ADR 0060 and the glossary: the working tree in `{children}`, and the refusal to announce a Terminal State while Children are unfinished.
- ADRs and CONTEXT.md are untracked here (ADR 0054). Comments, commit messages and docs in tracked files must state each rule inline and never cite them.
- Suggested order for the tickets:
  1. the Hold reading bug, standalone;
  2. Entry fields and the entrances;
  3. Spawn;
  4. the Join State in the Workflow file and the decision function;
  5. tick wiring and told-once;
  6. the Queue scan's Capacity and Child limit;
  7. the machine reading and the Supervisor wiring;
  8. cancel, Prune and listing;
  9. closing Sessions;
  10. the matt-pocock Workflow and docs.
- The maintainer runs with `NAIAD_CAPACITY=20`.
