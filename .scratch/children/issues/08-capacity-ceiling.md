# Capacity ceiling

Status: resolved
Blocked by: 03
Spec: `.scratch/children/PRD.md`

## What to build

The Supervisor resolves a **ceiling** once, when it starts, in this order:
1. the Supervisor commands' `--capacity N` option;
2. the `NAIAD_CAPACITY` environment variable;
3. `max(1, ⌊(total memory − 8 GiB) ÷ 1.5 GiB⌋)`.

A value that is not a positive whole number is refused when the Supervisor starts. Total memory comes from a new **machine reading** adapter: `sysctl -n hw.memsize` on macOS, and `MemTotal` from the proc meminfo file on Linux.

The Queue scan's Signals gain the ceiling and the set of Runs held at a Join State. The scan's rules:
- Every live Run is Resumed, whatever Capacity says.
- **Live** means started and not finished. Parked Runs count, because their Session is live. Runs held at a Join do not count, so a ceiling of 1 cannot deadlock a Parent against its only Child.
- A Start is emitted only while live is below the ceiling.
- There is at most one Start per scan.

When nothing starts because of Capacity, the scan gives the reason, and the Supervisor reports it once each time the reason changes. A Run waiting on Capacity reads `waiting`.

## Acceptance criteria

- [ ] Queue-scan tests:
  - at the ceiling, no Start is emitted but every Resume still is;
  - one Start per scan;
  - joining Parents are not counted, and a ceiling of 1 with a joining Parent starts its Child;
  - parked Runs are counted;
  - the reason is given.
- [ ] Machine-reading tests use a fake `sysctl` on `PATH` and a fake proc directory to read total memory. The ceiling formula is checked at 8, 16, 32 and 64 GiB.
- [ ] Supervisor tests:
  - the option beats the environment variable, which beats the derived value;
  - invalid values are refused;
  - the reason is reported once, not every pass.
- [ ] Refactor: candidates considered and a verdict recorded.
