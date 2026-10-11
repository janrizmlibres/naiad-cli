# Entries can be queued, listed and removed

Status: ready-for-agent
Blocked by: None — can start immediately
Spec: `.scratch/queue/PRD.md`

## What to build

An operator, or an agent inside a session, describes a Run that should happen later and it joins a Queue. They can see what is queued and take something back out. Nothing runs it yet — that is the next ticket — and that is deliberately demoable on its own: `naiad queue add` three times, `naiad queue list`, `naiad queue rm` one of them.

**An Entry is a Run that does not exist yet.** It carries what kickoff would otherwise be told: the Workflow, the task, the target repository, the Working branch, an optional pinned base, an optional start State, an optional Subject, and whether Gates are skipped. Plus one field for what became of it — the id of its Run — absent until it starts.

**It records nothing else, and this is a decision rather than an omission (ADR 0013).** No status field. Whether an Entry is waiting, running, parked or done is read from its Run, which already holds all four and was written by the party that observed them. A status the Queue writes about work it is not doing is a second copy that can disagree with the first, and it lies the moment a Supervisor is killed mid-Run. Listing therefore derives: no Run means waiting, a finished Run log means done, and anything in between is reported from the Run.

**Ids are sortable timestamps, built the way a Run id already is,** so sorting by id *is* the Queue order. No Entry holds a position, no index is stored, and removing one renumbers nothing — which is what keeps a Queue that steps over Entries possible later (ADR 0012).

**Storage sits beside the Runs**, under the same Naiad-owned root, honouring the same environment override, one file per Entry named by its id, serialised as JSON like a Run's metadata. It is never written into a target repository, for the reason a Run's directory is not.

**Every refusal that used to happen at kickoff happens here instead**, before the Entry exists, on the principle the missing-Subject check established: the operator is standing there and pays the error message only. Refuse when the Workflow file is invalid, when the start State is not one the Workflow declares, when that State's Prompt names a Subject and none was given, when the Working branch is missing, and when another queued Entry for the same repository already claims that Working branch. That last one is the subtle one: without it two Entries silently share a branch, and because checkout is idempotent the second stacks into the first invisibly.

**`naiad queue add` never supervises.** This is the command an agent inside a session uses, and it must return promptly — a tool call that becomes a process blocking for hours is the failure it exists to avoid.

**Prefactor.** The runs-root helper reads the `NAIAD_HOME` override; generalise it so the Queue root shares it rather than re-reading the environment in a second place.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] `naiad queue add` records an Entry with all its fields and returns without supervising anything
- [ ] `naiad queue list` shows Entries in id order, each with what became of it, deriving that from the Run rather than from a stored status
- [ ] `naiad queue rm` removes an Entry and leaves any Run and session it produced untouched
- [ ] An Entry with no Working branch is refused
- [ ] An Entry whose Working branch is already claimed by another queued Entry for the same repository is refused
- [ ] An Entry naming an invalid Workflow, an undeclared start State, or omitting a Subject its start State's Prompt requires, is each refused
- [ ] Two Entries for *different* repositories may share a Working branch
- [ ] The Queue root honours the same home override as the runs root, and the Queue is refused inside a target repository for the reason a Run directory is
- [ ] Entry ids sort into Queue order, and no Entry stores a position
