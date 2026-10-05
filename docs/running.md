# Running Naiad

This is the operator's page: what you do once Naiad is installed and a Run is
under way. For a first Run start with the [README](../README.md). For how the
agent's side works, see [How it works](how-it-works.md).

## The queue

`naiad queue add` describes a piece of work and puts it in the queue. It starts
nothing.

```
naiad queue add starter "Add a --dry-run flag to the export command" --repo .
naiad queue list
naiad queue watch
```

`queue watch` is the Supervisor. It takes the queue in order, starts a Run for
each entry, and keeps following the queue for entries you add later. Only one
Supervisor runs at a time; a second is refused. `naiad run` is `queue add`
followed by a Supervisor, when none is running already.

Entries in the same working tree go one after another, and entries in different
working trees go side by side. A parked Run holds its own tree's place and
nobody else's.

How many Runs go side by side is capped. The Supervisor starts no Run while the
live ones are at its ceiling, and starts at most one each time round. A Run
counts from the moment it starts until it finishes, parked or not, except while
it stands at a Join State waiting on its Children. Nothing already working is
ever stopped. The ceiling is sized from the machine's memory, one Run for each
1.5 GiB above 8 GiB and never fewer than one. Set it yourself with `--capacity`
on `queue watch` or `run`, or with `NAIAD_CAPACITY`; the flag wins over the
variable:

```
naiad queue watch --capacity 6
```

Below the ceiling, the machine must also be unstrained. No Run starts while the
operating system reports memory under pressure: on macOS,
`kern.memorystatus_vm_pressure_level` at critical (a warning does not count,
because a busy machine reads one all day); on Linux, `some avg10` above
10 in `/proc/pressure/memory`, or less than a tenth of memory available where
that file is missing. No Run starts into a working tree whose volume has less
free disk than the larger of 10% and 10 GB; a waiting entry there is passed over
and another tree may start instead. Where the machine gives no reading, the
ceiling alone applies.

An adoption is the exception. It joins a session that is already open, so
neither the ceiling nor memory pressure holds it back. Low disk still does.
Once started it counts toward the ceiling like any other run.

While nothing can start for one of these reasons (the ceiling, memory or
disk), the Supervisor says so once.

`queue list` prints one row per entry under a header, in queue order, with
each Child beneath the entry whose Run spawned it:

```text
ID      STATUS     STATE        REPO                             BRANCH           TASK
4242    ◌ parked   review       ~/dev/shop                       feat/dry-run     Add a --dry-run flag to the…
4318    ● joining  orchestrate  ~/dev/burrow                     feat/burrow      Build Burrow from the 55 ti…
├ 4407  ● running  build        ~/dev/burrow-wt-feat-burrow--26  feat/burrow--26  Build ticket 26
└ 4411  ◌ waiting  —            ~/dev/burrow-wt-feat-burrow--27  feat/burrow--27  Build ticket 27
```

That is the entry, what became of it, the State it stands in, the repository,
the branch and the task. An entry is shown by the end of its id, the process id
that queued it, made longer where two entries share it: an agent queueing a
night's work in one turn gives every entry the same one. `naiad queue rm` and
`naiad queue answers` take that short form as well as the full id, and refuse
one that has come to name more than one entry. The repository is never cut,
and the task is cut to fit the terminal. The branch is the one the
entry was queued with, or the one the agent declared on its Run, and `—` until
there is one. The settings an entry names are listed beneath its row. The
status is coloured on a terminal, and plain when the output is piped or
`NO_COLOR` is set. What became of an entry is one of five words:

- `waiting`: no Run yet. It is queued behind another entry for its tree, it is
  a Child held by its Parent's Child limit, the Supervisor is at its ceiling,
  memory is strained or its tree is low on disk, or no Supervisor has reached
  it.
- `running`: the agent is working.
- `joining`: the Run stands at a Join State and is waiting on its Children.
  Nothing is wrong: its Prompt goes out as soon as a Child finishes.
- `parked`: Naiad has stopped and told you it needs you. The State column says
  where.
- `done`: the Run reached its last State, or you removed it.

To take an entry out, `naiad queue rm <entry>` removes it and cancels its Run.
The Run's tmux session is left alone, and the command names its pane. Removing
a Parent cancels its Children too: a started Child's Run is cancelled, a Child
not yet started leaves the queue, and the command prints the working tree of
each Child the Parent was not yet told of, for you to remove. `naiad queue
prune` removes every done entry together with the Run it became, except a done
Child its Parent is still waiting to be told of.

`queue add --file <batch-file>` queues every entry a batch file declares.
`naiad queue add --help` lists every option, including `--branch`, `--base`,
`--at` and `--subject`.

