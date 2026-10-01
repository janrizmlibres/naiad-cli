# How Naiad works

This page is the agent's side of a Run: what Claude Code is told, what Naiad
listens for, and what Naiad does with each thing it hears. You do not need it to
use Naiad. It is here for when a Run does something you want explained, and for
anyone writing a Workflow who wants to know what a Prompt can rely on. For
day-to-day operation see [Running Naiad](running.md).

## Who owns what

The agent owns the Workflow's progress. Naiad cannot see the agent's work and
never decides that a phase is finished. The agent decides that, and says so by
**announcing** the State it is entering. Naiad reacts to the announcement and
never guesses at one.

That split is why an announcement is a command (`naiad announce`) and not an
edit to a file. Reading, changing and writing a progress file across a cleared
context is the clerical work a model slips on, and a slip would be silently
inert. The command writes atomically and refuses what cannot work.

## The Protocol

Naiad teaches the agent how to take part with a short text, the **Protocol**. It
is not in your Workflow file and you never paste it into a Prompt. Naiad puts it
into every fresh context: a session starting, a `/clear`, and a compaction. A
context that has just been cleared remembers nothing, so it is told again each
time.

In paraphrase, the Protocol says:

1. **Announce, do not assume.** When the phase is finished and the agent is
   satisfied with it, run `naiad announce <name>` for the State it is entering.
   Until it does, nothing happens and the Run waits.
2. **Never ask a human directly.** No human is watching, so a question put to one
   blocks forever. Run `naiad ask` with the question and every option weighed. The
   answer comes back into the session. One Question at a time: a second while one
   is open is refused.
3. **Declare your waits.** When the agent must wait for background work or an
   external check before it can announce, run `naiad wait` with what it waits on
   and how long, then end its turn. Silence during a declared wait is left alone.
4. **Relay a pause.** When the human says to pause or stop for now, run
   `naiad hold` with their words and end the turn. The Run is parked, with no
   reminders and no time limit, until they type into the session again.
5. **Spawn only when asked.** Only when a Prompt asks for it, run `naiad spawn`
   to queue a Child: a Run of its own, beside this one. Its working tree must
   be its own, because in the Parent's it would wait behind the Parent forever.

It ends with the State or States the agent may announce next, taken from the
Workflow file. A State with one successor says "announce X". A fork says
"announce whichever applies", and lists them, so the agent's judgment decides the
branch and the Workflow does not bias it toward the first one written.

Here is what the agent reads in the starter's `plan` State. It is abridged and
illustrative. `naiad protocol` prints nothing outside a Run, so you cannot run it
yourself to see the real text, which also names the absolute path of the `naiad`
that is driving the Run:

```text
# Naiad protocol

You are being driven through a workflow by Naiad. It cannot see your work and
never decides that a phase is finished — you do, and you say so. Five rules:

1. Announce, do not assume. When you have finished the phase you are in and
   are satisfied with the result, run `/path/to/naiad announce <name>` to
   announce the State you are entering. ...

2. Never ask a human directly. ...

3. Declare your waits. ...

4. Relay a pause. ...

5. Spawn only when asked. ...

When this phase is done, announce: review
```

### The verbs

- **`announce <name>`** says which State the agent is entering. `--subject <value>`
  says what item of a series the phase is about, which a Prompt can then name
  with `{subject}`. Announcing the same State twice is legitimate and is how a
  loop works. An announcement is not a progress report: announce when the phase is
  done.
- **`ask "<question>" --option "<one>" --option "<another>"`** puts a Question
  to whoever answers for this State: the Answerer if the Workflow declares one,
  otherwise you. See [Running Naiad](running.md).
- **`wait "<reason>" --seconds <n>`** declares that silence is deliberate. The
  default is ten minutes. However the waits chain, one announcement buys at most
  half an hour of them. When a wait expires the agent is reminded, with the reason
  it gave.
- **`hold "<their words>"`** relays a pause the human asked for. Unlike a wait it
  does not expire. Running `wait` afterwards releases the hold.
- **`branch <name>`** declares the working branch the agent created, when the
  entry was queued without one. Naiad invents no branch name. The agent derives
  one from the repository's conventions and tells Naiad.
