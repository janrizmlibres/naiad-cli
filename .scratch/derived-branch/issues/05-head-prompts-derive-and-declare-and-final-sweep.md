# Head Prompts derive and declare, and the final sweep

Status: resolved
Blocked by: 03, 04

## Parent

`.scratch/derived-branch/PRD.md` (ADR 0022 is the authoritative decision record).

## What to build

The shipped workflow's two head Prompts (`grill`, `diagnose`) gain the derive-mode rule, cued by the Working branch line rendering empty: derive a name from this repository's own conventions — recent branch names, the pull request list, the team's prefixes — falling back to `feat/`/`fix/`/`chore/` plus a slug of the task where no convention is discernible; create the branch exactly as the existing instruction describes (based on the Predecessor or the base branch); declare it with `naiad branch <name>` in the same turn. When the branch line is filled, the Prompt reads as it does today.

Then the sweep that makes the feature whole: CLI help no longer calls `--branch` "(required)"; comments and docstrings describing the removed refusal are gone or rewritten; type-checking and the full test suite pass; the work is committed.

## Acceptance criteria

- [ ] Both head Prompts carry the derive-and-declare rule, keyed to an empty branch line, and name the fallback prefixes and the declaration command
- [ ] The shipped-workflow test seam verifies the rule's presence in both heads
- [ ] `--branch` help text and every stale "(required)" / refusal comment is updated
- [ ] mypy and the full test suite pass
- [ ] Committed (no attribution lines), with the glossary and ADR 0022 already in place from the design session
- [ ] Prompt-prose changes verify by the shipped-workflow tests plus a manual smoke read; the sweep needs no new tests, but every existing one passes

## Blocked by

- 03 — the guard the derive-mode Prompt relies on for loudness
- 04 — the Predecessor path a Derived branch feeds
