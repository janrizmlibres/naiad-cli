# An undeclared branch refuses the next Announcement

Status: resolved
Blocked by: 02

## Parent

`.scratch/derived-branch/PRD.md` (ADR 0022 is the authoritative decision record).

## What to build

Forgetting to declare is loud, not silent. Once a Prompt containing `{branch}` has been delivered to a Run with no Working branch, the next State Announcement arriving while it is still absent is refused, with the fix in the message: declare it first with `naiad branch <name>`. The shape is the missing-Subject refusal's — caught while the agent is in a turn that can repair it (the checked-out branch is one `git branch --show-current` away).

The guard fires only after a `{branch}`-carrying Prompt has gone out: a pre-head State (classify) announces freely on a branchless Run, because no such Prompt precedes it. Whether one was delivered is derivable from the workflow file and the Announcement history; record it on the Run only if that proves simpler.

## Acceptance criteria

- [ ] Announcing a State on a branchless Run after a `{branch}`-carrying Prompt was delivered is refused, and the message names `naiad branch`
- [ ] Announcing before any `{branch}`-carrying Prompt was delivered (e.g. the classify State) is not refused
- [ ] After declaring, the same Announcement succeeds
- [ ] A Run whose branch was given is never touched by the guard
- [ ] TDD per behaviour, at the announce-command seam

## Blocked by

- 02 — the refusal's remedy is the declaration command.
