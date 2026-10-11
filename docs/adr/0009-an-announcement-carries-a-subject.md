# An Announcement carries a Subject

A State that repeats needs to say what it is repeating over. The implement loop is one State, Cleared and announced once per ticket, and until now the Prompt it received was the same sentence every time: *"the next ticket in the project's issue tracker that is ready to start"*. Which ticket that named was left to the agent receiving it — an agent whose context had just been wiped, and which therefore had to reconstruct the whole tracker to answer a question the previous iteration already knew the answer to.

That is where it went wrong in practice. Handed a tracker whose tickets were all labelled for a human, the receiving agent had no rule covering the case, and asked a human directly — which the Protocol forbids. The Prompt's vagueness was the proximate cause, but the deeper one is that the selection was being made in the worst-informed context available.

So an Announcement now carries a **Subject**: `naiad announce implement --subject .scratch/feature/issues/04-x.md`. Naiad substitutes it for `{subject}` in the Prompt it delivers, records it in the Run log, and does nothing else with it.

## Why the Subject is opaque

The obvious spelling was `{ticket}`, and it was rejected. `naiad/domain/prompt.py` would have acquired the word *ticket*, and it would have been the first term from a particular Workflow's vocabulary to reach the domain layer. Nothing would have stopped the second: the next Workflow with a loop wants `{file}`, or `{endpoint}`, and there is no principled line to hold once the first one is across.

The refusal is the same one ADR 0002 makes about Claude Code's internals and ADR 0005 makes about routing, and it is the property the glossary's first entry names — swapping the Workflow file swaps the Workflow, because Naiad knows nothing about any particular Workflow's meaning. A Subject is a string Naiad carries from an Announcement to a Prompt. That it happens to be a path to a markdown file with a `Status:` line is known to the Workflow and to the agent, and to nothing else.

The cost is one glossary entry and a name less evocative than `ticket` at the one call site that currently uses it. That is cheap now, and `{ticket}` is also cheap now — the difference is which one is still cheap after the second Workflow exists.

## Why the two directions are not symmetrical

A Prompt containing `{subject}` announced without one is rejected by `announce`, with the correct invocation in the error. This follows the rule already in `naiad/cli/announce.py` for a State the Workflow does not declare: it is a clerical slip, the agent can fix it inside its own turn, and *"a slip would be silently inert"* if unchecked. Catching it at delivery instead would park the Run and summon a human for a typo, which teaches an operator to ignore notifications. Rendering it empty, or leaving the placeholder in, would send a malformed Prompt into a session that has just been Cleared and so has no memory of what it meant to pass — the one failure here that cannot be recovered from.

Naiad does not need to be told which States require a Subject. The Workflow says so by using the placeholder, which keeps the requirement in the Workflow file where the rest of that Workflow's meaning lives.

The guard has to sit at *every* entrance to delivery, not merely the common one, and there are two. Kickoff is the second: a Run started with `--at implement` announces nothing, so `announce_state` never sees it, and the Run's opening Prompt would arrive with the placeholder rendered empty. That path is real rather than hypothetical — ADR 0010 describes starting there against a hand-written tracker — and it is the worse of the two, because the Prompt goes on to say the ticket has been triaged as ready, so a blank one tells the agent to trust a decision about a ticket that was never named. `naiad run` therefore takes a `--subject` of its own and refuses without one, before the Run directory or the session exists, exactly as it already refuses a malformed Workflow or a mistyped start State.

Both guards test the Subject for being *blank*, not for being absent. `--subject ""` is not `None`, and a check written against `None` would let an empty string through to be persisted, rendered, and delivered — the same unrecoverable failure reached by a different door. An agent building the invocation from a path it scanned and did not find produces exactly that, and it is likelier than omitting the flag outright.

The reverse is not an error. A Subject given to a State whose Prompt has no slot for it is kept and logged, because the Prompt is one reader of a Subject and the Run log is another. The case that settled it is the Gate State this loop hands work to: it has no Prompt at all, so its Subject is substituted nowhere — and it is the most useful Subject in the Run, because it is the one telling the human which ticket they have been handed. Rejecting it would have rejected the best instance of the feature. Without it the Run log records that a Gate was reached and leaves the operator to go read the session to find out what about, which is what the Run log exists to prevent.

Stated generally: a required input that is absent is an error, an optional annotation that goes unused is not.

## Consequences

An Announcement is no longer only a name. `Announcement` gains a field, and so do `Deliver` and the Run log; `render_prompt` gains a third placeholder. The Subject is optional throughout, so every existing Workflow and every State that does not use it is unaffected.

The agent that names a Subject is the agent that announces, which means the choice of the next item is made *before* the Clear rather than after it. This is the point of the change and not a side effect: the selecting context is the one that has just done the previous item and can see the whole series, and the Cleared context that receives the Prompt is told what to work on rather than asked to work it out.

Naiad still models no iteration and no exhaustion condition, exactly as ADR 0001 says. It does not know that Announcements naming the same State form a series, or that the Subjects differ between them. It substitutes a string.
