# 08 — Reading a Run's Answers

Status: resolved
Mode: AFK
Blocked by: 05, 07
Spec: [PRD](../PRD.md), "The engine" and "The Run-facing verbs"; map ticket [15](../issues/15-reading-a-runs-answers.md)

**What to build:** The operator reads what happened to every Question without opening JSON.

- **The Answer log records the State.** Each entry records the Standing State the Question was asked from. Older entries read with no State.
- **`naiad queue answers <entry|run>`.** The argument is required, and there is no "latest" default.
  - An Entry that hasn't started says so.
  - A Run with no Questions prints `no questions were asked in <run>`.
  - Otherwise it prints one numbered block per Question, with a blank line between blocks:
    - the number and the State;
    - the Question wrapped to the terminal width (80 when piped);
    - `options:`, one per line;
    - one outcome line: `→ answerer: <answer>`, `→ yours: <reason>`, or `→ abandoned: <what the agent moved on to>`.
  - No colour and no `--json`.
- **Notifications point at the verb.** When the Answerer answered at least once, the Finish and the Gate notifications add `N answered by the Answerer — naiad queue answers <entry>`, with the Run id for a Run that has no Entry. The Gate line sits beside ticket 07's `next:` clause. Escalations, human Questions and abandonments are not counted.
- **The watch echo shortens.** `naiad queue watch` prints `consulted` and `answered` as one line cut to the terminal width, dropping the options and keeping the answer's first clause.

- [ ] A Run with an answered, an escalated, a human-reserved and an abandoned Question prints four blocks with the matching outcome lines and States.
- [ ] Both an Entry id and a Run id are accepted, a missing argument is a usage error, and an unstarted Entry says so.
- [ ] Finish and Gate notifications carry the count line only when the count is positive.
- [ ] The watch echo lines never exceed the terminal width.
- [ ] Built test-first, Refactor verdict recorded.
