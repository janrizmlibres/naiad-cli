# How the tail ends is read from the project, not fixed by Naiad

> Amended by commit d856840 (the shipped tail ends when the pull request is open), and by ADR 0052.

ADR 0016 made the tail project-neutral but left two assumptions inside it that only hold for one kind of project. It assumed the host is GitHub — `pull-request` opens through "the GitHub MCP server," and the bare open is described as what "every other GitHub repository" gets. And it assumed a pull request is always the ending: its final consequence paragraph treats a repository with no remote as a case that "does not arise in practice," one the Run handles by stalling until Naiad Nudges and parks it. Both assumptions are now wrong in practice. Some repositories are hosted on Gitea, which has pull requests and an MCP server of its own; and some have no remote at all, where the honest ending is not a parked Run but a finished one.

We decided the tail reads how it ends from the repository in front of it rather than fixing a single ending. There are three endings, and the agent selects among them from facts the repository holds:

- **A pull request, on whatever host can open one.** `pull-request` opens through the MCP server for the repository's host — GitHub or Gitea — comparing the branch against its base for the description, exactly as before but no longer GitHub-only. The one named exception stays HCGPS → `/hcgps-pr`, for the reason 0016 gives: its conventions are rich enough to earn a skill, and the file names the skill rather than inlining it.
- **No pull request, because the repository opted out.** A repository records the preference in itself — a `naiad.toml` at its root suppressing the pull request — and the agent reads it. This is the only way an operator preference that is not otherwise a fact about the repository reaches the tail without Naiad carrying it: the marker turns the preference into something the repository knows about itself, which is the same channel every other tail fact travels (ADR 0015, ADR 0016).
- **No pull request, because there is nowhere to open one.** A repository with no remote has nothing to open against. The agent announces `done` — which is already a declared successor of `pull-request` (ADR 0017) — rather than stalling. This is what supersedes 0016's precondition paragraph: the no-remote case is real, and its ending is `done`, not a park.

The default is to open a pull request wherever one can be opened. The marker suppresses it; its absence opens one. This direction is deliberate: the path that silently drops review is the one that must be declared. A repository that opts out carries a visible line a reviewer can question; a repository that says nothing gets review, never loses it by omission. It is the same instinct as 0015 defaulting to stacking and the triage label defaulting to `ready-for-human` — the lossy path is the one made explicit.

## Considered alternatives

**A workflow file per project** — one with a pull-request tail, one ending at `done` — is rejected for the reason 0016 already gave: the tail is a dozen lines and the spine above it three hundred of hand-tuned prose, and copying all of it to vary the ending is a standing invitation to drift.

**A per-Entry flag** for the ending is rejected for now, and for the same reason 0016 rejected it: it reopens the placeholder set `render_prompt` closes at five and buys explicitness at queue time for something the repository can hold itself. The marker is the better home for a *standing per-project* preference. A per-Entry *override* — a single Run differing from the project's default — is a genuinely different case, because it carries information the repository does not hold; it is designed but deferred until a Run needs it, recorded as a precedence chain (override → marker → default) in `.scratch/deferred/issues/06-per-entry-pull-request-override.md`, and it will want its own ADR rather than reopening this one.

## Consequences

The `pull-request` State's Prompt is where all three endings resolve, because the branches converge on it: it is the one place that reads the host and the marker, so no rejoin State (`implement`, `handover`, `diagnose`, `no-repro`) learns anything about remotes. The order of the Prompt matters — the "is there anywhere to open a pull request, and does this project want one?" question comes first, before the open, the branch, and the review wait, so a `done` ending costs no PR attempt and no ten-minute wait. A no-remote or opted-out Run still enters `pull-request` and Clears first: that one turn is the same no-op price ADR 0017 already pays for the empty-review case, and it buys the containment of keeping every rejoin remote-blind.

The branch heads are untouched. A Working branch is local git and is created remote-blind at `grill` and `diagnose` as before (ADR 0015); a local-first repository still gets its branch and its ancestry-based stacking, because pushing is the only thing a remote gates and pushing is the tail's business, not the head's.

The review tail needs nothing new. A Gitea pull request opens, waits its budget, finds no Claude Code Review — Gitea runs none — and falls through to `done` on ADR 0017's existing branch. `review-fix` keeps naming Claude Code Review, honestly, because it is reached only where such a review completed.

Onboarding stays cheap where it was and gains one file where it must. A plain GitHub repository is still zero-config. A Gitea repository that wants pull requests is zero-config too, now that the open path is host-neutral. Only a local-first repository — no remote, or a remote whose pull requests it does not want driven this way — writes the one `naiad.toml` line, and deleting that line is how it opts back in.