`--child-limit N` on `queue add`, `run` and `adopt` caps how many of the Run's Children
work at once; a batch file says `child-limit = N`, at the top or per entry. With
none, every Child starts as soon as it is queued. A limit of 1 takes them one at
a time, in the order they were spawned. A parked Child still counts. The number
also reaches the Run's Prompts as `{child_limit}`, so a Workflow can act on it,
for example by spawning no Children at 1 and doing the work in the Run's own
session.

An entry can run some States on a different model or effort from the one the
Workflow names, without editing the Workflow. Name each State with `--model` or
`--effort`, once per State:

```
naiad queue add starter "Add a --dry-run flag to the export command" --model implement=sonnet --effort implement=medium --model verify=sonnet
```

A setting beats the State's own key and the file's default, for that entry only.
It is refused before anything is queued, and again when the entry starts, if it
names a State the Workflow lacks, a Gate, a Terminal State, or one State twice.
`naiad queue list` shows an entry's settings under its row. `naiad adopt` and
`naiad run` take the same flags. A batch file cannot name settings yet.

## Watching and attaching

Leave `queue watch` running in a terminal. It prints what happens to each Run,
one line per event after the Run's id, and every notification that fires also
lands there, so it is the record of a night's work. On a terminal each line's
leading verb is coloured by kind: work going ahead, something worth a look (a
nudge, a Question put to the Answerer, nothing starting), or an ending. Interrupt it with `C-c`. Nothing is lost: the records are on disk,
and a new `queue watch` picks the queue up again.

Each Run has one tmux session, named `naiad-` and the Run's id, opened in the
repository. Attach to see the agent working, or to type into it:

```
tmux ls
tmux attach -t naiad-<run-id>
```

Detach with `C-b d`; the Run carries on. Naiad only types into the session when
the agent is between turns, so it does not collide with you, but it also does not
know what you typed. Type when the Run is parked and leave the agent alone while
it works.

## Gates

A Gate is a State with no Prompt. When the agent announces one, Naiad types
nothing. It parks the Run and tells you, naming what follows:

```
state 'review' is a Gate State and is waiting for you; next: implement
```

The agent has been told the same when it announced the Gate: a human takes over,
end the turn and wait. Naiad has also given it the name of the State that
follows, because nothing clears the context before you arrive.

So the hand-off is a verdict, typed into the Session:

1. Attach to the session.
2. Read what the Gate is about (in the starter, `PLAN.md`).
3. Type your verdict and **send it**: "go ahead", or what you want changed.

The agent acts on it and announces the next State itself. You do not run a
command to approve. Name a State only when you want to send the Run somewhere
other than the expected next State.

`--skip-gates` on `queue add` and `run` resolves past Gates, for an unattended Run
of a Workflow written with a human in mind.

## Questions and the Answerer

When the agent cannot decide something alone it asks a Question with `naiad ask`,
giving the options it was weighing, one Question at a time. Who answers depends on
the Workflow.

**A Workflow with no `[answerer]` table sends every Question to you.** The starter
is one. The Run parks and you are told:

```
no Answerer is declared: which of these two files should own the parser?
```

Attach and answer in the Session, as you would at a Gate. The agent carries on.

**A Workflow with an `[answerer]` table opts in to an Answerer.** That is a
separate headless Claude, started in the target repository, one per Run and
resumed across every Question so later answers do not contradict earlier ones. It
answers what the repository itself settles: conventions, naming, which module owns
what. It escalates what it cannot find there, such as credentials, external
spend or business priorities. An escalation parks the Run exactly as above, with
the Answerer's reason:

```
the Answerer escalated: the pricing tier is not in the repository
```

An Answerer that cannot be run at all, for instance because `claude` is not on
`PATH`, escalates the same way and says so.

A State can keep its Questions for you even when the file declares an Answerer,
with `questions = "human"`. The keys of the table are in
[Writing a Workflow](workflow-authoring.md).

If the agent announces a State while its Question is unanswered, it abandons the
Question. That is allowed, since the agent owns progress, and it is recorded.

### Reading what the Answerer said

An unattended Run finishes with a notification that says how many Questions the
Answerer settled and how to read them:

```
3 answered by the Answerer — naiad queue answers 20260929-101204-482113-starter-4242
```

`naiad queue answers` takes an entry, as `naiad queue list` names it, or a Run
by its id, and prints one numbered block per Question in the order they were asked:

```
naiad queue answers <entry-or-run>
```

```text
1  plan
   Where should the export flag be parsed?
   options:
     - in the command handler
     - in the shared argument parser
   → answerer: in the shared argument parser, like the other flags

2  implement
   Should the dry run print to stdout or stderr?
   options:
     - stdout
     - stderr
   → yours: no Answerer is declared
```

