# Branchless work is accepted at both entrances, and claims resolve through the Run

Status: resolved

## Parent

`.scratch/derived-branch/PRD.md` (ADR 0022 is the authoritative decision record).

## What to build

An operator can describe work without naming a Working branch, at every entrance: `naiad run` and `naiad queue add` without `--branch`, and a batch Entry without a `branch` key. A given branch behaves exactly as today and is never second-guessed.

The `MissingWorkingBranch` refusal disappears along with its remedy vocabulary; the shared start checks and their result carry an optional Working branch, as do the Work and the Entry. A branchless Entry claims no branch, so two branchless Entries for the same repository coexist in the Queue.

The two-Entries-one-branch refusal keeps working across the gap this opens: the claim check resolves an Entry whose own record carries no Working branch through its Run — the same pattern as `status_of` (ADR 0013), no second copy, no new Entry mutation. So enqueueing `--branch X` is refused when a branchless Entry's Run has recorded X.

## Acceptance criteria

- [ ] `naiad queue add` and `naiad run` accept omission of `--branch`; the Entry (and Run) record no Working branch
- [ ] A batch Entry without a `branch` key is valid; named and branchless Entries compose in one file
- [ ] A given branch is recorded verbatim, and the existing claimed-branch refusal for named Entries is unchanged
- [ ] Two branchless Entries for the same repository coexist in the Queue
- [ ] An Entry with no recorded branch but a Run that holds one claims that branch: enqueueing the same name for the same repository is refused
- [ ] `MissingWorkingBranch`, its check, and its remedy strings are gone; tests asserting the refusal are removed or inverted
- [ ] TDD per behaviour (Red → Green → Refactor with a named verdict), at the enqueue seam using its existing test style

## Blocked by

None — can start immediately.
