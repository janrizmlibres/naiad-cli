# Kickoff — a Run spawns a session and delivers its first Prompt

Status: ready-for-agent
Blocked by: None — can start immediately
Spec: `.scratch/core-engine/PRD.md`

## What to build

Starting a Run from a single command. The operator names a Workflow file and describes a task; Naiad reads the Workflow, creates the Run, opens a session, and types the first State's Prompt into it. Nothing advances yet — this ticket ends with a real Prompt sitting in a real session.

A Workflow file describes an ordered list of States, each with a name, an optional Prompt, whether entering it Clears, and whether it is Terminal. A State with no Prompt is a Gate State; nothing needs to handle that yet, but the format must express it. The format must also tolerate a State declaring more than one candidate successor, because branching is coming later (ADR 0005) and the format should not have to change when it arrives.

An invalid Workflow is rejected at kickoff, before a session exists, with an error naming what is wrong. Finding out halfway through a Run is the failure this prevents.

The Run owns a directory outside the target repository holding its metadata — the identifiers linking it to its session, and the task it was started with. Naiad writes nothing into the target repository (ADR 0002 storage rule, see spec).

Two constraints from deferred work apply here and are cheap now, expensive later:

- Run resolution must sit behind a single seam. Naiad sets an environment variable on the session it spawns, but that must be a shortcut rather than the mechanism, because a variable cannot be injected into a process that already exists.
- Nothing about a Run may be module-global (ADR 0004). Paths, session identifiers and task all reached through the Run.

The session is spawned in bypass permissions mode, so that a later unattended Run is never stopped by a permission prompt.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] A well-formed Workflow file parses into its States, preserving order, Prompts, Clear flags and Terminal marking
- [ ] A State with no Prompt parses successfully
- [ ] A State declaring multiple candidate successors parses successfully, even though nothing reads them yet
- [ ] A malformed Workflow is rejected with an error naming the problem, and no Run directory or session is created
- [ ] `naiad run` creates a Run directory outside the target repository containing the Run's metadata
- [ ] The target repository is not written to
- [ ] A tmux session is spawned in bypass permissions mode
- [ ] The first State's Prompt is typed into that session with the task interpolated
- [ ] The Run can be resolved by something other than the environment variable
- [ ] No Run state is held in a module-level global
