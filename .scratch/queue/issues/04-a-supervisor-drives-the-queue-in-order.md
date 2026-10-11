# A Supervisor drives the Queue in order

Status: ready-for-agent
Blocked by: 01-a-run-carries-a-working-branch-and-a-predecessor, 03-entries-can-be-queued-listed-and-removed
Spec: `.scratch/queue/PRD.md`

## What to build

`naiad queue watch` takes the Queue in order and runs it: first waiting Entry, start its Run, watch it to a Terminal State, move on. Queue two Entries, start the Supervisor, and both run one after the other without a human between them.

**The rules go in one pure function, the sibling of the one the engine already has (ADR 0004).** Signals in, Action out; it reads no file, runs no subprocess and looks at no clock. Its signals are the Entries in order, which of their Runs have finished, and whether it is following or draining. Its Actions are:

- **Start** an Entry — carrying the Predecessor resolved for it, so resolution is part of the decision rather than something the loop works out afterwards
- **Resume** an Entry whose Run exists and has not finished
- **Drained** — nothing waiting, nothing running, and not following
- **Idle** — nothing to do, come round again

**The rule is one scan:** take the Entries in id order, find the first that is not done; if it has a Run, Resume it; otherwise Start it. If every Entry is done, Drained or Idle by mode.

That single scan produces three behaviours with no special case for any of them, and each is worth asserting separately because each would be a different bug:

- **Sequential ordering**, because the scan stops at the first unfinished Entry.
- **A parked Run blocks the Queue** (ADR 0012), because a parked Run is not finished, so the scan keeps returning Resume — and watching a Run already never returns while it is parked, since a Run needing a human must stay tickable so their typing revives it. Blocking therefore costs no code at all, in the way a Gate State needed no gate feature.
- **Crash recovery**, because a restarted Supervisor finds the same Entry and watches its Run again, which the existing watch handles correctly in both directions: it reports that a finished Run has finished and returns, and picks an unfinished one up mid-flight. There is no resume path to design.

**Drain or follow is the only difference between the two modes.** One loop; on an empty Queue it either returns or comes round again. `naiad queue watch` follows.

**The Predecessor is the pinned base only, at this ticket.** Resolving it from the Queue is the next ticket, and Start's shape does not change when it lands.

**The wiring holds no rules.** It gathers the signals, calls the function, and either starts a Run and watches it, watches one, sleeps, or returns. If a condition ever needs adding to the loop, it belongs in the function instead. Test it the way the existing watch loop is tested, with sleeping and reporting injected so that nothing waits on a clock.

**The Supervisor holds no Run of its own.** Which Run is live stays derivable from the Entries, so a concurrent Queue later is an addition rather than a rewrite.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] The Queue's rules live in one pure function, tested as data in and Action out with no tmux, subprocess or clock
- [ ] An empty Queue drains when draining and idles when following
- [ ] The first Entry with no Run is started, carrying its Predecessor
- [ ] An Entry whose Run has not finished is Resumed, and the next Entry is not started
- [ ] A Queue whose every Entry is done drains, or idles when following
- [ ] A Supervisor restarted mid-Run resumes the same Entry rather than starting the next
- [ ] `naiad queue watch` runs two queued Entries in order, one after the other
- [ ] The loop holds no rule of its own, and is tested with sleeping and reporting injected
