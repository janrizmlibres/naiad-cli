# The State column in the Queue listing

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

What does `naiad queue list` show beside the four status words? The current State is the latest Announcement's State name and is what makes `parked` legible without opening the notification. Decide: what the column shows for a `waiting` Entry (nothing, or the State it starts at); for a `done` Run (the terminal State's name, or blank); for a `running` Run in a Wait; whether a Question in flight is shown; and where in the line it sits so the existing layout is not reflowed.

## Answer

The column shows the Run's **Standing State** (new glossary term in `CONTEXT.md`): the State of its latest Announcement, or before it has announced, the State it began at.

- **Line layout**: `id  status  state  repo  branch  task  (run)`. The State sits right after the status word, padded to the longest State name in this listing, so `parked  review` reads as one phrase. Only repo and the columns after it shift. No header row.
- **`waiting`**: `-`. No Run exists, so nothing is standing anywhere; the column never reads the Entry or the Workflow.
- **`running`, before the first Announcement**: the start State. Kickoff (and Adoption) records the resolved start State's name on the Run, so the listing never reads a Workflow.
- **`running` in a Wait, or with a Question in flight**: the State alone, with no mark. A Question Announcement already carries the agent's State. Marking a Wait or Question would be naming a park's reason, which the map rules out of scope; Questions are read through "Reading a Run's Answers".
- **`done`**: the latest Announcement's State, the same rule as every other status. A normal ending shows the terminal State; a Cancellation or Finish shows where the work stopped.
- **Subject**: not shown. The column is one bare State name.
- **A State the Workflow no longer declares**: shown exactly as recorded. `naiad announce` refuses an undeclared State (ADR 0001), so this only happens when the Workflow is edited under a live Run (`naiad state rm|rename`). The listing reports what the Run recorded.
- **One resolver**: `standing_state` stops reading the Workflow for the start State and reads the Run's record instead, so the Protocol, the Compaction reminder and the listing all give the same answer. It also stops a Workflow edited under a live Run from leaving the Protocol with nothing to expect.
- **Runs that predate the record** (no recorded start State, no Announcement): `-`, with no fallback to reading the Workflow. Only the maintainer's old Runs are affected, and a Prune clears them.

No ADR: each choice is cheap to reverse, and the no-Workflow-read rule applies ADR 0013 (asked of the Run) and ADR 0001 (the agent owns progress).
