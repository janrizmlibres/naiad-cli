# A completed Child's Session closes once its Parent is told

Status: resolved
Blocked by: 03
Spec: `.scratch/children/PRD.md`

## What to build

The Session adapter gains `close`. If the Session is already gone, that is ignored. After a Join delivery is sent, the Parent's tick closes the Session of each **completed** Child it named and records the closing on that Child's Run, so the close is never repeated. The transcript, Run log and Answer log stay on disk. Sessions of cancelled Children, parked Children and Children not yet told are left alive, and so is every top-level Run's Session.

## Acceptance criteria

- [ ] A loop test with a recorded Session shows a completed Child's Session closed after the delivery that names it, and not before.
- [ ] A cancelled Child's Session is never closed.
- [ ] A second tick does not close the same Session again.
- [ ] Closing a Session that is already gone does not fail the tick.
- [ ] Top-level Runs are never closed.
- [ ] Refactor: candidates considered and a verdict recorded.
