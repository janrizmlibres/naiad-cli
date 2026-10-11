# A State may reserve its Questions for the human

> Amended by ADR 0050.

ADR 0045 wanted the Wayfinder loop never to put a Question to the Answerer: a map's tickets are the decisions the map exists to put in front of a person, and an Answerer settling one is the grilling agent answering its own questions. Naiad had no way to say so, so the Prompt said it — never ask a Question; if you need one, leave the ticket claimed and announce `chart` instead. That was a pin standing in for a rule.

We decided a State may declare whose its Questions are: `questions = "human"` reserves them, and absence is the Answerer, which is what every State meant before the key existed.

## The rule lives in the decision, not the Prompt

A pin holds only as long as the agent obeys it, and the failure when it does not is silent: the Answerer decides a design question with the Answer log the only witness, and the human finds out at review, if at all. A declaration in the Workflow cannot be disobeyed. The decision function reads the State the Question was announced from, and where it reserves, the Answerer is never consulted; nothing in the adapter layer has to know (ADR 0004).

It also puts the fact where its kind already lives. A State declares its Model and Effort because they are judgments about the phase's work rather than the agent's (ADR 0026); whose a Question is belongs to the same list. A Prompt telling the agent not to ask was a State setting written as an instruction.

## The agent's side is unchanged

The Protocol says never ask a human directly, and ask through Naiad instead. A reserving State keeps that word for word: the agent asks exactly as it does anywhere, and who answers is Naiad's business. The alternative — a second Protocol for reserving States, or a Prompt that contradicts the Protocol as ADR 0045 accepted — was rejected because the Protocol is what the agent reads on every Nudge, and it must not depend on which State it is in.

## Parking is an Escalation

A Reserved Question takes the Escalation's road: Naiad notifies at once, without waiting on a turn ending — notifying sends nothing into the session — and the Run parks until the human answers in the Session and the agent carries on. Notified once per Announcement, as everything reaching a human is. No new Action was added, for the reason ADR 0004 gave when Escalation was folded into Notify: a Gate reached, an Answerer escalating and a Workflow reserving are one behaviour.

The notification carries the Question's text and the State's name. An Escalation's carries the Answerer's reason, and the human reads the Question itself in the session; here no Answerer has phrased anything, and the notification is what the human sees before they sit down.

The Answer log records it as escalated, with that reason. The log's columns answer "what became of it", and what became of it is that a human was woken — the reason says by whom. A third flag was rejected as a format change bought for a distinction the reason already makes.

## What `chart` no longer means

ADR 0045 gave `chart` two meanings the Subject told apart: the next ticket is HITL, or the current one turned out to need a person. The second was the pin's detour, and goes with it. A `wayfind` pass that needs a person asks, the Run parks in `wayfind`, and when the answer arrives the same context finishes the ticket and scans on. `chart` means one thing again.

## Consequences

The Workflow gains a key, the State a field, and the loader rejects any value but the two. The shipped Workflow declares it on `wayfind` alone; every other State keeps the Answerer, and the tests hold that a State saying nothing consults as before.

`wayfind`'s Prompt loses its longest paragraph. What remains is the skill invocation, the one-ticket rule, and the routing table.

A Reserved Question wakes the human for every decision the pass cannot make, including ones the Answerer would have settled correctly from the repository. That is the choice ADR 0045 made and this ADR keeps: on a map, the human's clock is the price of the human's decision.
