# The workspace trust dialog blocks an unattended kickoff

Status: needs-info
Trigger: starting a Run in a directory Claude Code has not been run in before

## What was found

Discovered while smoke-testing ticket 01. Spawning a session in a directory Claude Code has never seen shows a first-run dialog before the TUI accepts anything:

```
Quick safety check: Is this a project you created or one you trust?
  ❯ 1. Yes, I trust this folder
    2. No, exit
```

The Run's first Prompt is handed to Claude Code as a command-line argument, so it is not lost — it simply never runs, because the dialog is waiting on a keypress nobody is there to give. The session sits there indefinitely. This is precisely the failure user story 31 exists to prevent ("sessions started in bypass permissions mode, so that an unattended Run is never blocked by a permission prompt"), except that bypass permissions mode does not cover this dialog: it appears before the session is under way.

Every target repository the operator already works in is trusted, so the shipped path is unaffected. It bites the first Run in a fresh clone — which is exactly what a disposable worktree is.

## Why it is deferred

The obvious fix is the one ADR 0002 forbids. Detecting the dialog means reading the terminal UI, and answering it means deciding on the operator's behalf that a directory is trustworthy — a decision with real blast radius that Naiad has no basis to make. Ticket 01 originally did both and it was removed for that reason; recording the gap is better than shipping a scrape.

Three directions worth weighing before choosing:

- **Pre-trust the directory out of band.** Whether a supported, documented surface exists for this is unestablished and needs checking against current Claude Code, not assumed.
- **Detect it through a supported surface.** A `SessionStart` hook fires once the session is genuinely under way; a Run whose hook has not fired within a bound has not started. That is the same notify-and-wait outcome everything else abnormal resolves to, so it may need no new vocabulary — it is the shape ticket 04 already builds.
- **Refuse to start.** Check trust at kickoff and reject with an error telling the operator to open the directory once by hand, in the same spirit as rejecting an invalid Workflow before a session exists.

The second composes with work already planned and is the most likely answer, but this should not be settled without confirming what the first direction actually offers.

## Constraints this places on the work shipping now

None beyond what already holds. Naiad must not read the terminal UI (ADR 0002), which is why this is a deferred issue rather than a fix.
