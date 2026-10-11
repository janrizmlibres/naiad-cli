# A Child limit of one builds in the Parent's Session

> Revises ADR 0063's answer to waves. Builds on ADR 0060. Amended by ADR 0066.

ADR 0063 turned `implement` into a coordinator that spawns a Child for every ready ticket. It said a repository that wants one ticket at a time sets `children = 1`, "which keeps the old order exactly". It keeps the order, but not the cost. At a limit of one, every ticket still gets a worktree, a copy-on-write clone and an install, a fresh Session, a merge back into the Working branch, and a cleanup. None of that buys anything, because nothing runs alongside the Child. The Parent waits for it in a Join State, doing nothing. We decided that a Run builds with Children only when they can actually run in parallel.

## Naiad hands the number to the Prompt

The Entry's Child limit (ADR 0060) used to reach only the Supervisor. A Prompt could not see it, so a Workflow could not act on an operator saying "one at a time". A new slot, `{child_limit}`, carries it into every State. It is empty when the Entry names no limit, the same way `{branch}` and `{predecessor}` are empty when there is nothing to carry. Naiad still knows only a number. Deciding that one means "build it here" is the Workflow's business, which keeps the reasoning that made the Child limit a number rather than a mode.

## `implement` picks its mode on each pass

The build limit is the smaller of `{child_limit}` and the `children` key of the repository's `.matt-pocock.toml`. Absent means no limit. When the build limit is one, `implement` spawns nothing and claims nothing. It hands the lowest-numbered ready-for-agent ticket to `build-here`, a new State in the same Run, passing the ticket's file as the Subject. Nothing is claimed, because nothing runs alongside the Run that could pick the same ticket. Above one, the pass claims and spawns as ADR 0063 describes.

`build-here` opens with `/implement {subject}` and builds that one ticket on the Working branch, in the Run's own Session. When its tests pass, it sets the ticket's Status to resolved, commits, and announces `implement`, which takes the next ticket after a Clear. When it cannot get them passing, it leaves the Status as it is and announces handover. It is entered only by name and placed after the Terminal State, beside `build`. It declares no Clear, since the `implement` pass before it Cleared and did nothing but scan. It declares no Model or Effort, since it runs on what `implement` set. This is the old ticket-per-Announcement loop, with the choice of ticket moved from `tickets` and `triage` into `implement`.

Only which tickets run at the same time differs between the two modes. Both use the same frontier rules: a ticket waiting on a person does not stop the others, needs-triage goes to `triage`, and handover comes only when no ticket can move. The old loop's stop at the first ticket that was not ready-for-agent does not come back.

`implement` stays the one coordinating State, and it stays a Join State. With no Children it is delivered at once, so single-session mode pays nothing for being one. `tickets`, `triage` and `handover` announce `implement` as before and never need to read the limit. Only `implement` announces `build-here`.

## An empty pass says so

A Join State delivered at once, with no Child named, rendered `{children}` as nothing. That left a gap after "take in each Child named below", followed by rules for completed and cancelled Children that applied to none of them. Naiad now renders `- none`, which is neutral enough for any Workflow. `implement` also gives the take-in rules first and puts the slot after them, so the agent knows what to look for before it sees the list.

## Considered options

**Only the repository's `children` key decides.** This needs no change to Naiad. Rejected, because `--child-limit 1` is how an operator, and the adopt skill on their behalf, says "one at a time". If that number never reached the Prompt, the most common way of asking for serial work would still spawn.

**Build in place whenever exactly one ticket is ready and no Child is in flight, whatever the limit.** This covers a strict chain of tickets with no limit set. Rejected for now. The number of ready tickets changes between passes, and switching on it would mix tickets built on the Working branch with tickets built on their own branches within one feature. That makes "a Child in flight" and the pull-request sweep harder to reason about. It can be added later as a rule in the Prompt.

**Restore the old ticket-per-Announcement `implement` as a State of its own.** Rejected. `tickets`, `triage` and `handover` would each have to read the limit to choose which State to announce, which adds a third copy to the scan-and-route text that ADR 0063 already notes is drifting.

**`implement` builds the ticket itself, by running the implement skill partway through its own Prompt.** This saves one Announcement per ticket. Rejected, because a skill is reliably invoked only by a slash command at the start of the typed message, and the steps after it would be a procedure rather than an argument. Both break the Prompt conventions in `docs/workflow-authoring.md`. It also left a build whose tests failed with nowhere to go but resolved.

## Consequences

The `implement` Prompt now has two branches in its scan and route steps, and both must keep using the same frontier rules. A ticket in single-session mode costs one extra Announcement, `implement` to `build-here`, but no extra Clear. A ticket left claimed by an earlier parallel pass, for example after the repository's key changed in the middle of a feature, reads as claimed with no Child in flight and goes to handover under the existing rule.

The adopt skill's wording is unchanged. "One ticket at a time" still maps to `--child-limit 1`. That this keeps the work in one Session is the Workflow's choice and not Naiad's.
