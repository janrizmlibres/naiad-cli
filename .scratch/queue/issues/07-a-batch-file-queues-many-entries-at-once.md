# A batch file queues many Entries at once

Status: ready-for-agent
Blocked by: 03-entries-can-be-queued-listed-and-removed
Spec: `.scratch/queue/PRD.md`

## What to build

`naiad queue add --file batch.toml` queues a night's work in one command, from a document that can be read before committing to it.

**A batch is heterogeneous, which is what makes a file worth having.** Three bugs starting at the diagnosing State and two designs starting at the grilling State go in one file, each Entry naming its own start State, Working branch and pinned base. Repeated command-line flags cannot express that without positional pairing nobody can read.

**TOML, like a Workflow file**, because it is written by a person or an agent rather than by Naiad — where an Entry's own storage is JSON, like a Run's metadata, because Naiad writes that.

**Top-level keys are defaults; per-Entry keys override them.** Five Entries against one repository should not repeat the same Workflow and repository five times. This is a convenience rather than a concept.

**Rejected whole, before anything is enqueued.** A file with one bad Entry queues none of them: a half-failed batch leaves a partial Queue with no signal, which is worse than an error. Errors name the file and the offending Entry's position, the way Workflow parsing names a State's, so the message says which line to fix. Every refusal from the single-Entry path applies unchanged — missing Working branch, a branch another Entry claims, invalid Workflow, undeclared start State, missing Subject — and the duplicate-branch check must also catch two Entries *within the same file* claiming one branch.

**A batch is not a domain concept.** It produces N Entries and the Queue does not know they arrived together: nothing has been asked of it that requires knowing, so there is no batch to cancel and no batch to report on. If that changes, it is additive.

**Ordering follows the file.** Entries queue in the order they are written, which matters because it is what the Predecessor rule reads — a batch is usually also a stack.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] A well-formed batch file queues every Entry it declares, in file order
- [ ] Entries in one file may differ in start State, Working branch, pinned base, Subject and gate-skipping
- [ ] Top-level keys apply as defaults and per-Entry keys override them
- [ ] A file with one invalid Entry queues none of them
- [ ] Malformed TOML is rejected naming the file
- [ ] An invalid Entry is rejected naming the file and the Entry's position
- [ ] Two Entries within one file claiming the same Working branch for the same repository are refused
- [ ] Every single-Entry refusal applies to a batched Entry
- [ ] Nothing records that the Entries arrived together
