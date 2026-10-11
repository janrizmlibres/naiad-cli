# Capacity pressure check

Status: resolved
Blocked by: 08
Spec: `.scratch/children/PRD.md`

## What to build

Below the ceiling, a Run starts only while the machine is unstrained. The machine reading gains two answers.

- **Memory strained.**
  - macOS: `sysctl -n kern.memorystatus_vm_pressure_level` reads above 1.
  - Linux: the `some avg10` figure in the memory pressure file is above 10. Where that file is missing, `MemAvailable` below 10% of `MemTotal` counts as strained.
  - If neither can be read, the answer is unknown.
- **Free disk** for a path, which is low when below the larger of 10% and 10 GB.

The Supervisor reads these each pass. Unknown pressure counts as not strained, and an unreadable disk counts as not low. The scan's Signals gain **strained** and **low_disk** (the working trees whose volume is low). No Run starts while memory is strained. A waiting Entry whose working tree is low on disk is skipped, and a later Lane may start in its place. The reason reported for nothing starting now also covers memory and disk.

## Acceptance criteria

- [ ] Machine-reading tests:
  - a fake `sysctl` at pressure levels 1, 2 and 4;
  - a fake proc directory with a pressure file above and below the threshold, and without one, falling back to `MemAvailable`;
  - unknown when nothing is readable;
  - free disk around the floor.
- [ ] Queue-scan tests:
  - strained means no Start, while Resumes continue;
  - a low-disk working tree is skipped and a later Lane starts;
  - unknown pressure means the ceiling alone applies.
- [ ] Refactor: candidates considered and a verdict recorded.
