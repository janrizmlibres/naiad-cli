# A Wayfinder map is walked AFK-first, and its stop is a Gate

> Narrowed by ADR 0060.

`/wayfinder` plans an effort too big for one session as a map of decision tickets and resolves them one per session. Some of those tickets are AFK — research, or a task the agent can drive alone — and until now every one of them cost a human a session start, because nothing walked the map unattended. The shipped Workflow gains a loop that does: it resolves the AFK tickets at the head of the frontier in order, and stops the moment the next one is a human's.

We decided three States: `wayfind`, `chart` and `map-spec`.

## Entered by name, never by classification

A Run reaches `wayfind` only because an Entry was made `--at wayfind`, or an Adoption was made from a Session that charted the map. `classify` never routes there. Whether an effort is too big for one session is the judgment the wayfinder documentation gives to the human, and charting is human-in-the-loop by the skill's own rule, so there is nothing for `classify` to decide.

The Entry names the first ticket as its Subject and nothing else. An Entry with a Subject and no Task takes the Subject as its Task, so the operator types one path. The Prompt opens with `/wayfinder {subject}`, and a Subject slot is what makes a bare Entry refuse (ADR 0009): a State that would otherwise scan the frontier itself on entry was considered and rejected, because it needs either a Prompt with no slot — which loses the Subject's role as the Run log's per-ticket line — or a change to Naiad so a State may declare its Subject optional, which is a domain change bought for one convenience.

## `Mode:` is the authority

Every ticket carries a `Mode:` line reading `AFK` or `HITL`, whatever its `Type:`. The scan reads that line and nothing else. The skill's types imply a mode — research is AFK, grilling and prototype are HITL — but `task` is either, and inferring it from the body is a judgment the selecting agent should not make about work it will then do alone. A missing line reads HITL, which is the one-way bias ADR 0010 states: an unnecessary stop costs one interaction, and an agent provisioning access on its own reading of a paragraph costs more.

## The stop is strict

The scan takes the lowest-numbered open, unclaimed ticket whose blocking edges are all satisfied, and routes on its `Mode:`. A HITL ticket at the head of the frontier stops the loop even when AFK tickets sit behind it. Wayfinder's frontier order is deliberate, and a decision a human makes may reshape the tickets after it without an explicit edge naming them. Stepping past it to keep the Run busy would resolve tickets on assumptions the human is about to overturn.

## The stop is a Gate, not a Hold

`chart` is a Gate State: no Prompt, no Model. The human works the HITL ticket in the parked Session, and Naiad types nothing.

The alternative was a Prompted State that delivers `/wayfinder {subject}` on a model of its own and then declares a Hold while the human answers its questions. It was rejected because a Hold is declared on the human's instruction, and a Workflow-instructed one widens that verb; because the Protocol says never ask a human directly, and the pin would say the opposite; and because the only thing bought is a Model typed for the human, which they can type themselves at any Gate today. Every Notify discards the Belief, so the next `wayfind` pass re-types its own settings without help.

`handover` was not reused. Mechanically it could be — a Gate is a name and its candidates — but a Run parked at `handover` tells the operator the loop declined an implementation ticket, and a Run parked at `chart` tells them the opposite: a decision is theirs to make, then the loop resumes. ADR 0041 dropped the Subject from `handover` announcements, so the State name is the only word the notification carries, and one Gate per kind of hand-off is the pattern `no-repro`, `review` and `handover` already follow.

## The Answerer is never consulted

An AFK pass that meets something the ticket does not settle does not ask a Question. Elsewhere in the Workflow the Answerer settles what the repository settles (ADR 0034), but a decision ticket is the thing the map exists to put in front of a person, and the skill's own rule is that the agent never stands in for the human's side of it. An Answerer resolving one would be the grilling agent answering its own questions, with the Answer log the only witness.

As first written, this was a pin: Naiad routed every Question to the Answerer with no per-State override, so the Prompt told the agent never to ask one and to announce `chart` with the ticket as Subject instead. ADR 0046 replaced the pin with a declaration — `wayfind` reserves its Questions for the human — so the agent asks as the Protocol says and Naiad parks the Run without consulting. `chart` keeps one meaning: the next ticket is HITL.

## One ticket per Announcement

The skill lets research tickets be resolved several to a session, as parallel subagents. The Prompt pins one ticket per pass, research included. One Subject per Announcement is what makes the Run log read per ticket and keeps the loop the shape `implement` has. The skill's parallelism serves a human's clock, and a Run has no clock to serve.

## No Working branch

`wayfind` derives no branch and reads no Predecessor. Planning writes to the tracker, and research findings go where the skill puts them. A Working branch declared here would become the Predecessor of the next Entry for the same repository and stand for nothing.

## A cleared map gets its own spec

When the scan finds no open ticket, the way is clear, and the wayfinder documentation hands off to `/to-spec` pointed at the map. `spec` cannot serve. `/to-spec` synthesises "the current conversation", so on the grill path `spec` must not Clear; a spec written from a map wants a fresh context pointed at the map, which is a Clear plus a Prompt naming it. One State cannot both Clear and not Clear, so `map-spec` is the second: it Clears, delivers `/to-spec {subject}` with the map file as Subject, and continues into `tickets`. Reusing `spec` by pinning a read of the map into a context that had just spent itself on one ticket was rejected as exactly the pin ADR 0041 removed.

Which State announces `map-spec` depends on who has looked at the map. From `wayfind`, the last pass was unattended, so the scan announces `review` and the human sees the cleared map before a spec is written from it; `review` gains `map-spec` as a candidate beside `spec`, and the agent announcing after the Gate stands in the context that read an empty frontier and knows which road it is on. From `chart`, the human already holds the keyboard — they resolved the last ticket by hand — and a Gate after a Gate hands the keyboard to the person holding it, so `chart` names `map-spec` directly.

## Consequences

Three Gate States become four, and `review` is the first Gate in the declared order to branch. The tests assert nothing about either, because they hold invariants rather than content (ADR 0043).

The scan's routing table now exists in three Prompts, reading a different line in the third. ADR 0034 accepted the second copy for the same reason the third is accepted: the alternative is a State whose whole job is to read one line, at a Clear, a delivery and a turn per ticket.

A `task` ticket marked AFK is now implemented unattended, and the skill's own warning applies with more force: a task that is a slice of the build rather than a step that unblocks a decision is mis-typed, and this loop will do it without anyone watching. The `Mode:` line is where a human says so, and reading it as the authority is what makes that line worth writing carefully.
