# One entrance to starting Runs

With a Queue there are two obvious ways to start a Run: enqueue it and let the Supervisor pick it up, or run it now with the command that already exists. Keeping both is the smaller change and it is the one we rejected. Starting a Run means going through the Queue, and `naiad run` becomes the sugar that puts one Entry at the back of it.

The argument is in the code already. The rule that a Prompt naming a Subject cannot be delivered without one is enforced where the agent announces, and a separate check had to be written for kickoff — because kickoff is a second entrance to delivery that the first check does not reach. That was one guard duplicated for one rule. A second entrance to *starting Runs* bypasses the guard that matters most: nothing would stop an immediate Run from spawning a second agent into the same working tree while the Supervisor is driving a queued one, which is the single thing one-at-a-time exists to prevent. An invariant with two places to break it is a convention, not an invariant.

Which leaves the question of what the command does when you type it. It adopts or becomes: if a Supervisor is already running it enqueues and returns, and if none is it becomes the Supervisor in the foreground. At a cold terminal that is strictly better than what it replaced, where starting a Run and driving it were two commands. Where something is already supervising, the same command is a fire-and-forget enqueue — which is what an agent inside a session needs, since a session cannot host a process that blocks for hours.

Knowing whether a Supervisor is running is done with an advisory lock rather than a recorded process id, so that the kernel releases it when the process dies and there is no stale lock to reconcile after an interrupt or a crash. The lock is not a cost of the ergonomics: a single-Supervisor guarantee is required regardless, because two Supervisors each take the first waiting Entry and put two agents in one working tree. The adopt-or-become behaviour is read off a lock that had to exist anyway.

## Consequences

`naiad run` stops meaning "start this now", and appends rather than jumping the Queue. That is a real loss and the honest place for it to show is where the Entry lands, rather than hidden behind a jump that makes the command mean "soon" in a way nothing guarantees. A flag to insert at the front is one comparison key away if the loss turns out to bite.

The Supervisor drains and exits when started as `naiad run`, and follows an empty Queue when started to supervise. It is one loop differing only in what it does with nothing to do — a command that hangs after finishing the work is one you have to remember to interrupt, and remembering it at seven in the morning is the tax this project exists to remove.

Enqueueing from inside a session needs nothing built: a session can already run the command or write a batch file. What is *not* covered is Naiad taking over the session that is already running, which remains deferred, and is now harder than when it was first written down — Runs need permissions a live session cannot be switched into, and both heads of the shipped Workflow Clear, which destroys the conversation that motivated adopting it.
