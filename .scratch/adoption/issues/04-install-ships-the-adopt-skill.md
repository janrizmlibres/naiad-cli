# naiad install ships the naiad-adopt skill

Status: resolved
Blocked by: none

## Parent

`.scratch/adoption/PRD.md` (ADR 0028).

## What to build

`naiad install` writes, beside the hooks it already writes, a user skill named `naiad-adopt` into the operator's Claude configuration. The skill is how the operator's prose becomes the mechanical act: its description triggers on handover intents — "start to-spec", "let naiad take over" — and its body carries the whole adopt contract: name the Workflow and start State, settle the Working branch (pass one the human made, or derive, create, and declare one per the repository's conventions), distil the Task from the conversation, run `naiad adopt`, relay its output and warnings to the operator, and end the turn.

The contract is Naiad's, so the file that teaches it is versioned and reinstalled with Naiad rather than hand-maintained: installation is idempotent, replaces an earlier Naiad-installed copy, and leaves everything else of the operator's configuration exactly as it was — the same posture the hooks installation already takes, including refusing rather than overwriting anything unreadable.

## Acceptance criteria

- [x] After `naiad install`, the skill exists in the operator's Claude configuration with the trigger description and the full contract in its body.
- [x] Installing twice leaves one copy; an earlier Naiad-installed copy is replaced, not duplicated.
- [x] Nothing else in the operator's configuration is created, removed, or altered by the skill installation.
- [x] The hooks installation behaves exactly as before, in the same `naiad install` run.
