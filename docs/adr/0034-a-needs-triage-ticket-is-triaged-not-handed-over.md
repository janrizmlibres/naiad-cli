# A needs-triage ticket is triaged, not handed over

> Amended by ADR 0041.

ADR 0010 sends every status other than `ready-for-agent` to the `handover` gate. Its argument is a one-way bias. An unnecessary pause costs one operator interaction. An agent implementing an under-specified ticket costs a review cycle and a revert. Where the loop is unsure it pays the cheap one.

`needs-triage` satisfies only half of that argument. The loop must not implement such a ticket, and that half stands. But `ready-for-human` names work an agent cannot do, while `needs-triage` names work nobody has specified yet. Specifying it is precisely what an agent can do. So the gate woke a human to ask for a brief the agent was able to write, and woke them again on every later Run that scanned the same file.

Two things produce such a ticket. `/to-tickets` writes a status this repository does not sanction — the `tickets` Prompt pins `ready-for-agent`, and a pin can fail silently (ADR 0033). And an agent files follow-up work in the middle of a Run. Nobody specified that work, so `needs-triage` is the honest status for it.

We decided the Workflow gains a `triage` State. It runs `/triage` on one ticket, writes an outcome, and then chooses what comes next. `implement` and `handover` both name it as a candidate, and it names itself.

## One ticket per pass

`triage` takes its ticket as a Subject, exactly as `implement` does, and ADR 0009 gives Subjects that job already. The loop meets `needs-triage` one ticket at a time, because the scan stops at the frontier. A pass over the whole tracker would triage tickets the Run may never reach, and one bad judgment would contaminate every ticket after it in the same context.

## The pass always scans again

`triage` ends with the scan-and-route paragraph `implement` ends with, and one row is added to it: `needs-triage` announces `triage`.

Scanning again is what makes `wontfix` advance on its own. That outcome closes the ticket and moves the frontier past it, so the Run must find the next ticket rather than park. Every other outcome falls out of the same scan without a rule of its own. `ready-for-agent` leaves the ticket as the frontier, so the scan announces `implement` for it. `ready-for-human` and `needs-info` leave it open and not implementable, so the scan announces `handover` — ADR 0010's routing, untouched. One rule covers all four outcomes.

The cost is that the routing table now exists in two Prompts. We accepted it. The alternative is below.

## The Answerer settles what the ticket leaves open

A pass will meet things the ticket does not say. The State announces those as Questions rather than writing `needs-info` at the first one. The Answerer carries its understanding of the repository across the whole Run, so it settles things a Cleared triage context cannot.

The Answerer may decline, and an Escalation parks the Run as a Gate does. Naiad notifies and sends nothing into the session — `Respond` types the Answer in, `Notify` does not — so the agent never learns that its Question was escalated. What reaches it is a person typing at the parked session. The Prompt is written to that fact: it acts on a reply that does not settle the question, rather than on an Escalation it cannot observe.

The State then writes `needs-info` on the ticket, with the open questions on it. The Answer log records the Question, but a person reading the tracker next week reads the ticket. A ticket left saying "not yet looked at" would lie to that reader.

That write also closes a loop. A pass that ended with the ticket still `needs-triage` is a pass the next scan repeats, forever, with nothing to stop it. `needs-info` routes to `handover` instead.

## The pins are ADR 0033's

`/triage` is written for a maintainer at the keyboard. It recommends, then waits for direction, and it can open a grilling session. Both stall an unattended Run. The Prompt therefore pins four things: triage this ticket only, decide without waiting, ask the Answerer rather than a human, and never end a pass at `needs-triage`. ADR 0033 holds the instances and states the rule, so they are recorded there.

## Considered alternatives

**A selector State.** One State scans and routes, and `implement` and `triage` both announce it. It holds one copy of the table. Rejected because it spends a Clear, a delivery and a turn on every ticket to read one line. It also moves the choice away from the context that has just done the work, which ADR 0010 chose deliberately.

**A `needs-info` line in place of the Answerer.** The State settles what the repository settles and writes `needs-info` for the rest. Rejected because it wastes the one party built for this: the Answerer already holds the Run's understanding, and a Cleared context holds less.

**A guard in place of the pin.** The scan reads a `needs-triage` ticket that already carries triage notes as a second pass, and sends it to `handover`. Rejected because this project met the same hazard once and answered it with a pin — ADR 0033 records `/implement` leaving tickets unmarked and the loop picking them again. A guard also dresses a fault as an ordinary route, and costs two edits because the table is in two places.

**Letting `tickets` publish `needs-triage`.** Rejected because the context that writes a ticket holds the whole spec. A ticket it declines to specify is deferred to a Cleared context that knows less. The pin stays, and `tickets` gains no `triage` candidate — naming one would advertise a case the same file forbids.

## Consequences

`triage` Clears on entry, like `implement`. On the path from `handover` that discards what a human just typed into the session. The ticket is the Artifact that must carry it, and `issue-tracker.md` gives conversation a home under `## Comments`. Nothing enforces the write-down, and no Prompt can pin it, because `handover` is a Gate and delivers nothing.

Two Prompts now carry a decision procedure, where ADR 0010 said `implement` was the one to watch. The two tables must agree. If they drift, the Run log shows it: a ticket the two Prompts read differently produces a different Announcement from each.

An unattended Run now writes `wontfix` without a human seeing it. ADR 0027 makes that a real closure, and whoever drops a ticket must tend its dependents in the same act. The Answerer's boundary is what holds here — an already-implemented ticket is the repository's fact, while rejecting a request is a business judgment the Answerer escalates.
