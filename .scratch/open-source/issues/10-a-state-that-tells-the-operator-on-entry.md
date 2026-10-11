# A State that tells the operator on entry

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

May a Workflow declare that entering a State tells the operator, without parking the Run? Today Naiad interrupts a human for exactly two reasons, held as a two-member enum: the Run needs them (a Gate, an escalated or reserved Question, a hold, silence, idleness, an unknown State, a dropped Clear) or the Run is over. Every such telling parks the Run and discards the Belief, because a human is assumed to have the keyboard afterwards. An adopter who wants to hear that a Run reached `implement` or opened its pull request is asking for a third kind: a telling that hands nothing over. Decide: whether the key exists and what it is called (`notify = true` on a State, or a file-level list); whether it is a third Notification member or a Notify that does not park; what the telling carries (State name, Subject, Task); whether it discards the Belief (it should not, since nobody took the keyboard); whether it goes down every leg (terminal, desktop, push) or only the push; and how the once-per-Announcement rule applies to it. Record the decision as an ADR if the enum grows, since the two-member limit is a stated invariant.

## Answer

Yes. The new term is **Report** (added to `CONTEXT.md`), declared per State with `report = true`. ADR 0055 amends the two-reasons invariant: Naiad interrupts a human for two reasons and informs them for one.

- **Key**: `report = true` on a State. No file-level default and no file-level list. `notify` was rejected because Notify already means a park.
- **Enum and Action**: `Notification` gains a third member, `REPORT`, and `decide` gains a separate `Report` Action, not a Notify with a no-park flag. Its record is Reports, keyed like Notices, and its log kind is `reported`, never `notified`, so neither the parked status nor the Belief's hand-off sees it.
- **Belief**: kept, because nobody took the keyboard.
- **When**: on the first Tick that sees the Announcement, before the Clear, without waiting for a turn to end. It types nothing, which is the same exemption a Consultation has. It costs one Tick.
- **Once per Announcement**: each Announcement of the State reports, so the fifth `implement` reports a fifth time. An Announcement replaced before Naiad looks reports nothing. A Question's Announcement is not an entry and never reports. The start State of a spawned or adopted Run has no Announcement and does not report.
- **Content**: title `naiad: <run id>`, message `entered <state>` plus `: <subject>` when there is a Subject. No Task.
- **Legs**: terminal, desktop and ntfy, with ntfy at priority 2.
- **Refusals**: the loader (and so `naiad workflow check`) refuses `report` on a Gate State or a Terminal State and names the State, since each already tells on entry.
- **Surface**: `naiad state set|unset <wf> <state> report` through the generic key table, and a `report` mark beside the kind in `show` and `list`. The starter declares none. `docs/workflow-authoring.md` explains it using `ship` as the example.
