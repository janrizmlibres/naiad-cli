# A Working branch is given or derived, never invented by Naiad

ADR 0015 made the Working branch required at the making of an Entry and refused when absent, on the grounds that Naiad cannot derive a correct name — a correct one follows the target repository's conventions, and Naiad knows no repository's conventions. That grounds was about *Naiad* inventing a name. It says nothing against the agent naming one, because the agent derives inside the repository with the conventions in front of it — the recent branch names, the pull request list, the prefixes the team actually uses — which is more than the operator typing `--branch` at a terminal ever sees.

We decided `--branch` is optional everywhere an Entry is made — `run`, `enqueue`, batch files, all through the one shared entrance (ADR 0014). Given, it behaves exactly as before. Absent, the Run starts with no Working branch and the head Prompt carries the rule: derive a name from this repository's conventions, falling back to conventional prefixes (`feat/`, `fix/`, `chore/`) slugged from the task where no convention is discernible; create the branch; declare it with `naiad branch <name>`. The rule lives in the Prompt because that is where every rule about what branch names mean already lives (ADR 0015), and `{branch}` rendering empty is what the Prompt reads as its cue.

The declaration is a command, not a file edit, for the reason announcing is (ADR 0001): the command checks and refuses where the agent can still correct itself. It writes `run.working_branch` once — a Run that already has a Working branch, given or declared, refuses a second, because the next Entry's Predecessor stands on it and a branch that moves mid-Run is the silent stacking failure 0015 was built against. It also refuses a name another Entry in the same repository holds, which is the two-Entries-one-branch refusal relocated: an Entry that named no branch at its making could not be checked then, so it is checked at declaration, and the agent retries with another name in the same turn.

Forgetting to declare is loud, not silent. Once a `{branch}`-carrying Prompt has been delivered, the next State Announcement arriving while the Run still has no Working branch is refused, with the fix in the message — the same shape as the missing-Subject refusal, caught while the agent is still in a turn that can repair it. This is what answers 0015's objection to agent-named branches: the failure it feared was the agent forgetting to report and the next Entry quietly basing wrong; the guard turns that into a refusal one State later at the latest, before the Run can end undeclared.

The Queue learns one thing: an Entry whose own record carries no Working branch resolves its claim through its Run, exactly as `status_of` already resolves status (ADR 0013) — no second copy, no new Entry mutation. Two branchless Entries may wait together unchecked; each declares against the claims that exist when its turn comes, and since Lanes are sequential the previous Run has declared long before the next Entry resolves its Predecessor.

## Considered alternatives

**A `naiad.toml` boolean** — "this repository has conventions, the agent may derive" — was designed and dropped. It would have made Naiad a reader of repository files, which nothing else requires (the existing marker of ADR 0018 is read by the agent, never by Naiad), and the attestation it bought was thin: the agent deriving in-repo is trusted with commit messages and pull request descriptions already, and a repo whose conventions it misreads is a repo whose conventions were too faint to attest to.

**A template Naiad expands** (`branch_template = "feat/{slug}"`) keeps the name known at enqueue, but puts convention knowledge — the very thing 0015 keeps out — into Naiad's hands, and a slug of free task text is worse than what the agent derives with the repository in view.

**No guard, catch it at the tail** rebuilds 0015's silent failure: the Run ends undeclared, the next Entry's Predecessor resolves empty, and the stack is wrong until somebody reads the diff.

## Consequences

Omission is intent. There is no strict mode left: an operator who meant to name a branch and forgot gets a Derived branch, not an error. This is accepted — the derived name is on-convention or close to it, and the refusal it replaces cost every Entry the ceremony to protect the rare slip.

The Working branch's off-convention risk moves from "structural, so refuse" to "the agent's in-repo judgment." On a convention-strict team repository a miss is publicly visible on the pull request list; the operator who cares names the branch, which is why `--branch` given always wins and is never second-guessed.

0015's invariant stands untouched: Naiad carries branch names as opaque strings, runs no git, and holds no repository's conventions. What changed is only who supplies the name and when — the operator at the Entry's making, or the agent at the head of the Run.
