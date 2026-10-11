# Cancelling reaches Children, and Prune waits for the Join

Status: resolved
Blocked by: 03
Spec: `.scratch/children/PRD.md`

## What to build

**Cancelling a Parent cancels each of its Children.** A Child that has started gets the same Cancellation written onto its Run, which releases its Session. A Child that has not started has its Entry removed. The command then lists the Children's working trees as left for the operator to remove. Naiad knows the paths, not what they are.

**Cancelling one Child** is an ordinary Cancellation. Its Parent finds it through the Children record and is told of it as cancelled at its next Join delivery.

**Prune** skips a done Child while its Parent's Run is live and the Child is in no told set. Once the Parent has been told of it, or the Parent's Run has ended, the Child is pruned like any done Entry.

## Acceptance criteria

- [ ] Cancelling a Parent with one running Child, one parked Child and one unstarted Child cancels the first two, removes the third, and prints all three working trees.
- [ ] Cancelling a lone Child leads to the Parent's next Join delivery naming it as cancelled. This is checked at the loop seam.
- [ ] Prune leaves an untold done Child of a live Parent, and takes it once told or once the Parent has ended.
- [ ] Cancelling and pruning Entries that have no Children are unchanged.
- [ ] Refactor: candidates considered and a verdict recorded.