- **`spawn [<task>] --repo <path>`** queues a **Child** of this Run and returns
  at once, printing `queued <id>`. The Child takes the Parent's Workflow,
  settings, `--skip-gates` and task, unless the command names its own with the
  task, `--model`, `--effort` or `--skip-gates`. `--branch`, `--base`, `--at`
  and `--subject` mean what they mean on `naiad queue add`. `--repo` is
  required and must be a working tree of the Child's own, such as a
  `git worktree add` beside the repository: a different working tree is a Lane
  of its own, so the Child runs beside its Parent. Spawn is refused outside a
  Run, from a Run that has ended, from inside a Child (only one level), into
  the Parent's own working tree, and wherever `naiad queue add` would refuse
  the same Entry. `naiad queue list` shows each Child indented under its
  Parent. A Parent takes its Children in at a Join State (see
  [Writing Workflows](workflow-authoring.md#3-state-kinds-and-marks)).
  Once a Join delivery has named a Child that completed, Naiad closes that
  Child's Session and writes the closing in its Run log. The transcript, the Run
  log and the Answer log stay on disk. A cancelled Child keeps its Session, and
  a top-level Run's Session is never closed.

### Rejections

`announce` refuses what could not work, in a turn where the agent can still fix
it. An unknown State lists the valid ones:

```text
unknown state 'reveiw'; this workflow declares: plan, review, implement, verify, ship, done
```

It also refuses a State whose Prompt uses `{subject}` when no `--subject` was
given, and it refuses an announcement in a branchless Run that has already been
asked to derive a branch but has not declared it. It refuses a Terminal State
while the Run has a Child that has not finished, whether not yet started,
running or parked, naming those Children and pointing at the Join State. Each
message ends with the command to type instead.

If the agent announces over a Question it has not had answered, the announcement
stands. The Question is recorded as abandoned, so the log of an unattended Run is
never tidier than the Run was.

## The three hooks

Naiad hears about the session through three Claude Code hooks, and they are almost
its whole coupling to Claude Code.

| Hook | Runs | It does |
| --- | --- | --- |
| `SessionStart`, for `startup`, `clear` and `compact` | `naiad protocol` | Prints the Protocol into the fresh context. After a compaction it adds a reminder of the State the agent is in, its Subject, and any Question still unanswered, because a summary can lose them. It says nothing after `resume`: a resumed session gets its old context back, Protocol included. |
| `Stop` | `naiad stopped` | Records that the agent ended a turn. Naiad only types into the session after one, so it never types over work in progress. |
| `UserPromptSubmit` | `naiad submitted` | Confirms that a Prompt Naiad typed arrived whole. A Prompt Naiad did not type is let through untouched. |

The hooks find their Run from the session they run in. In a session that is not
part of a Run they print and record nothing, so they are safe to leave installed
in your user settings for all your other Claude Code work.

**What `naiad install` writes.** It merges the hooks into `settings.json` under
`$CLAUDE_CONFIG_DIR`, or `~/.claude` if that is not set, and keeps everything else
in the file. The commands it writes hold the absolute path of the `naiad` that
installed them, because the session's `PATH` is whatever tmux inherited. Running it
again replaces Naiad's earlier entries and no one else's, so it is safe to repeat.
It refuses to overwrite a settings file it cannot parse. It also installs the
`naiad-adopt` skill under `skills/`, and with `--starter` copies the starter
Workflow into your library. A hook written for one `naiad` and run by another is
what `naiad doctor` reports as hooks that name a different one.

## Ticks

Naiad drives a Run in **Ticks**. Every couple of seconds it gathers what it knows,
which is the latest announcement, whether a turn has ended since, whether a Wait
or a Hold is in force, and how long the session has been quiet. It hands that to
one function that returns at most one **Action**, and carries the Action out. The
rules live in that function and the loop holds none, which is why the sequences
below cost a Tick each.

## Clears

A State marked `clear = true` starts from an empty context. This is the point of
the tool: each phase reads its input cold from the files the earlier one left in
the repository, such as `PLAN.md`, so a long task does not bloat one context until
the agent loses the thread.

When the agent has announced a Clearing State and ended its turn, Naiad types
`/clear`. It does not assume the discard worked. The `SessionStart` hook fires with
source `clear` when it does, and until then the State's Prompt is not delivered. If
the confirmation does not come within about eight seconds, Naiad types `/clear`
again, up to three times, and after that tells you rather than delivering into a
context it could not clear. The fresh context gets the Protocol from the hook, and
then the State's Prompt.

## Switches and the Belief

A State may ask for a different `model` or `effort` from the one before it. Naiad
changes them the only way a session takes a change, by typing `/model` or
`/effort`. Each such command is a **Switch**, and one is typed per Tick, ahead of
the Prompt, because the session drops whatever arrives while it is handling a
slash command. Typing a setting and the Prompt together would lose one of them.

An entry may name its own `model` or `effort` for a State
(`--model implement=sonnet`), and for that State it beats the Workflow's.

A State that declares neither key, and has none from its entry, runs on whatever
the last one set, and Naiad types nothing for it. Only the first State of a
spawned Run gets its model and effort as launch flags instead, because nothing
has yet been running.

Claude Code fires no hook on a Switch and Naiad never reads the session back. So
what Naiad knows about the session's model and effort is a **Belief**: what it last
typed. A State that asks for what the Belief already holds spends no Switch. When
a human has had the keyboard, at a Gate or after a notification, Naiad throws the
Belief away, since you may have typed a `/model` of your own, and the next State
that names a setting types it again.

A Prompt is then delivered, and the `UserPromptSubmit` hook says whether it
arrived whole. One that was cut short is turned away and typed again, up to three
times, and then you are told.

## Nudges

If the agent ends a turn and says nothing for about two minutes, Naiad reads that
as a forgotten Protocol and sends a **Nudge**: a reminder typed into the session
that it has not announced, with the verbs to use. There are two, and the second is
firmer and does not teach `wait`, since a wait declared only to buy off a final
warning is what the bound is there to stop. After the second, Naiad stops and
tells you.

A declared Wait or a Hold silences all of this. When a Wait expires the Nudge
names what the agent said it was waiting on. A session that has not even ended a
turn and has produced no signal for half an hour is treated as hung, and Naiad
tells you.

## Why `bypassPermissions` is fixed

Every Session Naiad opens, and the Answerer's, runs in `bypassPermissions` mode.
An unattended Session cannot answer a permission prompt, so a Run that met one
would stop as unexplained silence. Making the mode a setting would not fix that,
because to honor a stricter one Naiad would have to recognize a permission prompt
in the pane, and that is a signal rather than a setting. The mode therefore is not
a knob, and containment is the machine's job: run Naiad in a container, a VM or a
devcontainer, and try your first Run on a throwaway repository.
