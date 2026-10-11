# Adoption honors the start State's Clear

Status: resolved
Blocked by: 02

## Parent

`.scratch/adoption/PRD.md` (ADR 0028).

## What to build

The one place Adoption diverges from kickoff. Kickoff ignores the first State's Clear flag because a new session holds nothing to discard; an Adoption honors it, because the adopted session holds everything and the Workflow's declaration of a clean start is not Naiad's to overrule. Adopting at a Clearing State Clears first — confirmed through the SessionStart hook before the Prompt follows, re-typed within the bounded tries when the confirmation does not come (ADR 0019) — and adopting at a non-Clearing State touches the context not at all, which is the whole point of the feature.

## Acceptance criteria

- [ ] Adopting at a Clearing start State types the Clear after the Turn end, and the Prompt is held back until the SessionStart hook confirms the Clear landed.
- [ ] Adopting at a non-Clearing start State delivers the Prompt with no Clear typed and nothing else sent first.
- [ ] The unconfirmed-Clear path behaves as delivery already does: bounded retries, then the human is told.
- [ ] Kickoff's behavior is unchanged: a spawned Run still ignores its first State's Clear flag.
