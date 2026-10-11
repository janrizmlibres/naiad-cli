# `naiad run` folds into the Queue

Status: ready-for-agent
Blocked by: 04-a-supervisor-drives-the-queue-in-order
Spec: `.scratch/queue/PRD.md`

## What to build

One entrance to starting Runs (ADR 0014). `naiad run` stops spawning a session directly: it adds one Entry, then adopts or becomes. If a Supervisor already holds the lock it returns immediately. If none does, this process becomes the Supervisor in the foreground, drains the Queue and exits.

At a cold terminal that is one command where there were two — starting a Run and then driving it. Where something is already supervising, the same command is a fire-and-forget enqueue.

**Why one entrance rather than two.** The rule that a Prompt naming a Subject cannot be delivered without one is enforced where the agent announces, and a second check had to be written for kickoff, because kickoff is a second entrance to delivery the first does not reach. That was one guard duplicated for one rule. A second entrance to *starting Runs* bypasses the guard that matters most: nothing would stop an immediate Run spawning a second agent into the same working tree while the Supervisor drives a queued one. An invariant with two places to break it is a convention.

**The lock is an advisory file lock held for the Supervisor's life,** so the kernel releases it when the process dies and there is no stale record to reconcile after an interrupt or a crash. A second Supervisor is refused rather than queued behind the first. The lock is not a cost of the ergonomics: a single-Supervisor guarantee is needed regardless, because two Supervisors each take the first waiting Entry and put two agents in one working tree. Adopt-or-become is read off a lock that had to exist anyway. It is an adapter and holds no rules.

**`naiad run` appends rather than jumping the Queue.** It stopped meaning "start this now" the moment a Queue existed, and the honest place for that to show is where the Entry lands, rather than hidden behind a jump that makes it mean "soon" in a way nothing guarantees.

**`naiad watch` refuses while the lock is held.** The Queue is sequential, so a held lock means the Supervisor is driving the only live Run, and a second ticker on one Run delivers everything twice.

**Do not test the lock by racing two real Supervisors** — flaky, slow, and what would be asserted is the operating system's rather than ours. Assert the behaviour that depends on the lock's answer instead: enqueue-and-return when held, become-and-drain when not, refuse a second Supervisor, refuse a watch.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] `naiad run` adds an Entry rather than spawning a session directly
- [ ] `naiad run` returns immediately when a Supervisor holds the lock
- [ ] `naiad run` becomes the Supervisor when none holds the lock, drains the Queue and exits
- [ ] A second Supervisor is refused with an error saying one is already running
- [ ] The lock is released when the Supervisor's process dies, including on interrupt
- [ ] `naiad watch` refuses while the lock is held
- [ ] `naiad run` appends to the Queue rather than inserting at the front
- [ ] The kickoff-time refusals still fire, now at enqueue
