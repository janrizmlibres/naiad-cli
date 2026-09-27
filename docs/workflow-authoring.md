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

### The compaction point is the file's, not a State's

`autocompact` at the top of the file names the point at which the Session
summarises its own context, in the platform's own syntax (`"200k"`). It rides
the launch of a spawned Session and is never typed after, so it belongs to the
file and no State may declare one. Leave it out and the Session compacts where
the platform would anyway. ADR 0047 gives the reasoning.

### A branching State writes its successors out

`{next_state}` renders every candidate as one joined phrase. Use the
placeholder where a Prompt says only "announce what comes next". Write the
names out where each exit carries a different condition. ADR 0010 and ADR 0017
give the reasoning.

## The choices `workflows/matt-pocock.toml` makes

These are tuning rather than decisions. Change them when the work changes.

### Models and effort

The file declares no file-level default. Every State that delivers a Prompt
declares its own pair instead, and for now every one of them declares the same
pair: `opus` at `medium`. `spec` and `tickets` declare nothing and run on what
the State before them set.

The phases that interview, diagnose, triage and write specs ran on `fable`
until the Fable credit balance ran out mid-Run, which reaches a State as a
non-zero exit and the Answerer as an Escalation. Putting every phase on one
model is the stopgap, not the considered split; restore a per-phase pair when
the balance is back.

Each delivering State carries its own pair because an Entry may name the State
it starts at: a batch of known bugs enters at `diagnose`, because the operator
has already made the judgement `classify` exists to make. A pair declared on
`classify` alone would never reach those Runs, and they would take the
platform's own setting with nothing in this file to say so (ADR 0040).

### The compaction point

The file declares `autocompact = "200k"`. A long `implement` pass on a 1M
window otherwise runs far past that, and past it the work is worse and every
turn re-sends the whole context. The Answerer session is untouched: it is not
the one that grows.

### The Answerer

The `[answerer]` table declares `opus` at `medium` effort. It has to declare
something to run on either, because a headless session starts clean each time
and inherits nothing the States set.

The Answerer replies from the Run's own record rather than reasoning fresh.
Naiad invokes it on every Question, so its cost recurs, and this file used to
discount that recurring spend with `fable` where it did not discount the
States'. It runs on the same pair as the States for now, for the reason under
Models and effort above.

The `fallback` key is the Answerer's alone. ADR 0031 gives the reasoning and
the syntax. It names `sonnet` alone: a fallback repeating the primary is a
retry on the model that just declined.

A State may keep the Answerer out with `questions = "human"`. A Question asked
from such a State is never consulted: the Run parks as it does on an
Escalation, the notification carries the Question's text, and the human
answers in the Session. `wayfind` declares it, because a Wayfinder map's
tickets are the decisions a human is meant to make (ADR 0046). Every other
State says nothing and keeps the Answerer.

## Where each State's shape was decided

The shipped file carries no ADR pointers, because it is shipped to projects
that have never seen this repository. This table is the index its comments
used to be. Read the ADRs named for a State before reshaping it.

| State | Decided in |
|---|---|
| file as a whole | ADR 0040 (a State without a setting has no opinion), ADR 0043 (its tests assert invariants, not content), ADR 0047 (the compaction point rides the launch) |
| `[answerer]` | ADR 0026 (model and effort ride the Workflow file), ADR 0031 (fallback rides the invocation) |
| `classify` | ADR 0005 (classification is a State, not a router), ADR 0041 (fewer pins) |
| `diagnose` | ADR 0008 (the bug branch is one State), ADR 0015 (branch names, not git knowledge), ADR 0022 (a Working branch is given or derived) |
| `no-repro` | ADR 0007 (Gate skipping follows the declared order), ADR 0008 |
| `grill` | ADR 0015, ADR 0022 |
| `review` | ADR 0007, ADR 0045 (the Wayfinder loop re-enters here) |
| `spec` | ADR 0033 (a Prompt pins what a skill leaves loose), ADR 0041 |
| `tickets` | ADR 0010 (the implement loop triages), ADR 0033, ADR 0041 |
| `implement` | ADR 0009 (an Announcement carries a Subject), ADR 0010, ADR 0027 (wontfix is closed), ADR 0033, ADR 0034 (needs-triage is triaged), ADR 0041 |
| `triage` | the same six as `implement`; ADR 0034 is the one that created it |
| `handover` | ADR 0007, ADR 0010, ADR 0034 |
| `pull-request` | ADR 0015, ADR 0016 (the tail is project-neutral), ADR 0018 (how the tail ends is read from the project), ADR 0048 (a companion repository gets its own pull request), ADR 0051 (a companion is a repository, not a checkout) |
| `wayfind` | ADR 0009, ADR 0045 (a Wayfinder map is walked AFK-first and stops at a Gate), ADR 0046 (a State may reserve its Questions for the human) |
| `chart` | ADR 0045 |
| `map-spec` | ADR 0045 |
