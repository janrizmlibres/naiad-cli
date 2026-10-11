# Issue tracker: Local Markdown

Issues and PRDs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The PRD is `.scratch/<feature-slug>/PRD.md`
- Implementation issues are `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- A ticket is **closed** when its Status is `resolved` (closed by completion) or `wontfix` (closed by decision); every other status is open. Scans walk past closed tickets.
- No ticket is created `wontfix`. The status is applied deliberately, mid-effort, and whoever drops a ticket addresses its dependents in the same act — rewrites them, drops them too, or clears their `Blocked by:` edges (ADR 0027). That is what lets scans trust every surviving edge.
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## Ticket operations

The operations a Workflow's implement loop names, and how this tracker records each (ADR 0066):

- **Closed**: the `Status:` line reads `resolved` or `wontfix`. Every other status is open, `claimed` included.
- **Claim**: set `Status: claimed`.
- **Resolve**: set `Status: resolved`, and nothing more.
- **Comment**: append a line under the file's `## Comments` heading, creating the heading if it is missing.
- **Blocking edges**: the `Blocked by: NN, NN` line near the top, satisfied when every ticket it lists is closed.

Where the ticket files are tracked by git, a change to them is committed on the branch the work is on.

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` — the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Mode:` line records `AFK` or `HITL` on every ticket, whatever its type, and is the one line an unattended loop reads to decide whether the ticket is its to resolve — absent, the ticket is HITL; a `Status:` line records `open`/`claimed`/`resolved` — or `wontfix`, when a human drops the ticket (see Conventions).
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is closed (`resolved` or `wontfix` — see Conventions).
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
