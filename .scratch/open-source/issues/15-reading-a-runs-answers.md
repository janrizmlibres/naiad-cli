# Reading a Run's Answers

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

The Answer log is the adopter's only visibility into the Answerer (ADR 0050), and today it is `answers.json` in the Run's directory, holding for every Question its text, options, answer, whether it was escalated and whether it was abandoned; no verb reads it, and `naiad queue watch` echoes the Question and Answer as one wrapped line each. Decide: the verb that prints a Run's Answers as a readable block (Question, options, answer or escalation with its reason, the State it was asked from) and its home on the verb surface, given `naiad queue` is the only Run-facing noun; whether it takes a Run id, an Entry, or defaults to the latest Run; whether the watch stream shortens its consulting and answered lines to a first line and points at the verb; and whether the block is what a finish notification links to. Surfaced by "The Answerer is opt-in and visible".

## Answer

Resolved 2026-09-27 by grilling. No ADR: every part is cheap to reverse. Glossary: **Answer log** now names the Standing State each Question was asked from, and says that for a Question the human took it holds who put it with them, never their reply.

- **The verb is `naiad queue answers <entry>`**, beside `list/add/rm/prune/watch`: `queue` stays the one Run-facing noun, and a general `queue show` was rejected as an invitation to print the Run log, notices and deliveries too.
- **It takes the Entry id or the Run id**, both of which `queue list` prints; the argument is required. No "latest Run" default: with lanes in parallel it is ambiguous, and reading the wrong Run's Answers is worse than a refusal. An Entry that has not started yet says so rather than printing an empty block.
- **The log records the State.** Each entry gains `state`, the Run's Standing State when the Question was asked. No timestamp: the log is append-only, so order is the story, and the Run log holds the times. Entries written before the change print with no State.
- **Human Questions stay in the block**, with the outcome said plainly: Naiad knows who put the Question with the human (the reason), not what the human replied in the Session. An abandoned Question shows what the agent moved on to.
- **The block**: one per Question, numbered, with a blank line between blocks. The first line is the number and the State. Then the Question in full, wrapped to the terminal width (80 when piped), then `options:` one per line, then one outcome line starting `→ answerer:`, `→ yours:` or `→ abandoned:`. A Run with no Questions prints `no questions were asked in <run>`. No colour and no `--json`, because `answers.json` is the machine form.

  ```
  1  implement
     The local API on :3939 is stale … May I stop it and rebuild?
     options:
       - Yes — rebuild, restart, migrate/seed as needed
       - No — commit the script unrun and note it in the ticket
     → answerer: Yes: stop PID 37420, run `rm -rf dist && bun run build`, …
  ```

- **The watch stream shortens** its `consulted` and `answered` echo to one line cut to the terminal width, with the options dropped and the answer's first clause kept. There is no pointer on each line, because it would repeat constantly. The Run log keeps the full detail; only the echo changes.
- **Notifications point at the verb.** When the Answerer has answered at least once, the Finish notification and the Gate notification add `N answered by the Answerer — naiad queue answers <entry>`. The Gate line sits beside the `next:` line from "What the agent and the human each know at a Gate". Questions the human took and escalations don't count, because the human already saw each one. A Run the Answerer never answered gets no line.