The last line says whose outcome it was. `answerer` is what the Answerer replied.
`yours` is a Question that reached you, by an escalation or because the Workflow
gave it to you. Naiad records that it was put to you and never what you typed.
`abandoned` is a Question the agent walked away from. The output above is an
example; your Workflow's States and Questions will differ.

## Reports and notifications

Naiad tells you three kinds of thing:

- **You are needed.** A Gate, a Question that reached you, a Hold, or trouble
  (below). The Run is parked.
- **The Run is done.** It reached its last State.
- **A Report.** A State marked `report = true` tells you `entered <state>` each
  time the agent announces it, and hands nothing over. The Run does not park.

Each goes down every leg that exists on your machine:

- **Terminal**, always: printed by the `watch` or `queue watch` process. This is
  the one that is still there in the morning.
- **Desktop**, on macOS only: a banner through `osascript`. There is no desktop
  leg on Linux.
- **Push**, when `NAIAD_NTFY_URL` is set. This is the only leg that reaches you
  away from the machine.

For push, choose a hard-to-guess topic at [ntfy](https://ntfy.sh), subscribe to
it in the ntfy app, and export the full topic URL before you start the watcher:

```
export NAIAD_NTFY_URL=https://ntfy.sh/some-hard-to-guess-name
export NAIAD_NTFY_TOKEN=<token>
```

`NAIAD_NTFY_TOKEN` is sent as a bearer token and is only needed where the topic is
access-controlled. Leave it unset otherwise. The push priority carries the
difference between the kinds: needed is 4, done is 3, a Report is 2, so a
milestone never sounds like a Gate. A failed push is reported in the terminal.
`naiad doctor` says which legs will fire.

### Other reasons a Run parks

A Run also parks, and tells you why, when:

- the human asked the agent to pause: `held at your request: <what you said>`.
  A Hold has no clock. It stands until you type to the agent and it signals again;
- the agent went silent and did not answer two Nudges (see
  [How it works](how-it-works.md));
- the session produced no signal for half an hour, which is what a hung session
  looks like;
- a `/clear` or a Prompt would not land after three tries. Naiad stops rather
  than deliver into a context it could not clear or a Prompt that arrived cut
  short;
- the agent announced a State the Workflow does not declare.

In each case attach, see what state the session is in, and type to it. A parked
Run stays alive and keeps being watched, so the agent's next announcement
un-parks it.

## `NAIAD_HOME`

Everything Naiad owns is under one directory, `~/.naiad` unless `NAIAD_HOME` says
otherwise:

- `queue/`: the entries;
- `runs/`: one directory per Run, holding its records and its log;
- `workflows/`: the library that a bare Workflow name such as `starter` resolves
  in;
- `supervisor.lock`: what the one Supervisor holds.

Naiad never writes into a repository it works on, and refuses a home inside one.
Set `NAIAD_HOME` in the shell for every `naiad` command you run, or you will be
looking at a different queue. A home you move away from keeps its Runs; they do
not follow.

## Adoption

A Run normally starts its own session. An **Adoption** attaches a Run to a
Claude Code session you are already in, so the phases that remain run there with
the conversation still in context. It needs that session to be in tmux.

`naiad install` puts the `naiad-adopt` skill in your skills directory. In the
session, ask for it by naming Naiad, for example "naiad, start to-spec" or "let
naiad take over". A phase word alone does not trigger it. The agent then:

1. reads the library with `naiad states` to settle which Workflow and which State
   your words meant, and asks you if they fit more than one;
2. settles the branch: the one you named, or one it derives and declares;
3. writes the task from the conversation;
4. runs `naiad adopt`, which validates, queues one entry and returns at once.

It then tells you where the work lands and ends its turn. The Supervisor attaches
the Run on its own pass, once the lane for the repository is free, and the first
Prompt arrives after that. If no Supervisor is running the agent tells you the
entry will wait until you start one with `naiad queue watch`. If the State you
adopt at clears, it clears; the Workflow said the phase starts clean.

## tmux

tmux is a prerequisite, not a setting. Every Run is a tmux session, and typing
Prompts, `/clear` and reminders into it is how Naiad drives Claude Code. A tmux
server that was already running keeps the `PATH` it started with, so a session it
opens cannot run a `claude` installed since. Doctor warns about that case (see
Troubleshooting).

## What you can configure

Naiad reads these, and nothing else:

- `NAIAD_HOME`: where Naiad keeps its queue, Runs and library. Default
  `~/.naiad`.
- `NAIAD_NTFY_URL`: the full ntfy topic URL. Setting it turns the push leg on.
- `NAIAD_NTFY_TOKEN`: a bearer token for a protected topic.
- `CLAUDE_CONFIG_DIR`: Claude Code's own variable. Naiad reads it and does not
  own it: `naiad install` writes the hooks to `$CLAUDE_CONFIG_DIR/settings.json`
  and the skill to `$CLAUDE_CONFIG_DIR/skills` when it is set, and to `~/.claude`
  otherwise, and `naiad doctor` looks in the same places.

The timings, and the permission mode, are fixed on purpose. The timings (how
long before a silent agent is reminded, how long before a hung session is given
up on, how often a dropped `/clear` is retyped) describe Claude Code and tmux,
not any one Workflow. The permission mode is `bypassPermissions` for every
Session, because an unattended Session cannot answer a permission prompt and a
Run would stall on it as unexplained silence. Containment is your machine's job.
What varies per Workflow lives in the Workflow file: see
[Writing a Workflow](workflow-authoring.md).

## Troubleshooting

`naiad doctor` checks the machine, prints one line per finding with what to run,
and repairs nothing:

```
naiad doctor
```

Every line starts with its severity, coloured on a terminal and plain when the
output is piped or `NO_COLOR` is set. `fail` means Naiad cannot work, and doctor
exits 1. `warn` means Naiad works but something you expect will not. `info` is
worth knowing. `naiad install` ends by printing the same report.

`naiad run`, `naiad watch`, `naiad adopt` and the Supervisor run the `fail` checks
before they act. They stop at the first one with a single line on stderr and exit
2: the missing thing, why Naiad needs it, the fix, then `naiad doctor`. `naiad
queue add` never checks, so you can queue work on a machine that will run it later.

### fail

**`tmux is not on PATH`**: Naiad runs every Run in a tmux session. Install it
(`brew install tmux` on macOS, `apt install tmux` on Debian and Ubuntu), then run
`naiad doctor` again.

**`claude is not on PATH`**: Naiad drives Claude Code sessions and asks it
Questions. Install Claude Code and make sure `claude` resolves in the shell you
run `naiad` from.

**`the Naiad home <path> is not writable`**, or **`... does not exist and cannot
be created`**: Naiad keeps its queue, its Runs and its lock there. Make the
directory writable, or point `NAIAD_HOME` at one that is.

**`naiad's hooks are missing from <settings file>`**: the hooks are how Naiad
teaches the Protocol and hears a turn end. Run `naiad install`. The line lists
which are absent, as `Event` or `Event(matcher)`. Check that the file named is
the one Claude Code reads: with `CLAUDE_CONFIG_DIR` set, install and doctor use
`$CLAUDE_CONFIG_DIR/settings.json`, so set it the same way in both places. If
the line instead says the file **cannot be read**, it could not be opened or is
not valid JSON. Install refuses to overwrite a file it cannot parse, so repair or
remove it first, then run `naiad install`.

**`the hooks in <settings file> name <path>, not this naiad`**: the hooks run a
different `naiad`, or none. This is what a moved or rebuilt install looks like,
for example after `uv tool upgrade` or reinstall. Run `naiad install` from the
`naiad` you mean to use. It replaces the old entries and leaves everything else in
the file alone.

### warn

**`claude <version> is older than 2.1.221`**: `2.1.221` has every flag Naiad can
pass. A Workflow that uses only the older ones still runs. Run `claude update`.

**`could not tell which version of claude this is`**: `claude --version` failed
or printed something Naiad could not read. Run it yourself; `claude update` if it
is old.

**`the adopt skill is missing from <skills directory>`**: only Adoption is
affected. Run `naiad install`.

**`the library entry <file> does not load`**: a file in `~/.naiad/workflows` (or
under `NAIAD_HOME`) is a broken link, is not valid TOML, or fails
`naiad workflow check`. The error is on the line. Repair the file or remove it
from the library.

**`the running tmux server's PATH does not include claude`**: the tmux server
started before `claude` was on `PATH` and hands its own `PATH` to every session
it opens, so a Run's session cannot start Claude Code. Run
`tmux set-environment -g PATH "$PATH"` from a shell where `claude` resolves.
Restarting the server with `tmux kill-server` also works, but it ends every tmux
session, including any Run in progress. Only doctor runs this check.

### info

**`the library at <path> is empty`**: nothing for `naiad queue add` to name yet.
Run `naiad install --starter`, or put your own Workflow in that directory.

**`notifications will fire through: ...`**: the legs that exist right now. If
`push` is missing and you expected it, `NAIAD_NTFY_URL` is not set in the shell
that runs the watcher.
