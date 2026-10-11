# The adopt skill takes the operator's words

The operator says "naiad, spec this out". The sentence names a phase, but not in the Workflow's own words. The State is `spec`, and its Prompt opens with the `/to-spec` skill, so the operator says "to-spec" for a State that is not called that. The adopt skill therefore takes two arguments — the Workflow and the State — and each carries the operator's words rather than a resolved value. The agent resolves them.

To resolve them, the agent must see what the Workflow declares, and today it cannot. So Naiad gains `naiad states [workflow]`. Given a Workflow, it prints that Workflow's States. Given none, it prints every Workflow in the library with its States. Each line carries the State name, the slash command its Prompt opens with, a mark for a Gate State or the Terminal State, and a Branching State's candidates. The slash command is the column that settles "to-spec" onto `spec`. The mark keeps a loose word off a State that parks the Run immediately or ends it.

This reverses a choice inside ADR 0023, which declined a listing command and let the refusal do the listing. The refusal still lists and still refuses. But it teaches only an agent that has already guessed, and an agent guessing at States it has not read is what this change prevents.

Reading the Workflow file directly was the free alternative, and it was rejected. The agent can read a path, but a bare name lives under the Naiad home, so the skill would expand `<home>/workflows/<name>.toml` itself. That is a second resolver, shipped by Naiad, against ADR 0023's rule that a name resolves at the entrance and nowhere else.

Three rules govern the resolution, and each one prefers a question to a guess. The agent takes the State when exactly one matches the operator's words, and asks when two or more match — `review` and `review-fix` both answer to "review this". It takes the sole Workflow in the library when the operator named none, because one candidate is not a choice, and asks when the library holds several. It never falls back to a Workflow by name: Naiad knows no Workflow's meaning.

Both arguments are optional, which decides their form. Claude Code expands an omitted named argument to an empty string, and leaves an omitted positional `$1` in the text as the literal `$1`. Only the named form degrades cleanly, so the skill declares `arguments: [workflow, state]`.

The State word never triggers the skill. "spec this out" is also the most ordinary way to ask any agent for a spec, and a description matching it would queue a takeover of the session on an everyday request. The description keeps the takeover phrases the operator already uses, and the agent reads the State word off the same sentence.

## Consequences

An unknown start state stays a refusal the agent reports and stops on, as ADR 0028 requires. The agent read the State list before it chose, so a refusal means its reading was wrong, and the operator is the one who must see that.

`naiad states` becomes a public verb that the adopt skill depends on. Naiad installs that skill onto the operator's machine, so an installed copy can outlive a change to the command it names — the same drift the marker in the skill already warns about.
