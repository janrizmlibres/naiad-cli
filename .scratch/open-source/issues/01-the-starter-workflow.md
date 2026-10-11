# The starter workflow

Type: prototype
Mode: HITL
Status: resolved
Blocked by:

## Question

Which States and Prompts does the skill-free starter workflow ship with? It must run on a plain Claude Code install with no custom skills, demonstrate Naiad's value (no manual session instantiation; Clears that contain context bloat), and end at a terminal State. Draft it as a real `workflows/starter.toml`, run one Run of it on a throwaway repository, and react to what the Prompts actually do. Decide: the States and their order; which States Clear; which Gates exist and what each hand-off is called; whether any State branches; what the `{task}` and `{subject}` slots are used for; and whether it declares any Model or Effort at all.

## Answer

Resolved 2026-09-19 by a grilling round, a draft, and one supervised Run on a throwaway repository. The draft is `workflows/starter.toml` on branch `prototype/starter-workflow` (commit on that branch); the Run is `20260919-053031-starter-10709` in `~/.naiad/runs/`, driven against a two-file Python package with a five-test suite, task "add a `--top N` option to the CLI". It reached `done` with four commits on `feat/top-words`.

### The Workflow

Six States, one straight line: `plan` → `review` (Gate) → `implement` (Clear) → `verify` (Clear) → `ship` (Clear) → `done` (terminal). No State branches, so every Prompt names its one successor through `{next_state}` and the Protocol's own line carries the route.

- **`plan`** takes `{task}` and `{branch}`. It creates the Working branch (given, or derived and declared with `naiad branch`, based on the default branch), reads the repository, and writes `PLAN.md` at the root under four fixed headings: Goal, Approach, Steps, How to verify. Commits it on the Working branch. `{predecessor}` is unused: stacking is a second-week feature and the Prompt has to fit one screen.
- **`review`** is the one Gate, skipped by `--skip-gates`. Its hand-off is "the plan is written; read it and send the agent on". A Gate before `ship` was rejected because the pull request reviews the diff better.
- **`implement`** Clears and builds from `PLAN.md` alone, committing as it goes, noting under Approach where the plan was wrong about the code, and leaving `PLAN.md` in place.
- **`verify`** Clears and reads the plan and the diff against the default branch, runs every How-to-verify command plus whatever the repository defines, fixes what fails, and adds a `## Status` heading to `PLAN.md` saying what passes and what remains. It never parks: a suite it cannot make pass is written down and shipped, so the hand-off tells the truth and an unattended first Run still ends.
- **`ship`** Clears, turns the plan into a change description, removes `PLAN.md` in its own commit, and opens a pull request with `gh pr create` when the repository has a remote and `gh` is authenticated; otherwise it stops at the branch. Its last words are the branch name and the URL if any. No MCP server, no `naiad.toml`, no opt-out key: the starter's convention is "a pull request if it can".
- **Settings**: no `model`, `effort` or `autocompact`, and no `[answerer]` table. A plain install runs on what its Claude Code holds; three commented lines at the top show where each key goes. Without an Answerer a Question parks the Run for the human, which is the position ticket 11 has to honour.
- **Slots**: `{task}` and `{branch}` in `plan`, `{next_state}` everywhere a Prompt exists, `{subject}` nowhere. `{task}` and `{subject}` are not synonyms: Task is fixed per Run in the operator's words, Subject is chosen per Announcement by the agent and is what lets a State repeat over a series (ADR 0009). The starter has no repeating State, so it needs only `{task}`.

The draft passes every invariant `tests/test_shipped_workflow.py` holds (name equals stem, every slot fillable, every successor named, no "you just" after a Clear, every non-terminal State leads somewhere).

### What the Run showed

The Run log, in order: `declared` (branch `feat/top-words`), `announced review`, `notified` (Gate waiting), then for each of `implement`, `verify` and `ship`: `announced`, `cleared`, `delivered` with the next State named, and finally `announced done`, `finished`.

1. **The plan Prompt works cold.** The agent derived and declared the branch in one turn, and wrote a plan with per-step file lists and a verify section with exact commands and expected output. `implement` built from it in one commit with no access to the planning context, `verify` found everything passing and recorded a Status heading without touching code, `ship` removed the plan and took the no-remote fallback. The containment claim held three times.
2. **The adopter's own rules ride along.** The plan spoke of TDD and a refactor verdict because the operator's global `CLAUDE.md` applies inside the Session. Correct, and the documentation should say so: the starter adds no rules, the adopter's apply.
3. **Claude Code's folder-trust dialog blocks the first Prompt** on a repository it has never opened. The Session sat on "Yes, I trust this folder" until a human answered it in the pane. Naiad never sees it. Goes on the first-run smoke fog item; the doctor ticket cannot fix it, the first-run documentation has to name it.
4. **At the Gate the agent does not know the next State's name.** The Protocol's "when this phase is done, announce X" is injected only into fresh contexts, and a Gate is not one, so after announcing `review` the agent has last been told to announce `review`. The human clearing the Gate had to say "announce implement". The notification does not name the next State either. Ticketed as "What the agent and the human each know at a Gate".
5. **The typed verdict had to be sent.** A human's line typed into the pane and left unsent parks the Run indefinitely, by design; nothing to change, but the Gate documentation should say "type and send".

### Verdicts

- Five delivering States, not four: `verify` as its own cleared State earned its place by reading the diff with no memory of writing it.
- `PLAN.md` at the root, committed on the branch, removed by `ship`: the fixed path is what lets three cold contexts find it.
- No settings and no Answerer in the shipped file: model names rot, and the starter's audience has not opted into unattended decisions.
- The `{predecessor}` slot stays out of the starter.
