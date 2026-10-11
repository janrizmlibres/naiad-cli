# Capacity is a ceiling and a pressure check

> Revises ADR 0020's "there is no cap". Revised by ADR 0064.

ADR 0020 started Lanes without a limit. Its reasoning was that concurrency is bounded by what the operator queues, and that a cap would be "one counter in the scan" if it were ever needed. Children make it needed (ADR 0060). One Entry can now become a dozen Sessions, every one of them building and testing at the same moment, and the operator never queued them one by one. On the maintainer's 32 GB machine, with an ordinary day's browser and editor open, memory pressure already read *warn* and swap was nearly full before any Run had started. A Claude Code session with its MCP servers took 0.6–1.2 GB, and more while a child was testing.

A fixed number is wrong in both directions. A machine with apps open needs fewer than the operator would guess, and a machine left alone overnight can take far more. A number computed at install goes stale the first time a browser opens.

We decided **Capacity** is two bounds, checked each time the Supervisor would start a Run:

- **A ceiling.** It is derived from the machine's total memory when the Supervisor starts, as `max(1, ⌊(total − 8 GB) ÷ 1.5 GB⌋)`, unless the operator sets one through a Supervisor option or an environment variable. The maintainer sets 20.
- **A pressure check.** Below the ceiling, a waiting Run starts only while the operating system reports its memory pressure as normal and free disk is above the larger of 10% and 10 GB. On macOS memory pressure comes from `kern.memorystatus_vm_pressure_level`, and on Linux from the memory pressure file or the available memory. The Supervisor makes at most one start per pass, so pressure can catch up before the next. Where the operating system offers no reading, the ceiling alone applies.

Capacity counts every Run that is working, Children included. A Parent held at a Join State is not counted, because it is idle and because counting it deadlocks a ceiling of one: the Parent would hold the only slot its Child needs. Capacity bounds starting and nothing else. A Run that is already live is always ticked, so a Parent released from its Join State is never held back, and nothing working is ever stopped. Sessions the operator started by hand are invisible to the count, but the pressure check sees their effect, and that is the point of having one.

Reading the operating system's memory gauge is not reading Claude Code's internals, so ADR 0002 stands. It needs no new dependency.

## Considered options

**A fixed default number.** It is safe on one machine and wrong on the next, and it ignores whatever else is open.

**Computed at install.** It goes stale with every browser tab and every RAM upgrade.

**A ceiling derived from memory alone.** It is better than a fixed number, but it still starts a twentieth Run into a machine that is already swapping.

## Consequences

The ceiling counts Lanes and Children with the same number, because a Child costs what a top-level Run costs. An operator who wants fewer Children for one feature gives that Entry a Child limit instead. A repository whose tests share a database says how many Children it can take in its own project file, which is the Workflow's business and not Naiad's.

A Run waiting on Capacity reads `waiting`, exactly like one waiting behind its Lane.
