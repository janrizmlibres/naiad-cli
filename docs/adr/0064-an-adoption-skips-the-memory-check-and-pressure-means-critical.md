# An Adoption skips the memory check, and pressure means critical

> Revises ADR 0061's pressure check.

ADR 0061 started a Run only while the operating system reported memory pressure as normal. On macOS that meant `kern.memorystatus_vm_pressure_level` at 1. The ADR already noted that on the maintainer's 32 GB machine pressure read *warn* before any Run had started. In practice that is the reading for an ordinary day: a browser, an editor, a container VM and a few dev servers hold it at 2 for hours. Nothing started at all. The first time it mattered, the waiting Entry was an Adoption. Its Session was already open and already using its memory, and starting it would have added nothing.

We decided two things:

- **An Adoption is asked only about disk.** Its Run joins a Session that already exists, so starting it opens nothing new. Neither memory pressure nor the ceiling holds it back. The low-disk check still applies because the work it is about to do writes to that working tree, and so does the one-start-per-pass rule. Once started it is counted toward the ceiling like any Run, since its Session is live. The Children it spawns are new Sessions and go through every check.
- **On macOS, only critical is strain.** A level of 4 holds starts back, and 1 and 2 do not. The ceiling is what bounds concurrency on a busy machine. The pressure check is there to stop a start into a machine that is actually in trouble, not one that is merely busy.

Linux is unchanged. `some avg10` above ten measures time actually lost to memory stalls rather than a warning level, and no Linux machine has shown the problem.

## Considered options

**An operator override that skips the pressure check.** It is one more flag to remember, and an operator who reaches for it on a busy day will leave it on when the machine really is in trouble.

**Keep warn as strain and lower the ceiling instead.** The ceiling was never the problem. With warn as the everyday reading, nothing starts at any ceiling.

**Hold an Adoption at the ceiling.** That makes a Session that already exists wait for room it already takes up, and the ceiling would only start counting it once it was adopted.

## Consequences

A machine at warn starts Runs up to its ceiling, so the ceiling the operator sets (or the one derived from memory) carries more weight than before. An Adoption can take the live count above the ceiling. That is temporary: nothing else starts until the count falls back below it.
