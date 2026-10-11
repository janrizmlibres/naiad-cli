# PRD: Adoption — Naiad takes over a live session

Status: ready-for-agent

Decisions recorded in ADR 0028 (`docs/adr/0028-a-run-can-adopt-a-live-session.md`) and the glossary (`CONTEXT.md`, entries **Adoption** and **Task**). This spec is self-contained; the ADR carries the fuller rationale.

## Problem Statement

The operator's real flow does not always start with Naiad. They open a Claude Code session themselves inside tmux, run the grilling interview by hand, and only then want the machine to take over the remaining phases — spec, tickets, the implement loop, the tail. Today their only option is to queue a fresh Run, which spawns a fresh session — and a fresh session has none of the grilling conversation, which is exactly what the non-Clearing States (`spec`, `tickets`) feed on. The operator wants to state their intent in the session ("start to-spec") and have Naiad drive everything after that, in that same session, with the conversation intact.

## Solution

**Adoption**: an Entry that attaches its Run to a session that already exists, instead of spawning one. The operator says their intent to the agent; the agent runs a new subcommand, `naiad adopt`, from inside the session. The command validates and enqueues an Entry marked to attach, prints the Protocol so the hitherto-undriven agent learns the verbs, and returns at once. The Supervisor — still the one entrance to starting Runs (ADR 0014) — takes the Entry in Lane order, attaches the Run to the existing tmux pane, and delivers the start State's Prompt once the current Turn has ended. From there the Run is an ordinary Run: announcements, waits, holds, nudges, the Answerer, the logs — all unchanged.

A user skill installed by `naiad install` teaches the agent the whole adopt contract, so the operator's intent phrase is all it takes.

## User Stories

1. As an operator, I want to grill a feature manually in my own session and then hand the session to Naiad, so that the remaining phases run without me driving each step.
2. As an operator, I want to hand over by stating my intent in prose ("start to-spec"), so that I never have to remember or type the adopt command myself.
3. As an operator, I want the grilling conversation to remain in context after the handover, so that the spec State synthesises from what was actually discussed rather than from disk alone.
4. As an operator, I want the adopted Run to start at the State I name, so that phases I did by hand are not re-run.
5. As an agent in an adopted session, I want the Protocol delivered to me at the moment of adoption, so that I can announce, wait, and hold correctly without a Clear having fired.
6. As an agent adopting a session, I want to declare the Working branch in the same turn — passing one the human already made, or deriving one from the repository's conventions — so that the Run's work never lands on whatever branch happened to be checked out.
7. As an agent adopting a session, I want a branch already claimed by another Entry to be refused at declaration, so that two Runs never silently stack work on one branch.
8. As an agent adopting a session, I want to write the Entry's Task myself, distilled from the conversation, so that the Queue reader and the Answerer see what the work is.
9. As an operator, I want an Adoption to wait its turn in its Lane, so that a Run already live in that working tree is never typed over.
10. As an operator, I want to be told — via the agent — when no Supervisor is running, with the exact command to start one (`naiad queue watch`), so that a queued Adoption never waits silently forever.
11. As an operator, I want `naiad adopt` to refuse bad input (unknown Workflow, unknown start State, a Prompt whose `{subject}` has no Subject, a claimed branch) while I am still at the session, so that nothing fails hours later at takeover.
12. As an operator, I want adopting at a Clearing State to Clear first, confirmed before the Prompt follows, so that the Workflow's declaration of a clean start is honored.
13. As an operator, I want adopting at a non-Clearing State to preserve the session context untouched, so that the conversation is the context the Prompt lands in.
14. As an operator, I want the adopted Run in the Run log from its first Announcement, so that an overnight run reads as the same auditable sequence any Run does.
15. As an operator, I want `naiad install` to install the adopt skill alongside the hooks, so that reinstalling Naiad heals a drifted or missing skill.
16. As an operator, I want the hooks in my manual session to keep doing nothing until a Run is attached, so that adoption support never disturbs sessions I never hand over.
17. As an operator, I want the adopted session's model and effort switched per the Workflow's declarations on each delivery, so that an adopted Run costs and thinks as the Workflow intended.
18. As an operator working outside tmux, I want a clear refusal telling me adoption needs tmux, so that I know the constraint instead of queueing a takeover that can never happen.
19. As an operator, I want the Entry produced by adoption visible in `naiad queue list` like any other, so that I can see, reorder my expectations around, or remove it.
20. As an operator, I want removing an adoption Entry before takeover to leave my session untouched, so that changing my mind costs nothing.

## Implementation Decisions

