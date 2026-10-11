# Notify-and-wait — Gates, stalls, and hangs

Status: ready-for-agent
Blocked by: 02-the-core-loop
Spec: `.scratch/core-engine/PRD.md`

## What to build

Everything that ends with Naiad stopping and the human taking over. The spec argues these are one behaviour rather than a family of them — a Gate reached, an agent fallen silent, and an agent hung all resolve to notify-and-wait — so they are built together and share one path.

**A Gate State** is a State with no Prompt. Naiad has nothing to deliver and takes no action; the human types into the session directly. This needs no gate feature — it falls out of the general delivery rule. There is deliberately no approve or reject command; all human interaction goes through the session, which is why the session must stay alive.

**A silent agent** has usually just forgotten the Protocol. Naiad sends at most two Nudges reminding it, the second worded more firmly than the first, and then stops. The bound is the point: an agent that is genuinely stuck will not recover from being asked again, and unbounded nudging is Naiad fighting the agent rather than driving it.

**A hung agent** never ends a turn at all, so no signal ever arrives. A wall-clock timeout with neither a turn ending nor an Announcement resolves to the same notify-and-wait.

**Notification is once per Announcement, not once per tick.** Every one of these conditions persists across ticks with identical signals, so a naive implementation notifies every couple of seconds until the operator wakes up. Whether a notification has already been sent is a signal the decision function reads, reset when a new Announcement arrives. This is the defect most likely to ship; it deserves its own test.

**The Run stays alive.** Notifying does not end a Run — the human types, the agent announces, and delivery resumes. Only a Terminal State ends a Run, and that belongs to another ticket.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] An Announcement naming a State with no Prompt results in no delivery
- [ ] A Gate State notifies the operator exactly once, however many times the decision is made with unchanged signals
- [ ] A new Announcement re-arms notification, so a later Gate notifies again
- [ ] Idle with nothing announced sends a Nudge
- [ ] A second idle period sends a second Nudge, worded differently from the first
- [ ] A third sends no Nudge and notifies instead
- [ ] Nudges are counted per Announcement, so an agent that recovers and later stalls again gets a fresh allowance
- [ ] Neither a turn ending nor an Announcement within the timeout notifies the operator
- [ ] The tick loop keeps running after any notification, and a subsequent Announcement is delivered normally
- [ ] The notification names why the operator is needed
- [ ] All rules tested as data in, Action out — no clock, no sleeping, no fakes; elapsed time is a signal, not something the test waits for
