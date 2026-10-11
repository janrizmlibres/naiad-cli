# Predecessors resolve through Runs

Status: resolved
Blocked by: 01, 02

## Parent

`.scratch/derived-branch/PRD.md` (ADR 0022 is the authoritative decision record).

## What to build

The stacking chain works for Derived branches exactly as for given ones. When the Supervisor resolves a starting Entry's Predecessor — the Working branch of the most recent preceding Entry for the same repository, absent a pinned base — a preceding Entry whose own record carries no branch yields the branch its Run declared. Lanes are sequential, so by the time the next Entry starts, the previous Run declared long before (or was refused at its Announcements until it did).

A preceding branchless Entry whose Run never recorded a branch (it never reached a head) contributes none, exactly as a missing Predecessor renders today: absent, ordinary, walked past to the next preceding Entry for the repository.

## Acceptance criteria

- [ ] A Run starting behind a branchless Entry whose Run declared a branch receives that branch as its Predecessor, rendered into its Prompts
- [ ] A pinned base still wins over any resolution
- [ ] A preceding Entry with neither a recorded nor a declared branch is walked past, and resolution continues to the Entry before it
- [ ] Entries for other repositories are still walked over unchanged
- [ ] TDD per behaviour, at the kickoff/supervise seam using its existing test style

## Blocked by

- 01 — branchless Entries and claim-resolution-through-the-Run
- 02 — a declared branch is what resolution reads
