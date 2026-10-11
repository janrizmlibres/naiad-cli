# A Run spawns a Child

Status: resolved
Blocked by: None — can start immediately
Spec: `.scratch/children/PRD.md`

## What to build

An agent inside a Run runs `naiad spawn` to enqueue an Entry as its own **Child**. It resolves the calling Run through the same resolution chain as `announce`, `wait` and `branch`. It takes:
- an optional task, which defaults to the Parent's;
- `--repo`, the Child's working tree, which is required;
- `--branch`, `--base`, `--at` and `--subject`;
- the per-State settings flags and `--skip-gates`.

A Child takes its Parent Entry's Workflow file, settings and Gates-skipped, unless the command names its own. It enqueues through the same path as `naiad queue add`, so every check an Entry gets applies, including the branch claim per working tree. It prints `queued <id>` and returns without supervising anything.

Spawn refuses in each of these cases, as a message the agent can act on inside its own turn:
- no Run resolves;
- the Run has ended;
- the Run is itself a Child (only one level);
- the working tree normalises to the Parent's own, where the Child would wait behind its Parent in the same Lane forever.

The Entry gains an optional `parent`, the Parent's Run id. It is persisted, and documents written before this change read it as absent. The Parent's Run keeps a **Children record**: each Child's Entry id, which Spawn writes, and its Run id, which the Supervisor writes when it starts the Child. A Child stays findable after its Entry leaves the Queue.

The injected Protocol text gains the Spawn rule beside the other verbs. Spawn is used only when a Workflow's Prompt asks for it, and a Child's working tree must be its own.

The Supervisor needs no new rule to start a Child. Its working tree differs, so it is a Lane of its own. When it starts one, it records the Child's Run id on the Parent's Children record.

`naiad queue list` lists each Child indented under its Parent, with its own status.

## Acceptance criteria

- [ ] `naiad spawn` from inside a Run queues a Child whose Entry names the Parent and inherits the Workflow, settings and Gates-skipped. A flag given on the command overrides what it inherits, and the task defaults to the Parent's.
- [ ] Each refusal (no Run, ended Run, inside a Child, the Parent's own working tree, a branch claimed in that working tree, an unknown State, a missing Subject) exits non-zero with a message naming the fix.
- [ ] Spawn returns at once and never supervises.
- [ ] The Parent's Children record holds the Child's Entry id after Spawn, and its Run id once the Supervisor starts it.
- [ ] A spawned Child is Started in its own Lane beside its live Parent, in the Supervisor-loop test.
- [ ] `naiad queue list` shows Children indented under their Parent.
- [ ] The Protocol text describes Spawn, and the Protocol tests and the docs-drift test pass.
- [ ] Queue documents without `parent` still load.
- [ ] Refactor: candidates considered and a verdict recorded.
