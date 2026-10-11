# 06 — A State can Report on entry

Status: resolved
Mode: AFK
Blocked by: 02
Spec: [PRD](../PRD.md), "The Workflow loader" and "The engine"; ADR 0055

**What to build:** A State may declare `report = true`. Each Announcement of it is Reported: the operator is told `entered <state>`, plus `: <subject>` when the Announcement has one, titled `naiad: <run id>`, on the terminal, desktop and ntfy legs. ntfy sends it at priority 2. The Run does not park and the Belief stands.

- `Notification` gains `REPORT`, and the decision function gains its own `Report` Action, separate from Notify.
- The Report has its own Reports record, keyed like Notices, and a `reported` Run-log kind that neither the parked status nor the Belief reads.
- It fires on the first Tick that sees the Announcement, before any Clear or Switch, without waiting for a turn end, once per Announcement. Repeats report again.
- A Question's Announcement and a Run's start State never report.
- The loader accepts `report` as a boolean on a State and refuses it on a Gate State or a Terminal State, naming the State.

- [ ] A `report = true` State produces one Report per Announcement, then the Clear and Prompt proceed as before.
- [ ] After a Report the Run reads `running`, not `parked`, and a following State's Switch is not re-typed.
- [ ] No Report for a Question asked from that State, nor for a Run that started there.
- [ ] ntfy receives priority 2 for a Report.
- [ ] `report = true` on a Gate or Terminal State is refused at load, naming the State.
- [ ] Built test-first, Refactor verdict recorded.
