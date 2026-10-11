# naiad adopt: enqueue an attach-marked Entry and teach the agent

Status: resolved
Blocked by: none

## Parent

`.scratch/adoption/PRD.md` (ADR 0028, glossary entry **Adoption**).

## What to build

From inside a tmux session, the agent runs `naiad adopt <workflow> --at <state> --task "..."` (plus the optional describers: `--branch`, `--subject`, pinned base, skip-gates) and a validated Entry appears in the Queue, marked with the pane to attach to — read from the adopting process's environment, with the Claude session id recorded too when it can be gathered. The command only validates, enqueues, prints, and exits; it supervises nothing and blocks on nothing (ADR 0014).

Its output is what teaches the hitherto-undriven agent: the Protocol text (the same text the SessionStart hook injects), a closing instruction — settle the Working branch per the ADR 0022 discipline and end the turn; the Prompt arrives when the Lane is free — and, when no Supervisor holds the lock, a warning that the Entry is queued with the exact remedy quoted: `naiad queue watch`.

## Acceptance criteria

- [ ] Running the command inside tmux writes one Entry carrying the attachment mark (pane, and Claude session id when available); `naiad queue list` shows it and `naiad queue rm` removes it without touching the session.
- [ ] Every refusal `check_start` makes today fires here at the terminal: unknown Workflow, unknown start State, a Prompt whose `{subject}` has no Subject; a Workflow bare name resolves through the library (ADR 0023).
- [ ] `--task` is required and becomes the Entry's Task; there is no Subject stand-in for an Adoption.
- [ ] `--branch` flows through the existing claim check and a branch another Entry holds is refused; absent `--branch`, the Entry queues branchless and claims nothing until the agent declares (ADR 0022).
- [ ] No pane in the environment is a plain refusal naming the tmux constraint; nothing is enqueued.
- [ ] The output contains the Protocol, the closing instruction, and — only when no Supervisor holds the lock — the `naiad queue watch` warning.
- [ ] An Adoption Entry queues in Lane order like any Entry; nothing about it jumps a live Run.
