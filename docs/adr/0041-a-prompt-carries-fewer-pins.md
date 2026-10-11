# A Prompt carries fewer pins

ADR 0033 let a Prompt pin what a skill leaves loose. The pins grew, and each pin came with its explanation. The prompts became long, and the length has a cost of its own: a long Prompt is hard to review, and it buries the argument the skill needs. We judged that cost above the value of most pins.

We decided to remove most pins and trust the skills. The Prompt names the work and the input, and little else.

## The pins removed

- **`classify`** no longer says "Do no other work." The Prompt asks for one judgment, and that is the scope.
- **`spec`** no longer pins the seam decision. `/to-spec` runs as written.
- **`tickets`** no longer pins the `ready-for-agent` label or the `ready-for-human` exception. `/to-tickets` applies its own labels.
- **`implement`** opens with `/implement {subject}` and no longer says "only that one" or "take that as given".
- **`triage`** no longer pins "decide without waiting", "only that one", or "ask as the protocol describes".
- **The scan block** no longer defines a satisfied edge. It says "blocking edges are all satisfied" and leaves the reading to the agent.
- **`handover` announcements** no longer carry a Subject. The agent states the status it found in the session instead.

## The pins kept

- **`implement`** still sets the finished ticket's Status line to `resolved`. The scan reads that line, so an unmarked ticket is picked again.
- **`triage`** still bounds `needs-info` to the case a person has closed, and still lists the four permitted end statuses. The list omits `needs-triage`, which keeps the pass from ending where it started.

## Consequences

The incidents ADR 0010 and ADR 0033 record can recur. `/to-tickets` can improvise a label, and the loop then parks at its first ticket. `/to-spec` and `/triage` can stop and wait for a person who is not there, and Naiad then Nudges and parks the Run. We accept this. If a Run parks that way, the fix is to restore the one pin that failed, not all of them.

The tests changed with the prompts, because a test here asserts a design decision and changing the test is the change (ADR 0010).

ADR 0010, ADR 0033 and ADR 0034 carry notes that point here. Their reasoning stands as history; the pins they record are no longer all in the file.
