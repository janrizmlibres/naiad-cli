# Protocol injection and next-State resolution

Status: ready-for-agent
Blocked by: 02-the-core-loop
Spec: `.scratch/core-engine/PRD.md`

## What to build

The point at which the human stops typing. Until now someone has been announcing on the agent's behalf; after this ticket a real agent runs the chain by itself.

Two things make that possible. The agent must know the Protocol — announce rather than assume, never ask a human directly — and it must know which State to announce next.

The Protocol is injected into every fresh context by a hook covering the three moments a context is created or destroyed: a session starting, a Clear, and a compaction. The last two matter most: a Run Clears between loop iterations, and compaction can strike unannounced mid-phase. Either would otherwise leave the agent unable to participate, after which it falls silent and the Run dies quietly.

The Protocol is Naiad's responsibility and never the Workflow author's (spec, Implementation Decisions). A Workflow file contains States and Prompts and nothing else — if an author has to paste boilerplate into every Prompt, one omission produces a State that silently never advances.

The expected next State reaches the agent by interpolation into the Prompt, so the Workflow file remains the single source of truth for ordering rather than the ordering being restated by hand in each Prompt.

Resolving that next State is also where two operator options live:

- Running with Gates skipped resolves past Gate States to the next State with a Prompt. Naiad still never writes the State file — it interpolates a different value, which is what keeps the single-writer rule intact (ADR 0001).
- Starting a Run at a named State rather than the first, for when the operator already has the earlier phase's output.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] The Protocol is injected when a session starts, after a Clear, and after a compaction
- [ ] The injected Protocol names the announce and ask commands and instructs the agent never to ask a human directly
- [ ] The injected Protocol names the agent's expected next State
- [ ] A Prompt carrying a next-State placeholder is delivered with the Workflow's ordering substituted in
- [ ] Next-State resolution is a pure function of the Workflow and the current State, tested as data in, State out
- [ ] With Gates skipped, resolution returns the next State that has a Prompt, skipping any number of consecutive Gate States
- [ ] With Gates skipped, the State file is still only ever written by the agent
- [ ] A Run started at a named State delivers that State's Prompt first
- [ ] A Run started at a State not in the Workflow is rejected before a session is created
- [ ] A Workflow file still needs no Protocol text in any Prompt
