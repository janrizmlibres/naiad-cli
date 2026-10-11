# Derived branch: `--branch` becomes optional, the agent derives and declares

Status: ready-for-agent

## Problem Statement

Every way of describing work to Naiad — `naiad run`, `naiad queue add`, a batch file — requires a Working branch, and work described without one is refused before it exists. For an operator queueing a night's backlog this is ceremony: naming a correct branch means knowing each target repository's conventions (issue number, application prefix) at the terminal, for every Entry, even when the agent that will do the work is far better placed to name one — it works inside the repository with the recent branch names, the pull request list, and the team's actual prefixes in front of it.

## Solution

`--branch` (and a batch Entry's `branch` key) becomes genuinely optional at every entrance. Given, it behaves exactly as today and is never second-guessed. Absent, the Run starts with no Working branch, and the head Prompt carries the rule: derive a name from the target repository's own conventions — falling back to conventional prefixes (`feat/`, `fix/`, `chore/`) slugged from the task where no convention is discernible — create the branch, and declare it to Naiad with a new `naiad branch <name>` command in the same turn it is created. The declaration is write-once and claim-checked; forgetting it is refused loudly at the next State Announcement rather than surfacing as a silently mis-stacked Queue.

This is recorded as ADR 0022, which amends ADR 0015: the invariant that Naiad carries opaque branch names and holds no git knowledge stands untouched; what changes is only who supplies the name and when. The glossary term is **Derived branch** (CONTEXT.md).

## User Stories

1. As an operator queueing work, I want to omit `--branch` on `naiad queue add`, so that I can queue an Entry without knowing the target repository's branch conventions.
2. As an operator starting a one-off Run, I want to omit `--branch` on `naiad run`, so that a quick task needs no naming ceremony.
3. As an agent writing a batch file, I want the `branch` key to be optional per Entry, so that a night's backlog can be declared without inventing names for every line.
4. As an operator who names a branch explicitly, I want `--branch` to behave exactly as before, so that my named branch is used verbatim and never second-guessed or rewritten.
5. As the agent at the head of a Run with no Working branch, I want the head Prompt to tell me to derive a name from the repository's conventions, so that the name I create is one the team would have chosen.
6. As the agent in a repository with no discernible branch conventions, I want a stated fallback (`feat/`, `fix/`, `chore/` plus a task slug), so that I am never stuck inventing a scheme from nothing.
7. As the agent that has just created a Derived branch, I want a `naiad branch <name>` command, so that I can declare the branch in the same turn I created it.
8. As the agent that mistyped or mistimed a declaration, I want the command's refusals to reach me as error messages inside my own turn, so that I can correct myself without stalling the Run.
9. As the next Entry in the Lane, I want the previous Run's Derived branch recorded on that Run, so that my Predecessor resolves to a real branch name exactly as it does for a given one.
10. As an operator, I want a declared branch to be write-once on its Run, so that no agent can silently move a Run's work mid-flight and break the stack behind it.
11. As an operator, I want `naiad branch` to refuse a name another Entry in the same repository already holds, so that two Entries never share a branch and stack one's work into the other's.
12. As an operator, I want two branchless Entries for the same repository to coexist in the Queue, so that queueing is never blocked by a name that does not exist yet.
13. As an operator, I want a Run that was delivered a branch-carrying Prompt and never declared to be refused at its next Announcement, so that a forgotten declaration is a loud error one State later at the latest, not a silently empty Predecessor.
14. As the agent receiving that refusal, I want the fix in the error message (declare it: `naiad branch <name>`), so that I can recover with the checked-out branch one `git branch --show-current` away.
15. As an operator enqueueing against a repository with a branchless Entry already running, I want the claim check to see that Run's declared branch, so that my `--branch` cannot collide with a Derived branch invisibly.
16. As a human reading the Run log, I want the declaration recorded like other protocol acts, so that "where did this branch name come from" has a readable answer.
17. As a workflow author, I want `{branch}` rendering empty to be the Prompt's cue for derive-mode, so that the rule lives in prose I own rather than in Naiad.
18. As the agent at a pre-head State (classify), I want to announce with no branch declared and no refusal, so that the guard fires only after a branch-carrying Prompt has actually been delivered.
19. As an operator whose batch mixes named and branchless Entries, I want each behaviour applied per Entry, so that the two styles compose in one file.
20. As a maintainer, I want ADR 0022 and the glossary to record why omission is intent and where the off-convention risk moved, so that the trade-offs are not re-litigated in six months.

## Implementation Decisions

- **Refusal removal.** `MissingWorkingBranch` and its check disappear from the shared start checks; the `Start` result carries an optional Working branch. The `Remedy` vocabulary loses its branch remedy. Both entrances and the batch path inherit this through the one shared entrance (ADR 0014) — no per-entrance logic.
- **Entry and Run models.** An Entry's Working branch becomes optional (given or absent), serialized as it is today. The Run's `working_branch` is already nullable; a Run created from a branchless Entry starts with none.
- **New command `naiad branch <name>`.** The agent-side declaration, a sibling of the announce command and following its shape: resolves the current Run, validates, writes atomically, and prints refusals the agent can act on. Refusals: (1) the Run already has a Working branch — given or previously declared — because the next Entry's Predecessor stands on it (write-once); (2) another Entry for the same repository holds the name — the two-Entries-one-branch refusal relocated to declaration time, with the same message shape as enqueue's, so the agent derives another name and retries in the same turn.
- **Claim resolution through the Run.** The enqueue-time claim check resolves an Entry's branch through its Run when the Entry itself carries none — the same pattern as `status_of` (ADR 0013): no second copy, no new Entry mutation. Two branchless waiting Entries claim nothing and coexist; each is checked at its own declaration against the claims existing then.
- **The guard.** Once a Prompt containing `{branch}` has been delivered for a Run whose Working branch is absent, the next State Announcement while it is still absent is refused, with the declaration command in the message — the missing-Subject refusal's shape, on a different actor. Whether a delivered Prompt carried `{branch}` is derivable from the workflow file and the Announcement history; no new stored state unless implementation finds recording "a branch-carrying Prompt went out" on the Run simpler.
- **Prompt rendering unchanged.** `{branch}` already renders empty when absent; the placeholder set stays closed at five. The kickoff-time "refused rather than rendered empty" comment becomes obsolete alongside the refusal.
- **Head Prompt edits (workflow file).** The two head Prompts (`grill`, `diagnose`) gain the conditional: if the Working branch line is empty, derive a name from this repository's conventions (recent branches, PR list, team prefixes), fall back to `feat/`/`fix/`/`chore/` + task slug, create it as the existing instruction describes (based on Predecessor or base branch), then declare it with `naiad branch <name>` in the same turn.
- **Precedence.** A given branch always wins; there is no strict mode. Omission is intent (ADR 0022, Consequences).
- **Run log.** The declaration is recorded like other received protocol acts, so the log answers where a name came from.

## Testing Decisions

- **Method: TDD (Red → Green → Refactor)** on the existing pytest harness, per task. Each behaviour gets a failing test first, run to confirm it fails for the expected reason; minimal code to green; then an explicit, named Refactor verdict per task, even when "keep".
- **Good tests here test external behaviour at existing seams**: what a command refuses or records, what the Queue holds, what a Prompt renders — never internals like which module holds a check.
- **Seams (all existing; no new ones needed):**
  - The enqueue seam (`enqueue`/`prepare` with an in-memory Queue) — branchless Entries queue, given branches still claim, claim resolution through the Run, batch mixing. Prior art: `tests/test_enqueue.py`.
  - The announce/command seam — `naiad branch` declaration, write-once refusal, claimed-name refusal, and the undeclared-branch guard on announcing. Prior art: `tests/test_announce_command.py`, `tests/test_wait_command.py` (the most recent protocol-verb addition — closest prior art for adding a command).
  - The kickoff/run seam — a Run created branchless, Predecessor resolution reading a declared branch. Prior art: `tests/test_kickoff.py`, `tests/test_supervise.py`.
  - The prompt seam — `{branch}` empty rendering already covered; extend only if behaviour changes. Prior art: `tests/test_prompt.py`.
  - The shipped-workflow seam — head Prompts carry the derive-and-declare rule. Prior art: `tests/test_shipped_workflow.py`.
- Tests asserting `MissingWorkingBranch` and the required-branch refusal are removed or inverted (the same inputs now succeed), which is the natural Red for the removal itself.

## Out of Scope

- Any Naiad reading of `naiad.toml` or other repository files — considered and rejected (ADR 0022, Considered alternatives).
- Branch-name templates or slugs computed by Naiad — same rejection.
- Renaming or re-declaring a branch mid-Run — write-once is the rule; a wrong Derived branch is handled by a human like any other wrong agent output.
- The per-Entry pull-request override (`.scratch/deferred/issues/06`) — unrelated deferred work, untouched.
- Worktree-per-Run and anything else deferred by ADR 0012/0020.
- Changing how a *given* branch behaves anywhere.

## Further Notes

- ADR 0022 (`docs/adr/0022-a-working-branch-is-given-or-derived-never-invented.md`) and the CONTEXT.md **Derived branch** / **Working branch** entries are already written and are the authoritative record of the decisions; this PRD is the implementation-facing restatement.
- The design was interviewed to shared understanding on 2026-07-30; the accepted trade-offs (no strict mode; off-convention risk moves to the agent's in-repo judgment) are recorded in ADR 0022's Consequences and should not be re-opened during implementation.
