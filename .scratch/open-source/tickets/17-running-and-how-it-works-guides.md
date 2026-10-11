# 17 — `docs/running.md` and `docs/how-it-works.md`

Status: resolved
Mode: AFK
Blocked by: 06, 08, 09, 16
Spec: [PRD](../PRD.md), "Documentation"; map tickets [09](../issues/09-the-documentation-set.md), [12](../issues/12-what-an-adopter-can-configure-and-where.md), [13](../issues/13-naiad-doctor-and-the-refusals.md)

**What to build:** Two guides.

**`docs/running.md`**, the operator's day-to-day:
- the queue, watching and attaching;
- Gates, where the hand-off is a verdict;
- Questions and the opt-in Answerer;
- `naiad queue answers`;
- Reports and notifications, and `NAIAD_NTFY_URL`/`NAIAD_NTFY_TOKEN`, with the desktop leg macOS only;
- `NAIAD_HOME`;
- Adoption and the `naiad-adopt` skill;
- tmux as a prerequisite;
- "What you can configure": `NAIAD_HOME`, the two ntfy variables, and `CLAUDE_CONFIG_DIR` as read but not owned, plus a line that the timings and permission mode are fixed on purpose;
- troubleshooting, with one entry per doctor failure and warning.

**`docs/how-it-works.md`**, the agent's side:
- the Protocol paraphrased: `announce`, `ask`, `wait`, `hold` and `branch`, and the rejection of unknown States, with one sample block marked illustrative;
- the three hooks and what install writes;
- Clears, Switches and the Belief;
- why `bypassPermissions` is fixed;
- Belief, Tick, Switch and Nudge explained where they arise.

- [ ] The drift test passes over both files.
- [ ] Every doctor fail and warn from ticket 09 has a troubleshooting entry.
- [ ] Neither file cites an ADR, `CONTEXT.md`, a ticket or `.scratch`.
