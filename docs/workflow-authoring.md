# Writing a Workflow

A Workflow is a TOML file: an ordered list of States, each with a Prompt Naiad
types into the agent's session, plus the few settings that say which model runs
them. This guide teaches it by task. You change the starter with the verbs, then
build a Workflow from nothing, then learn what the kinds, marks and slots mean,
how to write a Prompt, and what the file looks like by hand. The last section
explains why the starter is shaped as it is, so you know which parts to keep.

Every verb here edits the file for you and refuses a change the loader would
reject, so the file on disk always loads. `naiad workflow check` is the net for
anything you edit by hand.

Workflows live in your library, `~/.naiad/workflows` unless `NAIAD_HOME` says
otherwise. A bare name such as `starter` resolves there, and every verb also
takes a path.

## 1. Start from the starter and change it

`naiad install --starter` puts the starter in the library, and reinstalling with
`--force` overwrites it. Copy it under your own name and change the copy:

```
naiad workflow new mine --from starter
naiad workflow show mine
```

`show` prints the file's own settings and each State's kind and marks:

```text
name  mine

  plan       prompt    questions: human
  review     gate
  implement  prompt    clears  questions: human
  verify     prompt    clears  questions: human
  ship       prompt    clears  questions: human
  done       terminal
```

`questions: human` says a Question asked from that State goes to you, because the
starter declares no Answerer (Part 6 covers it).

Now change it. Choose a model and effort for the whole file, or for one State:

```
naiad workflow set mine model opus
naiad state set mine verify effort high
```

Set where the Session summarises its own context, which is a property of the
file and never of a State:

```
naiad workflow set mine autocompact 200k
```

