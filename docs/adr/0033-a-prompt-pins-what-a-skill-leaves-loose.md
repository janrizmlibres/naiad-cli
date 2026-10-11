# A Prompt pins what a skill leaves loose

> Amended by ADR 0041.

Most of the shipped Workflow's States run an external skill. The skills are not
ours to edit. An instruction added to a skill file is lost the next time the
skill updates, so a skill file is not a place a Workflow's requirement can
live. The Prompt is ours, and it is the only place such a requirement
survives.

We decided the Prompt pins what the skill leaves loose. A pin is an input to
the skill, not a copy of its logic: how the skill does its work stays the
skill's own, and the Prompt adds only what the skill left unsaid. ADR 0010
already argued this once for the triage label. This ADR states the rule and
holds the instances, so the next pin needs no ADR of its own.

## The instances

**`tickets` pins the triage label.** `/to-tickets` applies `ready-for-agent`
only on its real-issue-tracker branch, and says nothing about a status for a
local markdown tracker. The label was improvised each Run. The implement loop
filters on that label, and a filter that reads noise is worse than no filter:
every Run would park at its first ticket. ADR 0010 gives the full argument and
the exception criterion.

**`spec` pins the seam decision.** Left alone, `/to-spec` sketches its seams
and offers them. In a Run that is a question nobody is awake to answer. The
Answerer cannot settle it either: which seam a feature is tested at is a
judgment about the work, and ADR 0001 puts those with the agent, which is the
party holding the codebase. So the pin is not "choose well" but "choose, and
write down what you chose". The Prompt tells the agent to record the seams it
took, and the ones it rejected, in the spec's Testing Decisions section. The
choice is then reviewed where the rest of the spec is reviewed, rather than
waking a human to approve it in advance.

**`implement` pins the finished ticket's status.** `/implement` marked a
ticket done unreliably — sometimes yes, sometimes no. The `Status:` line is
the only record the loop and a reader have. Marking it is also what shrinks
the frontier: the loop's scan reads open tickets only, so a ticket left
unmarked is one the loop picks again. The Prompt therefore sets the line to
`resolved` itself, before anything else. `resolved` is `issue-tracker.md`'s
own completion status, reused here rather than added as a sixth triage role,
which the triage table is not (ADR 0010, ADR 0027).

**`triage` pins who decides, and where a pass stops.** `/triage` is written for a
maintainer at the keyboard. It recommends a category and a state and then waits
for direction, it can open a `/grilling` session to specify the ticket, and it
flags unusual transitions for a maintainer to confirm. All three stall an
unattended Run, which Naiad then Nudges and parks — the failure this rule exists
to prevent. The Prompt pins four inputs. Triage the ticket the Subject names,
and only that one. Decide the category and the status without waiting on anyone.
Raise a Question for what the ticket leaves open, so the Answerer settles it,
and write `needs-info` where the reply does not settle it. End the pass on one
of the four remaining statuses, never on `needs-triage` — a ticket left at
`needs-triage` is one the next scan hands straight back, forever. ADR 0034 gives
the routing these pins serve, and the reason the last two are written against a
reply rather than against an Escalation.

## Considered alternatives

**Edit the skill.** Rejected because the edit is lost on the next update, and
the loss is silent — the Workflow keeps running and the pin simply stops
applying.

**Fork the skill.** Rejected because it trades one lost edit for a permanent
second copy, and the copy drifts from the original with nobody watching.

**Let the skill ask.** Rejected because an unattended Run has nobody to answer.
The question routes to the Answerer, which by construction cannot settle a
judgment about the work (ADR 0001), so it escalates and the Run parks for a
decision the agent was already able to make.

## Consequences

Every pin makes a Prompt longer, and a Prompt carrying a decision procedure is
the one to watch — ADR 0010 says so about `implement` already. The boundary
that keeps this affordable is the pin's shape: an input, never a procedure. A
pin that starts to describe how the skill works has become the copied logic
this rule exists to prevent.

A pin can outlive its reason. A skill that later specifies the behaviour
itself leaves the Prompt instructing for a case the skill now handles, and
nothing detects that. The cost of a stale pin is a redundant line rather than
a wrong Run, which is why this is accepted rather than solved.