- **New agent-facing subcommand `naiad adopt`**, beside `state`, `ask`, `wait`, `hold`, `branch`. Arguments: the Workflow (bare name resolved through the Workflow library, or a path — ADR 0023), `--at <state>` for the start State, `--task` (required; the agent distils it from the conversation), `--branch` (optional; the ADR 0022 discipline applies — given or derived, never invented by Naiad), and the existing optional describers where they make sense (`--subject`, pinned base, skip-gates).
- **The Entry grows an attachment mark**: the tmux pane (read from the adopting process's environment) and the Claude session id when available. An Entry so marked tells the Supervisor to attach rather than spawn. Everything else about the Entry — id, Lane, ordering, claim checks, `queue list`, `queue rm` — is unchanged.
- **One entrance preserved (ADR 0014)**: `naiad adopt` only validates, enqueues, prints, and exits. The Supervisor performs the takeover on its ordinary pass. Adoption Entries queue in Lane order and wait behind a live Run.
- **Attachment instead of spawn**: where kickoff would open a tmux session, the Supervisor attaches the new Run to the recorded pane and records the session on the Run as spawned Runs do. Resolution of hooks and agent commands flows through the existing resolution seam (environment variable first, then pane, then Claude session id); the environment-variable shortcut is simply absent for adopted Runs.
- **First delivery waits for the Turn**: the takeover delivers the start State's Prompt only after a Turn end has been reported for that session — the same never-type-over-a-working-agent rule an Answer follows. Model and effort switches ride the delivery as ever (ADR 0026).
- **Clear flag honored, unlike kickoff**: kickoff ignores the first State's Clear because a new session holds nothing; adoption honors it because the session holds everything. The Clear is confirmed by the SessionStart hook before the Prompt follows (ADR 0019).
- **Protocol via command output**: `naiad adopt` prints the Protocol text (the same text the SessionStart hook injects) plus a closing instruction — settle the branch and end the turn; the Prompt arrives when the Lane is free. No typing into the pane, no new hook surface.
- **Branch at the adopt act**: both Workflow branch heads are skipped by a mid-Workflow start, so the ADR 0022 discipline moves into the adopt contract. A `--branch` the human made is claimed at enqueue through the existing claim check; absent one, the Entry queues branchless and the agent derives, creates, and declares via the existing `naiad branch` in the same turn.
- **No Supervisor: warn, never spawn.** The adopt output reports whether a Supervisor holds the lock; when none does, it says the Entry is queued and quotes `naiad queue watch`. The agent relays this to the operator.
- **tmux only, for now.** No pane in the adopting environment is a refusal at the command, stated plainly. A future non-tmux delivery mechanism is out of scope (below).
- **Skill installation**: `naiad install` writes, beside the hooks, a user skill directory (name: `naiad-adopt`) into the operator's Claude configuration. The skill's description triggers on handover intents; its body carries the contract: name Workflow and start State, settle the branch, write the Task, run `naiad adopt`, relay warnings, end the turn. Installation is idempotent and replaces an earlier Naiad-installed copy, as the hooks logic already does.
- **Refusals at the terminal**: everything `check_start` refuses today is refused by `naiad adopt` at the session, and re-checked at takeover, exactly as enqueue/kickoff already pair.

## Testing Decisions

Method: **TDD (Red → Green → Refactor)** for every unit of behavior — a failing test first, confirmed failing for the expected reason; minimal code to green; then a named refactor verdict, even when it is "keep". Tests assert external behavior only: what is on disk, what a command prints, what a fake session was told to do — never internals.

Seams — chosen here deliberately, recorded per the review discipline:

- **Chosen: the CLI command seam.** `naiad adopt` is tested the way `test_run_command.py` / `test_queue_command.py` drive their commands: invoke the handler with a controlled environment (pane variable set or absent), real stores in a temp directory, and assert the Entry on disk, the printed Protocol, the warning text, and each refusal. This is the highest existing seam and covers stories 2, 5–8, 10–11, 18–20.
- **Chosen: the Supervisor seam.** The takeover is tested the way `test_supervisor.py` / `test_kickoff.py` do — fake sessions object recording spawns, sends, and clears; assert an adoption Entry produces an attach (no spawn), delivery deferred until the Turn-end signal, Clear honored and confirmed at a Clearing start State, model/effort riding the delivery. Covers stories 3–4, 9, 12–13, 17.
- **Chosen: the settings/install seam.** Skill installation is tested as `test_hook_install.py` tests hooks: pure function or temp-directory install, idempotency, replacement of an earlier copy, everything else preserved. Covers story 15.
- **Rejected: a real-tmux integration seam.** The suite fakes sessions everywhere (`test_tmux_send.py` tests keystroke construction, not tmux); adding a live-tmux harness would be a new seam for confidence the fakes already give.
- **Rejected: a decision-core seam addition.** If attachment routes through the existing decide/supervise pure functions, their existing tests extend; no new seam is created for it.

Net new seams: zero. Prior art: `tests/test_run_command.py`, `tests/test_queue_command.py`, `tests/test_kickoff.py`, `tests/test_supervisor.py`, `tests/test_hook_install.py`.

## Out of Scope

- Delivery to sessions outside tmux (acknowledged future need; the design keeps the door open via the resolution seam).
- Any Naiad-side detection or watching of manual sessions (ruled out by ADR 0002).
- Jumping the Lane: an Adoption never preempts a live Run.
- Spawning a Supervisor from `naiad adopt`.
- Changes to the matt-pocock Workflow file: no third branch head, no new States.
- Auto-generating the intent phrase list beyond the shipped skill's description.

## Further Notes

- The glossary reserves *handover* (a matt-pocock State) — the feature is **Adoption** everywhere, including flag and skill naming.
- The adopted agent acts un-Protocolled until it reads the adopt output; everything between that read and its turn ending is on trust, as all Protocol acts are.
- The Claude session id may be unknowable from inside a Bash tool call; the resolution seam treats it as optional, with the pane as the reliable key. Whichever keys the adopt command can gather are recorded.
