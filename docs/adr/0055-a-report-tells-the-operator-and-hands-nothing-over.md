# A Report tells the operator and hands nothing over

Naiad interrupted a human for exactly two reasons: the Run needs them, or the Run is over. The `Notification` enum had two members and said so, and every telling of the first kind parks the Run and discards the Belief, because a human is assumed to hold the keyboard afterwards. An adopter who wants to hear that a Run reached `implement`, or that it started `ship`, is asking for neither. Nobody is needed and nothing is over, and parking the Run to say so would stop the work the telling reports on.

We decided a Workflow may mark a State `report = true`, and an Announcement of that State is then **Reported**: the operator is told the Run entered it, and nothing is handed over. The two reasons become two reasons to interrupt and one to inform. `Notification` gains a third member, `REPORT`.

## A third Action, not a Notify that doesn't park

Everything that reads a hand-off reads a Notify. A Run is parked when its Notices say it was notified about the Announcement it stands in, and the Belief is discarded when a `notified` line follows the last Switch. A Notify with a "does not park" flag would make each of those readers check the flag, and a reader that forgot would park a Run nobody was asked to look at. So a Report is its own Action in the decision function, with its own record and its own `reported` log kind. Nothing that decides parking or the hand-off can see it. The Belief survives a Report because nobody took the keyboard.

## When it fires

On the first Tick that sees the Announcement, before the Clear, without waiting for a turn to end. It sends nothing into the Session, so it can't type over an agent still writing, the same exemption a Consultation has. The operator hears "entered `implement`" when the agent says it, not after a Clear and two Switches. It costs one Tick. Tying it to the Prompt's delivery was rejected: a Prompt that is typed again or never lands would delay the Report or send it twice.

Once per Announcement, like every Action. A State announced for the fifth ticket reports a fifth time, and the Subject tells the five apart. An Announcement replaced before Naiad looks reports nothing. A Question's Announcement names the State the agent stands in but is not an entry, and never reports. The State a Run starts at has no Announcement behind it, spawned or adopted, and does not report: the operator just queued or adopted the Run.

## What it says and where

The title is `naiad: <run id>`, like every telling. The message is `entered <state>`, followed by `: <subject>` when the Announcement carries a Subject. The Task is left out because the run id already names the Run and a Task can swamp a banner. It goes down every leg: the terminal is the record of the night, and the desktop banner costs nothing. ntfy sends it at priority 2, low enough that a milestone never sounds like a Gate. As before, the mapping belongs to the adapter.

## Where it may be declared

On a State, and nowhere else. A file-level default was rejected because a Report is for particular milestones, and an operator who wants every State is really asking to watch the Run log. A default can still be added later without breaking any file. The loader refuses `report = true` on a Gate State or a Terminal State, naming the State, because each already tells on entry (a Notify and a Finish), and a second telling is a mistake to point out, not a preference to honour.

## Considered alternatives

**`notify = true`.** Rejected: Notify already means Naiad needs a human, and the key would read as asking for a park.

**A file-level list of States to report.** Rejected: it puts one State's behaviour away from the State, which every other State key keeps together.

**Push only.** Rejected: the terminal leg is never configured away, because it is the one that can be read hours later.

## Consequences

`Notification` has three members, and its docstring's "two members and no more" becomes two reasons to interrupt and one to inform. The decision function gains a `Report` Action. The tick gains a Reports record keyed like Notices, and the Run log gains a `reported` line that `belief` and the parked status ignore. ntfy maps `REPORT` to priority 2. The Workflow loader reads `report` on a State and refuses it on Gate and Terminal States. `naiad state set|unset` handle it through the generic key table, and `show` and `list` add a `report` mark beside the kind. The starter declares none. `docs/workflow-authoring.md` explains it using `ship` as the example.
