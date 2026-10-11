# The core loop — announce, advance, Clear, repeat

Status: ready-for-agent
Blocked by: 01-kickoff-spawns-a-session
Spec: `.scratch/core-engine/PRD.md`

## What to build

The engine. The agent announces the State it is in; Naiad notices and delivers that State's Prompt. Running `naiad state <name>` by hand inside the session and watching the next Prompt arrive is the demo.

Announcing is a command rather than a file edit (ADR 0001). The command allocates the ordering, writes atomically so a tick cannot read a half-written file, and rejects a State name that is not in the Workflow with an error listing the valid ones — an error the agent can read and correct itself. A typo must not be silently inert.

Announcements are distinct and ordered even when they name the same State twice. Naiad acts once per Announcement, never twice, and never skips one. This is what makes a loop State work: the agent implementing its fifth ticket announces the same State a fifth time and gets a fifth delivery. No iteration, ticket list, or exhaustion condition exists anywhere in Naiad — which tickets remain lives in the ticket files.

Delivery requires two independent facts, and neither substitutes for the other:

- an Announcement Naiad has not yet acted on — the agent's intent
- a turn has ended since that Announcement — the safety signal, reported by a `Stop` hook

A turn ending is not enough, because turns end constantly without the agent being ready to advance. An Announcement is not enough, because the agent writes it and then keeps working; delivering into a busy session means typing over work in progress, and Clearing is destructive.

A State declaring Clear has its context discarded before its Prompt is delivered. This is what gives a phase a clean context without a new session (ADR 0003).

Every rule here belongs in the pure decision function (ADR 0004) — the tick loop gathers signals, calls it, and carries out the result, holding no rules of its own.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] Announcing a State allocates a strictly increasing sequence and records the State
- [ ] The State file is written atomically — a concurrent read never observes a partial write
- [ ] Announcing a State not in the Workflow exits non-zero with an error listing the valid names, and does not alter the State file
- [ ] The agent-facing command is exercised as a real subprocess against a temporary Naiad directory, asserting exit status, resulting file, and error text
- [ ] An unhandled Announcement with a turn ended since it delivers that State's Prompt
- [ ] An unhandled Announcement with no turn ended since takes no action
- [ ] An Announcement already acted on takes no action, however many times the decision is made
- [ ] The same State announced twice delivers twice
- [ ] A State declaring Clear has the context cleared before its Prompt is delivered; a State not declaring it does not
- [ ] Decision rules are tested as data in, Action out — no tmux, no subprocess, no clock, no sleeping, no fakes
- [ ] The tick loop contains no rules, only signal gathering and dispatch
