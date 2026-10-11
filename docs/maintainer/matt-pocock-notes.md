# The Matt Pocock Workflow: tuning notes and where each State was decided

`workflows/matt-pocock.toml` carries no explanation of its own, because a
Workflow file is configuration. These are the notes it used to sit beside: the
tuning choices it makes, and the index of decisions behind each State's shape.
The conventions that govern how any Prompt is written are in
`docs/workflow-authoring.md`.

## The choices `workflows/matt-pocock.toml` makes

These are tuning rather than decisions. Change them when the work changes.

### Models and effort

The file declares no file-level default. Every State that delivers a Prompt
declares its own pair instead. The States that build or merge code
(`orchestrate`, `implement` and `build`) declare `opus` at `high`; every other
one declares `opus` at `medium`. `spec` and `tickets` declare nothing and run on
what the State before them set.

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

The file declares `autocompact = "200k"`. A long `orchestrate` pass on a 1M
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

The table is also the file's default for whose Questions are whose. A file
that declares `[answerer]`, even an empty table, sends every State's Questions
to the Answerer; a file that declares none sends them all to the human. Either
default gives way to a State's own `questions = "human"` or
`questions = "answerer"`, and a State that opts in within a table-less file
consults the Answerer on the platform's defaults (ADR 0050).

A Question that is the human's is never consulted: the Run parks as it does on
an Escalation, the notification carries the Question's text, and the human
answers in the Session. The reason ahead of the text says why: "no Answerer is
declared" where the file's default put it with the human, and "state X reserves
its Questions for you" where the State asked. `wayfind` declares
`questions = "human"`, because a Wayfinder map's tickets are the decisions a
human is meant to make (ADR 0046). Every other State says nothing and follows the
file's default, which here is the Answerer this file declares.

### The project file

A repository tells this Workflow its own facts in a `.matt-pocock.toml` at its
root (ADR 0052). Naiad never reads it; the Prompts do.

- **`companions`**: a list of paths, relative to the repository root, to the
  checkouts of companion repositories. `orchestrate`, `implement`, `build`
  and `pull-request` read it (ADR 0048, ADR 0051).
- **The pull-request opt-out**: a repository that says not to open a pull
  request is skipped by `pull-request` (ADR 0018).
- **`children`**: a positive whole number, the most Children `orchestrate` has
  in flight at once in this repository. Absent, there is no limit of the
  repository's own. Set it when the repository cannot take many builds at
  once, such as tests that share one database. It is counted by the Prompt,
  beside the Entry's Child limit and Capacity, which Naiad applies (ADR 0063).
  When the smaller of it and the Entry's Child limit is 1, `orchestrate`
  spawns nothing and hands each ticket in turn to `implement`, which builds it
  on the Working branch in the Run's own Session (ADR 0065).

### What the tracker document must say

The implement loop's Prompts speak in five ticket operations and leave the
mechanics to the repository's `docs/agents/issue-tracker.md` (ADR 0066):
what makes a ticket closed, how to claim one, how to resolve one, how to
comment on one, and how a ticket names what blocks it. The documents
`setup-matt-pocock-skills` generates already cover all five, some of them under
their Wayfinding heading, so a repository needs nothing new. A tracker document
that spells them out under a heading of their own, as this repository's does,
leaves the agent less to infer.

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
| `tickets` | ADR 0010 (the implement loop triages), ADR 0033, ADR 0041, ADR 0063 (it no longer picks a ticket) |
| `orchestrate` | ADR 0009 (an Announcement carries a Subject), ADR 0010, ADR 0027 (wontfix is closed), ADR 0033, ADR 0034 (needs-triage is triaged), ADR 0041, ADR 0058 (a Run's work is its Working branch), ADR 0060 (Spawn and the Join State), ADR 0063 (it coordinates and spawns a Child per ready ticket), ADR 0065 (at a build limit of one it hands tickets to `implement`), ADR 0066 (it speaks in ticket operations and resolves each Child's ticket after the merge). ADRs before 0066 call it `implement`. |
| `implement` | ADR 0065 (one ticket on the Working branch, in the Parent's own Session), ADR 0066 (it declares its own Model and Effort). ADRs before 0066 call it `build-here`. |
| `triage` | ADR 0009, ADR 0010, ADR 0027, ADR 0033, ADR 0034 (which created it), ADR 0041, ADR 0063 (it hands routing back to `orchestrate`), ADR 0066 (it reads triage statuses as the tracker's labels) |
| `build` | ADR 0063 (a Child builds one ticket in a sibling worktree), ADR 0066 (it leaves its ticket for the Parent to resolve) |
| `handover` | ADR 0007, ADR 0010, ADR 0034 |
| `pull-request` | ADR 0015, ADR 0016 (the tail is project-neutral), ADR 0018 (how the tail ends is read from the project), ADR 0048 (a companion repository gets its own pull request), ADR 0051 (a companion is a repository, not a checkout), ADR 0063 (the sweep of Children's worktrees and branches) |
| `wayfind` | ADR 0009, ADR 0045 (a Wayfinder map is walked AFK-first and stops at a Gate), ADR 0046 (a State may reserve its Questions for the human) |
| `chart` | ADR 0045 |
| `map-spec` | ADR 0045 |
