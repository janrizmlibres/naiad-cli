# 03 — The Answerer is opt-in

Status: resolved
Mode: AFK
Blocked by: None — can start immediately
Spec: [PRD](../PRD.md), "The Workflow loader" and "The engine"; ADR 0050

**What to build:** A Workflow with no `[answerer]` table gives every Question to the human. The Run parks as it does on an Escalation. The notification carries the reason "no Answerer is declared" ahead of the Question's text, and the Answer log records the Question as escalated with that reason. Declaring `[answerer]` (even an empty table) flips every State to the Answerer. A State overrides either default with `questions = "human"` or `questions = "answerer"`. A State that opts in within a table-less file consults the Answerer on the platform's defaults. The "state X reserves its Questions for you" wording stays for a State that asked for the human itself. The Protocol is unchanged.

- [ ] No table and no State key: `naiad ask` parks the Run, notifies "no Answerer is declared: <question>", and never consults.
- [ ] Table declared: the Answerer is consulted unless the State says `questions = "human"`, which keeps the existing reserve wording.
- [ ] No table, State says `questions = "answerer"`: the Answerer is consulted with no model or effort flags.
- [ ] `workflows/matt-pocock.toml` behaves exactly as before.
- [ ] Built test-first, Refactor verdict recorded.