Ask to hear about a milestone, without stopping the Run (see
[Marks](#marks) below):

```
naiad state set mine ship report true
```

Add a State, place it, and give it its Prompt from a file, from `--prompt`, or
from your editor when you give neither:

```
naiad state add mine lint --after implement --from lint-prompt.md
naiad state move mine lint --before verify
```

Change a Prompt, or where a State can lead:

```
naiad state set-prompt mine plan --from plan-prompt.md
naiad state next mine verify implement ship
```

`state next` declares the successors in order, replacing what was there. Without
any it opens a picker, and `--none` clears them. Every verb has `--help`, and `naiad state unset` and
`naiad workflow unset` take a setting back off, so the State or file has no
opinion again.

Check the result and queue it:

```
naiad workflow check mine
naiad queue add mine "Add a --dry-run flag to the export command" --repo .
```

## 2. Build a Workflow from scratch

`naiad workflow new` creates a Workflow with one State, the terminal `done`:

```
naiad workflow new fix
```

Add States one at a time. Each lands before the terminal State unless you place
it. This one reproduces a bug, fixes it in a clean context, then waits for you:

```
naiad state add fix reproduce --prompt "Reproduce this bug and write a failing test for it: {task}. When it fails for the right reason, announce {next_state}."
naiad state add fix patch --clear --from patch-prompt.md
naiad state add fix approve --gate
naiad state list fix
```

```text
  reproduce  prompt    questions: human
  patch      prompt    clears  questions: human
  approve    gate
  done       terminal
```

Then check it the way a Run would load it, and queue it:

```
naiad workflow check fix
naiad queue add fix "Exports crash on an empty date range" --repo .
```

`workflow check` loads the file exactly as a Run does and says what is wrong. It
finds an unknown key, a `next` naming a State that does not exist, a duplicate
name, a Workflow with no terminal State, and a `report` on a State where it is
refused. Run it after every hand edit.

A Run starts at the first State unless `queue add --at <state>` names another.
It ends when the agent announces a terminal State.

## 3. State kinds and marks

### Kinds

A State is one of three kinds:

- **Prompt.** It has a `prompt`. When the agent announces it, Naiad types the
  Prompt into the session and the agent works.
- **Gate.** It has no `prompt`. Naiad types nothing, parks the Run and tells
  you. A Gate is where a human decides.
- **Terminal.** `terminal = true`, and no Prompt. Announcing it ends the Run.

The agent, not Naiad, decides when a State is finished: it runs
`naiad announce <state>` for the State it is entering, and that is what moves
the Run.

A Gate's hand-off is a verdict. Attach to the session, read what the Gate is
about, and type your answer: "go ahead", or what you want changed. The agent acts
on it and announces the next State itself. There is no command to approve.
Naiad has told the agent, when it announced the Gate, which State follows, so it
carries on when you answer. [Running Naiad](running.md#gates) has the walk-through.

A Gate is a sensible place for the first human judgement. The starter puts one
after `plan`, when a wrong direction is still cheap to correct.

### Marks

Marks are optional keys on a State:

- **`clear = true`** enters the State in a fresh context: Naiad sends `/clear`
  first, confirms it landed, and only then types the Prompt. The agent knows
  nothing but what is in the Prompt and in the repository.
- **`report = true`** tells you `entered <state>` each time the agent announces
  it, plus the Subject when the Announcement carries one, and hands nothing
  over. The Run does not park.
- **`model`** and **`effort`** switch the Session before the Prompt is typed.
- **`questions`** decides whose a Question asked from this State is: `"answerer"`
  or `"human"` (see [Part 6](#6-the-file-by-hand)).
- **`next`** lists the successors, and makes a State branch when it lists more
  than one.

`report` is easiest to see on the starter's `ship`, the State that hands the
work over. Give it `report = true`:

```
naiad state set mine ship report true
```

Now a Run announcing `ship` sends `entered ship` down every notification leg
Naiad has, at push priority 2: quiet enough that a milestone never sounds like a
Gate. You learn the branch has been built and checked while the pull request is
still being opened, and the Run carries on. `done`, the Terminal State, already
tells you when the Run ends, so `ship` is the milestone worth a second word.

A Report fires when an Announcement of the State is seen, before that State's
Clear. It never fires for the State a Run starts at, and never for a Question
asked from the State. It goes on a Prompt State only. On a Gate or a Terminal
State the loader refuses it, because each already tells you on entry. Take it off
again with `naiad state unset mine ship report`.

## 4. The slots

A Prompt is prose, and five slots in it are filled in when it is typed. Only
these five are substituted. Anything else that looks like a placeholder, such as
JSON in a Prompt, is left alone.

| Slot | Renders as | Empty when |
|---|---|---|
| `{task}` | The task text given to `queue add`. Every Prompt of the Run gets it, including after a Clear. | Never: a Run without a task must have a `--subject`, which stands in for it. |
| `{branch}` | The Working branch: the one `queue add --branch` named, or the one the agent declared with `naiad branch <name>`. | Until a branch is named or declared. An empty line is the Prompt's cue to derive a name and declare it. Once a Prompt with `{branch}` has gone out, an Announcement is refused until a branch is declared. |
| `{predecessor}` | The branch the work stands on, from `queue add --base`. Naiad does not check that it exists, so the Prompt decides what to do with it. | No `--base` was given, which is ordinary. |
| `{subject}` | What the agent said its last Announcement was about: `naiad announce <state> --subject <value>`. For the State a Run starts at, the `--subject` given to `queue add`. | The Announcement carried none. A Prompt with `{subject}` in it refuses an Announcement of its State that has none, so the agent corrects itself in its own turn. |
| `{next_state}` | The States the agent may announce next, read as a phrase: `verify`, or `no-repro or pull-request`. It is the State's `next` list when it has one, otherwise the next State in declared order. | Nothing follows: a Terminal State, the last State, or only skipped Gates. |

`{branch}` and `{predecessor}` are facts of the Run, like the task, so they reach
every Prompt, and a State that has forgotten everything can still name the branch
it is on. `{subject}` belongs to one Announcement.

With `--skip-gates` the declared order steps past Gates, so `{next_state}` names
the State after the Gate. A Gate that some State names in its `next` is a
destination the agent chose, and is never stepped past.

## 5. Prompt conventions

These keep a Prompt short and stop it fighting the tools around it.

### A Prompt that runs a skill opens with its slash command

Claude Code reads a slash command only at the start of a message. Prose in front
of the command sends the skill's name as chat. So the command comes first,
before any other word:

```text
/deploy-checklist staging, for the release branch named below
```

Naiad types the Prompt into the session, so the command arrives as typed input
and is read as one. This is a rule about Prompts that invoke a skill, not a rule
that each State must invoke one. A State that runs no skill opens with prose. The
starter runs no skill at all.

### What follows the command is an argument, never a procedure

Write what you would have typed after the command. Name the work. Name the
input. Do not write the steps. A skill's own logic stays in the skill: logic
copied into a Prompt is kept in two places, and the two drift.

### A Prompt never restates the Protocol

Naiad injects the Protocol, which is how the agent learns to announce and ask,
into every fresh context, including each one a Clearing State creates. A Prompt
that repeats it adds a second copy to maintain. A Prompt says what to do and
which State to announce when it is done, and no more.

### A State declares a setting only where it changes one

The Session keeps its Model and Effort until something changes them. A State that
declares neither runs on what the State before it set, and Naiad types nothing
for it. So declare a setting where a phase needs a different one, and nowhere
else. A file-level default is optional, and a State's own key overrides it.

One caution: a Run may start at any State, with `queue add --at`. A State that
declares nothing, entered that way, takes whatever your Claude Code holds. If a
State must run on a particular model, declare it on that State.

### The compaction point is the file's key

`autocompact` at the top of the file names the point at which the Session
summarises its own context, in Claude Code's own syntax (`"200k"`). It rides the
launch of a Session and is never typed afterwards, so it belongs to the file and
no State may declare one. Leave it out and the Session compacts where Claude
Code would anyway.

### A branching State writes its successors out

`{next_state}` renders every candidate as one phrase. Use it where a Prompt only
says "announce what comes next". Where each exit carries a different condition,
write the names out with their conditions instead:

```text
If the bug reproduces, announce fix. If it does not, announce no-repro.
```

### No "you just…" after a Clear

A State with `clear = true` starts in an empty context. "You just finished the
plan" is false there, and an agent will invent the plan it believes it wrote. Say
what the work is and where to find it.

### Name the hand-off Artifact by path

What one State leaves for the next must be somewhere the next can open: a file
in the repository, committed on the branch. Name it by path in both Prompts,
`PLAN.md` at the repository root, not "the plan". The Prompt that writes it says
what it must hold. The Prompt that reads it says to read it first, because it
starts cold.

## 6. The file by hand

One annotated file with each key once. Top-level keys come first, then
`[answerer]`, then the States. Copy from it and delete what you do not need. A
key you misspell is refused at load rather than ignored.

```toml
# The Workflow's name. It is the file's stem in the library, and
# `naiad workflow rename` keeps the two together.
name = "example"

# The Model and Effort every State asks for unless it names its own. Absent
# means no opinion: the Session runs on what your Claude Code holds.
model = "opus"
effort = "medium"

# Where the Session summarises its own context, in Claude Code's own syntax.
autocompact = "200k"

# Declaring this table, even empty, sends every State's Questions to an
# Answerer: a separate headless Claude that answers from the repository. With
# no table, every Question parks the Run and goes to you.
[answerer]
# The Answerer starts clean each time, so it declares its own settings.
model = "sonnet"
effort = "medium"
# The Models it may degrade to when its own is unavailable, comma-separated.
fallback = "haiku"

[[states]]
# A State's name is what the agent announces.
name = "plan"
# A State with a Prompt is a Prompt State. The slots are described in Part 4.
prompt = """
Plan the following task. Do not build it yet.

{task}

Write the plan to `PLAN.md`, commit it, then announce {next_state}.
"""
# Whose a Question asked from this State is; it overrides the file's default,
# which is "answerer" where [answerer] is declared and "human" where it is not.
questions = "human"

[[states]]
name = "review"
# No prompt makes this a Gate: Naiad types nothing and you decide.

[[states]]
name = "implement"
# Enter in a fresh context.
clear = true
# This State's own Model and Effort, over the file's.
model = "sonnet"
effort = "high"
# The successors, in order. Without it, the next State in declared order. Two
# or more make the State branch, and its Prompt writes out when each applies.
next = ["implement", "ship"]
prompt = """
Build what `PLAN.md` at the repository root describes. When every Step is done,
announce ship. If a Step is left, announce implement.
"""

[[states]]
name = "ship"
clear = true
# Tell the operator `entered ship` without parking the Run. Refused on a Gate
# and on a Terminal State.
report = true
prompt = "Open the pull request for this branch, then announce {next_state}."

[[states]]
name = "done"
# Announcing this State ends the Run. Give it no Prompt. A Workflow needs at
# least one.
terminal = true
```

`naiad workflow check` loads a file exactly as a Run does, so run it after every
edit:

```
naiad workflow check example
```

## Why the starter is shaped this way

The starter is a small feature or fix on any repository, with no custom skills:
plan it, look at the plan, build it, check it, hand it over. Each choice in it
answers something that goes wrong otherwise. Keep the reasons when you change
the shape.

**Every Prompt is prose.** A Workflow that opens with a skill's slash command
runs only where that skill is installed. The starter has to run on a machine that
has nothing but Claude Code, so it asks for the work in words.

**`plan` writes a file, and the file is the hand-off.** `implement`, `verify`
and `ship` each start from a cleared context. Nothing survives a Clear but the
repository, so `PLAN.md` is where the plan goes: written with four fixed
headings, committed on the branch, named by path in every Prompt that reads it.
The Prompt that writes it says the next reader starts cold.

**`review` is a Gate straight after `plan`.** A wrong plan is the cheapest thing
to catch and the most expensive thing to build. The Gate is the one place the
starter stops for you. Everything after it can run unattended, and `--skip-gates`
takes the Gate out when you would rather not stop.

**`implement`, `verify` and `ship` clear.** A fresh context makes each phase
judge the repository as it is, not as the agent remembers it. `verify` in
particular reads the diff cold and checks it against the plan's Goal, so it
catches what `implement` believed it had done. `plan` does not clear: a Run
begins in a clean session already, and a Clear at the start of the first State
would only delay it.

**`plan` derives and declares the branch, and later States do not.** Only `plan`
names `{branch}`. It checks the Working branch out, or derives a name and runs
`naiad branch` to tell Naiad. Later States say "the branch that is already
checked out", which stays true across a Clear because git holds it, not the
context.

**`verify` never hides a failure.** If a check still fails after the agent has
tried, the Prompt tells it to write a `## Status` heading into `PLAN.md` saying
what remains. `ship` reads that heading and puts it in the pull request, so an
open problem reaches a reviewer.

**`ship` removes `PLAN.md`.** The plan becomes the pull request description and
does not ship. Removing it is a commit, so the branch's history shows it.

**No model, effort or compaction point.** The starter has no opinion, so a Run
uses what your Claude Code holds. A model you did not choose in a file you
copied is a bill you did not expect. Choose in your own copy, as Part 1 shows.

**No `[answerer]` table.** With none, every Question the agent asks parks the Run
and reaches you. That is the safe default for a Workflow you have not tuned:
nothing is decided for you until you opt in by declaring an Answerer.

**No `report`.** A Report is a choice about what you want to hear, and the
starter cannot know. Part 3 shows how to add one.
