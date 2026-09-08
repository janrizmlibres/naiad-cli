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
opens the pull request through the host's MCP server and runs no skill.

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

### A State declares a setting only where it changes one

The Session keeps its Model and its Effort until something changes them. A
State that declares neither runs on what the State before it set, and Naiad
types nothing for it. So declare a setting where a phase needs a different one,
and nowhere else. A file-level default is optional, and a State's own key
overrides it. ADR 0040 gives the reasoning.

### A branching State writes its successors out

`{next_state}` renders every candidate as one joined phrase. Use the
placeholder where a Prompt says only "announce what comes next". Write the
names out where each exit carries a different condition. ADR 0010 and ADR 0017
give the reasoning.

## The choices `workflows/matt-pocock.toml` makes

These are tuning rather than decisions. Change them when the work changes.

### Models and effort

The file declares `opus` at `high` effort as its file-level default, and no
State names either key. The whole chain runs on that pair.

It is the default that carries the choice, and not the first State, though
one declaration on `classify` would reach every State a Run walks from there.
An Entry may name the State it starts at: a batch of known bugs enters at
`diagnose`, because the operator has already made the judgement `classify`
exists to make. A pair declared on `classify` would never reach
those Runs, and they would take the platform's own setting with nothing in
this file to say so. A default reaches every State however a Run enters
(ADR 0040).

### The Answerer

The `[answerer]` table declares `fable` at `medium` effort. It has to declare
something to run on either, because a headless session starts clean each time
and inherits nothing the States set.

The Answerer replies from the Run's own record rather than reasoning fresh.
Naiad invokes it on every Question, so its cost recurs. This file discounts
that recurring spend where it does not discount the States'.

The `fallback` key is the Answerer's alone. ADR 0031 gives the reasoning and
the syntax.

A State may keep the Answerer out with `questions = "human"`. A Question asked
from such a State is never consulted: the Run parks as it does on an
Escalation, the notification carries the Question's text, and the human
answers in the Session. `wayfind` declares it, because a Wayfinder map's
tickets are the decisions a human is meant to make (ADR 0046). Every other
State says nothing and keeps the Answerer.
