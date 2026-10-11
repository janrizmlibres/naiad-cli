# What becomes of the personal workflow

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

What happens to `workflows/matt-pocock.toml`, its plugin dependency, and the two `naiad.toml` keys its Prompts read? It depends on seven slash commands from the mattpocock-skills plugin and on `naiad.toml` for `companions` and the pull-request opt-out, none of which Naiad owns. Decide: whether it moves to an examples directory in this repo, to a repository of its own, or stays as a second shipped file; its name once the repo is public; where its plugin dependency and its `naiad.toml` convention are documented; what happens to `tests/test_shipped_workflow.py`, `docs/workflow-authoring.md` and ADRs 0018 and 0048, which describe that convention as Naiad's; and how your own library link keeps working through the move.

## Comments

2026-09-19, from "The starter workflow": the starter is drafted on branch `prototype/starter-workflow` as `workflows/starter.toml`, six States, no skills, no `[answerer]`. Once it is the shipped file, `tests/test_shipped_workflow.py` has to point at it, or be parametrised over every file in `workflows/`, so the personal file keeps its invariants wherever it moves. The starter shows an adopter what a Prompt without a skill looks like; the personal file remains the example of Prompts that open with a slash command.

2026-09-19, from "Where shipped and authored workflows live": the starter becomes package data at `naiad/workflows/starter.toml` and the root `workflows/` directory stops being where shipped files live, so the personal file cannot stay beside it. Your own library keeps a hand-made link to wherever the file ends up, which is ADR 0037's rule for a repository-maintained Workflow and is unchanged by ADR 0049.

## Answer

`workflows/matt-pocock.toml` is the maintainer's personal Workflow, not something offered to adopters. ADR 0052 records the decision; the spec carries the following.

- **Where it lives.** It stays where it is, `workflows/matt-pocock.toml`, a regular tracked file anyone can read. It is not package data, `naiad install` never offers it, and no adopter-facing document (README, the documentation set) names it. No `examples/` directory, no second shipped file, no repository of its own.
- **Its name.** Unchanged. It has no public name to choose, since nothing presents it.
- **The project file.** `naiad.toml` is the personal Workflow's convention, not Naiad's; it is renamed `.matt-pocock.toml`, keys unchanged (`companions` and the pull-request opt-out). The spec edits the `pull-request` Prompt, both places it names `naiad.toml` (the companions paragraph and the per-repository opt-out sentence), to read `.matt-pocock.toml`. The maintainer renames the file in his own projects that keep one. Adopters keep per-project facts wherever their own Prompts say; Naiad has no opinion.
- **The plugin dependency.** Documented nowhere adopter-facing. The file's own slash commands are the statement of it.
- **ADRs.** ADR 0052 is the new record; ADRs 0018, 0048 and 0043 carry an `Amended by ADR 0052` pointer. 0048 and 0051 keep their wording as history.
- **`CONTEXT.md`.** **Companion repository** is removed: it is one Workflow's concept, not a term an adopter meets in Naiad (done in this session).
- **`tests/test_shipped_workflow.py`.** Parametrised over the packaged starter and `workflows/matt-pocock.toml`, the same invariants for both. Its docstring loses its pointers to ADRs, `docs/workflow-authoring.md` and the smoke doc (see below).
- **Maintainer docs.** Follow "The public repository" ticket's untracked direction (comment there, 2026-09-24): the personal file's tuning notes, its per-State ADR index (now in `docs/workflow-authoring.md`) and `docs/smoke/matt-pocock.md` go untracked with the ADRs. The tracked `docs/workflow-authoring.md` keeps only the Prompt-writing conventions, rewritten inline without ADR citations, and may become the starter's. `AGENTS.md`'s "Workflow files" section is retargeted at the starter as the shipped file.
- **Your library link.** Untouched: `~/.naiad/workflows/matt-pocock.toml` already links to `workflows/matt-pocock.toml`, which does not move.
