# Waiting on external state stays in the Prompt

> Superseded by ADR 0021.

A State may need something that arrives from outside the session: the `pull-request` State cannot announce its successor until Claude Code Review has posted, because `/fix-review` has nothing to work from until then. Naiad has no vocabulary for this. An agent that ends its turn without announcing is Nudged twice and then parks the Run for a human, and a review arriving afterwards would wake nothing.

We considered teaching Naiad about it — a `waits` property on a State suppressing the silence rule, in the same family as `clear` and `terminal`. We decided against, and the wait stays in the Prompt: the agent blocks inside its turn and announces when the thing it waited for is there.

Two reasons, and the second is the one that settled it.

The property does not stand alone. Naiad cannot distinguish an agent deliberately waiting from an agent that forgot to announce — the signals are identical, and that indistinguishability is deliberate, because it is the whole reason `Nudge` exists. Suppressing the silence rule for a State therefore buys nothing on its own: nothing would ever poke the agent to look again, and the Run would stall permanently rather than for six minutes. The property needs a scheduled re-check beside it to be useful at all, which is two additions to the pure core (ADR 0004) rather than one.

And the cost that motivated it was a Prompt-wording problem. The objection to waiting in-turn was that it burns tokens: the Prompt said "poll", the agent reads that as a loop of separate tool calls, and each round re-sends the accumulated context. A single blocking command costs one call instead of fifteen. The engine was being asked to solve something the Prompt had caused.

## Consequences

Three bounds now hold this together, and a Workflow author writing another waiting State needs all three.

The Bash tool caps a single call at ten minutes, so that is the longest a blocking wait can be — and the budget the Prompt states is therefore the same number as the cap the tool enforces, rather than the fifteen minutes it claimed before, which no mechanism anywhere would have honoured. `HANG_SECONDS` is the real outer limit: an agent blocking in a tool call writes none of Naiad's records, so `idle_for` is indistinguishable from a hang and simply runs. A wait must fit inside thirty minutes with the rest of the State's work.

The wait needs a predicate with a terminal state. Claude Code Review is a check run on the pull request, so "has the check completed" is unambiguous where "has a comment appeared" is not — a partially posted review would otherwise let the agent announce early, and `/fix-review` would address a fraction of the findings while claiming to have addressed them. The predicate must also name that check alone: the build checks on the target repository run past fourteen minutes and would overrun the budget for a reason unrelated to the review.

The wait can expire, so the State after it must tolerate an absent input. `pull-request` announces `review-fix` anyway when nothing arrives, and Clearing discards the context that said so, which means `review-fix` reads a Prompt telling it to fetch findings that are not there. Its Prompt names the empty case explicitly. The failure this avoids is the quiet one: `/fix-review` stopping to ask a human who is not awake.

A review that lands after the budget expires is orphaned on the pull request and the Run ends clean. This is accepted rather than solved. Naiad's contribution degrades to what it would have been without the wait — the pull request is open, the findings are on it — and the human reads the pull request before merging it either way.

None of this is verified against a live repository. The behaviour of a real agent under this Prompt is a prediction until the smoke run in `docs/smoke/matt-pocock.md` says otherwise.
