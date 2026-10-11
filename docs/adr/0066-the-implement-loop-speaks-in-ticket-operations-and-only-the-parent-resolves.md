# The implement loop speaks in ticket operations, and only the Parent resolves

> Amends ADR 0063 and ADR 0065.

The States have new names since ADR 0065. The coordinator is now `orchestrate`, which used to be `implement`. A Child still builds its ticket in `build`. `implement` is now the State that builds one ticket in the Parent's own Session when the build limit is 1, which used to be `build-here`. `docs/maintainer/matt-pocock-notes.md` maps the names to the ADRs behind them. Earlier ADRs keep the old names.

The loop's Prompts were written for one issue tracker: markdown files with a `Status:` line, a `## Comments` heading and a `Blocked by:` line. The skills it runs never needed that. `/to-tickets` and `/triage` read the repository's `docs/agents/issue-tracker.md`, and `/implement` does not touch the tracker at all. A repository that keeps its tickets as GitHub issues could start a Run, but every pass would have to translate Status lines into labels, assignees and closed issues.

One part of the loop could not be translated, because of where a resolve is visible. A Child marked its own ticket resolved (ADR 0063). With git-tracked files, that change sits on the Child's branch and only shows on the Working branch once the Parent merges it. A closed GitHub issue is closed everywhere at once. Suppose a Child closes its issue, and a sibling finishes before that Child announces done. The Parent's next pass sees the blocker closed and spawns its dependents from a Working branch that does not have the blocker's code yet. Those Children build on work that is not there.

## The Prompts name operations, and the tracker supplies the mechanics

`orchestrate`, `implement`, `build` and `triage` now speak in five operations, each with a fixed meaning:

- **closed**: closed by completion or by decision. Every other ticket is open, claimed included.
- **claim**: mark the ticket taken, so that no later pass hands it out again.
- **resolve**: mark the ticket closed by completion, and nothing more.
- **comment**: add a note to the ticket's history.
- **blocking edges**: the tickets a ticket names as blocking it. They are satisfied when every one of them is closed.

Each operation is carried out the way the repository's issue tracker records it. Where an operation changes a file git tracks, it is committed on the Working branch; otherwise there is nothing to commit. That one clause replaces the old split between ticket sets git tracks and ticket sets it does not. Triage statuses are read as the tracker's labels, as `triage-labels.md` already maps them.

A repository needs nothing new for this. The tracker documents that `setup-matt-pocock-skills` generates already cover all five operations, though some sit in their Wayfinding section. "And nothing more" on resolve keeps an agent from copying that section's Wayfinder-only steps: an `## Answer` heading and a pointer in the map. This repository's own `issue-tracker.md` spells the five out as a worked example.

The scan now reads open, unclaimed tickets that carry ready-for-agent. With files, a claim replaces the ready-for-agent status, so "unclaimed" added nothing. With an assignee as the claim, the label stays on, and without the word the next pass would spawn the same ticket again.

A Child's Subject is the ticket's reference as the tracker names it: a path for a ticket file, `#26` for a GitHub issue. The Parent still copies into a Child's worktree whatever ticket files and spec the worktree would not otherwise have. A remote tracker needs nothing copied.

## Only the Parent resolves a Child's ticket

At take-in, the Parent merges the Child's branches and runs the tests, then resolves the ticket. `build` carries a pin: leave the ticket as it is, because the Parent resolves it once the branch is merged. ADR 0041 removed most pins, but this one guards the exact failure this decision exists to prevent. A helpful agent finishing work on `#26` might otherwise close it.

This holds for every tracker, files included. Git-tracked files still merge cleanly: the Parent commits the claim before it cuts the Child's branch, the Child never edits the ticket, and the Parent resolves after the merge.

`implement` still resolves its own ticket. It builds on the Working branch, so its code is there before the resolve, and nothing runs beside it.

If the resolve itself fails, for example because `gh` is not signed in, the Parent says which ticket in the session. The ticket then reads claimed with no Child in flight, and the existing route hands over once nothing else can move, listing it among the tickets it found. The handover does not name the failure itself, because a later pass starts from a Cleared context and the failure was recorded nowhere it can read. Nothing is built on a false blocker, because the blocker still reads open.

## `implement` declares its own Model and Effort

ADR 0065 gave `build-here` no Model or Effort, because it ran on what the coordinator set. `implement` now declares its own pair. It builds code, and the coordinator only scans and merges, so an Entry that lowers the coordinator's setting should not lower the builder's with it.

## Considered options

**Keep the Child resolving, except on remote trackers.** This keeps ADR 0063 for files and adds a branch for everything else. Rejected, because the Prompt would carry two rules that differ only in where a status is stored, which is the split this ADR removes.

**Mirror remote tickets as untracked local files for the length of a Run.** This needs no change to the Workflow, and it works today, because the untracked path already resolved after the merge. Rejected as the answer, because the tracker stops being the record while the Run works, and someone has to sync it back afterwards.

**Write each tracker's mechanics into the Prompt.** Rejected for the same reason as ADR 0016: a Workflow shipped to every repository would carry one repository's world. The tracker document is where that knowledge already lives.

**Have the Workflow refuse to run unless the tracker document has a ticket-operations section.** Rejected. The Workflow has no way to make that check, and the stock documents already hold what it would check for.

## Consequences

`wayfind` still speaks in Status and Mode lines. A Wayfinder map on GitHub needs its own representation of Mode, which is a separate decision.

The parked or live Runs that were standing in the old `implement` hold Prompt text that announces `implement`. After the rename that names the single-ticket builder, so they need telling to announce `orchestrate` when they resume.
