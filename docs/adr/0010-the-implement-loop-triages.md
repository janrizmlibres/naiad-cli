# The implement loop triages, and declines work it should not do

> Amended by ADR 0034, ADR 0041.

The tickets a feature breaks down into are not uniformly agent-implementable. `docs/agents/triage-labels.md` gives this repository five triage roles, of which one — `ready-for-agent` — means fully specified and ready for an unattended agent, and another — `ready-for-human` — means the opposite. The implement loop had no vocabulary for either. Its Prompt asked for the next ticket *"that is ready to start"*, a phrase that appears in no other document and maps to no label.

Given eight tickets all marked `ready-for-human`, the agent did the only sensible thing left to it and asked a human directly. That is a Protocol violation, but the Protocol was not really the problem: the loop had no exit that meant *this is not mine to do*. Its only announcements were itself and the pull request, so declining a ticket was unsayable.

Three things change.

## The tickets are labelled deliberately

The loop's rules are worth nothing if the labels they read are noise, and they were noise. `/to-tickets` applies `ready-for-agent` only on its "real issue tracker" branch; its local-files branch writes a single flat `tickets.md` with no status at all. This repository uses neither shape — it uses per-issue files under `.scratch/` with a `Status:` line, per `docs/agents/issue-tracker.md`, which the skill has no branch for. So the layout came from the repository's documentation and the label from nowhere, and was improvised each time: `ready-for-agent` in two trackers here, the undefined `ready` and `needs-info` in a third, and `ready-for-human` across all eight tickets of the run that failed.

`/to-tickets` is an external skill and is not ours to edit; editing it means re-editing it on every update. The `tickets` State's Prompt is ours, and the skill leaves the hook open itself — *"Apply the `ready-for-agent` triage label unless instructed otherwise."* So the Prompt instructs, and names the exception: a ticket is marked for a human only where the work genuinely cannot be done by an agent, and says why.

The criterion for that exception is the Answerer's, deliberately. The glossary already draws this line once — credentials, external spend and business priorities are not in the repository, so answering from it would be inventing. What the Answerer must escalate and what an agent cannot implement are the same boundary, and one criterion stated once is worth more than the brevity of leaving the second implicit.

This holds only for tickets this Workflow created. A Run started at `implement` against a hand-written tracker meets whatever labels are there, which is why the loop's rules below treat an unrecognised label as a real case rather than an impossible one. That Run must name its first ticket — `naiad run … --at implement --subject <file>` — and is refused without one (ADR 0009).

## Declining is a Gate State

`implement` gains a candidate, `handover`, with no Prompt. Naiad delivers nothing, the operator types into the still-live session, and the agent announces `implement` for the next ticket or `pull-request` if none remain.

This is the shape `diagnose → no-repro` already has, and ADR 0007 gives it the behaviour it needs without an argument: a Gate State named as a branch candidate is never skipped, because it is a destination the agent chose rather than a routine checkpoint on the path. A Run resolving with Gates skipped still parks here, which is right — `ready-for-human` means the agent cannot proceed, not that a review is optional.

The alternatives were worse in ways worth recording. Announcing a Question would route through the Answerer, which by construction cannot settle this one — a `ready-for-human` ticket is precisely the work the repository does not determine — so it would escalate every time, paying a Consultation to reach a notification by a longer road and filling the Answer log with things that were never questions. Simply stopping without announcing would reach the same notification through the silence and Nudge path, but that path exists to detect a *broken* agent, and using it for a correct decision makes the two indistinguishable in the Run log.

`tickets` declares the gate too, alongside the loop. Its Prompt has to name the loop's first ticket — there is no previous iteration to choose one, and it is the context that has just published them all — so it is also the first place that can find nothing implementable. A feature whose every ticket is genuinely a person's to write is a real outcome rather than a malformed one. Leaving it undeclared would still work, since a Deviation is permitted, but it would be recorded as one on every legitimate use, and a Deviation is read as the symptom of a confused agent.

`implement` declares itself among its candidates, the only State in the Workflow that does. It does not have to: `deviation()` exempts re-announcing the State the agent is standing in, and that exemption is what makes the loop a loop. But the Protocol injected into every fresh context renders the candidates verbatim, and a Protocol reading *"announce whichever applies: handover or pull-request"* omits the announcement this State makes more often than both of the others together.

## Unrecognised labels go to the human, and say so

Only `ready-for-agent` is implemented. `ready-for-human`, `needs-triage`, `needs-info`, `wontfix`, a status this repository does not define, and a missing `Status:` line all route to `handover` — and the Prompt requires the agent to say in the session which status it found.

That last clause is the whole reason this is a rule rather than a default. Routing everything unknown to a human and routing `ready-for-human` to a human are the same action, but they need opposite responses: the first means the label is wrong and should be fixed, the second means the work is a person's to do. A gate that cannot tell the operator which one it hit wastes their time on every occurrence.

The bias is deliberate and runs one way throughout. An unnecessary pause costs one operator interaction. An agent confidently implementing a `needs-info` ticket — one whose specification is *known to be incomplete* — costs a review cycle and a revert, and is the most expensive outcome available here. Where the loop is unsure it pays the cheap one.

## The selector routes, not the receiver

The agent that reads the `Status:` line is the one *choosing* the next ticket, not the one receiving it. It announces `implement` with the ticket as its Subject when the label is `ready-for-agent`, and `handover` with the same Subject otherwise.

Having the receiver check instead would spend a full Clear, delivery and turn on every declined ticket, only to read one line and hand back — and the Clear destroys the context that did the selecting, so the receiver would have to re-scan the tracker to explain itself. It also splits one judgment in two. Choosing the next ticket is inseparable from the labels and the `Blocked by:` edges, because the frontier is what is unblocked *and* implementable; computing it in one context and vetoing it in another is the same knowledge held twice, free to drift.

Doing both was rejected for the reason ADR 0033 gives about Prompts and skills: logic in two places is maintained in two places. If the two ever disagreed the receiver would silently win, and the Run log would show a `handover` the selector never intended.

So the Prompt tells the receiver to implement the ticket at its Subject, flatly, with no condition attached. By construction it cannot have arrived there otherwise, and stating it as a given is what makes the contract legible.

## Consequences

`implement` now does two things: implement the ticket it was given, then triage the tracker to choose what it announces. That is more than running a skill on an input, and it is the one Prompt in the Workflow carrying a decision procedure rather than an argument. The loop's continuation logic already lived there — *"If tickets remain after it, announce implement again"* — so this sharpens an existing responsibility rather than adding one, but it is the State to watch if that Prompt keeps growing.

Like `diagnose`, this Prompt writes its successors out rather than interpolating `{next_state}`, and now for both of the reasons that pattern exists: the placeholder renders every candidate as one joined phrase, which is useless where a different condition attaches to each exit, and wrong here in particular where the "no tickets remain" line must name the pull request alone.

The Workflow has three Gate States rather than two, and the test asserting the exact list changes with it. That test asserts a design decision, so changing it is the change.
