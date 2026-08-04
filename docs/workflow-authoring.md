# Writing a Workflow file

A Workflow file is configuration. It holds a Workflow's States, their Prompts,
and the models they run on. It holds no explanation of why.

Decisions about Naiad live in `docs/adr/`. The vocabulary lives in
`CONTEXT.md`. This file holds two things those do not: the conventions that
govern how a Prompt is written, and the tuning choices
`workflows/matt-pocock.toml` makes for itself.

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

One procedure is written out anyway, and it is not a skill's. The scan that
reads the issue tracker and routes on what it finds belongs to no skill, so
there is nowhere else for it to live. It ends both the `implement` and the
`triage` Prompt, in identical words, and a test asserts the two copies stay
identical. ADR 0010 and ADR 0034 give the reasoning, and 0034 records the
rejected alternative — a State whose whole job is the scan.

### A Prompt never restates the Protocol

Naiad injects the Protocol into every fresh context. This includes each
context a Clearing State creates. A Prompt that repeats the Protocol adds a
second copy to maintain.

### A branching State writes its successors out

`{next_state}` renders every candidate as one joined phrase. Use the
placeholder where a Prompt says only "announce what comes next". Write the
names out where each exit carries a different condition. ADR 0010 and ADR 0017
give the reasoning.

## The choices `workflows/matt-pocock.toml` makes

These are tuning rather than decisions. Change them when the work changes.

### Models and effort

The file sets `fable` at `medium` effort as its file-level default. A
file-level default is required here, because States in the file declare their
own (ADR 0026).

Most of this chain is the work the top model does well without deep thought.
Two States step off the default and run `opus` at `high` effort: `classify`
and the `implement` loop. For those two, sustained volume matters more than
the top model's edge.

### The Answerer

The `[answerer]` table runs at the same default. The Answerer replies from the
Run's own record rather than reasoning fresh. Naiad invokes it on every
Question, so its cost recurs. This file takes that recurring spend at the
default rather than discounting it.

The `fallback` key is the Answerer's alone. ADR 0031 gives the reasoning and
the syntax.
