# An Entry's Child limit

Status: resolved
Blocked by: 02
Spec: `.scratch/children/PRD.md`

## What to build

The operator gives an Entry a **Child limit**: `--child-limit N` on `naiad run` and `naiad queue add`, or a `child-limit` key in a Batch file, either as a top-level default or per Entry. Anything other than a positive whole number is refused at the entrance, in the entrance's usual remedy vocabulary. The limit is persisted on the Entry. Documents written before this change read it as absent, which means no limit of the Run's own. Spawn takes no limit, because a Child can have no Children.

The Queue scan holds back a Child whose Parent already has as many live Children as its limit. Live means started and not finished, parked included. A held Child reads `waiting`. The scan takes Children in id order, so a limit of 1 runs them one at a time in the order they were spawned.

## Acceptance criteria

- [ ] Queue-scan tests:
  - with a limit of 2 and three spawned Children, two are Started and the third waits until one finishes;
  - a limit of 1 runs Children one at a time in id order;
  - no limit starts every Child's Lane;
  - a parked Child counts toward the limit.
- [ ] `--child-limit` on both entrances and `child-limit` in a Batch file are accepted and persisted, and 0, negative and non-numeric values are refused.
- [ ] `naiad queue list` shows a held Child as `waiting`.
- [ ] Refactor: candidates considered and a verdict recorded.
