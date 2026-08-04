# Writing a Workflow file

A Workflow file is configuration. It holds a Workflow's States and their
Prompts. It holds no explanation of why.

Decisions about Naiad live in `docs/adr/`. The vocabulary lives in
`CONTEXT.md`. This file holds what those do not: the conventions that govern
how a Prompt is written.

## Rules for any Workflow file

### A Prompt that runs a skill opens with its slash command

Claude Code reads a slash command only at the start of a message. Prose in
front of the command sends the skill's name as chat. So the command comes
first, before any other word.

Opening with the command is necessary. It is not sufficient. The Prompt must
also arrive as typed input, which is the adapter's work and ADR 0011's
decision.

This is a rule about Prompts that invoke a skill. It is not a rule that each
State must invoke one. A State that runs no skill opens with prose instead.
The `classify` State is one example. The `pull-request` State is a second: it
names `/hcgps-pr` in mid-sentence, where the name does not read as a command.

### What follows the command is an argument, never a procedure

Write what the human would have typed after the command. Name the work. Name
the input. Do not write the steps.

A skill's own logic stays in the skill. Logic copied into a Prompt is
maintained in two places, and the two drift. ADR 0033 covers the one
exception: a Prompt pins what a skill leaves loose.

### A Prompt never restates the Protocol

Naiad injects the Protocol into every fresh context. This includes each
context a Clearing State creates. A Prompt that repeats the Protocol adds a
second copy to maintain.

### A branching State writes its successors out

`{next_state}` renders every candidate as one joined phrase. Use the
placeholder where a Prompt says only "announce what comes next". Write the
names out where each exit carries a different condition. ADR 0010 and ADR 0017
give the reasoning.
