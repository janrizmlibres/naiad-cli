# The `naiad branch` declaration command

Status: resolved
Blocked by: 01

## Parent

`.scratch/derived-branch/PRD.md` (ADR 0022 is the authoritative decision record).

## What to build

The agent that has just created a Derived branch declares it in the same turn: `naiad branch <name>`. The command resolves the current Run, records the name as the Run's Working branch, and logs the declaration in the Run log so a human can read where the name came from. It is a sibling of the announce command and follows its shape: refusals are error messages the agent can act on inside its own turn.

Two refusals:

- **Write-once.** A Run that already has a Working branch — given at the Entry's making or declared earlier — refuses a second, because the next Entry's Predecessor stands on it.
- **Claimed name.** A name another Entry for the same repository holds (resolved through Runs, per ticket 01) is refused with the same message shape as enqueue's claimed-branch refusal, so the agent derives another name and retries.

## Acceptance criteria

- [ ] `naiad branch <name>` on a branchless Run records the name on the Run; a subsequent enqueue sees the claim
- [ ] A second declaration, or one against a Run whose branch was given, is refused and changes nothing
- [ ] A name held by another Entry in the same repository is refused, naming the holder; the same name in another repository is accepted
- [ ] The declaration appears in the Run log
- [ ] TDD per behaviour, at the command seam, with the Wait command's tests as prior art (the most recent protocol-verb addition)

## Blocked by

- 01 — branchless Runs must exist, and the claimed-name refusal reuses claim-resolution-through-the-Run.
