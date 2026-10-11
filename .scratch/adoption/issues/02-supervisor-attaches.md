# The Supervisor attaches instead of spawning

Status: resolved
Blocked by: 01

## Parent

`.scratch/adoption/PRD.md` (ADR 0028).

## What to build

The takeover, end to end. A Supervisor reaching an attach-marked Entry at the head of its Lane attaches the new Run to the recorded pane instead of opening a session: the Run is created and the session recorded on it as spawned Runs record theirs, and the start State's Prompt is delivered only after a Turn end has been reported for that session — the same never-type-over-a-working-agent rule an Answer follows. Model and effort ride the delivery as they ride any delivery (ADR 0026); the environment-variable shortcut is simply absent, so hooks and agent commands resolve the adopted Run through the existing resolution seam (pane, then Claude session id).

From the first Announcement on, the adopted Run is an ordinary Run: announcements, waits, holds, nudges, the Answerer, both logs — all unchanged. An Adoption behind a live Run in its Lane waits; the takeover happens when its turn comes.

## Acceptance criteria

- [ ] An attach-marked Entry produces no spawn: the sessions adapter records an attachment to the given pane and the Run's metadata records that session.
- [ ] The start State's Prompt is not delivered while no Turn end has been reported; it is delivered once one has, with the State's model and effort riding it.
- [ ] A Gate start State delivers nothing and the Run parks for the human, as the general rule already says.
- [ ] The adopted Run resolves from its pane for the Stop and SessionStart hooks and for agent commands, with no environment variable set.
- [ ] An Adoption queued behind a live Run in the same Lane starts only after that Run finishes; other Lanes proceed beside it.
- [ ] The checks are re-made at takeover, as kickoff re-makes them, and a Workflow edited since enqueue is refused with the remedy quoting the re-queue command.
- [ ] The Run log records the takeover and every Announcement after it as it records any Run's.
