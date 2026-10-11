# A Join State holds its Prompt until a Child finishes

Status: resolved
Blocked by: 02
Spec: `.scratch/children/PRD.md`

## What to build

A Workflow author declares a State with `join = true`. When the Workflow file is loaded, any of these is refused:
- a Join State without a Prompt;
- a Terminal State marked join;
- a `{children}` slot in a State that is not a Join State.

When a Run's owed Prompt belongs to a Join State, the decision function decides from two Join signals: the number of the Run's Children that are unfinished, and the finished Children not yet told.
- **Delivered**, naming the untold finished Children, when there are any.
- **Delivered with nothing named**, when no Child is unfinished.
- **Otherwise, Nothing.**

Holding comes before any Clear, so the Session is left alone until release. While it holds, the silence rule does not run: no Nudge, no Notify after the Nudge limit, and no hang Notify. A parked Child is unfinished, so it does not release the Join. A cancelled Child releases it, as cancelled.

The prompt renderer fills `{children}` with one line per Child: its Subject, its Working branch (given or declared), its working tree, and its outcome, completed or cancelled. The outcome comes from the Child's Run log (Terminal State reached, or Cancellation), and a Child whose Entry is gone and never started counts as cancelled.

**Told-once.** The tick records the set of Children it names against the Announcement before sending the Prompt. A redelivery or a retry of the same Announcement renders that recorded set again. A later Announcement of the Join State names only Children outside every set recorded before it.

A new derived status, `joining`, covers a live Run held at a Join State. `naiad queue list` shows it.

The workflow-authoring documentation describes `join` and `{children}`.

## Acceptance criteria

- [ ] The Workflow parser accepts `join = true` and refuses the three invalid shapes, each with a clear message.
- [ ] Decision-function tests:
  - held gives Nothing at every idle time, with no Nudge or Notify;
  - one untold finished Child releases it;
  - no unfinished Child delivers at once with an empty slot;
  - a parked Child does not release;
  - a cancelled Child releases as cancelled;
  - the Clear happens only on release.
- [ ] Loop tests over real Run files:
  - `{children}` is rendered from the Children record;
  - two Join deliveries never name the same Child;
  - a redelivery names the same set;
  - a Supervisor restart between recording and sending neither drops nor repeats a Child.
- [ ] `naiad queue list` prints `joining` for a Parent held at a Join State.
- [ ] Workflows without `join` behave exactly as before.
- [ ] The docs-drift test passes with the new key and slot documented.
- [ ] Refactor: candidates considered and a verdict recorded.
