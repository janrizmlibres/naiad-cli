# A Parent cannot end over unfinished Children

Status: resolved
Blocked by: 02
Spec: `.scratch/children/PRD.md`

## What to build

If a Parent reached its Terminal State while Children were still working, those Children would be orphaned and would build work nobody takes in. `naiad announce` of a Terminal State is refused while the announcing Run has any unfinished Child, meaning one that has not started, is running, or is parked. The refusal names those Children and tells the agent to announce its Join State instead. Announcing a non-terminal State, including a Gate State such as a handover, is unaffected, and the Children keep working.

## Acceptance criteria

- [x] Announcing a Terminal State with an unfinished Child exits non-zero, names the Child, and points at the Join State.
- [x] Announcing a Terminal State with every Child finished, or with no Children, works as before.
- [x] Announcing a Gate State with Children in flight is accepted.
- [x] Refactor: candidates considered and a verdict recorded.
